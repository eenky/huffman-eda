"""Settling semantics. Implements docs/SEMANTICS.md §3."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from huffman_eda.model import FlowTable

__all__ = ["Outcome", "SettleResult", "settle"]


class Outcome(Enum):
    """How the successor walk along one column ended (SEMANTICS §3)."""

    STABLE = auto()
    OSCILLATION = auto()
    UNDEFINED = auto()
    NONDET = auto()


@dataclass(frozen=True)
class SettleResult:
    """The states visited while settling, and why the walk stopped.

    ``path`` holds distinct states in visit order starting with the start state.
    ``cycle`` is only set for ``OSCILLATION``: the suffix of ``path`` that repeats.
    """

    kind: Outcome
    path: tuple[int, ...]
    cycle: tuple[int, ...] = ()

    @property
    def final(self) -> int:
        """The last state reached; the settled state when ``kind`` is STABLE."""
        return self.path[-1]


def settle(table: FlowTable, start: int, column: str) -> SettleResult:
    """Follow the column-``column`` successor function from ``state``.

    Implements SEMANTICS §3: the walk stops at an unspecified or nondeterministic
    cell, at a self-holding state, or at the first state revisited (a cycle).
    Linear in the length of the returned path, iterative by construction.
    """
    path: tuple[int, ...] = (start,)
    seen = {start: 0}
    cur = start
    while True:
        cell = table.cell(cur, column)
        if not cell.is_specified:
            return SettleResult(Outcome.UNDEFINED, path)
        if not cell.is_deterministic:
            return SettleResult(Outcome.NONDET, path)
        next_state = cell.next
        if next_state == cur:
            return SettleResult(Outcome.STABLE, path)
        if next_state in seen:
            return SettleResult(Outcome.OSCILLATION, path, path[seen[next_state] :])
        seen[next_state] = len(path)
        path = (*path, next_state)
        cur = next_state
