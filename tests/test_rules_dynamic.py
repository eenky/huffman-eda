"""Tests for the dynamic rules and validate() (T106)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from huffman_eda.diagnostics import Diagnostic
from huffman_eda.explore import explore
from huffman_eda.io import load_table, parse_cell
from huffman_eda.model import FlowTable
from huffman_eda.rules.dynamic import dynamic_rules
from huffman_eda.validate import validate

GOLDEN = Path(__file__).parent / "golden"
DYNAMIC_IDS = {"FT000", "FT005", "FT006", "FT007"}

CLEAN = {1: {"0": "[1],0", "1": "2,-"}, 2: {"0": "1,-", "1": "[2],1"}}


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


def dynamic(table: FlowTable) -> list[Diagnostic]:
    return dynamic_rules(table, explore(table))


# --- FT000 -------------------------------------------------------------------


def test_ft000_missing_reset_row() -> None:
    table = table_of({1: {"0": "[1],0"}}, reset=(7, "0"))
    assert keys(dynamic(table)) == [("FT000", "error", 7, "0")]


def test_ft000_unstable_reset() -> None:
    table = table_of({1: {"0": "2,0"}, 2: {"0": "[2],0"}}, reset=(1, "0"))
    diagnostics = dynamic(table)
    assert keys(diagnostics) == [("FT000", "error", 1, "0")]
    assert "not stable" in diagnostics[0].message


def test_ft000_is_the_only_rule_when_the_reset_is_unusable() -> None:
    # This table would also produce FT005 and FT006 if the walk were attempted.
    table = table_of({1: {"0": "2,0", "1": "9,0"}, 2: {"0": "[2],0"}}, reset=(1, "0"))
    assert [d.rule for d in dynamic(table)] == ["FT000"]


# --- FT005 -------------------------------------------------------------------


def test_ft005_input_change_into_an_unspecified_entry() -> None:
    # From (1,"0") the environment may flip x, and (1,"1") is unspecified.
    table = table_of({1: {"0": "[1],0"}})
    assert keys(dynamic(table)) == [("FT005", "error", 1, "1")]


def test_ft005_ignores_deeper_undefined_paths() -> None:
    # (1,"1") is specified, so this is FT003's business (static), not FT005's.
    table = table_of({1: {"0": "[1],0", "1": "2,0"}})
    assert [d for d in dynamic(table) if d.rule == "FT005"] == []


# --- FT006 -------------------------------------------------------------------


def test_ft006_lists_unreachable_specified_entries() -> None:
    table = table_of({1: {"0": "[1],0"}, 2: {"0": "[2],0"}, 3: {"0": "3,0"}})
    assert keys(dynamic(table)) == [
        ("FT005", "error", 1, "1"),
        ("FT006", "info", 2, "0"),
        ("FT006", "info", 3, "0"),
    ]


def test_ft006_is_silent_for_a_reachable_table() -> None:
    assert dynamic(table_of(CLEAN)) == []


# --- FT007 -------------------------------------------------------------------


def test_ft007_names_only_the_non_monotonic_output() -> None:
    # Over (1,"0") -> column "1": z1 stays 0; z2 goes 0,1,0,1.
    table = table_of(
        {1: {"0": "[1],00", "1": "2,01"}, 2: {"1": "3,00"}, 3: {"1": "[3],01"}},
        outputs=("z1", "z2"),
    )
    diagnostics = [d for d in dynamic(table) if d.rule == "FT007"]
    assert [(d.state, d.column) for d in diagnostics] == [(1, "1")]
    assert "'z2'" in diagnostics[0].message
    assert "'z1'" not in diagnostics[0].message


def test_ft007_counts_changes_after_dropping_unassigned_outputs() -> None:
    # z: 0 at the source, then -, then 1: one change once the dash is dropped.
    assert [d for d in dynamic(table_of(CLEAN)) if d.rule == "FT007"] == []


def test_ft007_ignores_unstable_results() -> None:
    table = table_of({1: {"0": "[1],0", "1": "2,0"}})
    assert [d for d in dynamic(table) if d.rule == "FT007"] == []


# --- validate ----------------------------------------------------------------


def test_validate_merges_static_and_dynamic_diagnostics_sorted() -> None:
    table = table_of({1: {"00": "[1],-", "10": "2,0"}}, inputs=("x1", "x2"), reset=(1, "00"))
    report = validate(table)
    assert report.table == "t"
    assert [d.rule for d in report.diagnostics] == ["FT003", "FT005", "FT009"]
    assert report.has_errors
    assert (report.diagnostics[1].state, report.diagnostics[1].column) == (1, "01")


def test_validate_accepts_the_golden_clean_case() -> None:
    report = validate(load_table(GOLDEN / "clean_toggle" / "table.yaml"))
    assert report.diagnostics == ()
    assert not report.has_errors


# --- golden ------------------------------------------------------------------


@pytest.mark.parametrize(
    "case", sorted(p for p in GOLDEN.iterdir() if p.is_dir()), ids=lambda p: p.name
)
def test_dynamic_subset_matches_golden(case: Path) -> None:
    """The dynamic part of the owner-written expectations, for every golden case."""
    table = load_table(case / "table.yaml")
    expected = json.loads((case / "expected.json").read_text(encoding="utf-8"))["diagnostics"]
    want = sorted(
        (
            d["rule"],
            d["severity"],
            -1 if d["state"] is None else d["state"],
            "" if d["column"] is None else d["column"],
        )
        for d in expected
        if d["rule"] in DYNAMIC_IDS
    )
    assert keys(dynamic(table)) == want
