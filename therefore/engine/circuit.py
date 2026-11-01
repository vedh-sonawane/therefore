"""Boolean logic circuits: inventing hardware-level logic, verified on every input.

A circuit is a small list of gates (and, or, xor, nand, nor, not) wired from the inputs
and earlier gates, with the last gate as the output. The engine searches for a circuit
that computes a target boolean function, and correctness is checked exhaustively against
the function's full truth table (all 2^n inputs). A circuit is only kept when it is
exactly right; then dead logic is stripped to report the real gate count.

The target function is NOT hardcoded. The engine generates it from one of its own invented
number functions (the parity of that function's output over each input), so the problem it
solves is one it posed itself, and the circuit becomes a hardware form of an invention.
"""

OPS = ["and", "or", "xor", "nand", "nor", "not"]


def _gate(op, x, y):
    if op == "and":  return x & y
    if op == "or":   return x | y
    if op == "xor":  return x ^ y
    if op == "nand": return 1 - (x & y)
    if op == "nor":  return 1 - (x | y)
    return 1 - x     # not


def eval_circuit(gates, n, bits):
    vals = list(bits)
    for op, a, b in gates:
        vals.append(_gate(op, vals[a], vals[b]))
    return vals[-1] if gates else bits[-1]


def truth_vector(gates, n):
    return tuple(eval_circuit(gates, n, [(x >> k) & 1 for k in range(n)]) for x in range(1 << n))


def random_gate(n, upto, rng):
    op = rng.choice(OPS)
    a = rng.randrange(n + upto)
    b = rng.randrange(n + upto)
    return [op, a, b]


def random_circuit(n, size, rng):
    return [random_gate(n, k, rng) for k in range(size)]


def reachable(gates, n):
    """Count the gates that actually feed the output (dead logic removed)."""
    if not gates:
        return 0
    need = {n + len(gates) - 1}
    keep = set()
    for idx in range(len(gates) - 1, -1, -1):
        gi = n + idx
        if gi in need:
            keep.add(idx)
            op, a, b = gates[idx]
            if a >= n:
                need.add(a)
            if op != "not" and b >= n:
                need.add(b)
    return len(keep)


def fitness(gates, n, target_vec):
    v = truth_vector(gates, n)
    return sum(1 for i in range(len(v)) if v[i] == target_vec[i]) / len(v)


def search(target, n, rng, size=7, budget=350, restarts=6):
    """Hill-climb toward a target truth vector, with restarts to escape plateaus.
    Returns the best (gates, fitness) found."""
    g_best, g_fit = None, -1.0
    for _ in range(restarts):
        cur = random_circuit(n, size, rng)
        cf = fitness(cur, n, target)
        for _ in range(budget):
            if cf >= 1.0:
                break
            cand = [g[:] for g in cur]
            k = rng.randrange(len(cand))
            cand[k] = random_gate(n, k, rng)    # rewire one gate (stays acyclic)
            f = fitness(cand, n, target)
            if f >= cf:
                cur, cf = cand, f
        if cf > g_fit:
            g_best, g_fit = cur, cf
        if g_fit >= 1.0:
            break
    return g_best, g_fit
