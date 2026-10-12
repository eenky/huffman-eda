"""The static rules FT001-FT004, FT008, FT009. Implements docs/SEMANTICS.md §5.

Static rules consider every entry of the table, reachable or not. One function per rule,
all of them taking a ``FlowTable`` and returning diagnostics in no particular order;
``static_rules`` concatenates them in rule order.
"""

from __future__ import annotations

from collections.abc import Iterator

from huffman_eda.diagnostics import Diagnostic
from huffman_eda.model import FlowTable
from huffman_eda.semantics import Outcome, settle

__all__ = ["ft001", "ft002", "ft003", "ft004", "ft008", "ft009", "static_rules"]

_WHITE, _GRAY, _BLACK = 0, 1, 2


def static_rules(table: FlowTable) -> list[Diagnostic]:
    """Every static diagnostic for ``table``, in rule order."""
    diagnostics: list[Diagnostic] = []
    for rule in (ft001, ft002, ft003, ft004, ft008, ft009):
        diagnostics.extend(rule(table))
    return diagnostics


def ft001(table: FlowTable) -> list[Diagnostic]:
    """Error: an entry with two or more choices is nondeterministic."""
    return [
        Diagnostic(
            "FT001",
            "error",
            state,
            column,
            message=f"{len(cell.choices)} choices at ({state},{column})",
        )
        for state in table.states()
        for column in table.columns()
        if (cell := table.cell(state, column)).is_specified and not cell.is_deterministic
    ]


def ft002(table: FlowTable) -> list[Diagnostic]:
    """Error: a cycle of length >= 2 in a column's successor function.

    Each cycle is reported once, at its lowest state. Self-holding entries are stable,
    not cycles, so a length-1 cycle is not reported.
    """
    diagnostics = []
    for column in table.columns():
        successors = {
            state: cell.next
            for state in table.states()
            if (cell := table.cell(state, column)).is_deterministic
        }
        for cycle in _cycles(successors):
            if len(cycle) >= 2:
                diagnostics.append(
                    Diagnostic(
                        "FT002",
                        "error",
                        min(cycle),
                        column,
                        message=f"oscillation in column {column!r}: cycle {cycle}",
                    )
                )
    return diagnostics


def ft003(table: FlowTable) -> list[Diagnostic]:
    """Error: an unstable entry whose settling runs into an unspecified entry."""
    diagnostics = []
    for state in table.states():
        for column in table.columns():
            cell = table.cell(state, column)
            if not cell.is_deterministic or cell.next == state:
                continue
            result = settle(table, state, column)
            if result.kind is Outcome.UNDEFINED:
                diagnostics.append(
                    Diagnostic(
                        "FT003",
                        "error",
                        state,
                        column,
                        message=f"settling runs into an unspecified entry: path {result.path}",
                        path=result.path,
                    )
                )
    return diagnostics


def ft004(table: FlowTable) -> list[Diagnostic]:
    """Warning: an unstable entry pointing at a specified, still-unstable entry."""
    diagnostics = []
    for state in table.states():
        for column in table.columns():
            cell = table.cell(state, column)
            if not cell.is_deterministic or cell.next == state:
                continue
            target = cell.next
            target_cell = table.cell(target, column)
            if target_cell.is_specified and not table.is_stable(target, column):
                diagnostics.append(
                    Diagnostic(
                        "FT004",
                        "warning",
                        state,
                        column,
                        message=(
                            f"non-normal table: ({state},{column}) -> {target}, "
                            f"and ({target},{column}) is not stable"
                        ),
                    )
                )
    return diagnostics


def ft008(table: FlowTable) -> list[Diagnostic]:
    """Warning: a state that has a row but is stable in no column."""
    columns = table.columns()
    return [
        Diagnostic(
            "FT008",
            "warning",
            state,
            None,
            message=f"state {state} has no stable entry in any column",
        )
        for state in table.states()
        if not any(table.is_stable(state, column) for column in columns)
    ]


def ft009(table: FlowTable) -> list[Diagnostic]:
    """Warning: a stable entry with an unassigned output character."""
    return [
        Diagnostic(
            "FT009",
            "warning",
            state,
            column,
            message=f"stable entry ({state},{column}) has '-' in outputs {cell.outputs!r}",
        )
        for state in table.states()
        for column in table.columns()
        if table.is_stable(state, column) and "-" in (cell := table.cell(state, column)).outputs
    ]


def _cycles(successors: dict[int, int]) -> Iterator[tuple[int, ...]]:
    """Every cycle of a partial function, once each, in linear time.

    Iterative depth-first colouring: a node reached while still on the current path
    closes a cycle; the nodes on that path then go black so no cycle is walked twice.
    """
    color: dict[int, int] = {}
    for start in sorted(successors):
        if color.get(start, _WHITE) != _WHITE:
            continue
        path: list[int] = []
        position: dict[int, int] = {}
        node: int | None = start
        while node is not None:
            seen = color.get(node, _WHITE)
            if seen == _GRAY:
                yield tuple(path[position[node] :])
                break
            if seen == _BLACK:
                break
            color[node] = _GRAY
            position[node] = len(path)
            path.append(node)
            node = successors.get(node)
        for walked in path:
            color[walked] = _BLACK
