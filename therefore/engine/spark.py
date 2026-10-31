"""Spark: propose candidate genomes.

Three idea sources, all producing well-typed Int->Int genomes:
  * recurrences  - f(n) defined from f(n-1), f(n-2), ... with a base case. This is where
                   the rich sequences live (Fibonacci, factorials, Pell, polynomials, ...).
  * closed forms - expression trees over n, constants, and *calls to existing inventions*.
  * mutation / crossover - perturb or splice existing genomes.

Generators only ever build type-correct trees, and recurrences always decrease toward a
base case, so most candidates are total. The ones that aren't are caught by the fuel cap,
not by hanging the engine.
"""

from ..vm import genome as g

INT_UNARY = ["neg", "abs", "inc", "dec", "square", "sign"]
INT_BINARY = ["add", "sub", "mul", "min", "max"]
CMP = ["lt", "le", "gt", "ge", "eq"]


def _small_const(rng):
    return g.const(rng.choice([0, 1, 1, 2, 2, 3, -1, 4, 5]))


def _safe_divisor(rng):
    return g.const(rng.choice([2, 2, 3, 3, 5, 7]))


def gen_int(rng, depth, callables, allow_self, order):
    """Generate an Int-typed expression node."""
    if depth <= 0 or rng.random() < 0.32:
        roll = rng.random()
        if roll < 0.5:
            return g.param(0)
        if roll < 0.72:
            return _small_const(rng)
        if allow_self and roll < 0.9:
            back = rng.randint(1, max(1, order))
            return g.selfcall(g.prim("sub", g.param(0), g.const(back)))
        if callables:
            c = rng.choice(callables)
            return g.call(c, gen_int(rng, depth - 1, callables, allow_self, order))
        return g.param(0)

    kind = rng.random()
    if kind < 0.18:
        op = rng.choice(INT_UNARY)
        return g.prim(op, gen_int(rng, depth - 1, callables, allow_self, order))
    if kind < 0.33:
        # safe division / modulo
        op = rng.choice(["idiv", "mod"])
        return g.prim(op, gen_int(rng, depth - 1, callables, allow_self, order),
                      _safe_divisor(rng))
    if kind < 0.45:
        # bounded power with a tiny exponent
        return g.prim("pow", gen_int(rng, depth - 1, callables, allow_self, order),
                      g.const(rng.choice([2, 2, 3])))
    if kind < 0.6:
        # conditional expression
        return g.iff(gen_bool(rng, depth - 1, callables, allow_self, order),
                     gen_int(rng, depth - 1, callables, allow_self, order),
                     gen_int(rng, depth - 1, callables, allow_self, order))
    op = rng.choice(INT_BINARY)
    return g.prim(op, gen_int(rng, depth - 1, callables, allow_self, order),
                  gen_int(rng, depth - 1, callables, allow_self, order))


def gen_bool(rng, depth, callables, allow_self, order):
    if depth <= 0 or rng.random() < 0.6:
        op = rng.choice(CMP)
        return g.prim(op, gen_int(rng, depth - 1, callables, allow_self, order),
                      gen_int(rng, depth - 1, callables, allow_self, order))
    roll = rng.random()
    if roll < 0.33:
        return g.prim("not", gen_bool(rng, depth - 1, callables, allow_self, order))
    op = rng.choice(["and", "or"])
    return g.prim(op, gen_bool(rng, depth - 1, callables, allow_self, order),
                  gen_bool(rng, depth - 1, callables, allow_self, order))


def gen_recurrence(rng, callables):
    order = rng.choice([1, 2, 2, 2, 3])
    # base case: value for n < order
    base = rng.choice([g.const(rng.choice([0, 1, 1, 2])), g.param(0),
                       g.prim("inc", g.param(0))])

    # recursive body: combine previous term(s) and maybe n / a part
    terms = [g.selfcall(g.prim("sub", g.param(0), g.const(1)))]
    if order >= 2:
        terms.append(g.selfcall(g.prim("sub", g.param(0), g.const(2))))
    if order >= 3 and rng.random() < 0.7:
        terms.append(g.selfcall(g.prim("sub", g.param(0), g.const(3))))

    extra = rng.random()
    if extra < 0.3:
        terms.append(g.param(0))
    elif extra < 0.45:
        terms.append(_small_const(rng))
    elif extra < 0.6 and callables:
        terms.append(g.call(rng.choice(callables), g.param(0)))

    rng.shuffle(terms)
    acc = terms[0]
    for t in terms[1:]:
        op = rng.choice(["add", "add", "sub", "mul", "max"])
        acc = g.prim(op, acc, t)

    # occasionally scale by n for factorial-like growth
    if rng.random() < 0.25:
        acc = g.prim("mul", g.param(0), g.selfcall(g.prim("sub", g.param(0), g.const(1))))
        base = g.const(1)

    cond = g.prim("lt", g.param(0), g.const(order))
    return g.iff(cond, base, acc), order


def spark_one(rng, callables):
    """Return (body, origin_label)."""
    roll = rng.random()
    if roll < 0.55:
        body, _order = gen_recurrence(rng, callables)
        return body, "recurrence"
    body = gen_int(rng, rng.randint(2, 4), callables, allow_self=False, order=1)
    return body, "closed-form"


# ---- mutation / crossover --------------------------------------------------

def _positions(node, path=()):
    yield path, node
    tag = node[0]
    kids = node[2:] if tag in ("prim", "call") else (node[1:] if tag == "self" else ())
    base = 2 if tag in ("prim", "call") else (1 if tag == "self" else 0)
    for i, k in enumerate(kids):
        yield from _positions(k, path + (base + i,))


def _get(node, path):
    for p in path:
        node = node[p]
    return node


def _set(node, path, new):
    import copy
    node = copy.deepcopy(node)
    cur = node
    for p in path[:-1]:
        cur = cur[p]
    cur[path[-1]] = new
    return node


def mutate(rng, body, callables, order=2):
    """Replace a random Int subexpression with a freshly grown one."""
    spots = [(p, n) for p, n in _positions(body)
             if n[0] in ("prim", "call", "self", "param", "const")
             and not (n[0] == "prim" and n[1] in CMP + ["and", "or", "not"])]
    if not spots or len(spots) == 1:
        return gen_int(rng, 3, callables, allow_self=g.uses_self(body), order=order)
    path, _ = rng.choice(spots[1:])  # avoid replacing whole root most of the time
    new = gen_int(rng, rng.randint(1, 3), callables, allow_self=g.uses_self(body), order=order)
    return _set(body, path, new)


def crossover(rng, a, b):
    """Graft a random Int subtree of b into a."""
    a_spots = [p for p, n in _positions(a) if p and n[0] in ("prim", "call", "self", "param", "const")]
    b_spots = [(p, n) for p, n in _positions(b) if n[0] in ("prim", "call", "self", "param", "const")]
    if not a_spots or not b_spots:
        return a
    dst = rng.choice(a_spots)
    _, sub = rng.choice(b_spots)
    return _set(a, dst, sub)
