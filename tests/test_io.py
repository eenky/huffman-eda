"""Tests for the cell grammar and YAML/JSON loader (T102)."""

from __future__ import annotations

from pathlib import Path

import pytest

from huffman_eda.io import ParseError, dump_table, load_table, parse_cell
from huffman_eda.model import Cell, Choice, FlowTable

GOLDEN = Path(__file__).parent / "golden"
GOLDEN_TABLES = sorted(GOLDEN.glob("*/table.yaml"))

ONE_INPUT = """\
name: example
inputs: [x]
outputs: [z]
reset: [1, "0"]
rows:
  1: {"0": "[1],0", "1": "2,-"}
  2: {"0": "1,-", "1": "[2],1"}
"""


def write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def example(tmp_path: Path) -> FlowTable:
    """ONE_INPUT, loaded from disk."""
    return load_table(write(tmp_path, "example.yaml", ONE_INPUT))


# --- parse_cell: accept ------------------------------------------------------


def test_parse_unspecified_cell() -> None:
    assert parse_cell("-", row=1, m=1) == Cell()


def test_parse_stable_single_choice() -> None:
    assert parse_cell("[1],0", row=1, m=1) == Cell((Choice(1, "0"),))


def test_parse_transient_single_choice() -> None:
    assert parse_cell("2,-", row=1, m=1) == Cell((Choice(2, "-"),))


def test_parse_nondeterministic_cell() -> None:
    assert parse_cell("2,0|3,1", row=1, m=1) == Cell((Choice(2, "0"), Choice(3, "1")))


def test_parse_allows_whitespace_between_tokens() -> None:
    assert parse_cell("  [1] , 0  ", row=1, m=1) == Cell((Choice(1, "0"),))


def test_parse_zero_output_cell() -> None:
    assert parse_cell("2", row=1, m=0) == Cell((Choice(2, ""),))
    assert parse_cell("-", row=1, m=0) == Cell()


def test_parse_two_outputs() -> None:
    assert parse_cell("2,0-", row=1, m=2) == Cell((Choice(2, "0-"),))


def test_parse_deduplicates_repeated_choices() -> None:
    assert parse_cell("2,0|2,0", row=1, m=1) == Cell((Choice(2, "0"),))


# --- parse_cell: reject -----------------------------------------------------


def test_reject_bracketed_target_that_is_not_the_row() -> None:
    with pytest.raises(ParseError, match="must equal the row 1") as excinfo:
        parse_cell("[2],0", row=1, m=1, column="0")
    assert (excinfo.value.row, excinfo.value.column, excinfo.value.text) == (1, "0", "[2],0")


def test_reject_wrong_output_length() -> None:
    with pytest.raises(ParseError, match="exactly 1 characters"):
        parse_cell("2,00", row=1, m=1)
    with pytest.raises(ParseError, match="exactly 2 characters"):
        parse_cell("2,0", row=1, m=2)


def test_reject_outputs_outside_the_alphabet() -> None:
    with pytest.raises(ParseError, match="exactly 1 characters"):
        parse_cell("2,x", row=1, m=1)


def test_reject_outputs_when_there_are_no_outputs() -> None:
    with pytest.raises(ParseError, match="forbidden"):
        parse_cell("2,0", row=1, m=0)


def test_reject_missing_outputs_when_outputs_exist() -> None:
    with pytest.raises(ParseError, match="outputs are required"):
        parse_cell("2", row=1, m=1)


def test_reject_empty_choice() -> None:
    with pytest.raises(ParseError, match="empty choice"):
        parse_cell("2,0|", row=1, m=1)
    with pytest.raises(ParseError, match="empty choice"):
        parse_cell("|2,0", row=1, m=1)
    with pytest.raises(ParseError, match="empty choice"):
        parse_cell("", row=1, m=1)


def test_reject_dash_inside_a_multi_choice_cell() -> None:
    with pytest.raises(ParseError, match="whole cell"):
        parse_cell("2,0|-", row=1, m=1)


def test_reject_unbalanced_brackets() -> None:
    with pytest.raises(ParseError, match="unbalanced brackets"):
        parse_cell("[1,0", row=1, m=1)


def test_reject_non_integer_target() -> None:
    with pytest.raises(ParseError, match="must be an integer"):
        parse_cell("x,0", row=1, m=1)


# --- load_table --------------------------------------------------------------


def test_load_yaml(tmp_path: Path) -> None:
    table = load_table(write(tmp_path, "t.yaml", ONE_INPUT))
    assert table.name == "example"
    assert table.inputs == ("x",)
    assert table.outputs == ("z",)
    assert table.reset == (1, "0")
    assert table.states() == (1, 2)
    assert table.cell(1, "1") == Cell((Choice(2, "-"),))
    assert table.is_stable(1, "0")


