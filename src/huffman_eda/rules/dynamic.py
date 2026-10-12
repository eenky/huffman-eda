"""The dynamic rules FT000, FT005-FT007. Implements docs/SEMANTICS.md §5.

Dynamic rules come from ``explore``: they can only be seen by driving the table the way
the environment does. FT000 is exclusive — when the reset is unusable nothing is
reachable, so it is the only diagnostic reported.
"""

from __future__ import annotations

from itertools import pairwise

from huffman_eda.diagnostics import Diagnostic
from huffman_eda.explore import ExploreResult
from huffman_eda.model import FlowTable
from huffman_eda.semantics import Outcome

__all__ = ["dynamic_rules"]


def dynamic_rules(table: FlowTable, result: ExploreResult) -> list[Diagnostic]:
    """Every dynamic diagnostic, in rule order."""
    if not result.reset_ok:
        reset_state, reset_column = table.reset
        reason = "is missing" if reset_state not in table.rows else "is not stable"
        return [
            Diagnostic(
                "FT000",
                "error",
                reset_state,
                reset_column,
                message=f"reset entry ({reset_state},{reset_column}) {reason}",
            )
        ]
    diagnostics: list[Diagnostic] = []
    for rule in (_ft005, _ft006, _ft007):
        diagnostics.extend(rule(table, result))
    return diagnostics


def _ft005(table: FlowTable, result: ExploreResult) -> list[Diagnostic]:
    """Error: an input change the environment may apply lands on an unspecified entry."""
    return [
        Diagnostic(
            "FT005",
            "error",
            transition.src_state,
            transition.dst_col,
            message=(
                f"input change to column {transition.dst_col!r} is unspecified in state "
                f"{transition.src_state}"
            ),
        )
        for transition in result.transitions
        if transition.result.kind is Outcome.UNDEFINED
        and transition.result.path == (transition.src_state,)
    ]


def _ft006(table: FlowTable, result: ExploreResult) -> list[Diagnostic]:
    """Info: a specified entry the walk never reaches."""
    visited = set(result.visited)
    return [
        Diagnostic(
            "FT006",
            "info",
            state,
            column,
            message=f"specified entry ({state},{column}) is not reachable from the reset",
        )
        for state in table.states()
        for column in table.columns()
        if table.cell(state, column).is_specified and (state, column) not in visited
    ]


def _ft007(table: FlowTable, result: ExploreResult) -> list[Diagnostic]:
    """Error: an output that changes value more than once while settling."""
    diagnostics = []
    for transition in result.transitions:
        if transition.result.kind is not Outcome.STABLE:
            continue
        entries = [(transition.src_state, transition.src_col)]
        entries.extend((state, transition.dst_col) for state in transition.result.path)
        for index, name in enumerate(table.outputs):
            sequence = [table.cell(state, column).outputs[index] for state, column in entries]
            values = [value for value in sequence if value != "-"]
            if _changes(values) > 1:
                diagnostics.append(
                    Diagnostic(
                        "FT007",
                        "error",
                        transition.src_state,
                        transition.dst_col,
                        message=(
                            f"output {name!r} is non-monotonic over the change from column "
                            f"{transition.src_col!r} to {transition.dst_col!r}: "
                            f"{''.join(sequence)}"
                        ),
                    )
                )
    return diagnostics


def _changes(values: list[str]) -> int:
    """How often the value changes between neighbours, ignoring unassigned outputs."""
    return sum(1 for before, after in pairwise(values) if before != after)
