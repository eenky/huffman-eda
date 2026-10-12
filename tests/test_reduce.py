"""T404: the reduced table, `minimize`, and `hfe minimize` (§9.6-§9.8).

The reduced-table and `implements` assertions from `tests/golden_minimize` (mirrored, since
that harness asserts all of §9.8 per case), plus the §9.7 property and CLI tests.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, assume, given, settings
from strategies import flow_tables
from typer.testing import CliRunner

from huffman_eda.cli import app
from huffman_eda.equiv import implements
from huffman_eda.explore import explore
from huffman_eda.io import load_table, parse_cell
from huffman_eda.minimize import (
    MinimizationError,
    min_closed_cover,
    minimize,
    reduce,
)
from huffman_eda.model import Cell, Choice, FlowTable
from huffman_eda.validate import validate

GOLDEN = Path(__file__).parent / "golden_minimize"
CASES = sorted(p for p in GOLDEN.iterdir() if p.is_dir() and (p / "table.yaml").exists())

# §9.7's claim is for every table satisfying §9.1, so the criterion is 500 of them.
CRITERION = settings(
    max_examples=500,
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


def singletons(table: FlowTable) -> tuple[frozenset[int], ...]:
    """The all-singletons cover: always closed, since every implied set is a singleton."""
    return tuple(frozenset({state}) for state in table.states())


@pytest.mark.parametrize("name", [p.name for p in CASES if (p / "expected.json").exists()])
def test_golden_reduced_table(name: str) -> None:
    """The §9.8 assertions T404 owns, run in CI; the locked harness stays authoritative."""
    table, want = case(name)
    if want["precondition"] != "ok":
        with pytest.raises(MinimizationError):
            minimize(table)
        return
    red = want["reduced"]
    reduced = reduce(table, [frozenset(member) for member in red["cover"]])
    assert list(reduced.reset) == red["reset"]
    assert sorted(reduced.states()) == sorted(int(state) for state in red["rows"])
    for state, row in red["rows"].items():
        for column in reduced.columns():
            expected = parse_cell(row.get(column, "-"), int(state), len(table.outputs))
            assert reduced.cell(int(state), column) == expected, (state, column)
    assert implements(table, reduced).ok
    assert implements(table, minimize(table)).ok


def test_hand_checked_reduced_table() -> None:
    """`prime_not_maximal` reduces to two states: one merge is stable, the other redirects."""
    table, want = case("prime_not_maximal")
    reduced = reduce(table, [frozenset(member) for member in want["reduced"]["cover"]])
    assert reduced.reset == (1, "1")
    assert reduced.cell(1, "1") == Cell((Choice(1, "1"),))  # stable: members 1 and 2 hold at 1
    assert reduced.cell(1, "0") == Cell((Choice(2, "-"),))  # transient: no outputs of its own
    assert reduced.cell(2, "0") == Cell((Choice(2, "0"),))
    assert reduced.cell(2, "1") == Cell((Choice(2, "0"),))  # only member 4 is stable in "1"


def test_a_cover_that_is_not_closed_is_refused() -> None:
    """§9.6 requires a closed cover, and says so with a ValueError."""
    table, want = case("prime_not_maximal")
    bad = [frozenset(member) for member in want["not_closed"][0]]
    with pytest.raises(ValueError, match="not a closed cover"):
        reduce(table, bad)


def test_reduce_and_minimize_check_the_precondition() -> None:
    """§9.8: the §9.1 precondition comes first, so a non-normal table is never reduced."""
    table, _ = case("non_normal_rejected")
    with pytest.raises(MinimizationError) as caught:
        minimize(table)
    assert caught.value.rules == ("FT004",)


@CRITERION
@given(table=flow_tables(2, 2, 5, normal=True))
def test_a_reduced_table_implements_the_original(table: FlowTable) -> None:
    """§9.7: `implements(T, minimize(T))`, and the same for the all-singletons cover."""
    assume(precondition_ok(table))
    best = minimize(table)
    assert implements(table, best).ok
    assert implements(table, reduce(table, singletons(table))).ok
    assert len(best.states()) <= len(table.states())
    assert (best.inputs, best.outputs) == (table.inputs, table.outputs)


@CRITERION
@given(table=flow_tables(2, 2, 5, normal=True))
def test_minimize_agrees_with_reduce_on_the_cover_it_returns(table: FlowTable) -> None:
    """`minimize` is exactly `reduce` on a minimum closed cover (§9.8)."""
    assume(precondition_ok(table))
    cover = min_closed_cover(table)
    assert minimize(table) == reduce(table, cover)


def test_cli_minimize_writes_a_smaller_table(tmp_path: Path) -> None:
    """`hfe minimize IN -o OUT` writes a table that implements the original."""
    source = GOLDEN / "collapse_to_one" / "table.yaml"
    target = tmp_path / "reduced.yaml"
    result = CliRunner().invoke(app, ["minimize", str(source), "-o", str(target)])
    assert result.exit_code == 0, result.output
    assert "4 states -> 1" in result.output
    written = load_table(target)
    assert implements(load_table(source), written).ok


def test_cli_minimize_refuses_a_non_normal_table(tmp_path: Path) -> None:
    """§9.1: the rules are named and nothing is written."""
    source = GOLDEN / "non_normal_rejected" / "table.yaml"
    target = tmp_path / "reduced.yaml"
    result = CliRunner().invoke(app, ["minimize", str(source), "-o", str(target)])
    assert result.exit_code == 1, result.output
    assert "FT004" in result.output
    assert not target.exists()
