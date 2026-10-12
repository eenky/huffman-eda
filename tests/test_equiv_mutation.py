"""Mutation tests for the oracle and `hfe equiv` (T303).

The oracle checks the later passes, so it has to be shown to catch real bugs first. Two
operators are applied to random complete, normal tables:

``output_flip``
    one specified output bit of a reachable stable entry is flipped (the reset entry is
    included, since it is a reachable stable entry). SEMANTICS §8.7 allows no unobservable
    exemption for this operator: every such mutant must be killed.
``redirect``
    one reachable unstable entry is sent to a *different* stable state in the same column.
    A redirect can be genuinely invisible (the new target may settle to the same state with
    the same outputs), so a survivor must be justified — and §8.7 requires that
    justification to be an independent bounded trace enumeration, never `equiv.py` itself.
    `_observable_difference` below is that enumeration: it walks traces of columns and
    compares §8.2's observables with its own code.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

import hypothesis.strategies as st
from hypothesis import HealthCheck, given, settings
from strategies import flow_tables
from typer.testing import CliRunner

from huffman_eda.cli import app
from huffman_eda.equiv import implements
from huffman_eda.explore import explore
from huffman_eda.io import dump_table, parse_cell
from huffman_eda.model import Cell, Choice, FlowTable
from huffman_eda.semantics import Outcome, settle

SLOW = settings(
    # Five batches of BATCH tables is the 300 the task asks for, in chunks Hypothesis can
    # generate: a single 300-table draw is rejected as too large to produce.
    max_examples=5,
    deadline=None,
    database=None,
    suppress_health_check=[
        HealthCheck.too_slow,
        HealthCheck.filter_too_much,
        HealthCheck.large_base_example,
    ],
)

RUNNER = CliRunner()
N_INPUTS, N_OUTPUTS, MAX_STATES = 2, 2, 5
BATCH = 60
COMPLETE_NORMAL = flow_tables(N_INPUTS, N_OUTPUTS, MAX_STATES, normal=True, complete=True)


def build(
    rows: dict[int, dict[str, str]],
    *,
    reset: tuple[int, str] = (1, "0"),
    inputs: tuple[str, ...] = ("x",),
    outputs: tuple[str, ...] = ("z",),
    name: str = "t",
) -> FlowTable:
    """Build a table from §2 cell strings, so the CLI fixtures read like the YAML files."""
    return FlowTable(
        name=name,
        inputs=inputs,
        outputs=outputs,
        reset=reset,
        rows={
            state: {
                column: parse_cell(text, state, len(outputs), column)
                for column, text in row.items()
            }
            for state, row in rows.items()
        },
    )


@dataclass(frozen=True)
class Mutant:
    """One mutated copy of a table, plus what was changed."""

    table: FlowTable
    operator: str
    entry: tuple[int, str]
    detail: str


def mutants(table: FlowTable) -> Iterator[Mutant]:
    """Every mutant of ``table`` under the two operators; the reset entry included."""
    reachable = explore(table)
    for state, column in reachable.stable:
        cell = table.cell(state, column)
        for index, bit in enumerate(cell.outputs):
            if bit == "-":
                continue  # only specified bits are flipped
            flipped = (
                cell.outputs[:index] + ("0" if bit == "1" else "1") + cell.outputs[index + 1 :]
            )
            yield Mutant(
                _with_cell(table, state, column, Cell((Choice(state, flipped),))),
                "output_flip",
                (state, column),
                f"{table.outputs[index]} {bit}->{flipped[index]}",
            )
    for state, column in reachable.visited:
        cell = table.cell(state, column)
        if not cell.is_deterministic or cell.next == state:
            continue
        for target in sorted(
            other
            for other in table.states()
            if other != cell.next and table.is_stable(other, column)
        ):
            yield Mutant(
                _with_cell(table, state, column, Cell((Choice(target, cell.outputs),))),
                "redirect",
                (state, column),
                f"{cell.next} -> {target}",
            )


def _with_cell(table: FlowTable, state: int, column: str, cell: Cell) -> FlowTable:
    rows = {other: dict(row) for other, row in table.rows.items()}
    rows[state][column] = cell
    return FlowTable(
        name=f"{table.name}_mutant",
        inputs=table.inputs,
        outputs=table.outputs,
        reset=table.reset,
        rows=rows,
    )


# --- the kill rate -----------------------------------------------------------


@SLOW
@given(tables=st.lists(COMPLETE_NORMAL, min_size=BATCH, max_size=BATCH))
def test_mutation_kill_rate(tables: list[FlowTable]) -> None:
    """At least a 95% kill rate, and no survivor that the enumeration can see.

    Five batches of 60 tables is the 300 the task asks for. The rate is asserted per batch
    rather than pooled: with the operators below the measured rate is ~99% (every output
    flip, and 94% of the redirects, over 300 tables), so a batch of 60 is not near the
    threshold by luck.
    """
    killed = 0
    total = 0
    for table in tables:
        for mutant in mutants(table):
            total += 1
            if implements(table, mutant.table).ok is False:
                killed += 1
                continue
            assert mutant.operator == "redirect", (
                f"an output-flip mutant survived at {mutant.entry} ({mutant.detail}): §8.7 gives "
                f"this operator no unobservable exemption"
            )
            _justify(table, mutant)

    assert total > 0
    assert killed / total >= 0.95, f"kill rate {killed}/{total} is below 95%"


# --- justifying a survivor, independently of equiv.py -----------------------


def _look_alike(spec_outputs: str, impl_outputs: str) -> bool:
    """§8.2: every bit spec specifies must match; impl may not answer `-` for a 0 or 1."""
    return all(
        spec_bit == "-" or impl_bit == spec_bit
        for spec_bit, impl_bit in zip(spec_outputs, impl_outputs, strict=True)
    )


def _hazarded(
    table: FlowTable, state: int, column: str, dst: str, path: tuple[int, ...], out: int
) -> bool:
    """§5's FT007 sequence test, re-derived here so the check owes nothing to equiv.py."""
    values = [
        table.cell(source, col).outputs[out]
        for source, col in ((state, column), *((entry, dst) for entry in path))
    ]
    values = [value for value in values if value != "-"]
    return sum(1 for before, after in pairwise(values) if before != after) > 1


