"""Human-readable flow-table display. Implements docs/SEMANTICS.md §7.

Display only: columns run in Gray order, rows in increasing state order, and a stable
entry shows its bracketed self-target. Everything machine-readable comes from
``io.dump_table``, whose columns are lexicographic.
"""

from __future__ import annotations

from rich.table import Table as RichTable
from rich.text import Text

from huffman_eda.gray import gray_columns
from huffman_eda.model import FlowTable

__all__ = ["entry_text", "render_rich", "render_text"]

_CHOICE_SEPARATOR = " | "


def entry_text(table: FlowTable, state: int, column: str) -> str:
    """One entry in the §2 shorthand: ``-``, ``s,outs``, ``[s],outs`` or choices."""
    cell = table.cell(state, column)
    if not cell.is_specified:
        return "-"
    parts = []
    for choice in cell.choices:
        target = f"[{choice.next}]" if choice.next == state else str(choice.next)
        parts.append(target if not table.outputs else f"{target},{choice.outputs}")
    return _CHOICE_SEPARATOR.join(parts)


def caption(table: FlowTable) -> str:
    """One line naming the table and its interface."""
    reset_state, reset_column = table.reset
    return (
        f"{table.name}: inputs=[{', '.join(table.inputs)}] "
        f"outputs=[{', '.join(table.outputs)}] reset=({reset_state},{reset_column})"
    )


def render_text(table: FlowTable) -> str:
    """The plain-text grid, ending in a newline. Deterministic, so it snapshots."""
    columns = gray_columns(len(table.inputs))
    states = table.states()
    grid = [[entry_text(table, state, column) for column in columns] for state in states]
    widths = [
        max([len(column), *(len(row[index]) for row in grid)])
        for index, column in enumerate(columns)
    ]
    state_width = max([len("state"), *(len(str(state)) for state in states)])

    def row(label: str, cells: list[str], *, center: bool = False) -> str:
        if center:
            padded = [cell.center(widths[index]) for index, cell in enumerate(cells)]
        else:
            padded = [cell.ljust(widths[index]) for index, cell in enumerate(cells)]
        return f"  {label:>{state_width}} | " + " | ".join(padded)

    lines = [caption(table)]
    lines.append(row("state", columns, center=True))
    lines.append("  " + "-" * (len(lines[-1]) - 2))
    for state, cells in zip(states, grid, strict=True):
        lines.append(row(str(state), cells))
    return "\n".join(lines) + "\n"


def render_rich(table: FlowTable) -> RichTable:
    """The same grid as a rich table: stable entries in bold, unspecified as ``-``."""
    columns = gray_columns(len(table.inputs))
    rich_table = RichTable(title=caption(table), box=None, pad_edge=False)
    rich_table.add_column("state", justify="right")
    for column in columns:
        rich_table.add_column(column)
    for state in table.states():
        rich_table.add_row(
            str(state),
            *[
                Text(
                    entry_text(table, state, column),
                    style="bold" if table.is_stable(state, column) else "",
                )
                for column in columns
            ],
        )
    return rich_table
