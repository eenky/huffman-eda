"""The implementation relation. Implements docs/SEMANTICS.md §8.

``implements(spec, impl)`` walks the product of the two tables from their resets and
returns the first failure in §8.4's fixed order, so the counterexample it reports is the
shortest one and is unique. Three properties follow from the definition and are checked in
``tests/test_equiv.py``: ``implements(T, T)`` always holds, the relation is not symmetric
(``equivalent`` is), and renaming states changes nothing.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

from huffman_eda.model import FlowTable
from huffman_eda.semantics import Outcome, SettleResult, settle

__all__ = [
    "HAZARD",
    "IMPL_NOT_STABLE",
    "OUTPUT_MISMATCH",
    "RESET",
    "Counterexample",
    "EquivResult",
    "equivalent",
    "implements",
]

RESET = "RESET"
IMPL_NOT_STABLE = "IMPL_NOT_STABLE"
OUTPUT_MISMATCH = "OUTPUT_MISMATCH"
HAZARD = "HAZARD"

Entry = tuple[int, str]
Pair = tuple[Entry, Entry]


@dataclass(frozen=True)
class Counterexample:
    """Why the relation failed, and the shortest trace that shows it (SEMANTICS §8.5)."""

    trace: tuple[str, ...]
    kind: str
    output: str | None = None
    outcome: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """The §8.5 JSON shape, as the golden pairs spell it."""
        return {
            "trace": list(self.trace),
            "kind": self.kind,
            "output": self.output,
            "outcome": self.outcome,
        }


@dataclass(frozen=True)
class EquivResult:
    """An ``implements`` verdict: ``ok``, and the counterexample when it is false."""

    ok: bool
    counterexample: Counterexample | None = None


def equivalent(a: FlowTable, b: FlowTable) -> bool:
    """True when each table implements the other (SEMANTICS §8.4)."""
    return implements(a, b).ok and implements(b, a).ok


def implements(spec: FlowTable, impl: FlowTable) -> EquivResult:
    """Decide whether ``impl`` implements ``spec`` under SIC fundamental mode.

    Implements SEMANTICS §8: identical inputs and outputs are required (``ValueError``
    otherwise), the reset pair is checked first, and then the product of stable total
    states is explored breadth-first with the input bits tried in increasing order.
    """
    if spec.inputs != impl.inputs or spec.outputs != impl.outputs:
        raise ValueError(
            "implements needs identical inputs and outputs: "
            f"spec has {list(spec.inputs)} / {list(spec.outputs)}, "
            f"impl has {list(impl.inputs)} / {list(impl.outputs)}"
        )
    if not _reset_is_usable(spec):
        return EquivResult(True, None)  # §8.4: the spec has no behaviour to implement

    start = _reset_pair(spec, impl)
    if isinstance(start, Counterexample):
        return EquivResult(False, start)
    return _explore_product(spec, impl, start)


def _reset_is_usable(spec: FlowTable) -> bool:
    """True when ``explore(spec)`` would start: the reset row exists and is stable."""
    state, column = spec.reset
    return state in spec.rows and spec.is_stable(state, column)


def _reset_pair(spec: FlowTable, impl: FlowTable) -> Pair | Counterexample:
    """§8.4's reset check: returns the starting pair, or the failure."""
    spec_state, spec_column = spec.reset
    impl_state, impl_column = impl.reset
    if impl_column != spec_column or impl_state not in impl.rows:
        return Counterexample((), RESET, None, None)
    if not impl.is_stable(impl_state, impl_column):
        return Counterexample((), RESET, None, None)
    offenders = _incompatible(
        spec.cell(spec_state, spec_column).outputs, impl.cell(impl_state, impl_column).outputs
    )
    if offenders:
        return Counterexample((), RESET, spec.outputs[offenders[0]], None)
    return ((spec_state, spec_column), (impl_state, impl_column))


def _explore_product(spec: FlowTable, impl: FlowTable, start: Pair) -> EquivResult:
    """§8.4's product exploration: breadth-first, first failure wins."""
    queue: deque[Pair] = deque([start])
    traces: dict[Pair, tuple[str, ...]] = {start: ()}

    while queue:
        (spec_state, column), (impl_state, _) = pair = queue.popleft()
        trace = traces[pair]
        for index in range(len(spec.inputs)):
            dst = column[:index] + ("0" if column[index] == "1" else "1") + column[index + 1 :]
            next_trace = (*trace, dst)
            spec_result = settle(spec, spec_state, dst)
            if spec_result.kind is not Outcome.STABLE:
                continue  # §8.4: the step is unconstrained
            impl_result = settle(impl, impl_state, dst)

            if impl_result.kind is not Outcome.STABLE:
                return EquivResult(
                    False,
                    Counterexample(next_trace, IMPL_NOT_STABLE, None, impl_result.kind.name),
                )
            offenders = _incompatible(
                spec.cell(spec_result.final, dst).outputs,
                impl.cell(impl_result.final, dst).outputs,
            )
            if offenders:
                return EquivResult(
                    False,
                    Counterexample(next_trace, OUTPUT_MISMATCH, spec.outputs[offenders[0]], None),
                )
            hazard = _introduced_hazard(
                spec, impl, (spec_state, impl_state, column, dst), spec_result, impl_result
            )
            if hazard is not None:
                return EquivResult(
                    False, Counterexample(next_trace, HAZARD, spec.outputs[hazard], None)
                )

            settled = ((spec_result.final, dst), (impl_result.final, dst))
            if settled not in traces:
                traces[settled] = next_trace
                queue.append(settled)

    return EquivResult(True, None)


def _introduced_hazard(
    spec: FlowTable,
    impl: FlowTable,
    step: tuple[int, int, str, str],
    spec_result: SettleResult,
    impl_result: SettleResult,
) -> int | None:
    """§8.4 check 3: the lowest output that impl hazards and spec does not, if any."""
    spec_state, impl_state, column, dst = step
    for index in range(len(spec.outputs)):
        introduced = _hazardous(impl, impl_state, column, dst, impl_result.path, index)
        inherited = _hazardous(spec, spec_state, column, dst, spec_result.path, index)
        if introduced and not inherited:
            return index
    return None


def _hazardous(
    table: FlowTable,
    src_state: int,
    src_column: str,
    dst_column: str,
    path: tuple[int, ...],
    index: int,
) -> bool:
    """True when output ``index`` changes value more than once over this settling.

    The same per-output test as §5's FT007: the sequence is the output in the source
    column, then in the destination column for every state the settling visited, ignoring
    unassigned characters.
    """
    sequence = [table.cell(src_state, src_column).outputs[index]]
    sequence.extend(table.cell(state, dst_column).outputs[index] for state in path)
    values = [value for value in sequence if value != "-"]
    return sum(1 for before, after in pairwise(values) if before != after) > 1


def _incompatible(spec_outputs: str, impl_outputs: str) -> list[int]:
    """§8.2: indices where impl contradicts a specified spec bit (``-`` in impl counts)."""
    return [
        index
        for index, (spec_bit, impl_bit) in enumerate(zip(spec_outputs, impl_outputs, strict=True))
        if spec_bit != "-" and impl_bit != spec_bit
    ]
