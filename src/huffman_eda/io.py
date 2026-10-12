"""File format and cell grammar. Implements docs/SEMANTICS.md §2."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from huffman_eda.gray import gray_columns
from huffman_eda.model import Cell, Choice, FlowTable, ModelError
from huffman_eda.render import entry_text

__all__ = [
    "ParseError",
    "dump_markdown",
    "dump_table",
    "load_markdown",
    "load_table",
    "parse_cell",
    "parse_markdown",
]

_OUTS_RE = re.compile(r"^[01-]+$")
_INT_RE = re.compile(r"^\d+$")
_YAML_SUFFIXES = (".yaml", ".yml")
_FRONT_MATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n?(.*)\Z", re.DOTALL)
_SEPARATOR_RE = re.compile(r"^:?-+:?$")


class ParseError(ValueError):
    """A malformed table file or cell. Carries the row, column and offending text."""

    def __init__(
        self,
        reason: str,
        *,
        row: int | None = None,
        column: str | None = None,
        text: str | None = None,
    ) -> None:
        self.reason = reason
        self.row = row
        self.column = column
        self.text = text
        where = []
        if row is not None:
            where.append(f"row {row}")
        if column is not None:
            where.append(f"column {column!r}")
        if text is not None:
            where.append(f"text {text!r}")
        location = f" ({', '.join(where)})" if where else ""
        super().__init__(f"{reason}{location}")


def parse_cell(text: str, row: int, m: int, column: str | None = None) -> Cell:
    """Parse one cell of the §2 grammar into a ``Cell``.

    ``row`` is the row's state (for the bracket check) and ``m`` the number of
    outputs. ``column`` is only used to label errors.
    """
    if text.strip() == "-":
        return Cell()
    parts = [part.strip() for part in text.split("|")]
    if len(parts) > 1 and "-" in parts:
        raise ParseError(
            "'-' is only valid as a whole cell, not as a choice", row=row, column=column, text=text
        )
    choices = []
    for part in parts:
        if not part:
            raise ParseError(
                "empty choice: every '|' must join two choices", row=row, column=column, text=text
            )
        choices.append(_parse_choice(part, row, m, column, text))
    return Cell(tuple(choices))


def _parse_choice(part: str, row: int, m: int, column: str | None, text: str) -> Choice:
    """Parse one ``target (',' outs)?`` choice."""
    target_text, comma, outs_text = part.partition(",")
    target_text = target_text.strip()
    outs = outs_text.strip()

    if target_text.startswith("[") != target_text.endswith("]"):
        raise ParseError(
            f"unbalanced brackets in next state {target_text!r}", row=row, column=column, text=text
        )
    bracketed = target_text.startswith("[")
    digits = target_text[1:-1].strip() if bracketed else target_text
    if not _INT_RE.match(digits):
        raise ParseError(
            f"next state must be an integer, got {target_text!r}", row=row, column=column, text=text
        )
    target = int(digits)
    if bracketed and target != row:
        raise ParseError(
            f"bracketed next state [{target}] must equal the row {row}",
            row=row,
            column=column,
            text=text,
        )

    if comma:
        if m == 0:
            raise ParseError(
                "outputs are forbidden when the table has no outputs",
                row=row,
                column=column,
                text=text,
            )
        if len(outs) != m or not _OUTS_RE.match(outs):
            raise ParseError(
                f"outputs must be exactly {m} characters over {{0,1,-}}, got {outs!r}",
                row=row,
                column=column,
                text=text,
            )
    elif m > 0:
        raise ParseError(
            f"outputs are required: expected {m} characters after ','",
            row=row,
            column=column,
            text=text,
        )
    return Choice(target, outs if comma else "")


def load_table(path: Path) -> FlowTable:
    """Load a table from YAML or JSON, chosen by file suffix."""
    path = Path(path)
    suffix = path.suffix.lower()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ParseError(f"cannot read {path}: {exc}") from exc

    if suffix == ".json":
        try:
            document: Any = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ParseError(f"invalid JSON: {exc.msg}") from exc
    elif suffix in _YAML_SUFFIXES:
        try:
            document = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ParseError(f"invalid YAML: {exc}") from exc
    else:
        raise ParseError(f"unsupported table suffix {suffix!r}: expected .yaml, .yml or .json")
    return table_from_dict(document)


def table_from_dict(document: Any) -> FlowTable:
    """Build a ``FlowTable`` from an already-parsed §2 document."""
    if not isinstance(document, dict):
        raise ParseError("a table must be a mapping")
    name = document.get("name", "")
    if not isinstance(name, str):
        raise ParseError(f"name must be a string, got {name!r}")
    inputs = _names(document.get("inputs"), "inputs")
    outputs = _names(document.get("outputs"), "outputs")

    reset = document.get("reset")
    if not isinstance(reset, (list, tuple)) or len(reset) != 2:
        raise ParseError(f"reset must be [state, column], got {reset!r}")
    reset_state = _state(reset[0], "reset state")
    reset_column = reset[1]
    if not isinstance(reset_column, str):
        raise ParseError(
            f"reset column must be a quoted string, got {reset_column!r}", text=str(reset_column)
        )

    rows: dict[int, dict[str, Cell]] = {}
    raw_rows = document.get("rows") or {}
    if not isinstance(raw_rows, dict):
        raise ParseError(f"rows must be a mapping, got {raw_rows!r}")
    for raw_state, raw_row in raw_rows.items():
        state = _state(raw_state, "row key")
        if not isinstance(raw_row, dict):
            raise ParseError(f"the row of state {state} must be a mapping, got {raw_row!r}")
        row: dict[str, Cell] = {}
        for raw_column, raw_cell in raw_row.items():
            if not isinstance(raw_column, str):
                raise ParseError(
                    "column keys must be quoted strings (an unquoted 01 is the integer 1 in YAML)",
                    row=state,
                    text=str(raw_column),
                )
            if not isinstance(raw_cell, str):
                raise ParseError(
                    f"the cell text must be a string, got {raw_cell!r}",
                    row=state,
                    column=raw_column,
                )
            row[raw_column] = parse_cell(raw_cell, state, len(outputs), raw_column)
        rows[state] = row

    try:
        return FlowTable(
            name=name,
            inputs=inputs,
            outputs=outputs,
            reset=(reset_state, reset_column),
            rows=rows,
        )
    except ModelError as exc:
        # Everything the IR rejects is a malformed file, not a caller error.
        raise ParseError(str(exc)) from exc


def dump_table(table: FlowTable) -> str:
    """Render a table as YAML in the §2 format.

    Every column is written, in lexicographic order, always quoted; a stable choice is
    bracketed, and an unspecified cell is ``"-"``. Reloading the output is lossless.
    """
    m = len(table.outputs)
    lines = [
        f"name: {table.name}",
        f"inputs: [{', '.join(table.inputs)}]",
        f"outputs: [{', '.join(table.outputs)}]",
        f'reset: [{table.reset[0]}, "{table.reset[1]}"]',
        "rows:",
    ]
    for state in table.states():
        cells = ", ".join(
            f'"{column}": "{_format_cell(table.cell(state, column), state, m)}"'
            for column in table.columns()
        )
        lines.append(f"  {state}: {{{cells}}}")
    return "\n".join(lines) + "\n"


def _format_cell(cell: Cell, state: int, m: int) -> str:
    if not cell.is_specified:
        return "-"
    return "|".join(_format_choice(choice, state, m) for choice in cell.choices)


def _format_choice(choice: Choice, state: int, m: int) -> str:
    target = f"[{choice.next}]" if choice.next == state else str(choice.next)
    return target if m == 0 else f"{target},{choice.outputs}"


def _names(value: Any, what: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(name, str) for name in value):
        raise ParseError(f"{what} must be a list of strings, got {value!r}")
    return tuple(value)


def _state(value: Any, what: str) -> int:
    """A state is an integer, or a string of decimal digits in JSON."""
    if isinstance(value, bool):
        raise ParseError(f"{what} must be an integer, got {value!r}")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and _INT_RE.match(value):
        return int(value)
    raise ParseError(f"{what} must be an integer, got {value!r}")


# --- Markdown transcription format (T204) -------------------------------------


def load_markdown(path: Path) -> FlowTable:
    """Load a table from a Markdown file with YAML front matter."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ParseError(f"cannot read {path}: {exc}") from exc
    return parse_markdown(text)


