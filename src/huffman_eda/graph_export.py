"""Export behaviour for inspection and diffing. Implements docs/SEMANTICS.md §4 output.

Two views of the same walk: ``to_json`` is the machine-readable one (nodes are the
stable total states, edges are the probes), and ``to_dot`` is the Graphviz one
(`s@c / outs` nodes, solid edges for settled changes, red sinks for the rest). Both are
deterministic — sorted, never dict-iteration order — so they can be snapshot-tested.
"""

from __future__ import annotations

from huffman_eda.explore import ExploreResult, Transition
from huffman_eda.model import FlowTable
from huffman_eda.semantics import Outcome

__all__ = ["to_dot", "to_json"]


def to_json(result: ExploreResult) -> dict[str, object]:
    """The walk as a JSON-ready mapping of nodes and edges."""
    return {
        "reset_ok": result.reset_ok,
        "nodes": [{"state": state, "column": column} for state, column in result.stable],
        "edges": [
            {
                "src_state": transition.src_state,
                "src_column": transition.src_col,
                "dst_column": transition.dst_col,
                "flipped": flipped_bit(transition.src_col, transition.dst_col),
                "outcome": transition.result.kind.name.lower(),
                "path": list(transition.result.path),
                "final": transition.result.final,
                "cycle": list(transition.result.cycle),
            }
            for transition in sorted(result.transitions, key=transition_key)
        ],
    }


def to_dot(table: FlowTable, result: ExploreResult) -> str:
    """The walk as Graphviz DOT.

    One node per stable total state. A probe that settles is a solid edge to the settled
    entry; a probe that fails goes to a red sink named by its outcome kind.
    """
    nodes = sorted(result.stable)
    lines = ["digraph behavior {", "  rankdir=LR;", "  node [shape=box];"]
    for state, column in nodes:
        label = f"{state}@{column}"
        if table.outputs:
            label += f" / {table.cell(state, column).outputs}"
        lines.append(f'  {node_id(state, column)} [label="{label}"];')
    for kind in sorted({t.result.kind.name for t in result.transitions} - {Outcome.STABLE.name}):
        lines.append(f'  {sink_id(kind)} [label="{kind}", shape=oval, color=red, fontcolor=red];')
    for transition in sorted(result.transitions, key=transition_key):
        source = node_id(transition.src_state, transition.src_col)
        label = table.inputs[flipped_bit(transition.src_col, transition.dst_col)]
        if transition.result.kind is Outcome.STABLE:
            target = node_id(transition.result.final, transition.dst_col)
            lines.append(f'  {source} -> {target} [label="{label}"];')
        else:
            sink = sink_id(transition.result.kind.name)
            lines.append(f'  {source} -> {sink} [label="{label}", style=dashed, color=red];')
    lines.append("}")
    return "\n".join(lines) + "\n"


def node_id(state: int, column: str) -> str:
    """A DOT-safe node name for a stable total state."""
    return f"n_{state}_{column}"


def sink_id(kind: str) -> str:
    """A DOT-safe node name for a failure sink."""
    return f"sink_{kind.lower()}"


def transition_key(transition: Transition) -> tuple[int, str, str]:
    """Sort key: source first, then the column change."""
    return (transition.src_state, transition.src_col, transition.dst_col)


def flipped_bit(before: str, after: str) -> int:
    """The index of the single bit that changed between two adjacent columns."""
    if len(before) != len(after):
        raise ValueError(f"columns {before!r} and {after!r} are not adjacent")
    differences = [index for index, (a, b) in enumerate(zip(before, after, strict=True)) if a != b]
    if len(differences) != 1:
        raise ValueError(f"columns {before!r} and {after!r} are not adjacent")
    return differences[0]
