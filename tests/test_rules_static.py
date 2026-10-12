"""Tests for the static rules (T105).

Tables are written in the §2 cell notation and parsed with T102's parser, so the tests
read like the spec.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from huffman_eda.diagnostics import Diagnostic
from huffman_eda.io import load_table, parse_cell
from huffman_eda.model import FlowTable
from huffman_eda.rules.static import ft001, ft002, ft003, ft004, ft008, ft009, static_rules

GOLDEN = Path(__file__).parent / "golden"
STATIC_IDS = {"FT001", "FT002", "FT003", "FT004", "FT008", "FT009"}


def table_of(
    rows: dict[int, dict[str, str]],
    outputs: tuple[str, ...] = ("z",),
    inputs: tuple[str, ...] = ("x",),
    reset: tuple[int, str] = (1, "0"),
) -> FlowTable:
    """Build a table from §2 cell text: state -> column -> cell."""
    return FlowTable(
        name="t",
        inputs=inputs,
        outputs=outputs,
        reset=reset,
        rows={
            state: {
                column: parse_cell(text, state, len(outputs), column)
                for column, text in row.items()
            }
            for state, row in rows.items()
        },
    )


def keys(diagnostics: list[Diagnostic]) -> list[tuple[str, str, int, str]]:
    return sorted(d.key() for d in diagnostics)


# --- one focused table per rule ----------------------------------------------


def test_ft001_nondeterministic_entry() -> None:
    table = table_of({1: {"0": "[1],0", "1": "2,0|3,1"}, 2: {"1": "[2],0"}, 3: {"1": "[3],1"}})
    assert keys(ft001(table)) == [("FT001", "error", 1, "1")]


def test_ft002_reports_one_cycle_once_at_its_lowest_state() -> None:
    # (1,0) holds itself: a stable entry, not a cycle. 3 -> 4 -> 5 -> 3 is a 3-cycle,
    # entered from 2, and is reported once at state 3.
    table = table_of(
        {
            1: {"0": "[1],0"},
            2: {"0": "1,0"},
            3: {"0": "4,-"},
            4: {"0": "5,-"},
            5: {"0": "3,-"},
        }
    )
    assert keys(ft002(table)) == [("FT002", "error", 3, "0")]


def test_ft002_reports_each_column_separately() -> None:
    table = table_of({1: {"0": "2,0", "1": "2,0"}, 2: {"0": "1,0", "1": "1,0"}})
    assert keys(ft002(table)) == [("FT002", "error", 1, "0"), ("FT002", "error", 1, "1")]


def test_ft002_ignores_nondeterministic_entries() -> None:
    table = table_of({1: {"0": "2,0"}, 2: {"0": "1,0|2,0"}})
    assert ft002(table) == []


def test_ft003_settling_into_an_unspecified_entry() -> None:
    # State 2 has no row, so (2,1) is unspecified.
    table = table_of({1: {"0": "[1],0", "1": "2,0"}})
    diagnostics = ft003(table)
    assert keys(diagnostics) == [("FT003", "error", 1, "1")]
    assert diagnostics[0].path == (1, 2)


def test_ft003_ignores_oscillations() -> None:
    table = table_of({1: {"0": "2,0"}, 2: {"0": "1,0"}})
    assert ft003(table) == []


def test_ft004_non_normal_table() -> None:
    table = table_of({1: {"0": "[1],0", "1": "2,0"}, 2: {"1": "3,0"}, 3: {"1": "[3],0"}})
    assert keys(ft004(table)) == [("FT004", "warning", 1, "1")]


def test_ft008_state_with_no_stable_entry() -> None:
    table = table_of({1: {"0": "[1],0"}, 2: {"0": "1,0", "1": "3,0"}})
    diagnostics = ft008(table)
    assert keys(diagnostics) == [("FT008", "warning", 2, "")]
    assert diagnostics[0].column is None


def test_ft009_stable_entry_with_an_unassigned_output() -> None:
    table = table_of({1: {"0": "[1],-", "1": "[1],0"}})
    assert keys(ft009(table)) == [("FT009", "warning", 1, "0")]


def test_a_clean_table_produces_no_diagnostics() -> None:
    table = table_of({1: {"0": "[1],0", "1": "2,-"}, 2: {"0": "1,-", "1": "[2],1"}})
    assert static_rules(table) == []


def test_static_rules_concatenates_every_rule_in_order() -> None:
    table = table_of({1: {"0": "[1],-", "1": "2,0|3,0"}})
    expected: list[Diagnostic] = []
    for rule in (ft001, ft002, ft003, ft004, ft008, ft009):
        expected.extend(rule(table))
    assert static_rules(table) == expected
    assert {d.rule for d in expected} == {"FT001", "FT009"}


# --- golden ------------------------------------------------------------------


@pytest.mark.parametrize(
    "case", sorted(p for p in GOLDEN.iterdir() if p.is_dir()), ids=lambda p: p.name
)
def test_static_subset_matches_golden(case: Path) -> None:
    """The static part of the owner-written expectations, for every golden case."""
    expected = json.loads((case / "expected.json").read_text(encoding="utf-8"))["diagnostics"]
    want = sorted(
        (
            d["rule"],
            d["severity"],
            -1 if d["state"] is None else d["state"],
            "" if d["column"] is None else d["column"],
        )
        for d in expected
        if d["rule"] in STATIC_IDS
    )
    assert keys(static_rules(load_table(case / "table.yaml"))) == want
