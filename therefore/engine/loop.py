"""The forever loop.

One tick, for one civilization:

    rent  ->  spark/mutate/combine candidates  ->  type-check  ->  experiment (run it)
          ->  verify it reproduces  ->  discover its properties  ->  check novelty (OEIS)
          ->  score by the civ's taste  ->  release the good ones  ->  pay their parts

Everything that happens is written to the one SQLite world as it happens, so closing
and reopening resumes exactly here.
"""

import json
import random
import threading
import time

from ..vm import type_check, run
from ..novelty import check_sequence
from . import spark, combine, contact, discover as disc, domains, exapt, taste as taste_mod, verify
from .civilization import Civilization, create_civilization
from .experiment import materialize, record, SEQ_LEN
from .invention import Invention, behavior_hash

# economy constants
INIT_WEALTH = 14.0
RENT = 0.45
EARN_PER_USE = 2.0
RELEASE_THRESHOLD = 3.0

# per-tick effort
N_SPARK = 7
N_MUTATE = 2
N_COMBINE = 3
OEIS_BUDGET = 3          # max live OEIS lookups per tick (cached ones are free)

# first contact
CONTACT_INTERVAL = 22    # ticks between contact attempts
CIV_NAMES = ["Aurorae", "Basilisk", "Cinder", "Delphi", "Ember", "Fathom", "Gyre"]

# eras and shifting laws
ERA_LENGTH = 80          # ticks per era
EXTINCT_EVERY = 3        # every Nth era, a mass extinction
RETEST_CAP = 160         # how many inventions to retest under the new laws per era
ENERGY_CHOICES = [0.18, 0.3, 0.5, 1.0, 1.0, 1.6, 2.2]  # scarce .. abundant compute

# cross-domain composition
CROSS_INTERVAL = 6       # every N ticks a world composes number inventions into figures/melodies
N_CROSS = 4              # attempts per pass

# the ouroboros: the engine's own swappable machinery, each organ fillable by an
# invented function so the engine is partly run by things it invented.
ORGANS = ["idea_bias", "combiner", "judge", "mutator"]
ORGAN_ROLE = {
    "idea_bias": "how many ideas it tries",
    "combiner": "which inventions it combines",
    "judge": "how it judges what is interesting",
    "mutator": "how it mutates inventions",
}
ADOPT_INTERVAL = 55      # ticks between adopting an invented function into an organ


