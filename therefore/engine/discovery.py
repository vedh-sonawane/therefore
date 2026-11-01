"""The discovery engine: finding what the inventions have in common.

The library is full of sequences invented independently, in different worlds, by different
means. Hidden among them are exact relationships: one sequence turns out to be the running
total of another, or its differences, or its squares. When such a relationship holds across
every term and the two sequences were NOT built from each other, that is a genuine discovery,
a verified identity the engine found on its own, not one it was told.

This module hunts for those. Every relationship it reports is checked term by term, and only
kept if it holds exactly and the two inventions are lineage-independent (neither is a part or
parent of the other), which rules out the ones that are related only because one was
constructed from the other.
"""

MINTERMS = 10   # a relationship must hold across at least this many terms


def _running_total(seq):
    out, s = [], 0
    for x in seq:
        s += x
        out.append(s)
    return out


def _differences(seq):
    return [seq[i + 1] - seq[i] for i in range(len(seq) - 1)]


def _squares(seq):
    return [x * x for x in seq]


# (name, human template, function B -> transformed) for unary relationships
TRANSFORMS = [
    ("running-total", "{A} is the running total of {B}", _running_total),
    ("differences", "{A} is the term-to-term difference of {B}", _differences),
    ("second-differences", "{A} is the second difference of {B}",
        lambda s: _differences(_differences(s))),
    ("squares", "{A} is the square of {B}, term by term", _squares),
    ("doubles", "{A} is twice {B}, term by term", lambda s: [2 * x for x in s]),
    ("negatives", "{A} is the negation of {B}", lambda s: [-x for x in s]),
]


def _match(a, t):
    """Do sequences a and t agree exactly over their overlapping prefix (>= MINTERMS)?"""
    m = min(len(a), len(t))
    if m < MINTERMS:
        return False
    return a[:m] == t[:m]


def _trivial(seq):
    return len(set(seq)) < 3


def find_relationships(items, limit=6):
    """items: list of dicts {id, civ_id, symbol, prefix, related:set(ids)}.
    Returns up to `limit` discovered relationships as dicts."""
    # index sequences by their first MINTERMS terms for fast exact lookup
    index = {}
    for it in items:
        if len(it["prefix"]) >= MINTERMS and not _trivial(it["prefix"]):
            index.setdefault(tuple(it["prefix"][:MINTERMS]), []).append(it)

    found = []
    seen_pairs = set()
    for B in items:
        bseq = B["prefix"]
        if len(bseq) < MINTERMS or _trivial(bseq):
            continue
        for tname, template, fn in TRANSFORMS:
            try:
                t = fn(bseq)
            except Exception:
                continue
            if len(t) < MINTERMS or _trivial(t):
                continue
            for A in index.get(tuple(t[:MINTERMS]), []):
                if A["id"] == B["id"]:
                    continue
                if A["id"] in B["related"] or B["id"] in A["related"]:
                    continue    # related by construction, not a discovery
                if not _match(A["prefix"], t):
                    continue
                pair = (tname, min(A["id"], B["id"]), max(A["id"], B["id"]))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                cross = A["civ_id"] != B["civ_id"]
                score = (3.0 if tname in ("running-total", "differences", "second-differences", "squares") else 1.0)
                score += 2.0 if cross else 0.0
                found.append({
                    "kind": "relation",
                    "subkind": tname,
                    "statement": template.format(A=A["symbol"], B=B["symbol"]) +
                                 (", and the two were invented in different worlds" if cross else ""),
                    "a": {"id": A["id"], "symbol": A["symbol"], "prefix": A["prefix"][:10]},
                    "b": {"id": B["id"], "symbol": B["symbol"], "prefix": B["prefix"][:10]},
                    "cross_world": cross,
                    "score": round(score, 2),
                    "key": f"rel:{tname}:{pair[1]}:{pair[2]}",
                })
                if len(found) >= limit:
                    return found
    return found
