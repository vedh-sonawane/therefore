"""The forever loop.

One tick, for one civilization:

    rent  ->  spark/mutate/combine candidates  ->  type-check  ->  experiment (run it)
          ->  verify it reproduces  ->  discover its properties  ->  check novelty (OEIS)
          ->  score by the civ's taste  ->  release the good ones  ->  pay their parts

Everything that happens is written to the one SQLite world as it happens, so closing
and reopening resumes exactly here.
"""

import random
import threading
import time

from ..vm import type_check
from ..novelty import check_sequence
from . import spark, combine, contact, discover as disc, taste as taste_mod, verify
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


class Engine:
    def __init__(self, store, n_civs=1):
        self.store = store
        self.n_civs = n_civs
        self.civs = []
        self.tick = int(store.get_meta("tick", 0) or 0)
        self._stop = threading.Event()
        self._load_or_create()

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
        self.store.set_meta("tick", self.tick)
        return self.tick

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

    def _propose(self, civ, rng):
        cands = []
        callables = civ.callables()
        alive = civ.alive_total()
        for _ in range(N_SPARK):
            body, origin = spark.spark_one(rng, callables)
            cands.append((body, origin, [], _ref_parts(body)))
        if alive:
            for _ in range(N_MUTATE):
                parent = rng.choice(alive)
                body = spark.mutate(rng, parent.body, callables)
                cands.append((body, "mutation", [parent.id], _ref_parts(body)))
        if len(alive) >= 2 and rng.random() < 0.6:
            a, b = rng.sample(alive, 2)
            body = spark.crossover(rng, a.body, b.body)
            cands.append((body, "crossover", [a.id, b.id], _ref_parts(body)))
        # combinations: build bigger inventions from released parts
        if alive:
            for _ in range(N_COMBINE):
                if len(alive) >= 2 and rng.random() < 0.6:
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
