"""Closed covers. Implements docs/SEMANTICS.md §9.4.

`is_closed_cover` checks the two clauses of the definition directly. `min_closed_cover` is
an exact branch-and-bound over the prime compatibles: §9.4 guarantees a minimum closed
cover made of primes exists, so searching that pool loses nothing. It branches on the
requirement with the fewest candidates, which is what makes it prune early.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from huffman_eda.minimize.compat import (
    LimitExceeded,
    MinimizationError,
    _implied,
    _order,
    check_precondition,
    incompatible_pairs,
)
from huffman_eda.minimize.compatibles import _Budget, prime_compatibles
from huffman_eda.model import FlowTable

__all__ = ["LimitExceeded", "MinimizationError", "is_closed_cover", "min_closed_cover"]

#: A cover: members are compatibles, i.e. non-empty sets holding no incompatible pair.
Cover = Sequence[frozenset[int]]


def _canonical(cover: Iterable[frozenset[int]]) -> tuple[frozenset[int], ...]:
    """The members in §9.5 order, so two equal covers are equal."""
    return tuple(sorted(cover, key=lambda member: tuple(sorted(member))))


def _requirements(table: FlowTable, member: frozenset[int]) -> set[frozenset[int]]:
    """The implied sets of ``member`` of size >= 2: sets some cover member must contain."""
    return {
        target for column in table.columns() if len(target := _implied(table, member, column)) >= 2
    }


def _is_compatible(
    table: FlowTable, member: frozenset[int], incompatible: frozenset[tuple[int, int]]
) -> bool:
    """True when ``member`` holds no pair from §9.2's incompatible set."""
    return not any(_order(p, q) in incompatible for p in member for q in member if p < q)


def is_closed_cover(table: FlowTable, cover: Iterable[Iterable[int]]) -> bool:
    """True when ``cover`` is a closed cover of ``table`` (SEMANTICS §9.4).

    Members must be compatibles: the definition is a set of compatibles, so a member
    holding an incompatible pair is not a closed cover even if both clauses would hold.
    """
    check_precondition(table)
    members = [frozenset(member) for member in cover]
    if any(not member for member in members):
        return False
    if not set(table.states()) <= set().union(*members, set()):
        return False
    incompatible = incompatible_pairs(table)
    for member in members:
        if not _is_compatible(table, member, incompatible):
            return False
        for needed in _requirements(table, member):
            if not any(needed <= other for other in members):
                return False
    return True


def min_closed_cover(table: FlowTable, *, limit: int = 100_000) -> tuple[frozenset[int], ...]:
    """A minimum closed cover of ``table`` in canonical order (SEMANTICS §9.4).

    Exact rather than greedy. The requirements are the states still to cover, plus the
    implied sets of every member chosen so far; a solution is reached when none is
    outstanding. Branches that cannot beat the best cover already found are cut, and the
    search spends ``limit``, so a pathological table raises ``LimitExceeded``.
    """
    check_precondition(table)
    budget = _Budget(limit)
    primes = prime_compatibles(table, limit=limit)
    needed_by = {candidate: _requirements(table, candidate) for candidate in primes}
    best: tuple[frozenset[int], ...] | None = None

    def search(chosen: Cover, pending: set[frozenset[int]]) -> None:
        nonlocal best
        budget.spend()
        if best is not None and len(chosen) >= len(best):
            return
        if not pending:
            best = _canonical(chosen)
            return
        # Branch on the requirement with the fewest candidates: fewest ways to be wrong.
        requirement = min(pending, key=lambda need: sum(1 for c in primes if need <= c))
        for candidate in primes:
            if requirement <= candidate and candidate not in chosen:
                # §9.4 clause 2 has no "not a subset of the member" condition, so any
                # requirement a chosen member already contains is settled, not outstanding.
                chosen_now = (*chosen, candidate)
                outstanding = {
                    need
                    for need in pending | needed_by[candidate]
                    if not any(need <= member for member in chosen_now)
                }
                search(chosen_now, outstanding)

    search((), {frozenset({state}) for state in table.states()})
    if best is None:
        raise LimitExceeded(f"no closed cover found within the limit of {limit} steps")
    return best