def parse_markdown(text: str) -> FlowTable:
    """Parse the transcription format: YAML front matter plus one Markdown table.

    The header names the columns in whatever order the transcription used, cells are
    written in the §2 grammar with any ``|`` inside a cell escaped as ``\\|``.
    """
    front, body = _split_front_matter(text)
    try:
        document: Any = yaml.safe_load(front)
    except yaml.YAMLError as exc:
        raise ParseError(f"invalid front matter: {exc}") from exc
    if not isinstance(document, dict):
        raise ParseError("the front matter must be a mapping of name, inputs, outputs, reset")

    lines = [line for line in body.splitlines() if line.strip()]
    if len(lines) < 3:
        raise ParseError(
            "expected a Markdown table: a header, a separator row and at least one row"
        )
    header = _split_row(lines[0])
    if header[0].strip().lower() != "state":
        raise ParseError(f"the first header cell must be 'state', got {header[0]!r}")
    columns = header[1:]
    if not all(_SEPARATOR_RE.match(cell) for cell in _split_row(lines[1])):
        raise ParseError(f"expected a '|---|' separator row, got {lines[1]!r}")

    rows: dict[int, dict[str, str]] = {}
    for line in lines[2:]:
        cells = _split_row(line)
        if len(cells) != len(header):
            raise ParseError(
                f"expected {len(header)} cells, got {len(cells)}: is a '|' missing its "
                f"escape as '\\|'?",
                text=line,
            )
        rows[_state(cells[0], "row key")] = dict(zip(columns, cells[1:], strict=True))
    # table_from_dict parses every cell and validates columns, so a bad cell or a bad
    # header column fails the same way it would in YAML.
    return table_from_dict({**document, "rows": rows})


