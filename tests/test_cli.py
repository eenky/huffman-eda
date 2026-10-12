"""Tests for the `hfe` CLI (T203)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from huffman_eda.cli import app
from huffman_eda.explore import explore
from huffman_eda.graph_export import to_dot, to_json
from huffman_eda.io import dump_table, load_table
from huffman_eda.render import render_text
from huffman_eda.validate import validate

GOLDEN = Path(__file__).parent / "golden"
CASES = sorted(p for p in GOLDEN.iterdir() if p.is_dir())
RUNNER = CliRunner()


def expected_has_error(case: Path) -> bool:
    diagnostics = json.loads((case / "expected.json").read_text(encoding="utf-8"))["diagnostics"]
    return any(d["severity"] == "error" for d in diagnostics)


def invoke(*args: str):
    return RUNNER.invoke(app, list(args))


# --- exit codes (SEMANTICS §6) -----------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.name)
@pytest.mark.parametrize("command", [["validate"], ["view", "--plain"], ["explore"], ["fmt"]])
def test_exit_code_is_one_iff_there_is_an_error(command: list[str], case: Path) -> None:
    result = invoke(*command, str(case / "table.yaml"))
    assert result.exit_code == (1 if expected_has_error(case) else 0), result.output


def test_usage_error_exits_two() -> None:
    assert invoke("validate").exit_code == 2  # the FILE argument is missing


def test_unknown_format_exits_two() -> None:
    result = invoke("explore", str(GOLDEN / "clean_toggle" / "table.yaml"), "--format", "xml")
    assert result.exit_code == 2
    assert "unknown format" in result.output


def test_malformed_file_exits_two_with_file_row_column_reason(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(
        'name: t\ninputs: [x]\noutputs: [z]\nreset: [1, "0"]\nrows:\n  1: {"0": "[2],0"}\n',
        encoding="utf-8",
    )
    result = invoke("validate", str(path))
    assert result.exit_code == 2
    assert f"{path}:1:0: bracketed next state [2] must equal the row 1" in result.output


def test_missing_file_exits_two(tmp_path: Path) -> None:
    result = invoke("validate", str(tmp_path / "nope.yaml"))
    assert result.exit_code == 2
    assert "cannot read" in result.output


def test_unsupported_suffix_exits_two(tmp_path: Path) -> None:
    path = tmp_path / "table.txt"
    path.write_text("name: t\n", encoding="utf-8")
    assert invoke("validate", str(path)).exit_code == 2


# --- validate ----------------------------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.name)
def test_json_output_equals_report_to_dict(case: Path) -> None:
    path = case / "table.yaml"
    result = invoke("validate", str(path), "--json")
    assert json.loads(result.output) == validate(load_table(path)).to_dict()


def test_text_output_lists_every_diagnostic() -> None:
    result = invoke("validate", str(GOLDEN / "incomplete_2in" / "table.yaml"))
    assert result.output.splitlines()[0] == (
        "incomplete_2in: 6 diagnostic(s) (3 error, 2 warning, 1 info)"
    )
    for rule in ("FT003", "FT004", "FT005", "FT006", "FT008"):
        assert rule in result.output


def test_clean_table_reports_nothing() -> None:
    result = invoke("validate", str(GOLDEN / "clean_toggle" / "table.yaml"))
    assert result.exit_code == 0
    assert result.output.strip() == "clean_toggle: 0 diagnostic(s) (0 error, 0 warning, 0 info)"


# --- view --------------------------------------------------------------------


def test_view_plain_prints_the_snapshot_grid() -> None:
    path = GOLDEN / "clean_toggle" / "table.yaml"
    result = invoke("view", str(path), "--plain")
    assert result.output == render_text(load_table(path))
    assert result.exit_code == 0


def test_view_renders_a_rich_table() -> None:
    result = invoke("view", str(GOLDEN / "nondeterministic" / "table.yaml"))
    assert "nondeterministic" in result.output
    assert "[1],0" in result.output


# --- explore -----------------------------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.name)
def test_explore_json_matches_the_exporter(case: Path) -> None:
    path = case / "table.yaml"
    expected = to_json(explore(load_table(path)))
    assert json.loads(invoke("explore", str(path)).output) == expected


def test_explore_dot_matches_the_exporter() -> None:
    path = GOLDEN / "oscillation" / "table.yaml"
    table = load_table(path)
    assert invoke("explore", str(path), "--format", "dot").output == to_dot(table, explore(table))


# --- fmt ---------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.name)
def test_fmt_prints_canonical_text_that_reloads(case: Path, tmp_path: Path) -> None:
    path = case / "table.yaml"
    result = invoke("fmt", str(path))
    assert result.output == dump_table(load_table(path))
    again = tmp_path / "again.yaml"
    again.write_text(result.output, encoding="utf-8")
    assert load_table(again) == load_table(path)


def test_fmt_check_reports_canonical_files() -> None:
    result = invoke("fmt", str(GOLDEN / "clean_toggle" / "table.yaml"), "--check")
    assert result.output.strip().endswith(": canonical")


def test_fmt_check_reports_a_reordering(tmp_path: Path) -> None:
    # clean_toggle with the stable entry written unbracketed: legal §2 input, but
    # `dump_table` canonicalizes it to "[1],0".
    path = tmp_path / "unbracketed.yaml"
    path.write_text(
        'name: clean_toggle\ninputs: [x]\noutputs: [z]\nreset: [1, "0"]\n'
        'rows:\n  1: {"0": "1,0", "1": "2,-"}\n  2: {"0": "1,-", "1": "[2],1"}\n',
        encoding="utf-8",
    )
    result = invoke("fmt", str(path), "--check")
    assert result.output.strip().endswith(": would be reformatted")
    # §6 reserves 1 for error diagnostics, and this table has none.
    assert result.exit_code == 0
    assert load_table(path).is_stable(1, "0")
