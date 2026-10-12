#!/usr/bin/env python3
"""Local demo: load a flow table and see what every M1 module does with it.

    python scripts/demo.py                       # every case in tests/golden/
    python scripts/demo.py path/to/table.yaml    # one or more tables

Nothing here is part of a milestone task; it is a scratch pad for eyeballing M1 before
the `hfe` CLI (T203) exists. It walks the whole pipeline: load (T102), the grid and
stability (T101), settle (T103), explore (T104) and validate (T105/T106).
"""

from __future__ import annotations

import sys
from pathlib import Path

from huffman_eda.diagnostics import Diagnostic
from huffman_eda.explore import explore
from huffman_eda.io import ParseError, load_table
from huffman_eda.model import FlowTable
from huffman_eda.semantics import Outcome, settle
from huffman_eda.validate import validate

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests" / "golden"


def gray_columns(table: FlowTable) -> list[str]:
    """Columns in reflected Gray order, the §7 human display order."""
    width = len(table.inputs)
    return [format(k ^ (k >> 1), f"0{width}b") for k in range(1 << width)]


def cell_text(table: FlowTable, state: int, column: str) -> str:
    """The §2 shorthand for one entry; stable entries are bracketed."""
    cell = table.cell(state, column)
    if not cell.is_specified:
        return "-"
    parts = []
    for choice in cell.choices:
        target = f"[{choice.next}]" if choice.next == state else str(choice.next)
        parts.append(target if not table.outputs else f"{target},{choice.outputs}")
    return "|".join(parts)


def show(table: FlowTable) -> None:
    width = max((len(c) for c in table.columns()), default=1)
    width = max(width, 6)
    print(
        f"{table.name}: {len(table.inputs)} input(s) {list(table.inputs)}, "
        f"{len(table.outputs)} output(s) {list(table.outputs)}, reset={table.reset}"
    )
    header = "  state | " + " | ".join(c.center(width) for c in gray_columns(table))
    print(header)
    print("  " + "-" * (len(header) - 2))
    for state in table.states():
        cells = " | ".join(cell_text(table, state, c).ljust(width) for c in gray_columns(table))
        stable = sum(table.is_stable(state, c) for c in table.columns())
        print(f"  {state:>5} | {cells}   ({stable}/{len(table.columns())} stable)")
    print()

    reset_state, reset_column = table.reset
    entries = [(reset_state, reset_column)] + [
        (state, column)
        for state in table.states()
        for column in gray_columns(table)
        if (state, column) != (reset_state, reset_column)
    ]
    print(f"  settle from the reset entry ({reset_state}, {reset_column!r}) and every other:")
    for state, column in entries:
        result = settle(table, state, column)
        if result.kind is Outcome.STABLE:
            detail = f"final={result.final}"
        elif result.kind is Outcome.OSCILLATION:
            detail = f"cycle={result.cycle}"
        else:
            detail = "stopped at the unspecified/nondeterministic cell"
        print(f"    ({state}, {column!r}) -> {result.kind.name:12} path={result.path} {detail}")
    print()

    walked = explore(table)
    print(
        f"  explore: reset_ok={walked.reset_ok} stable={len(walked.stable)} "
        f"visited={len(walked.visited)} transitions={len(walked.transitions)}"
    )
    for entry in walked.stable:
        print(f"    stable {entry}")
    print()

    report = validate(table)
    counts = {
        severity: sum(d.severity == severity for d in report.diagnostics)
        for severity in ("error", "warning", "info")
    }
    print(
        f"  validate: {len(report.diagnostics)} diagnostic(s) {counts} "
        f"-> hfe exit code {1 if report.has_errors else 0}"
    )
    for diagnostic in report.diagnostics:
        print(f"    {format_diagnostic(diagnostic)}")
    print()


def format_diagnostic(diagnostic: Diagnostic) -> str:
    """One diagnostic as rule, severity, location, message."""
    where = f"({diagnostic.state},{diagnostic.column})"
    return f"{diagnostic.rule} {diagnostic.severity:7} {where:10} {diagnostic.message}"


def main(argv: list[str]) -> int:
    paths = [Path(a) for a in argv] or sorted(GOLDEN.glob("*/table.yaml"))
    for path in paths:
        print(f"=== {path.relative_to(ROOT) if ROOT in path.parents else path}")
        try:
            show(load_table(path))
        except ParseError as error:
            print(f"  ParseError: {error}\n")
            print(
                f"  reason={error.reason!r} row={error.row} "
                f"column={error.column!r} text={error.text!r}\n"
            )
    print("Display order is Gray code (§7); machine order is lexicographic.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
