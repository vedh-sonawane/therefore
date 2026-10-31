"""First contact between sealed civilizations.

Civilizations invent in isolation. Their inventions reference other inventions by ids
that only mean something inside their own world, and they run under different laws, so
one civilization cannot simply read another's invention. To receive it, the target has
to build a translator: walk the whole dependency closure of the offered invention and
re-create each piece in its own namespace, remapping every internal reference and
re-running it under its own laws to confirm it still behaves the same.

Two things fall out of this naturally:
  * a translation is a real artifact - a map from the source's ids to the target's.
  * if, while translating, the target finds it already has a piece with the exact same
    behaviour, that is convergent invention: two sealed worlds reaching the same thing
    on their own. That is logged as strong evidence the thing is fundamental.
"""

from .experiment import materialize, SEQ_LEN
from .invention import Invention, behavior_hash
from . import discover as disc


def dependency_closure(inv_id, civ):
    """Ids in `civ` that inv depends on (parts, recursively), with inv itself last."""
    seen, order = set(), []

    def visit(i):
        if i in seen or i not in civ.registry:
            return
        seen.add(i)
        for p in civ.registry[i].parts:
            visit(p)
        order.append(i)

    visit(inv_id)
    return order


def _remap(node, mapping):
    """Rewrite a genome so every call to a source id points at the target id."""
    tag = node[0]
    if tag == "call":
        new_id = mapping.get(node[1], node[1])
        return ["call", new_id] + [_remap(a, mapping) for a in node[2:]]
    if tag == "prim":
        return ["prim", node[1]] + [_remap(a, mapping) for a in node[2:]]
    if tag == "self":
        return ["self"] + [_remap(a, mapping) for a in node[1:]]
    return list(node)  # const / param are leaves


def translate(store, source_inv, civA, civB, tick, init_wealth):
    """Translate source_inv from civA into civB.

    Returns dict with the id mapping, the newly created immigrant ids, and any
    convergent matches (source_id, existing_target_id).
    """
    mapping = {}
    created = []
    convergent = []

    for aid in dependency_closure(source_inv.id, civA):
        a = civA.registry[aid]
        new_body = _remap(a.body, mapping)

        temp_id = -(tick * 100000 + 90000 + (aid % 9000))
        cand = Invention(id=temp_id, civ_id=civB.id, name="", symbol="",
                         sig_in=a.sig_in, sig_out=a.sig_out, body=new_body,
                         parents=[], parts=[], origin="immigrant", created_tick=tick)
        reg = dict(civB.registry)
        reg[temp_id] = cand
        prefix, total, stop, ops = materialize(cand, reg, civB.laws)
        if len(prefix) < 2:
            # could not be made to run in B's world; skip this piece
            continue
        bh = behavior_hash(prefix, total)

        existing = store.find_behavior(civB.id, bh)
        if existing is not None:
            # civB already knows this behaviour -> convergent invention
            mapping[aid] = existing
            convergent.append((aid, existing, bh))
            continue

        # otherwise, naturalise it as an immigrant invention in civB
        cand.parts = sorted({mapping[p] for p in a.parts if p in mapping})
        cand.symbol = civB.new_symbol()
        cand.name = f"from {civA.glyph}#{aid}"
        cand.behavior_hash = bh
        cand.prefix = prefix
        cand.total = total
        cand.status = "alive" if total else "dormant"
        cand.wealth = init_wealth if total else 0.0
        cand.novelty = "imported"
        cand.score = a.score
        inv_id = store.insert_invention(cand.to_row())
        cand.id = inv_id
        civB.register(cand)
        mapping[aid] = inv_id
        created.append(inv_id)

        store.insert_experiment(inv_id, "materialize", {"n": [0, len(prefix)]},
                                {"prefix": prefix[:SEQ_LEN]}, ops, total,
                                None if total else f"not total at {stop}", tick)
        if total:
            for name, detail in disc.discover(prefix):
                store.insert_property(inv_id, name, detail, tick)

    return {"mapping": mapping, "created": created, "convergent": convergent}
