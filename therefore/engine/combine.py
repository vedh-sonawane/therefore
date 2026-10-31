"""Combination: build bigger inventions out of existing ones.

These are the operators that make complexity climb - a new sequence defined in terms
of one or two released inventions. Because they call those inventions by id, the new
invention records them as its *parts* (lineage + economy both flow from that).
"""

from ..vm import genome as g


def combine_one(rng, f_id):
    """A new sequence from a single existing invention f."""
    n = g.param(0)
    choice = rng.random()
    if choice < 0.33:
        # cumulative sum: S(n) = S(n-1) + f(n), S(0) = f(0)
        body = g.iff(g.prim("le", n, g.const(0)),
                     g.call(f_id, g.const(0)),
                     g.prim("add", g.selfcall(g.prim("sub", n, g.const(1))),
                            g.call(f_id, n)))
        return body, "cumulative-sum", [f_id]
    if choice < 0.6:
        # first difference: D(n) = f(n+1) - f(n)
        body = g.prim("sub", g.call(f_id, g.prim("inc", n)), g.call(f_id, n))
        return body, "first-difference", [f_id]
    if choice < 0.8:
        # self-composition f(f(n))
        body = g.call(f_id, g.call(f_id, n))
        return body, "self-composition", [f_id]
    # dilation f(n // 2)
    body = g.call(f_id, g.prim("idiv", n, g.const(2)))
    return body, "dilation", [f_id]


def combine_two(rng, f_id, h_id):
    """A new sequence from two existing inventions f and h."""
    n = g.param(0)
    choice = rng.random()
    if choice < 0.5:
        op = rng.choice(["add", "sub", "mul", "max", "min"])
        body = g.prim(op, g.call(f_id, n), g.call(h_id, n))
        return body, "pointwise-" + op, [f_id, h_id]
    # composition f(h(n))
    body = g.call(f_id, g.call(h_id, n))
    return body, "composition", [f_id, h_id]
