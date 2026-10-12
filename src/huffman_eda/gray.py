"""Reflected Gray code column order. Implements docs/SEMANTICS.md §7.

Gray order is for human display only. Every machine-readable output uses the
lexicographic order of ``FlowTable.columns``.
"""

from __future__ import annotations

__all__ = ["gray_columns"]


def gray_columns(n: int) -> list[str]:
    """The ``2**n`` input columns in reflected Gray-code order.

    Column ``k`` is the ``n``-bit binary form (MSB first) of ``k XOR (k >> 1)``, so
    consecutive columns — including the last back to the first — differ in exactly one
    bit. For ``n = 2`` that is ``00, 01, 11, 10``.
    """
    if n < 1:
        raise ValueError(f"a flow table needs at least one input, got n={n}")
    return [format(k ^ (k >> 1), f"0{n}b") for k in range(1 << n)]
