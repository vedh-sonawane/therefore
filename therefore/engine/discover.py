"""Discovery: compute measured properties of a sequence.

Nothing here asks a model what it thinks. Everything is derived arithmetically from
the integers the invention actually produced, and every property carries the numbers
that justify it. These properties are what "interestingness" (taste) later scores.
"""


def _is_prime(n):
    n = abs(n)
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    i = 3
    while i * i <= n:
        if n % i == 0:
            return False
        i += 2
    return True


def _is_square(n):
    if n < 0:
        return False
    r = int(n ** 0.5)
    return any((r + d) * (r + d) == n for d in (-1, 0, 1))


def _finite_diff_degree(seq, max_deg=5):
    """Smallest d such that the d-th finite difference is constant (and nonzero
    at d-1), i.e. the sequence is a polynomial of degree d. None if not found."""
    cur = list(seq)
    for d in range(0, max_deg + 1):
        if len(cur) < 2:
            return None
        if len(set(cur)) == 1:
            return d
        cur = [cur[i + 1] - cur[i] for i in range(len(cur) - 1)]
    return None


def _period(seq, max_p=8):
    n = len(seq)
    for p in range(1, max_p + 1):
        if n < 2 * p:
            break
        if all(seq[i] == seq[i - p] for i in range(p, n)):
            if len(set(seq[:p])) > 1 or p == 1:
                return p
    return None


def discover(seq):
    """Return a list of (name, detail) measured properties for a sequence."""
    props = []
    if len(seq) < 4:
        return props
    distinct = len(set(seq))

    if distinct == 1:
        props.append(("constant", {"value": seq[0]}))
        return props  # nothing else is interesting about a constant

    props.append(("distinct-values", {"count": distinct, "of": len(seq)}))

    diffs = [seq[i + 1] - seq[i] for i in range(len(seq) - 1)]
    if len(set(diffs)) == 1:
        props.append(("arithmetic", {"step": diffs[0]}))

    # geometric: integer ratio, no zeros
    if all(x != 0 for x in seq[:-1]) and all(
            seq[i + 1] % seq[i] == 0 for i in range(len(seq) - 1)):
        ratios = {seq[i + 1] // seq[i] for i in range(len(seq) - 1)}
        if len(ratios) == 1 and abs(next(iter(ratios))) > 1:
            props.append(("geometric", {"ratio": next(iter(ratios))}))

    if all(seq[i] < seq[i + 1] for i in range(len(seq) - 1)):
        props.append(("strictly-increasing", {}))
    elif all(seq[i] <= seq[i + 1] for i in range(len(seq) - 1)):
        props.append(("non-decreasing", {}))

    if all(x >= 0 for x in seq):
        props.append(("non-negative", {}))
    if all(x > 0 for x in seq):
        props.append(("positive", {}))

    deg = _finite_diff_degree(seq)
    if deg is not None and deg >= 2:
        props.append(("polynomial", {"degree": deg}))

    p = _period(seq)
    if p is not None:
        props.append(("periodic", {"period": p}))

    nontrivial = [x for x in seq if abs(x) > 1]
    if len(nontrivial) >= 4 and all(_is_prime(x) for x in nontrivial):
        props.append(("prime-valued", {"count": len(nontrivial)}))

    if all(x % 2 == 0 for x in seq):
        props.append(("all-even", {}))
    elif all(x % 2 == 1 for x in seq):
        props.append(("all-odd", {}))

    if len(nontrivial) >= 4 and all(_is_square(x) for x in seq if x >= 0) and distinct >= 4:
        props.append(("square-valued", {}))

    # growth classification from the tail (real ratios)
    tail = seq[-6:]
    if all(x > 0 for x in tail) and len(tail) >= 4:
        rs = [tail[i + 1] / tail[i] for i in range(len(tail) - 1) if tail[i]]
        if rs:
            avg = sum(rs) / len(rs)
            if avg > 1.2 and max(rs) - min(rs) < 0.5:
                props.append(("exponential-growth", {"rate": round(avg, 3)}))

    return props