def test_load_json_with_string_row_keys(tmp_path: Path) -> None:
    text = """\
{"name": "j", "inputs": ["x"], "outputs": ["z"], "reset": [1, "0"],
 "rows": {"1": {"0": "[1],0", "1": "2,-"}, "2": {"0": "1,-", "1": "[2],1"}}}
"""
    table = load_table(write(tmp_path, "t.json", text))
    assert table.states() == (1, 2)
    assert table.is_stable(2, "1")


def test_load_yml_suffix(tmp_path: Path) -> None:
    assert load_table(write(tmp_path, "t.yml", ONE_INPUT)).name == "example"


def test_reject_unsupported_suffix(tmp_path: Path) -> None:
    with pytest.raises(ParseError, match="unsupported table suffix"):
        load_table(write(tmp_path, "t.txt", ONE_INPUT))


def test_reject_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ParseError, match="cannot read"):
        load_table(tmp_path / "nope.yaml")


def test_reject_unquoted_column_key(tmp_path: Path) -> None:
    # In YAML, an unquoted `01:` key is the integer 1, not the column "01".
    text = 'name: t\ninputs: [x1, x2]\noutputs: [z]\nreset: [1, "00"]\nrows:\n  1: {01: "2,0"}\n'
    with pytest.raises(ParseError, match="column keys must be quoted") as excinfo:
        load_table(write(tmp_path, "t.yaml", text))
    assert excinfo.value.row == 1


def test_reject_bad_column_in_the_file(tmp_path: Path) -> None:
    text = 'name: t\ninputs: [x1, x2]\noutputs: [z]\nreset: [1, "00"]\nrows:\n  1: {"2": "2,0"}\n'
    with pytest.raises(ParseError, match="must be 2 characters"):
        load_table(write(tmp_path, "t.yaml", text))


def test_reject_cell_error_carries_its_location(tmp_path: Path) -> None:
    text = 'name: t\ninputs: [x]\noutputs: [z]\nreset: [1, "0"]\nrows:\n  1: {"0": "[2],0"}\n'
    with pytest.raises(ParseError) as excinfo:
        load_table(write(tmp_path, "t.yaml", text))
    assert (excinfo.value.row, excinfo.value.column, excinfo.value.text) == (1, "0", "[2],0")


def test_reject_invalid_json(tmp_path: Path) -> None:
    with pytest.raises(ParseError, match="invalid JSON"):
        load_table(write(tmp_path, "t.json", "{"))


def test_reject_reset_that_is_not_a_pair(tmp_path: Path) -> None:
    text = "name: t\ninputs: [x]\noutputs: [z]\nreset: [1]\nrows: {}\n"
    with pytest.raises(ParseError, match=r"reset must be \[state, column\]"):
        load_table(write(tmp_path, "t.yaml", text))


# --- dump_table --------------------------------------------------------------


def test_dump_writes_columns_lexicographic_and_quoted(example: FlowTable) -> None:
    text = dump_table(example)
    assert '"0": "[1],0", "1": "2,-"' in text
    assert text.startswith('name: example\ninputs: [x]\noutputs: [z]\nreset: [1, "0"]\nrows:\n')


def test_dump_brackets_only_the_stable_choice(example: FlowTable) -> None:
    text = dump_table(example)
    assert '"1": "[2],1"' in text
    assert '"0": "1,-"' in text  # transient: no brackets


def test_dump_writes_all_columns_and_dashes_for_unspecified() -> None:
    table = FlowTable(
        name="t",
        inputs=("x1", "x2"),
        outputs=("z",),
        reset=(1, "00"),
        rows={1: {"00": Cell((Choice(1, "0"),))}},
    )
    rows = dump_table(table).splitlines()[-1]
    assert rows == '  1: {"00": "[1],0", "01": "-", "10": "-", "11": "-"}'


def test_dump_then_load_is_lossless(example: FlowTable, tmp_path: Path) -> None:
    assert load_table(write(tmp_path, "again.yaml", dump_table(example))) == example


def test_dump_omits_outputs_when_there_are_none() -> None:
    table = FlowTable(
        name="t",
        inputs=("x",),
        outputs=(),
        reset=(1, "0"),
        rows={1: {"0": Cell((Choice(1, ""),)), "1": Cell((Choice(2, ""),))}},
    )
    assert '1: {"0": "[1]", "1": "2"}' in dump_table(table)


# --- golden round-trip -------------------------------------------------------


@pytest.mark.parametrize("path", GOLDEN_TABLES, ids=lambda p: p.parent.name)
def test_golden_round_trip(path: Path, tmp_path: Path) -> None:
    table = load_table(path)
    assert load_table(write(tmp_path, "again.yaml", dump_table(table))) == table


def test_golden_cases_were_found() -> None:
    assert GOLDEN_TABLES, f"no golden tables under {GOLDEN}"
