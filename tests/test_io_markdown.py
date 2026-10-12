"""Tests for Markdown table import and the `hfe import` command (T204)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from huffman_eda.cli import app
from huffman_eda.io import (
    ParseError,
    dump_markdown,
    dump_table,
    load_markdown,
    load_table,
    parse_markdown,
)

GOLDEN = Path(__file__).parent / "golden"
CASES = sorted(p for p in GOLDEN.iterdir() if p.is_dir())
RUNNER = CliRunner()

TWO_INPUT = """\
---
name: example
inputs: [x1, x2]
outputs: [z]
reset: [1, "00"]
---
| state | 00 | 01 | 11 | 10 |
|---|---|---|---|---|
| 1 | [1],0 | 2,- | - | 3,- |
| 2 | 1,- | [2],1 | - | - |
"""


def golden_tables() -> dict[str, str]:
    return {case.name: (case / "table.yaml").read_text(encoding="utf-8") for case in CASES}


# --- the round trip the task asks for ----------------------------------------


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.name)
def test_golden_round_trip_through_markdown(case: Path) -> None:
    """Render the golden table as Markdown, import it, and get the same table back."""
    original = load_table(case / "table.yaml")
    assert parse_markdown(dump_markdown(original)) == original


def test_markdown_mirrors_the_yaml_cells() -> None:
    # The two serializers must agree on cell notation, brackets included.
    for case in CASES:
        table = load_table(case / "table.yaml")
        yaml_text = dump_table(table)
        markdown = dump_markdown(table)
        assert f'"{table.reset[1]}"' in yaml_text
        assert "| state |" in markdown
        assert "\\|" not in markdown or table.name == "nondeterministic"


# --- parsing -----------------------------------------------------------------


def test_parses_the_documented_example() -> None:
    table = parse_markdown(TWO_INPUT)
    assert table.name == "example"
    assert table.inputs == ("x1", "x2")
    assert table.reset == (1, "00")
    assert table.states() == (1, 2)
    assert table.cell(1, "10").next == 3
    assert table.is_stable(1, "00")


def test_header_columns_may_appear_in_any_order() -> None:
    lexicographic = TWO_INPUT.replace(
        "| state | 00 | 01 | 11 | 10 |", "| state | 00 | 01 | 10 | 11 |"
    ).replace("| 1 | [1],0 | 2,- | - | 3,- |", "| 1 | [1],0 | 2,- | 3,- | - |")
    assert parse_markdown(lexicographic) == parse_markdown(TWO_INPUT)


def test_escaped_pipe_is_a_choice_separator() -> None:
    text = TWO_INPUT.replace("| 1 | [1],0 | 2,- | - | 3,- |", "| 1 | [1],0 | 2,-\\|3,- | - | - |")
    table = parse_markdown(text)
    assert table.cell(1, "01") == table.cell(1, "01")
    assert len(table.cell(1, "01").choices) == 2


def test_unescaped_pipe_gives_a_cell_count_error() -> None:
    text = TWO_INPUT.replace("| 1 | [1],0 | 2,- | - | 3,- |", "| 1 | [1],0 | 2,-|3,- | - | - |")
    with pytest.raises(ParseError, match="missing its escape"):
        parse_markdown(text)


def test_separator_row_may_carry_alignment_colons() -> None:
    text = TWO_INPUT.replace("|---|---|---|---|---|", "|:--|:-:|--:|---|:--:|")
    assert parse_markdown(text).name == "example"


def test_load_markdown_reads_a_file(tmp_path: Path) -> None:
    path = tmp_path / "table.md"
    path.write_text(TWO_INPUT, encoding="utf-8")
    assert load_markdown(path) == parse_markdown(TWO_INPUT)


def test_missing_file_is_a_parse_error(tmp_path: Path) -> None:
    with pytest.raises(ParseError, match="cannot read"):
        load_markdown(tmp_path / "nope.md")


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("name: t\n", "front matter"),
        ("---\nname: t\n---\n", "Markdown table"),
        ("---\n- 1\n---\n| a |\n|---|\n| 1 |\n", "mapping"),
        ('---\nname: t\ninputs: []\noutputs: []\nreset: [1, "0"]\n---\n', "Markdown table"),
        (
            '---\nname: t\ninputs: [x]\noutputs: [z]\nreset: [1, "0"]\n---\n| s |\n|---|\n| 1 |\n',
            "first header cell",
        ),
        (
            '---\nname: t\ninputs: [x]\noutputs: [z]\nreset: [1, "0"]\n---\n'
            "| state | 0 |\n| state | x |\n| 1 | [1],0 |\n",
            "separator row",
        ),
        (
            '---\nname: t\ninputs: [x]\noutputs: [z]\nreset: [1, "0"]\n---\n'
            "| state | 0 |\n|---|---|\n| x | [1],0 |\n",
            "row key",
        ),
        (
            '---\nname: t\ninputs: [x]\noutputs: [z]\nreset: [1, "0"]\n---\n'
            "| state | 2 |\n|---|---|\n| 1 | [1],0 |\n",
            "column key",
        ),
    ],
)
def test_rejects_malformed_transcriptions(text: str, reason: str) -> None:
    with pytest.raises(ParseError, match=reason):
        parse_markdown(text)


# --- rendering ---------------------------------------------------------------


def test_dump_markdown_writes_gray_columns_and_a_separator() -> None:
    table = load_table(GOLDEN / "incomplete_2in" / "table.yaml")
    lines = dump_markdown(table).splitlines()
    assert lines[0] == "---"
    assert lines[5] == "---"
    assert lines[6] == ""
    assert lines[7] == "| state | 00 | 01 | 11 | 10 |"
    assert lines[8] == "|---|---|---|---|---|"
    assert lines[9] == "| 1 | [1],0 | 2,- | - | - |"


def test_dump_markdown_escapes_choice_separators() -> None:
    table = load_table(GOLDEN / "nondeterministic" / "table.yaml")
    # The §2 separator " | " becomes "\|" so the row keeps its cell count.
    assert "| 1 | [1],0 | 2,0 \\| 3,1 |" in dump_markdown(table)


def test_dump_markdown_reloads() -> None:
    table = load_table(GOLDEN / "nondeterministic" / "table.yaml")
    assert parse_markdown(dump_markdown(table)) == table


# --- hfe import --------------------------------------------------------------


def test_import_writes_canonical_yaml(tmp_path: Path) -> None:
    original = load_table(GOLDEN / "clean_toggle" / "table.yaml")
    source = tmp_path / "table.md"
    source.write_text(dump_markdown(original), encoding="utf-8")
    target = tmp_path / "table.yaml"
    result = RUNNER.invoke(app, ["import", str(source), "-o", str(target)])
    assert result.exit_code == 0, result.output
    assert f"wrote {target}" in result.output
    assert target.read_text(encoding="utf-8") == dump_table(original)
    assert load_table(target) == original


def test_import_exit_code_follows_the_diagnostics(tmp_path: Path) -> None:
    # `TWO_INPUT` names state 3 as a next state but defines no row for it (FT000).
    source = tmp_path / "two.md"
    source.write_text(TWO_INPUT, encoding="utf-8")
    target = tmp_path / "two.yaml"
    result = RUNNER.invoke(app, ["import", str(source), "-o", str(target)])
    assert result.exit_code == 1, result.output
    assert target.exists()  # the YAML is written either way


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.name)
def test_import_round_trips_a_golden_table(case: Path, tmp_path: Path) -> None:
    source = tmp_path / f"{case.name}.md"
    source.write_text(dump_markdown(load_table(case / "table.yaml")), encoding="utf-8")
    target = tmp_path / f"{case.name}.yaml"
    result = RUNNER.invoke(app, ["import", str(source), "-o", str(target)])
    expected_exit = (
        1
        if any(
            d["severity"] == "error"
            for d in __import__("json").loads((case / "expected.json").read_text())["diagnostics"]
        )
        else 0
    )
    assert result.exit_code == expected_exit, result.output
    assert load_table(target) == load_table(case / "table.yaml")


def test_import_reports_a_malformed_transcription(tmp_path: Path) -> None:
    source = tmp_path / "bad.md"
    source.write_text("name: t\n", encoding="utf-8")
    result = RUNNER.invoke(app, ["import", str(source), "-o", str(tmp_path / "out.yaml")])
    assert result.exit_code == 2
    assert "front matter" in result.output
    assert not (tmp_path / "out.yaml").exists()


def test_import_requires_an_output() -> None:
    result = RUNNER.invoke(app, ["import", "anything.md"])
    assert result.exit_code == 2
