"""Snapshot tests for the plain-text renderer (T201).

The snapshots under ``tests/snapshots/`` are the record of the §7 display format.
Regenerate them deliberately with ``UPDATE_SNAPSHOTS=1 pytest tests/test_render.py``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from rich.console import Console
from rich.table import Table as RichTable

from huffman_eda.io import load_table
from huffman_eda.model import Cell, Choice, FlowTable
from huffman_eda.render import caption, entry_text, render_rich, render_text

GOLDEN = Path(__file__).parent / "golden"
SNAPSHOTS = Path(__file__).parent / "snapshots"
CASES = sorted(p for p in GOLDEN.iterdir() if p.is_dir())


def snapshot(path: Path, produced: str) -> None:
    """Compare against the stored snapshot, or rewrite it when asked to."""
    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(produced, encoding="utf-8")
        return
    assert path.exists(), f"missing snapshot; run UPDATE_SNAPSHOTS=1 pytest {__file__}"
    assert path.read_text(encoding="utf-8") == produced


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.name)
def test_render_text_matches_snapshot(case: Path) -> None:
    snapshot(SNAPSHOTS / f"{case.name}.txt", render_text(load_table(case / "table.yaml")))


def test_render_text_is_deterministic() -> None:
    table = load_table(CASES[0] / "table.yaml")
    assert render_text(table) == render_text(table)
    assert render_text(table).endswith("\n")


def test_render_text_marks_gray_order_and_widths() -> None:
    table = load_table(GOLDEN / "incomplete_2in" / "table.yaml")
    lines = render_text(table).splitlines()
    assert lines[1].split() == ["state", "|", "00", "|", "01", "|", "11", "|", "10"]


def test_entry_text_shapes() -> None:
    table = FlowTable(
        name="t",
        inputs=("x",),
        outputs=("z",),
        reset=(1, "0"),
        rows={
            1: {"0": Cell((Choice(1, "0"),)), "1": Cell((Choice(2, "0"), Choice(3, "1")))},
        },
    )
    assert entry_text(table, 1, "0") == "[1],0"
    assert entry_text(table, 1, "1") == "2,0 | 3,1"
    assert entry_text(table, 2, "0") == "-"  # no row for state 2
    assert caption(table) == "t: inputs=[x] outputs=[z] reset=(1,0)"


def test_render_rich_bolds_stable_entries() -> None:
    table = load_table(GOLDEN / "clean_toggle" / "table.yaml")
    rendered = render_rich(table)
    assert isinstance(rendered, RichTable)
    assert rendered.row_count == 2
    assert len(rendered.columns) == 3  # state + one column per input combination

    console = Console(record=True, force_terminal=True, width=100)
    console.print(rendered)
    styled = console.export_text(styles=True)
    assert "clean_toggle" in styled  # the caption is the table title
    assert "\x1b[1m[1],0" in styled  # stable entries are bold
    assert "\x1b[1m2,-" not in styled  # transient entries are not
