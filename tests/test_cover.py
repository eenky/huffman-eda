"""T403: closed covers and the minimum closed cover (§9.4).

The `min_cover_size`, `min_closed_covers` and `not_closed` assertions from
`tests/golden_minimize` (mirrored, since that harness asserts all of §9.8 per case), plus
unit and property tests.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, assume, given, settings
from strategies import flow_tables

from huffman_eda.explore import explore
from huffman_eda.io import load_table
from huffman_eda.minimize import (
    LimitExceeded,
    MinimizationError,
    is_closed_cover,
    maximal_compatibles,
    min_closed_cover,
)
from huffman_eda.model import FlowTable
from huffman_eda.validate import validate

GOLDEN = Path(__file__).parent / "golden_minimize"
CASES = sorted(p for p in GOLDEN.iterdir() if p.is_dir() and (p / "table.yaml").exists())

SLOW = settings(
    max_examples=200,
    deadline=None,
    database=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)


def precondition_ok(table: FlowTable) -> bool:
    """True when ``table`` satisfies §9.1, judged by §4/§5 alone."""
    rules = {d.rule for d in validate(table).diagnostics}
    return explore(table).reset_ok and not rules & {"FT000", "FT001", "FT003", "FT004"}


def case(name: str) -> tuple[FlowTable, dict[str, Any]]:
    """A golden table and its expectations."""
    return (
        load_table(GOLDEN / name / "table.yaml"),
        json.loads((GOLDEN / name / "expected.json").read_text()),
    )


def as_lists(cover: tuple[frozenset[int], ...]) -> list[list[int]]:
    """Golden expectations are lists of sorted lists."""
    return [sorted(member) for member in cover]


def all_compatibles(table: FlowTable) -> list[frozenset[int]]:
    """Every compatible, written out as the non-empty subsets of the maximal ones."""
    found = set()
    for maximal in maximal_compatibles(table):
        states = sorted(maximal)
        for size in range(1, len(states) + 1):
            found.update(frozenset(part) for part in itertools.combinations(states, size))
    return sorted(found, key=lambda member: sorted(member))


@pytest.mark.parametrize("name", [p.name for p in CASES if (p / "expected.json").exists()])
def test_golden_minimum_cover(name: str) -> None:
    """The §9.8 assertions T403 owns, run in CI; the locked harness stays authoritative."""
    table, want = case(name)
    if want["precondition"] != "ok":
        with pytest.raises(MinimizationError):
            min_closed_cover(table)
        return
    cover = min_closed_cover(table)
    assert len(cover) == want["min_cover_size"]
    assert as_lists(cover) in want["min_closed_covers"]
    assert is_closed_cover(table, cover)
    for bad in want.get("not_closed") or []:
        assert not is_closed_cover(table, [frozenset(member) for member in bad]), bad


def test_the_only_minimum_cover_overlaps() -> None:
    """`overlap_required`: size 2 is reachable only by two members that share state 4."""
    table, want = case("overlap_required")
    cover = min_closed_cover(table)
    assert as_lists(cover) == want["min_closed_covers"][0]
    assert len(frozenset.intersection(*cover)) == 1
    # Every non-overlapping pair of compatibles of that size fails closure, as the case says.
    for pair in itertools.combinations(all_compatibles(table), 2):
        if not (pair[0] & pair[1]):
            assert not is_closed_cover(table, pair)


def test_a_cover_whose_member_is_not_compatible_is_rejected() -> None:
    """A closed cover is a set of compatibles (§9.4), so {1,3} cannot be a member."""
    table, _ = case("prime_not_maximal")
    assert not is_closed_cover(table, [frozenset({1, 3}), frozenset({2}), frozenset({4})])


def test_a_cover_that_misses_a_state_is_rejected() -> None:
    """Clause 1 of §9.4: the members must cover every state."""
    table, _ = case("prime_not_maximal")
    assert not is_closed_cover(table, [frozenset({1, 2}), frozenset({3})])


def test_both_functions_check_the_precondition() -> None:
    """§9.8: the §9.1 precondition comes first, so a non-normal table is never covered."""
    table, _ = case("non_normal_rejected")
    for call in (
        lambda: min_closed_cover(table),
        lambda: is_closed_cover(table, [frozenset({1})]),
    ):
        with pytest.raises(MinimizationError) as caught:
            call()
        assert caught.value.rules == ("FT004",)


def test_a_tiny_limit_is_refused() -> None:
    """A branch-and-bound that cannot finish raises instead of running forever."""
    table, _ = case("collapse_to_one")
    with pytest.raises(LimitExceeded):
        min_closed_cover(table, limit=0)


@SLOW
@given(table=flow_tables(2, 2, 5, normal=True))
def test_the_returned_cover_is_a_closed_cover(table: FlowTable) -> None:
    """Whatever the search returns must satisfy §9.4, including its own closure clause."""
    assume(precondition_ok(table))
    cover = min_closed_cover(table)
    assert is_closed_cover(table, cover)
    assert sorted(map(sorted, cover)) == sorted(map(sorted, set(cover)))


@SLOW
@given(table=flow_tables(1, 1, 4, normal=True))
def test_no_smaller_closed_cover_exists(table: FlowTable) -> None:
    """Exhaustive minimality: every combination of compatibles smaller than the answer fails."""
    assume(precondition_ok(table))
    cover = min_closed_cover(table)
    compatibles = all_compatibles(table)
    for size in range(1, len(cover)):
        for combination in itertools.combinations(compatibles, size):
            assert not is_closed_cover(table, combination), combination
