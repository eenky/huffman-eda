"""Maximal and prime compatibles. Implements docs/SEMANTICS.md §9.3.

Compatibility is pairwise (§9.2), so the maximal compatibles are exactly the maximal
cliques of the compatibility graph: Bron-Kerbosch with pivoting finds them. Prime
compatibles are then the compatibles whose class set no strictly larger maximal
compatible can match, because Γ(C') ⊆ Γ(C) carries up to any maximal compatible
containing C'. Both searches are exponential, so they spend a `limit`.
"""

from __future__ import annotations

from collections.abc import Iterable

from huffman_eda.minimize.compat import (
    LimitExceeded,
    MinimizationError,
    _order,
    check_precondition,
    class_set,
    incompatible_pairs,
)
from huffman_eda.model import FlowTable

__all__ = ["LimitExceeded", "MinimizationError", "maximal_compatibles", "prime_compatibles"]


class _Budget:
    """Counts candidate evaluations, so an exponential search stops at its ``limit``."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.left = limit

    def spend(self) -> None:
        """Consume one unit, raising ``LimitExceeded`` when the limit is already used up."""
        if self.left <= 0:
            raise LimitExceeded(f"search exceeded its limit of {self.limit} steps")
        self.left -= 1


def _canonical(sets: Iterable[frozenset[int]]) -> tuple[frozenset[int], ...]:
    """Order compatibles by their sorted state tuples (SEMANTICS §9.5)."""
    return tuple(sorted(set(sets), key=lambda states: tuple(sorted(states))))


def _vertices(table: FlowTable) -> tuple[int, ...]:
    """The state set ``S``: under §9.1 every next state has a row (SEMANTICS §9.1)."""
    return table.states()


def _compatibility_graph(table: FlowTable) -> tuple[tuple[int, ...], dict[int, set[int]]]:
    """States, and for each state the states compatible with it (SEMANTICS §9.2)."""
    incompatible = incompatible_pairs(table)
    states = _vertices(table)
    neighbours = {
        state: {
            other for other in states if other != state and _order(state, other) not in incompatible
        }
        for state in states
    }
    return states, neighbours


def _maximal_cliques(
    states: tuple[int, ...], neighbours: dict[int, set[int]], budget: _Budget
) -> list[frozenset[int]]:
    """Every maximal clique of the compatibility graph (Bron-Kerbosch with pivoting)."""
    found: list[frozenset[int]] = []

    def expand(chosen: set[int], candidates: set[int], excluded: set[int]) -> None:
        if not candidates and not excluded:
            budget.spend()
            found.append(frozenset(chosen))
            return
        # Pivot on the vertex with the most candidates: fewer recursive calls.
        pivot = max(candidates | excluded, key=lambda v: len(neighbours[v] & candidates))
        for vertex in sorted(candidates - neighbours[pivot]):
            expand(
                chosen | {vertex}, candidates & neighbours[vertex], excluded & neighbours[vertex]
            )
            candidates = candidates - {vertex}
            excluded = excluded | {vertex}

    expand(set(), set(states), set())
    return found


def maximal_compatibles(table: FlowTable, *, limit: int = 10_000) -> tuple[frozenset[int], ...]:
    """The maximal compatibles of ``table`` in canonical order (SEMANTICS §9.3)."""
    check_precondition(table)
    budget = _Budget(limit)
    states, neighbours = _compatibility_graph(table)
    return _canonical(_maximal_cliques(states, neighbours, budget))


def _subsets(states: frozenset[int], budget: _Budget) -> list[frozenset[int]]:
    """Every non-empty subset, largest included, spending one unit of budget each."""
    ordered = sorted(states)
    found = []
    for mask in range(1, 1 << len(ordered)):
        budget.spend()
        found.append(frozenset(ordered[i] for i in range(len(ordered)) if mask >> i & 1))
    return found


def prime_compatibles(table: FlowTable, *, limit: int = 10_000) -> tuple[frozenset[int], ...]:
    """The prime compatibles of ``table`` in canonical order (SEMANTICS §9.3).

    ``C`` is prime when no compatible ``C' ⊋ C`` has ``Γ(C') ⊆ Γ(C)``. It is enough to
    test the maximal compatibles: if any compatible ``C'`` witnesses non-primality then so
    does every compatible between ``C'`` and a maximal compatible containing it, because
    ``⊆`` carries along that chain.
    """
    check_precondition(table)
    budget = _Budget(limit)
    maximals = maximal_compatibles(table, limit=limit)
    candidates: set[frozenset[int]] = set()
    for maximal in maximals:
        candidates.update(_subsets(maximal, budget))
    classes = {candidate: class_set(table, candidate) for candidate in candidates}
    primes = [
        candidate
        for candidate in candidates
        if not any(
            candidate < bigger and classes[bigger] <= classes[candidate]
            for bigger in maximals
            if candidate <= bigger
        )
    ]
    return _canonical(primes)
