"""Exaptation: using an invention for something it was never built for.

An invention is a function from an integer to an integer. It was invented to generate a
sequence. Here we take that exact function and put it to a completely different job: the
transition rule of a cellular automaton. The next state of a cell is the invention applied
to the sum of its neighbourhood, taken modulo the number of states.

Nothing about the function changes. The same thing that was a number sequence becomes a
spatial, temporal, visible pattern. Some functions die out, some settle into stripes, some
produce nested fractals, and a rare few produce genuinely complex structure. When a function
turns out to make something non-trivial in this foreign domain, that is the most interesting
kind of discovery there is: a second, unintended use.

Everything here is computed from the real function and is fully reproducible.
"""

from ..vm import run


def rule_table(inv, registry, laws, states):
    """Precompute the invention applied to every possible neighbourhood sum.

    A 3-cell neighbourhood of `states`-valued cells has sums 0..3*(states-1), so the
    whole CA rule is just a handful of evaluations of the invention.
    """
    hi = 3 * (states - 1)
    table = []
    for s in range(hi + 1):
        r = run(inv, [s], registry, laws=laws, fuel=40_000)
        v = r.value if (r.ok and isinstance(r.value, int) and not isinstance(r.value, bool)) else 0
        table.append(v % states)
    return table


def spacetime(inv, registry, laws, states=4, width=81, steps=81):
    """Evolve the CA whose rule is `inv`, from a single seeded cell. Returns rows."""
    table = rule_table(inv, registry, laws, states)
    row = [0] * width
    row[width // 2] = states - 1
    rows = [row]
    for _ in range(steps - 1):
        nxt = [0] * width
        for i in range(width):
            s = row[(i - 1) % width] + row[i] + row[(i + 1) % width]
            nxt[i] = table[s]
        row = nxt
        rows.append(row)
    return {"states": states, "rows": rows, "table": table}


def _entropy(row):
    from math import log2
    n = len(row)
    counts = {}
    for x in row:
        counts[x] = counts.get(x, 0) + 1
    h = 0.0
    for c in counts.values():
        p = c / n
        h -= p * log2(p)
    return h


def classify(st):
    """Estimate a Wolfram-like behaviour class from the evolved pattern.

    Honest about being an estimate: distinguishing class III from IV is famously hard.
    """
    rows = st["rows"]
    last = rows[-1]
    tail = rows[-12:]

    if all(x == 0 for x in last):
        return {"class": "I", "label": "dies out", "detail": "extinct"}

    # constant / stable
    if all(r == rows[-1] for r in tail):
        return {"class": "II", "label": "settles (stable)", "detail": "fixed"}

    # periodic in time (small period)
    for p in range(1, 7):
        if len(rows) > 2 * p and all(rows[-1 - k] == rows[-1 - k - p] for k in range(p)):
            return {"class": "II", "label": f"repeats (period {p})", "detail": f"period {p}"}

    # entropy of the late rows: low-ish structured vs high chaotic
    h = sum(_entropy(r) for r in tail) / len(tail)
    import math
    hmax = math.log2(st["states"])
    density = sum(1 for r in tail for x in r if x) / (len(tail) * len(last))

    if h > 0.82 * hmax and density > 0.35:
        return {"class": "III", "label": "chaotic", "detail": f"entropy {round(h,2)}"}
    # structured but not periodic or constant: nested / complex
    if 0.25 < density < 0.75:
        return {"class": "IV", "label": "complex / nested", "detail": f"entropy {round(h,2)}"}
    return {"class": "II", "label": "structured", "detail": f"density {round(density,2)}"}


def is_notable(cls):
    """A pattern worth flagging as a cross-domain discovery."""
    return cls["class"] in ("III", "IV")
