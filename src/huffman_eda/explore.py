"""Behavioural exploration. Implements docs/SEMANTICS.md §4."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from huffman_eda.model import FlowTable
from huffman_eda.semantics import Outcome, SettleResult, settle

__all__ = ["ExploreResult", "Transition", "explore"]

Entry = tuple[int, str]


@dataclass(frozen=True)
class Transition:
    """One single-input-change probe: settle from a stable entry at a new column."""

    src_state: int
    src_col: str
    dst_col: str
    result: SettleResult


@dataclass(frozen=True)
class ExploreResult:
    """What a breadth-first walk of the single-input-change graph found.

    ``stable`` is every stable entry ever enqueued (the reset included), ``visited`` is
    every entry the walk stepped through, both sorted; ``transitions`` stay in the order
    they were recorded.
    """

    reset_ok: bool
    stable: tuple[Entry, ...]
    visited: tuple[Entry, ...]
    transitions: tuple[Transition, ...]


def explore(table: FlowTable) -> ExploreResult:
    """Enumerate the behaviour reachable from the reset entry.

    Implements SEMANTICS §4: a FIFO walk over stable total states, trying each input
    bit in increasing order. If the reset row is missing or ``(reset_state,
    reset_column)`` is not stable, nothing is reachable and every set is empty.
    """
    reset_state, reset_column = table.reset
    if reset_state not in table.rows or not table.is_stable(reset_state, reset_column):
        return ExploreResult(reset_ok=False, stable=(), visited=(), transitions=())

    queue: deque[Entry] = deque([(reset_state, reset_column)])
    enqueued: set[Entry] = {(reset_state, reset_column)}
    visited: set[Entry] = {(reset_state, reset_column)}
    transitions: list[Transition] = []

    while queue:
        src_state, src_col = queue.popleft()
        for _, dst_col in table.adjacent(src_col):
            result = settle(table, src_state, dst_col)
            transitions.append(Transition(src_state, src_col, dst_col, result))
            visited.update((state, dst_col) for state in result.path)
            if result.kind is Outcome.STABLE:
                settled: Entry = (result.final, dst_col)
                if settled not in enqueued:
                    enqueued.add(settled)
                    queue.append(settled)

    return ExploreResult(
        reset_ok=True,
        stable=tuple(sorted(enqueued)),
        visited=tuple(sorted(visited)),
        transitions=tuple(transitions),
    )
