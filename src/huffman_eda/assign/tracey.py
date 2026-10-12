"""Dichotomies, and the assignment procedure. Implements docs/SEMANTICS.md §10.4-§10.5 (T502).

Ordered dichotomies: ``(left, right)``. A cover of the seed dichotomies by primes, one variable
per member, is race-free whenever the seeds are — and the minimum cover is the smallest number of
state variables, so the search here is the whole of §10.4's minimization.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TypeAlias

from huffman_eda.assign.encoded import EncodedTable, LimitExceeded, encode
from huffman_eda.model import FlowTable

__all__ = ["Assignment", "Dichotomies", "assign", "dichotomies", "tracey"]

#: An ordered dichotomy: the states that take 0 on the left, and those that take 1 on the right.
Dichotomy: TypeAlias = tuple[frozenset[int], frozenset[int]]


@dataclass(frozen=True, slots=True)
class Dichotomies:
    """§10.5: the seed dichotomies, the primes, and which seeds are compatible with which."""

    seeds: frozenset[Dichotomy]
    primes: frozenset[Dichotomy]
    compatibilities: dict[Dichotomy, frozenset[Dichotomy]]


@dataclass(frozen=True, slots=True)
class Assignment:
    """§10.5: the codes, the minimum cover (in canonical order), and its certificate."""

    codes: dict[int, int]
    variables: tuple[Dichotomy, ...]
    certificate: tuple[tuple[Dichotomy, int], ...]


def _compatible(p: Dichotomy, q: Dichotomy) -> bool:
    """§10.4: neither puts a state on the left while the other puts it on the right."""
    return not (p[0] & q[1]) and not (p[1] & q[0])


def _covers(p: Dichotomy, q: Dichotomy) -> bool:
    """§10.4: ``p`` covers ``q`` as an unordered pair, so both orientations of q count."""
    return (q[0] <= p[0] and q[1] <= p[1]) or (q[0] <= p[1] and q[1] <= p[0])


def _d(left: Iterable[int], right: Iterable[int]) -> Dichotomy:
    return (frozenset(left), frozenset(right))


def _key(dichotomy: Dichotomy) -> tuple[tuple[int, ...], tuple[int, ...]]:
    return (tuple(sorted(dichotomy[0])), tuple(sorted(dichotomy[1])))


def seeds(table: FlowTable) -> frozenset[Dichotomy]:
    """§10.5 steps 1-2: the state pairs that must be told apart, with state 1 at all-zero.

    Both orientations of every dichotomy are kept — the procedure drops the ones that would put
    state 1 on the right, which is what fixes the all-zero code.
    """
    states = table.states()
    found = {_d([a], [b]) for a, b in itertools.permutations(states, 2)}
    for column in table.columns():
        for first, third in itertools.product(states, repeat=2):
            cell_first, cell_third = table.cell(first, column), table.cell(third, column)
            if not cell_first.is_specified or not cell_third.is_specified:
                continue
            second, fourth = cell_first.next, cell_third.next
            if second == fourth or (first == second and third == fourth):
                continue
            found |= {
                _d([first, second], [third]),
                _d([first, second], [fourth]),
                _d([first], [third, fourth]),
                _d([second], [third, fourth]),
                _d([third], [first, second]),
                _d([fourth], [first, second]),
                _d([third, fourth], [first]),
                _d([third, fourth], [second]),
            }
    proper = {x for x in found if x[0] and x[1] and not (x[0] & x[1])}
    return frozenset(x for x in proper if 1 not in x[1])


def _prime_candidates(seed_set: frozenset[Dichotomy], limit: int) -> list[Dichotomy]:
    """The unions of maximal pairwise-compatible seed sets: §10.5 step 2."""
    ordered = sorted(seed_set, key=_key)
    linked = {a: frozenset(b for b in ordered if b != a and _compatible(a, b)) for a in ordered}
    unions: set[Dichotomy] = set()
    explored = 0

    def extend(current: list[Dichotomy], candidates: frozenset[Dichotomy]) -> None:
        nonlocal explored
        explored += 1
        if explored > limit:
            raise LimitExceeded(f"dichotomy search explored more than {limit} sets")
        if not candidates:
            unions.add(
                _d(
                    frozenset().union(*[member[0] for member in current]),
                    frozenset().union(*[member[1] for member in current]),
                )
            )
            return
        remaining = candidates
        for candidate in sorted(candidates, key=_key):
            compatible = frozenset(b for b in remaining if b in linked[candidate])
            extend([*current, candidate], compatible - {candidate})
            remaining = remaining - {candidate}

    extend([], seed_set)
    return [
        union
        for union in unions
        if not any(other != union and _covers(other, union) for other in unions)
    ]


def _minimum_covers(
    seed_set: frozenset[Dichotomy], primes: list[Dichotomy], limit: int
) -> list[list[Dichotomy]]:
    """§10.5 steps 3-5: every smallest cover of the seeds by primes, each canonically ordered."""
    ordered = sorted(primes, key=_key)
    for size in range(1, len(ordered) + 1):
        if len(ordered) ** size > limit:
            raise LimitExceeded(f"cover search of size {size} exceeds {limit} combinations")
        found = [
            list(combination)
            for combination in itertools.combinations(ordered, size)
            if all(any(_covers(member, seed) for member in combination) for seed in seed_set)
        ]
        if found:
            found.sort(key=lambda cover: [_key(member) for member in cover])
            return found
    raise AssertionError("the uniqueness seeds alone need every state told apart")


def dichotomies(table: FlowTable, *, limit: int = 100_000) -> Dichotomies:
    """§10.5 steps 1-2, as a value: the seeds, the primes, and the compatibility map."""
    seed_set = seeds(table)
    primes = _prime_candidates(seed_set, limit)
    compatibilities = {
        a: frozenset(b for b in seed_set if b != a and _compatible(a, b)) for a in seed_set
    }
    return Dichotomies(seed_set, frozenset(primes), compatibilities)


def tracey(table: FlowTable, *, limit: int = 100_000) -> Assignment:
    """§10.5: the canonical-first minimum cover, and the codes it gives.

    Member i of the cover is variable i, zero on its left block and one on its right block, so
    the code of a state is the sum of ``2**i`` over the members that put it on the right.
    """
    seed_set = seeds(table)
    primes = _prime_candidates(seed_set, limit)
    cover = _minimum_covers(seed_set, primes, limit)[0]
    codes = {}
    for state in table.states():
        value = 0
        for index, member in enumerate(cover):
            if state in member[1]:
                value |= 1 << index
        codes[state] = value
    certificate = tuple(
        (seed, index)
        for seed in sorted(seed_set, key=_key)
        for index, member in enumerate(cover)
        if _covers(member, seed)
    )
    return Assignment(codes, tuple(cover), certificate)


def assign(table: FlowTable, *, limit: int = 100_000) -> EncodedTable:
    """§10.7: encode ``table`` with the codes of its minimum cover."""
    assignment = tracey(table, limit=limit)
    return encode(table, assignment.codes, bits=len(assignment.variables))