def _columns(table: FlowTable, depth: int) -> list[tuple[str, ...]]:
    """Every column sequence of at most ``depth`` single-bit changes from the reset."""
    _, reset_column = table.reset
    traces: list[tuple[str, ...]] = [()]
    frontier: list[tuple[str, ...]] = [()]
    for _ in range(depth):
        following: list[tuple[str, ...]] = []
        for trace in frontier:
            column = trace[-1] if trace else reset_column
            for index in range(len(table.inputs)):
                child = (
                    *trace,
                    column[:index] + ("0" if column[index] == "1" else "1") + column[index + 1 :],
                )
                traces.append(child)
                following.append(child)
        frontier = following
    return traces


def _observable_difference(spec: FlowTable, impl: FlowTable, depth: int) -> tuple[str, ...] | None:
    """The first enumerated trace whose observable run differs, or ``None`` (SEMANTICS §8).

    Bounded trace enumeration, §8.7's prescribed justification: each trace is simulated in
    both tables with `settle` and the observables are compared — the output vector at each
    stable total state reached (8.2) and whether a settling introduces a hazard the spec
    does not have (8.4 check 3).
    """
    for trace in _columns(spec, depth):
        spec_state, spec_column = spec.reset
        impl_state, impl_column = impl.reset
        if not _look_alike(
            spec.cell(spec_state, spec_column).outputs, impl.cell(impl_state, impl_column).outputs
        ):
            return trace
        for dst in trace:
            spec_result = settle(spec, spec_state, dst)
            impl_result = settle(impl, impl_state, dst)
            if spec_result.kind is not Outcome.STABLE:
                continue  # unconstrained step
            if impl_result.kind is not Outcome.STABLE:
                return trace
            if not _look_alike(
                spec.cell(spec_result.final, dst).outputs, impl.cell(impl_result.final, dst).outputs
            ):
                return trace
            for out in range(len(spec.outputs)):
                if _hazarded(
                    impl, impl_state, spec_column, dst, impl_result.path, out
                ) and not _hazarded(spec, spec_state, spec_column, dst, spec_result.path, out):
                    return trace
            spec_state, impl_state, spec_column = spec_result.final, impl_result.final, dst
    return None


def _justify(table: FlowTable, mutant: Mutant) -> None:
    """Assert a survivor really is unobservable, with the independent enumeration."""
    depth = 2 * len(table.states())  # §8.7's bound
    traces = _columns(table, depth)
    assert len(traces) > 1, "the enumeration reached nothing"
    assert _observable_difference(table, mutant.table, depth) is None, (
        f"surviving mutant at {mutant.entry} ({mutant.detail}) is observable within "
        f"depth {depth}, so the oracle should have killed it"
    )


# A table where the unstable entry (2,"0") reaches the stable (3,"0") through a via state 4,
# so redirecting it straight to 3 is invisible, and redirecting it to the stable 1 is not.
VIA = {
    1: {"0": "[1],0", "1": "2,-"},
    2: {"0": "4,-", "1": "[2],-"},
    3: {"0": "[3],0", "1": "[3],0"},
    4: {"0": "3,-", "1": "[4],-"},
}


