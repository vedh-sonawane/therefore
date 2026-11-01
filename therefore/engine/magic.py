"""Magic squares: a classic math-discovery problem, exactly verifiable.

An n-by-n magic square is an arrangement of 1..n^2 where every row, every column, and
both diagonals sum to the same number. The engine shuffles the grid and hill-climbs by
swapping cells to drive every line toward that target sum. A square is accepted only when
it is exactly magic, checked directly. Nothing is approximate.
"""


def magic_sum(n):
    return n * (n * n + 1) // 2


def _lines(sq, n):
    rows = [sum(sq[r * n:(r + 1) * n]) for r in range(n)]
    cols = [sum(sq[c + r * n] for r in range(n)) for c in range(n)]
    d1 = sum(sq[i * n + i] for i in range(n))
    d2 = sum(sq[i * n + (n - 1 - i)] for i in range(n))
    return rows + cols + [d1, d2]


def defect(sq, n):
    m = magic_sum(n)
    return sum(abs(x - m) for x in _lines(sq, n))


def is_magic(sq, n):
    return defect(sq, n) == 0


def random_square(n, rng):
    sq = list(range(1, n * n + 1))
    rng.shuffle(sq)
    return sq


def improve(sq, n, rng, tries=400):
    """Hill-climb by swapping two cells; keep swaps that reduce the total defect."""
    sq = list(sq)
    best = defect(sq, n)
    for _ in range(tries):
        if best == 0:
            break
        i = rng.randrange(n * n); j = rng.randrange(n * n)
        if i == j:
            continue
        sq[i], sq[j] = sq[j], sq[i]
        d = defect(sq, n)
        if d <= best:
            best = d
        else:
            sq[i], sq[j] = sq[j], sq[i]   # revert
    return sq, best
