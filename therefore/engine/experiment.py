"""Experiments: run an invention and record what it *actually* did.

For the Phase-1 domain, an invention is an integer-sequence generator: a function
from an index n to its n-th term. We materialise it by running it on n = 0,1,2,...
Every run is real: it either produces an integer within its fuel budget, or it does
not, and we record which. No term is ever assumed; every term is executed.
"""

from ..vm import run

SEQ_LEN = 24           # how many terms we materialise
TERM_FUEL = 60_000     # fuel budget per term


def materialize(inv, registry, laws, length=SEQ_LEN):
    """Run inv(n) for n in 0..length-1. Returns (prefix, total, stop, ops).

    The per-term fuel is the era's available compute: laws['_energy'] scales it, so
    when a civilization's laws make compute scarce, expensive inventions stop being
    total, and when compute is abundant, old failures can complete again.
    """
    energy = (laws.get("_energy", 1.0) if laws else 1.0)
    fuel = max(2000, int(TERM_FUEL * energy))
    prefix = []
    total_ops = 0
    for n in range(length):
        r = run(inv, [n], registry, laws=laws, fuel=fuel)
        total_ops += r.ops
        if not r.ok or not isinstance(r.value, int) or isinstance(r.value, bool):
            return prefix, False, n, total_ops
        prefix.append(r.value)
    return prefix, True, length, total_ops


def record(store, inv, prefix, total, stop, ops, tick):
    """Persist the materialisation as a real experiment row."""
    store.insert_experiment(
        inv_id=inv.id, kind="materialize",
        inp={"n": [0, len(prefix)]},
        out={"prefix": prefix[:SEQ_LEN], "stopped_at": None if total else stop},
        ops=ops, ok=total,
        error=None if total else f"not total: stopped at n={stop}",
        tick=tick)