class Engine:
    def __init__(self, store, n_civs=1):
        self.store = store
        self.n_civs = n_civs
        self.civs = []
        self.tick = int(store.get_meta("tick", 0) or 0)
        self._stop = threading.Event()
        self._load_or_create()
        self.civ_by_id = {c.id: c for c in self.civs}
        self.organs = json.loads(store.get_meta("organs", "{}") or "{}")

    # -- world setup / resume ------------------------------------------------
    def _load_or_create(self):
        for r in self.store.get_civs():
            civ = Civilization(r)
            for inv_row in self.store.load_inventions(civ.id):
                civ.register(Invention.from_row(inv_row))
            self.civs.append(civ)
        # ensure the world has at least n_civs; spawn any that are missing. New
        # civilizations join the existing world rather than replacing it.
        rng = random.Random(0xC0FFEE + len(self.civs))
        while len(self.civs) < self.n_civs:
            idx = len(self.civs)
            civ = create_civilization(self.store, CIV_NAMES[idx % len(CIV_NAMES)],
                                      idx, self.tick, rng)
            self.civs.append(civ)
            self.store.add_event(self.tick, civ.id, None, "genesis",
                                 {"name": civ.name, "glyph": civ.glyph})

    # -- the loop ------------------------------------------------------------
    def run_forever(self, sleep=0.05):
        while not self._stop.is_set():
            self.step()
            time.sleep(sleep)

    def stop(self):
        self._stop.set()

    def step(self):
        self.tick += 1
        for civ in self.civs:
            if civ.era >= 0 and civ_alive(civ):
                self._oeis_left = OEIS_BUDGET
                self._step_civ(civ)
        if len(self.civs) >= 2 and self.tick % CONTACT_INTERVAL == 0:
            self._first_contact()
        if self.tick % ERA_LENGTH == 0:
            self._era_transition()
        if self.tick % ADOPT_INTERVAL == 0:
            self._ouroboros_adopt()
        self.store.set_meta("tick", self.tick)
        return self.tick

    # -- the ouroboros --------------------------------------------------------
    def _organ_num(self, name, n, default):
        """Value from the invented function installed in an organ, or the default."""
        o = self.organs.get(name)
        if not o or not o.get("inv"):
            return default
        cid, iid = o["inv"]
        civ = self.civ_by_id.get(cid)
        if not civ or iid not in civ.registry:
            return default
        r = run(civ.registry[iid], [int(n) % 97], civ.registry, laws=civ.laws, fuel=15000)
        if r.ok and isinstance(r.value, int) and not isinstance(r.value, bool):
            return r.value
        return default

    def _ouroboros_adopt(self):
        best = None
        for civ in self.civs:
            for inv in civ.alive_total():
                if len(set(inv.prefix)) >= 4 and (best is None or inv.wealth > best[2]):
                    best = (civ.id, inv, inv.wealth, civ)
        if not best:
            return
        cid, inv = best[0], best[1]
        empty = [o for o in ORGANS if not self.organs.get(o, {}).get("inv")]
        if empty:
            name, verb = empty[0], "adopts"
        else:
            # every slot is already self-authored: keep renewing, replace one with a
            # stronger invention so the machinery keeps turning over.
            name = ORGANS[(self.tick // ADOPT_INTERVAL) % len(ORGANS)]
            if self.organs.get(name, {}).get("inv") == [cid, inv.id]:
                return
            verb = "replaces"
        self.organs[name] = {"inv": [cid, inv.id], "tick": self.tick}
        self.store.set_meta("organs", json.dumps(self.organs))
        pct = round(100 * sum(1 for o in ORGANS if self.organs.get(o, {}).get("inv")) / len(ORGANS))
        self.store.set_meta("ouroboros_pct", pct)
        self.store.add_event(self.tick, cid, inv.id, "ouroboros",
                             {"organ": name, "role": ORGAN_ROLE[name], "verb": verb,
                              "symbol": inv.symbol, "pct": pct})

    # -- eras: the laws of each world change, and the population is retested ----
    def _era_transition(self):
        rng = random.Random((self.tick * 777747 + 13) & 0xFFFFFFFF)
        for civ in self.civs:
            if not civ_alive(civ):
                continue
            civ.era += 1
            changed = self._shift_laws(civ, rng)
            self.store.update_civ(civ.id, era=civ.era, laws_json=json.dumps(civ.laws))
            self.store.add_event(self.tick, civ.id, None, "era",
                                 {"era": civ.era, "glyph": civ.glyph, "changed": changed,
                                  "energy": round(civ.laws.get("_energy", 1.0), 2)})
            old_top, new_top, revo = self._drift_taste(civ, rng)
            if revo or new_top != old_top:
                self.store.add_event(self.tick, civ.id, None, "taste",
                                     {"glyph": civ.glyph, "kind": "revolution" if revo else "shift",
                                      "from": old_top, "to": new_top})
            revived, broke = self._retest(civ, rng)
            if revived:
                self.store.add_event(self.tick, civ.id, None, "resurrection",
                                     {"count": revived, "glyph": civ.glyph,
                                      "note": "old failures that work under the new laws"})
            if broke:
                self.store.add_event(self.tick, civ.id, None, "law_death",
                                     {"count": broke, "glyph": civ.glyph})
            if civ.era % EXTINCT_EVERY == 0:
                killed = self._mass_extinction(civ)
                if killed:
                    self.store.add_event(self.tick, civ.id, None, "extinction",
                                         {"count": killed, "glyph": civ.glyph,
                                          "note": "most of the population fell dormant"})

    def _shift_laws(self, civ, rng):
        """Mutate a civilization's laws: operation costs and the era's compute energy."""
        laws = dict(civ.laws)
        keys = [k for k in laws if not k.startswith("_")]
        desc = []
        for k in rng.sample(keys, k=min(3, len(keys))):
            roll = rng.random()
            if roll < 0.4:
                laws[k] = laws[k] + rng.choice([4, 8, 16]); desc.append(f"{k} costlier")
            elif roll < 0.75:
                laws[k] = max(1, laws[k] - rng.choice([1, 2, 3])); desc.append(f"{k} cheaper")
            else:
                laws[k] = rng.randint(1, 8); desc.append(f"{k} reset")
        prev = laws.get("_energy", 1.0)
        laws["_energy"] = rng.choice(ENERGY_CHOICES)
        if laws["_energy"] < prev * 0.7:
            desc.append("compute scarce")
        elif laws["_energy"] > prev * 1.3:
            desc.append("compute abundant")
        civ.laws = laws
        return desc

    def _drift_taste(self, civ, rng):
        """A world's sense of what is interesting is not fixed. Each era it drifts, and
        now and then it has a revolution. Because taste gates what gets released, worlds
        with different taste build genuinely different libraries."""
        t = dict(civ.taste)
        old_top = max(t, key=t.get)
        revolution = rng.random() < 0.16
        for k in t:
            if revolution:
                t[k] = round(max(0.1, rng.uniform(0.3, 2.2)), 3)
            else:
                t[k] = round(min(2.4, max(0.1, t[k] + rng.uniform(-0.35, 0.35))), 3)
        civ.taste = t
        new_top = max(t, key=t.get)
        self.store.update_civ(civ.id, taste_json=json.dumps(t))
        return old_top, new_top, revolution

    def _retest(self, civ, rng):
        """Re-run inventions under the new laws. Some alive ones no longer complete and
        fall dormant; some dormant failures now complete and are resurrected."""
        members = [i for i in civ.registry.values() if i.domain == "number"]
        dormant = [i for i in members if i.status == "dormant"]
        alive = [i for i in members if i.status == "alive"]
        revived = broke = 0
        for inv in rng.sample(dormant, min(RETEST_CAP, len(dormant))):
            prefix, total, _stop, _ops = materialize(inv, civ.registry, civ.laws)
            if total and len(prefix) >= 6 and len(set(prefix)) >= 4:
                props = disc.discover(prefix)
                if any(p[0] not in ("distinct-values", "non-negative", "positive") for p in props):
                    inv.status = "alive"; inv.wealth = INIT_WEALTH; inv.total = True
                    inv.prefix = prefix; inv.behavior_hash = behavior_hash(prefix, True)
                    self.store.update_invention(
                        inv.id, status="alive", wealth=INIT_WEALTH, total=1,
                        prefix_json=json.dumps(prefix), behavior_hash=inv.behavior_hash,
                        exapted=0)
                    revived += 1
        for inv in rng.sample(alive, min(RETEST_CAP, len(alive))):
            prefix, total, _stop, _ops = materialize(inv, civ.registry, civ.laws)
            if not total:
                inv.status = "dormant"
                self.store.update_invention(inv.id, status="dormant")
                broke += 1
        return revived, broke

    def _mass_extinction(self, civ):
        alive = [i for i in civ.registry.values() if i.status == "alive"]
        if len(alive) < 16:
            return 0
        alive.sort(key=lambda i: i.wealth, reverse=True)
        keep = max(10, int(len(alive) * 0.15))
        doomed = alive[keep:]
        for inv in doomed:
            inv.status = "dormant"
        self.store.bulk_status([i.id for i in doomed], "dormant")
        return len(doomed)

    # -- first contact between two sealed civilizations ----------------------
    def _first_contact(self):
        rng = random.Random((self.tick * 2246822519) & 0xFFFFFFFF)
        pair = [c for c in self.civs if c.alive_total()]
        if len(pair) < 2:
            return
        a, b = rng.sample(pair, 2)
        # A offers its most valuable, genuinely structured invention
        offers = sorted(a.alive_total(), key=lambda i: i.wealth, reverse=True)
        offer = next((i for i in offers if len(i.prefix) >= 6 and len(set(i.prefix)) >= 4), None)
        if offer is None:
            return
        res = contact.translate(self.store, offer, a, b, self.tick, INIT_WEALTH)
        self.store.add_event(self.tick, b.id, None, "first_contact", {
            "from_civ": a.id, "from_glyph": a.glyph, "to_civ": b.id, "to_glyph": b.glyph,
            "offer": offer.symbol, "seq": offer.prefix[:8],
            "translated": len(res["mapping"]), "new": len(res["created"]),
            "convergent": len(res["convergent"]),
        })
        for (aid, bid, bh) in res["convergent"]:
            src = a.registry.get(aid)
            self.store.add_event(self.tick, b.id, bid, "convergent", {
                "a_civ": a.id, "a_glyph": a.glyph, "b_civ": b.id, "b_glyph": b.glyph,
                "seq": (src.prefix[:8] if src else []),
                "note": "independently invented in both worlds",
            })

    # -- one civilization ----------------------------------------------------
    def _step_civ(self, civ):
        rng = civ.rng_for_tick(self.tick)

        # 1) rent - the economy charges every living invention to exist
        if civ.registry:
            bankrupt = self.store.charge_rent(civ.id, RENT, self.tick)
            for iid in bankrupt:
                inv = civ.registry.get(iid)
                if inv:
                    inv.status = "dormant"
                    self.store.add_event(self.tick, civ.id, iid, "dormant",
                                         {"symbol": inv.symbol, "wealth": round(inv.wealth, 2)})

        # 2) propose candidates
        candidates = self._propose(civ, rng)

        # 3) evaluate each
        for body, origin, parents, parts in candidates:
            self._evaluate(civ, rng, body, origin, parents, parts)

        # 4) exaptation: try a few inventions in the foreign (cellular automaton) domain
        self._exapt_pass(civ)

        # 5) cross-domain: compose number inventions into figures and melodies
        if self.tick % CROSS_INTERVAL == 0:
            self._compose_domains(civ, rng)

    def _exapt_pass(self, civ):
        for row in self.store.get_unexapted(civ.id, limit=3):
            inv = civ.registry.get(row["id"])
            if inv is None:
                continue
            try:
                st = exapt.spacetime(inv, civ.registry, civ.laws, states=4, width=61, steps=40)
                cls = exapt.classify(st)
            except Exception:
                self.store.set_exapted(row["id"], "error")
                continue
            self.store.set_exapted(row["id"], cls["class"])
            self.store.insert_property(row["id"], "exaptation",
                                       {"domain": "cellular-automaton", **cls}, self.tick)
            if exapt.is_notable(cls):
                # a function invented for numbers turns out to build visible structure
                self.store.add_event(self.tick, civ.id, row["id"], "exaptation", {
                    "symbol": inv.symbol, "class": cls["class"], "label": cls["label"],
                    "seq": inv.prefix[:8],
                })

    # -- cross-domain composition --------------------------------------------
    def _compose_domains(self, civ, rng):
        sources = civ.alive_total()
        if len(sources) < 2:
            return
        for _ in range(N_CROSS):
            a, b = rng.sample(sources, 2)
            if rng.random() < 0.5:
                self._make_domain(civ, rng, a, b, "figure")
            else:
                self._make_domain(civ, rng, a, b, "melody")

    def _make_domain(self, civ, rng, a, b, kind):
        if kind == "figure":
            artifact = domains.build_figure(a, b, civ.registry, civ.laws)
            props, interesting, score = domains.measure_figure(artifact)
            sig = domains.figure_signature(artifact)
            body = {"kind": "figure", "turn": a.id, "step": b.id, "n": domains.FIG_N}
            sig_out, origin = "Figure", "figure"
        else:
            artifact = domains.build_melody(a, b, civ.registry, civ.laws)
            props, interesting, score = domains.measure_melody(artifact)
            sig = domains.melody_signature(artifact)
            body = {"kind": "melody", "pitch": a.id, "rhythm": b.id, "n": domains.MEL_N}
            sig_out, origin = "Melody", "melody"
        if not interesting:
            return
        bh = behavior_hash(sig, True)
        if self.store.find_behavior(civ.id, bh) is not None:
            return
        inv = Invention(
            id=-(self.tick * 100000 + rng.randint(1, 99999)), civ_id=civ.id,
            name=f"{origin}#{len(civ.registry) + 1}", symbol=civ.new_symbol(),
            sig_in=(), sig_out=sig_out, body=body, parents=[a.id, b.id],
            parts=sorted({a.id, b.id}), origin=origin, created_tick=self.tick,
            status="alive", wealth=INIT_WEALTH, behavior_hash=bh, prefix=sig,
            total=True, score=score, novelty="crossdomain", domain=origin)
        inv.id = self.store.insert_invention(inv.to_row())
        civ.register(inv)
        for name, detail in props:
            self.store.insert_property(inv.id, name, detail, self.tick)
        self._pay_parts(civ, inv.parts)
        self.store.add_event(self.tick, civ.id, inv.id, origin, {
            "symbol": inv.symbol, "parts": inv.parts,
            "from": [a.symbol, b.symbol], "score": score,
        })

    def _pay_parts(self, civ, part_ids):
        for pid in part_ids:
            if pid in civ.registry:
                self.store.bump_use_and_wealth(pid, EARN_PER_USE, self.tick)
                civ.registry[pid].wealth += EARN_PER_USE
                civ.registry[pid].uses += 1
                if civ.registry[pid].status == "dormant":
                    civ.registry[pid].status = "alive"
                    self.store.update_invention(pid, status="alive")

    def _propose(self, civ, rng):
        cands = []
        callables = civ.callables()
        alive = civ.alive_total()
        # organ: how many ideas it tries (an invented function may decide, within bounds)
        n_spark = N_SPARK + (abs(self._organ_num("idea_bias", self.tick, 0)) % 4)
        for _ in range(n_spark):
            body, origin = spark.spark_one(rng, callables)
            cands.append((body, origin, [], _ref_parts(body)))
        if alive:
            # organ: how much it mutates (an invented function may decide how many)
            n_mut = N_MUTATE + (abs(self._organ_num("mutator", self.tick, 0)) % 3)
            for _ in range(n_mut):
                parent = rng.choice(alive)
                body = spark.mutate(rng, parent.body, callables)
                cands.append((body, "mutation", [parent.id], _ref_parts(body)))
        if len(alive) >= 2 and rng.random() < 0.6:
            a, b = rng.sample(alive, 2)
            body = spark.crossover(rng, a.body, b.body)
            cands.append((body, "crossover", [a.id, b.id], _ref_parts(body)))
        # combinations: build bigger inventions from released parts
        if alive:
            for k in range(N_COMBINE):
                if len(alive) >= 2 and rng.random() < 0.6:
                    # organ: which inventions get combined (an invented function may steer)
                    pick = self._organ_num("combiner", self.tick + k, None)
                    if pick is not None:
                        f = alive[abs(pick) % len(alive)]
                        h = rng.choice(alive)
                    else:
                        f, h = rng.sample(alive, 2)
                    body, origin, parts = combine.combine_two(rng, f.id, h.id)
                else:
                    f = rng.choice(alive)
                    body, origin, parts = combine.combine_one(rng, f.id)
                cands.append((body, origin, list(parts), parts))
        return cands

    def _evaluate(self, civ, rng, body, origin, parents, parts):
        # type check against the civ's registry (self handled by the checker)
        if not type_check(body, ("Int",), "Int", civ.registry):
            return

        temp_id = -(self.tick * 100000 + rng.randint(1, 99999))
        cand = Invention(id=temp_id, civ_id=civ.id, name="", symbol="",
                         sig_in=("Int",), sig_out="Int", body=body,
                         parents=parents, parts=sorted(set(parts)), origin=origin,
                         created_tick=self.tick)
        registry = dict(civ.registry)
        registry[temp_id] = cand

        prefix, total, stop, ops = materialize(cand, registry, civ.laws)
        if len(prefix) < 2:
            return  # produced essentially nothing; not worth a row

        bh = behavior_hash(prefix, total)
        if self.store.find_behavior(civ.id, bh) is not None:
            return  # this civ already knows this exact behaviour

        # verify reproducibility (determinism gate)
        repro, _t = verify.reproducible(cand, registry, civ.laws, prefix, SEQ_LEN)

        props = disc.discover(prefix) if total else []
        distinct = len(set(prefix))

        # novelty - only spend a lookup on something total and structured
        novelty = {"status": "trivial", "catalog": "OEIS", "matches": [], "receipt": {}, "seq": prefix}
        structured = any(p[0] not in ("distinct-values", "non-negative", "positive")
                         for p in props)
        if total and repro and structured and distinct >= 5:
            cached = self.store.oeis_cached(",".join(str(x) for x in prefix[:14]))
            if cached is not None or self._oeis_left > 0:
                if cached is None:
                    self._oeis_left -= 1
                novelty = check_sequence(self.store, prefix, self.tick)
            else:
                novelty = {"status": "pending", "catalog": "OEIS", "matches": [],
                           "receipt": {"note": "novelty check deferred"}, "seq": prefix[:14]}

        from ..vm import genome as g
        score = taste_mod.score(civ.taste, props, novelty["status"], total,
                                distinct, len(prefix), g.size(body), g.uses_self(body))
        # organ: how it judges what is interesting (an invented function nudges the score)
        jb = self._organ_num("judge", distinct, None)
        if jb is not None and score > -1.0:
            score = round(score + (abs(jb) % 5) * 0.25, 3)

        released = total and repro and score >= RELEASE_THRESHOLD and structured
        status = "alive" if released else "dormant"
        symbol = civ.new_symbol()
        cand.symbol = symbol
        cand.name = f"{origin}#{len(civ.registry)+1}"
        cand.status = status
        cand.wealth = INIT_WEALTH if released else 0.0
        cand.behavior_hash = bh
        cand.prefix = prefix
        cand.total = total
        cand.score = score
        cand.novelty = novelty["status"]

        row = cand.to_row()
        inv_id = self.store.insert_invention(row)
        cand.id = inv_id
        civ.register(cand)

        # persist the real experiment, properties, novelty receipt
        record(self.store, cand, prefix, total, stop, ops, self.tick)
        if not repro:
            self.store.insert_property(inv_id, "NON-REPRODUCIBLE", {}, self.tick)
        for name, detail in props:
            self.store.insert_property(inv_id, name, detail, self.tick)
        if novelty["status"] in ("first", "known", "unchecked"):
            self.store.insert_novelty(inv_id, novelty.get("seq", prefix),
                                      novelty["status"], novelty["catalog"],
                                      novelty["matches"], novelty["receipt"], self.tick)

        if not released:
            return

        # pay the parts: inventions earn when used to build something released
        for pid in cand.parts:
            if pid in civ.registry:
                self.store.bump_use_and_wealth(pid, EARN_PER_USE, self.tick)
                civ.registry[pid].wealth += EARN_PER_USE
                civ.registry[pid].uses += 1
                # a dormant part that just got used wakes back up (resurrection-lite)
                if civ.registry[pid].status == "dormant":
                    civ.registry[pid].status = "alive"
                    self.store.update_invention(pid, status="alive")

        # events for the organism
        self.store.add_event(self.tick, civ.id, inv_id, "birth",
                             {"symbol": symbol, "origin": origin, "score": score,
                              "prefix": prefix[:10], "novelty": novelty["status"],
                              "parts": cand.parts})
        if novelty["status"] == "first":
            self.store.add_event(self.tick, civ.id, inv_id, "first",
                                 {"symbol": symbol, "seq": novelty.get("seq", prefix)[:12],
                                  "receipt": novelty["receipt"]})
        elif novelty["status"] == "known" and novelty["matches"]:
            self.store.add_event(self.tick, civ.id, inv_id, "known",
                                 {"symbol": symbol, "matches": novelty["matches"][:2]})
        notable = [p for p in props if p[0] in
                   ("prime-valued", "exponential-growth", "polynomial", "geometric",
                    "square-valued", "periodic")]
        if notable:
            self.store.add_event(self.tick, civ.id, inv_id, "discovery",
                                 {"symbol": symbol, "properties": [p[0] for p in notable]})

        # convergent invention: did another sealed civilization already reach this exact
        # behaviour on its own? If so, that is evidence the thing is fundamental.
        if structured and distinct >= 6 and len(prefix) >= 8:
            others = self.store.find_behavior_global(bh, exclude_civ=civ.id)
            if others:
                self.store.add_event(self.tick, civ.id, inv_id, "convergent", {
                    "a_civ": others[0]["civ_id"], "b_civ": civ.id, "b_glyph": civ.glyph,
                    "seq": prefix[:8], "also_in": len(others),
                    "note": "independently invented in another world",
                })


def _ref_parts(body):
    from ..vm import genome as g
    return sorted(g.referenced_ids(body))


def civ_alive(civ):
    return True
