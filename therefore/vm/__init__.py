"""The substrate: a tiny typed, fuel-limited virtual machine.

Inventions are not generated Python. They are typed expression trees ("genomes")
in a small language this VM interprets. That buys us four things the whole project
leans on:

  * safety      - no arbitrary code execution, ever.
  * measurement - every primitive has a cost, so compute is a real, counted resource
                  (this is what the internal economy and the shifting "laws" trade in).
  * composition - an invention can call another invention by id, so inventions plug
                  into each other and complexity has no ceiling.
  * determinism - no I/O, no randomness, a hard fuel cap: the same genome on the same
                  input always gives the same result. Reproducibility is structural.
"""

from .ops import LAWS_DEFAULT, PRIM_SIG, MAG_CAP
from .interp import run, type_check, VMError, Fuel, RunResult
from . import genome

__all__ = [
    "LAWS_DEFAULT", "PRIM_SIG", "MAG_CAP",
    "run", "type_check", "VMError", "Fuel", "RunResult", "genome",
]