def dump_markdown(table: FlowTable) -> str:
    """Render a table as front matter plus a Markdown table.

    Columns are written in Gray order, which is how the book's tables are transcribed;
    a pipe inside a cell is escaped so the table stays parseable. Reloading the output
    with :func:`parse_markdown` is lossless.
    """
    lines = [
        "---",
        f"name: {table.name}",
        f"inputs: [{', '.join(table.inputs)}]",
        f"outputs: [{', '.join(table.outputs)}]",
        f'reset: [{table.reset[0]}, "{table.reset[1]}"]',
        "---",
        "",
    ]
    columns = gray_columns(len(table.inputs))
    lines.append("| state | " + " | ".join(columns) + " |")
    lines.append("|" + "---|" * (len(columns) + 1))
    for state in table.states():
        cells = [_escape_cell(entry_text(table, state, column)) for column in columns]
        lines.append(f"| {state} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def _split_front_matter(text: str) -> tuple[str, str]:
    match = _FRONT_MATTER_RE.match(text)
    if match is None:
        raise ParseError("expected YAML front matter delimited by '---' lines")
    return match.group(1), match.group(2)


def _split_row(line: str) -> list[str]:
    """Split a Markdown table row on unescaped pipes, then unescape ``\\|``."""
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|") and not text.endswith("\\|"):
        text = text[:-1]
    return [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", text)]


def _escape_cell(text: str) -> str:
    """Escape a cell for a Markdown table: the §2 choice separator becomes ``\\|``."""
    return text.replace("|", "\\|")
