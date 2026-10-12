"""The reduced table. Implements docs/SEMANTICS.md §9.6, with §9.7 as its guarantee.

Members of the cover become reduced states in canonical order, so cover member ``i`` is
reduced state ``i``. Stable entries keep their specified output bits; transient entries
point at the member that holds their implied set and carry no outputs at all, since §8
observes stable outputs only and §12 assigns transient ones.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from huffman_eda.minimize.compat import (
    LimitExceeded,
    MinimizationError,
    _implied,
    check_precondition,
)
from huffman_eda.minimize.cover import _canonical, is_closed_cover, min_closed_cover
from huffman_eda.model import Cell, Choice, FlowTable

__all__ = ["LimitExceeded", "MinimizationError", "minimize", "reduce"]

#: A cover: members are compatibles, and position i (1-based) becomes reduced state i.
Cover = Sequence[frozenset[int]]


def _first(members: Cover, states: frozenset[int]) -> int:
    """The index of the first member in §9.5 order that contains ``states``.

    §9.6's ``choose`` relies on such a member existing by closure when ``|N| >= 2`` and by
    coverage when ``|N| = 1``; reaching the error means the cover was not closed.
    """
    for index, member in enumerate(members, start=1):
        if states <= member:
            return index
    raise ValueError(f"no cover member contains {sorted(states)} (SEMANTICS §9.4)")


def _stable_outputs(table: FlowTable, member: frozenset[int], column: str) -> str:
    """The stable output bits of §9.6, bit by bit, from the members stable in ``column``.

    Compatibility makes each bit's specified value unique, so more than one distinct value
    would mean the member is not a compatible at all.
    """
    bits = []
    for index in range(len(table.outputs)):
        values = {
            table.cell(state, column).outputs[index]
            for state in member
            if table.is_stable(state, column)
        } - {"-"}
        if len(values) > 1:
            raise ValueError(f"members of a compatible disagree at column {column!r}")
        bits.append(values.pop() if values else "-")
    return "".join(bits)


def reduce(table: FlowTable, cover: Iterable[Iterable[int]]) -> FlowTable:
    """The reduced table ``reduce(T, K)`` (SEMANTICS §9.6).

    Raises ``ValueError`` when ``cover`` is not a closed cover of ``table``.
    """
    check_precondition(table)
    if not is_closed_cover(table, cover):
        raise ValueError("the cover is not a closed cover of the table (SEMANTICS §9.4)")
    members = _canonical(frozenset(member) for member in cover)
    rows: dict[int, dict[str, Cell]] = {index: {} for index in range(1, len(members) + 1)}

    for index, member in enumerate(members, start=1):
        for column in table.columns():
            states = _implied(table, member, column)
            if not states:
                rows[index][column] = Cell()
            elif states <= member:
                outputs = _stable_outputs(table, member, column)
                rows[index][column] = Cell((Choice(index, outputs),))
            else:
                transient = _first(members, states)
                rows[index][column] = Cell((Choice(transient, "-" * len(table.outputs)),))

    reset_state, reset_column = table.reset
    current = _first(members, frozenset({reset_state})) - 1
    while True:
        states = _implied(table, members[current], reset_column)
        following = current if states <= members[current] else _first(members, states) - 1
        if following == current:
            break
        current = following
    reset = (current + 1, reset_column)

    return FlowTable(
        name=table.name,
        inputs=table.inputs,
        outputs=table.outputs,
        reset=reset,
        rows=rows,
    )


def minimize(table: FlowTable, *, limit: int = 100_000) -> FlowTable:
    """The smallest implementation of ``table``: ``reduce`` on a minimum closed cover (§9.8)."""
    return reduce(table, min_closed_cover(table, limit=limit))
