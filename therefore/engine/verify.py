"""Verification: before anything is believed, it is reproduced.

Determinism is the first gate - we run the invention a second time and require the
exact same output. (The VM has no randomness or I/O, so a mismatch would signal a real
bug, not noise.) Novelty is the second gate, handled by the OEIS check.
"""

from .experiment import materialize


def reproducible(inv, registry, laws, prefix, length):
    """Re-run and confirm the sequence is bit-for-bit identical."""
    again, total, _stop, _ops = materialize(inv, registry, laws, length=length)
    return again == prefix, total
