"""Taste: the engine's evolving sense of what counts as interesting.

Taste is a weight vector over "virtues". Crucially it is NOT hardcoded or shared:
each civilization samples its own weights, so civilizations value different things and
therefore invent in different directions. (Later phases mutate these weights over time
and let schools of taste form; the hook is here now.)
"""

VIRTUES = ["structure", "rarity", "growth", "novelty",
           "richness", "parsimony", "recurrence", "totality"]

_STRUCTURE = {"arithmetic", "geometric", "polynomial", "periodic",
              "strictly-increasing", "non-decreasing"}
_RARITY = {"prime-valued", "square-valued"}


def default_taste(rng):
    """Sample a taste for a new civilization."""
    return {v: round(rng.uniform(0.5, 2.0), 3) for v in VIRTUES}


def signals(props, novelty, total, distinct, length, size, uses_self):
    names = {p[0] for p in props}
    detail = {p[0]: p[1] for p in props}
    struct = len(names & _STRUCTURE)
    if "polynomial" in detail:
        struct += detail["polynomial"].get("degree", 0) * 0.5
    nov = {"first": 1.0, "known": 0.3, "unchecked": 0.15, "trivial": 0.0}.get(novelty, 0.0)
    return {
        "structure": struct,
        "rarity": len(names & _RARITY),
        "growth": 1.0 if "exponential-growth" in names else 0.0,
        "novelty": nov,
        "richness": (distinct / length) if length else 0.0,
        "parsimony": 1.0 / (1.0 + size / 8.0),
        "recurrence": 1.0 if uses_self else 0.0,
        "totality": 1.0 if total else 0.0,
    }


def score(taste, props, novelty, total, distinct, length, size, uses_self):
    if not total:
        return -1.0  # a thing that does not even run reliably is not interesting
    sig = signals(props, novelty, total, distinct, length, size, uses_self)
    s = sum(taste.get(v, 1.0) * sig[v] for v in VIRTUES)
    # a sequence with no detected structure at all is dull even if total
    if sig["structure"] == 0 and sig["rarity"] == 0 and sig["growth"] == 0:
        s -= 2.0
    return round(s, 3)