def test_an_invisible_redirect_survives_and_is_justified() -> None:
    table = build(VIA)
    mutant = Mutant(
        _with_cell(table, 2, "0", Cell((Choice(3, "-"),))), "redirect", (2, "0"), "4 -> 3"
    )
    assert mutant in list(mutants(table)), "the operator should offer this redirect"
    assert implements(table, mutant.table).ok is True, "the mutant is invisible"
    _justify(table, mutant)


def test_the_justification_detects_an_observable_redirect() -> None:
    """Control: an observable redirect is found by the enumeration, so `_justify` can fail."""
    table = build(VIA)
    observable = Mutant(
        _with_cell(table, 2, "0", Cell((Choice(1, "-"),))), "redirect", (2, "0"), "4 -> 1"
    )
    assert implements(table, observable.table).ok is False, "the oracle kills it"
    depth = 2 * len(table.states())
    assert _observable_difference(table, observable.table, depth) is not None


# --- hfe equiv ---------------------------------------------------------------


def _write(tmp_path: Path, name: str, table: FlowTable) -> Path:
    path = tmp_path / name
    path.write_text(dump_table(table), encoding="utf-8")
    return path


TOGGLE = {1: {"0": "[1],0", "1": "2,-"}, 2: {"0": "1,-", "1": "[2],1"}}
GLITCH = {1: {"0": "[1],0", "1": "3,1"}, 2: {"0": "1,-", "1": "[2],1"}, 3: {"0": "1,-", "1": "2,0"}}


def test_equiv_reports_a_holding_relation(tmp_path: Path) -> None:
    spec = _write(tmp_path, "a.yaml", build(TOGGLE))
    impl = _write(tmp_path, "b.yaml", build(TOGGLE))
    result = RUNNER.invoke(app, ["equiv", str(spec), str(impl)])
    assert result.exit_code == 0, result.output
    assert "holds" in result.output
    assert "equivalent: yes" in result.output


def test_equiv_prints_the_counterexample_and_exits_one(tmp_path: Path) -> None:
    spec = _write(tmp_path, "a.yaml", build(TOGGLE))
    impl = _write(tmp_path, "b.yaml", build(GLITCH))
    result = RUNNER.invoke(app, ["equiv", str(spec), str(impl)])
    assert result.exit_code == 1, result.output
    assert "fails" in result.output
    assert "trace: 1" in result.output
    assert "kind:  HAZARD" in result.output
    assert "output: z" in result.output


def test_equiv_reports_the_error_kinds(tmp_path: Path) -> None:
    spec = _write(tmp_path, "a.yaml", build(TOGGLE))
    oscillating = _write(
        tmp_path,
        "b.yaml",
        build({1: {"0": "[1],0", "1": "2,0"}, 2: {"0": "1,0", "1": "1,0"}}),
    )
    result = RUNNER.invoke(app, ["equiv", str(spec), str(oscillating)])
    assert result.exit_code == 1
    assert "kind:  IMPL_NOT_STABLE" in result.output
    assert "outcome: OSCILLATION" in result.output


def test_equiv_reports_a_reset_counterexample(tmp_path: Path) -> None:
    spec = _write(tmp_path, "a.yaml", build(TOGGLE))
    impl = _write(tmp_path, "b.yaml", build(TOGGLE, reset=(1, "1")))
    result = RUNNER.invoke(app, ["equiv", str(spec), str(impl)])
    assert result.exit_code == 1
    assert "kind:  RESET" in result.output
    assert "<empty> (the reset itself)" in result.output


def test_equiv_exits_two_on_mismatched_io(tmp_path: Path) -> None:
    spec = _write(tmp_path, "a.yaml", build(TOGGLE))
    impl = _write(tmp_path, "b.yaml", build(TOGGLE, inputs=("y",)))
    result = RUNNER.invoke(app, ["equiv", str(spec), str(impl)])
    assert result.exit_code == 2
    assert "identical inputs and outputs" in result.output


def test_equiv_exits_two_on_a_parse_error(tmp_path: Path) -> None:
    spec = _write(tmp_path, "a.yaml", build(TOGGLE))
    broken = tmp_path / "broken.yaml"
    broken.write_text(
        "name: t\ninputs: [x]\noutputs: [z]\nreset: [1, 0]\nrows: {}\n", encoding="utf-8"
    )
    result = RUNNER.invoke(app, ["equiv", str(spec), str(broken)])
    assert result.exit_code == 2
    assert "reset column" in result.output
