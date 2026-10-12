"""Tests for the implementation relation (T302).

The six golden pairs are checked by the protected harness in `tests/golden_pairs/`; this
file covers §8's own properties, the failure kinds the golden pairs do not all reach, the
preconditions, and the one piece of §5 logic that `equiv.py` mirrors (FT007).
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from strategies import flow_tables

from huffman_eda.equiv import (
    HAZARD,
    IMPL_NOT_STABLE,
    OUTPUT_MISMATCH,
    RESET,
    _hazardous,
    equivalent,
    implements,
)
from huffman_eda.explore import explore
from huffman_eda.io import parse_cell
from huffman_eda.model import Cell, Choice, FlowTable
from huffman_eda.rules.dynamic import _ft007
from huffman_eda.semantics import Outcome

SLOW = settings(
    max_examples=500,
    deadline=None,
    database=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)

# M3's exit criterion is `equiv(T, T)` holding for 1000 random tables (docs/ROADMAP.md).
CRITERION = settings(
    max_examples=1000,
    deadline=None,
    database=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)

# A two-state toggle: the shape most of these tests start from.
TOGGLE = {1: {"0": "[1],0", "1": "2,-"}, 2: {"0": "1,-", "1": "[2],1"}}


def build(
    rows: dict[int, dict[str, str]],
    *,
    reset: tuple[int, str] = (1, "0"),
    inputs: tuple[str, ...] = ("x",),
    outputs: tuple[str, ...] = ("z",),
    name: str = "t",
) -> FlowTable:
    """Build a table from §2 cell strings, so the tests read like the YAML files."""
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


# --- §8.4's consequences -----------------------------------------------------


def test_a_table_implements_itself() -> None:
    table = build(TOGGLE)
    result = implements(table, table)
    assert result.ok is True
    assert result.counterexample is None
    assert equivalent(table, table) is True


def test_equivalent_returns_a_real_bool() -> None:
    assert equivalent(build(TOGGLE), build(TOGGLE)) is True
    assert equivalent(build(TOGGLE), build({1: {"0": "1,0"}, 2: {"0": "[2],0"}})) is False


def test_the_relation_is_not_symmetric() -> None:
    # `impl` refines a don't-care; the spec cannot be refined by it in turn.
    spec = build({1: {"0": "[1],0", "1": "2,-"}, 2: {"0": "1,-", "1": "[2],-"}})
    impl = build(
        {
            1: {"0": "[1],0", "1": "2,-"},
            2: {"0": "3,-", "1": "[2],0"},
            3: {"0": "[3],0", "1": "4,-"},
            4: {"0": "1,-", "1": "[4],1"},
        }
    )
    assert implements(spec, impl).ok is True
    assert implements(impl, spec).ok is False
    assert equivalent(spec, impl) is False


def test_a_spec_without_a_usable_reset_implements_anything() -> None:
    # reset not stable, and a reset row that is missing: nothing to implement (§8.4).
    unstable = build({1: {"0": "1,0"}})
    missing = build({2: {"0": "[2],0"}}, reset=(1, "0"))
    impl = build(TOGGLE)
    for spec in (unstable, missing):
        assert implements(spec, impl).ok is True
        assert implements(spec, impl).counterexample is None


# --- the reset check ---------------------------------------------------------


def test_reset_column_must_match() -> None:
    result = implements(build(TOGGLE), build(TOGGLE, reset=(1, "1")))
    assert result.ok is False
    assert result.counterexample is not None
    assert result.counterexample.to_dict() == {
        "trace": [],
        "kind": RESET,
        "output": None,
        "outcome": None,
    }


def test_reset_row_must_exist() -> None:
    result = implements(build(TOGGLE), build(TOGGLE, reset=(17, "0")))
    assert result.ok is False
    assert result.counterexample is not None
    assert result.counterexample.kind == RESET
    assert result.counterexample.trace == ()


def test_reset_must_be_stable() -> None:
    result = implements(build(TOGGLE), build({1: {"0": "2,0", "1": "[1],0"}, 2: {"0": "[2],0"}}))
    assert result.ok is False
    assert result.counterexample is not None
    assert result.counterexample.kind == RESET


@pytest.mark.parametrize("bad", ["0", "-"])
def test_reset_outputs_must_be_compatible(bad: str) -> None:
    # §8.2: an unassigned impl bit is incompatible with a specified spec bit.
    spec = build({1: {"0": "[1],1"}, 2: {"0": "1,1"}})
    impl = build({1: {"0": f"[1],{bad}"}, 2: {"0": "1,0"}})
    result = implements(spec, impl)
    assert result.ok is False
    assert result.counterexample is not None
    assert result.counterexample.to_dict() == {
        "trace": [],
        "kind": RESET,
        "output": "z",
        "outcome": None,
    }


# --- the three checks on a step ---------------------------------------------


@pytest.mark.parametrize(
    ("impl_rows", "outcome"),
    [
        # x rise never settles: a two-state cycle.
        ({1: {"0": "[1],0", "1": "2,0"}, 2: {"0": "1,0", "1": "1,0"}}, "OSCILLATION"),
        # x rise runs into an unspecified entry.
        ({1: {"0": "[1],0", "1": "2,0"}, 2: {"0": "1,-"}}, "UNDEFINED"),
        # x rise reaches a nondeterministic entry.
        ({1: {"0": "[1],0", "1": "2,0|2,1"}, 2: {"0": "1,-", "1": "[2],0"}}, "NONDET"),
    ],
)
def test_impl_not_stable_reports_the_outcome(
    impl_rows: dict[int, dict[str, str]], outcome: str
) -> None:
    result = implements(build(TOGGLE), build(impl_rows))
    assert result.ok is False
    assert result.counterexample is not None
    assert result.counterexample.to_dict() == {
        "trace": ["1"],
        "kind": IMPL_NOT_STABLE,
        "output": None,
        "outcome": outcome,
    }


def test_output_mismatch_reports_the_lowest_index() -> None:
    spec = build(
        {1: {"0": "[1],00", "1": "2,00"}, 2: {"0": "1,00", "1": "[2],01"}},
        outputs=("z1", "z2"),
    )
    impl = build(
        {1: {"0": "[1],00", "1": "2,00"}, 2: {"0": "1,00", "1": "[2],10"}},
        outputs=("z1", "z2"),
    )
    result = implements(spec, impl)
    assert result.ok is False
    assert result.counterexample is not None
    assert result.counterexample.to_dict() == {
        "trace": ["1"],
        "kind": OUTPUT_MISMATCH,
        "output": "z1",
        "outcome": None,
    }


def test_a_dont_care_bit_is_compatible() -> None:
    # spec leaves z2 unassigned, so impl may produce either value there.
    spec = build(
        {1: {"0": "[1],00", "1": "2,00"}, 2: {"0": "1,00", "1": "[2],0-"}},
        outputs=("z1", "z2"),
    )
    impl = build(
        {1: {"0": "[1],00", "1": "2,00"}, 2: {"0": "1,00", "1": "[2],01"}},
        outputs=("z1", "z2"),
    )
    assert implements(spec, impl).ok is True


def test_hazard_is_reported_when_impl_introduces_it() -> None:
    spec = build(TOGGLE)
    impl = build(
        {1: {"0": "[1],0", "1": "3,1"}, 2: {"0": "1,-", "1": "[2],1"}, 3: {"0": "1,-", "1": "2,0"}}
    )
    result = implements(spec, impl)
    assert result.ok is False
    assert result.counterexample is not None
    assert result.counterexample.to_dict() == {
        "trace": ["1"],
        "kind": HAZARD,
        "output": "z",
        "outcome": None,
    }


def test_an_inherited_hazard_is_allowed() -> None:
    # §8.4 check 3 is relative: the same hazard in the spec is not a failure.
    specs = build(
        {1: {"0": "[1],0", "1": "2,1"}, 2: {"0": "1,0", "1": "3,0"}, 3: {"0": "1,0", "1": "[3],1"}}
    )
    assert implements(specs, specs).ok is True


def test_hazard_reports_the_lowest_index() -> None:
    spec = build(
        {1: {"0": "[1],00", "1": "2,00"}, 2: {"0": "1,00", "1": "[2],00"}}, outputs=("z1", "z2")
    )
    # z1 goes 0 (reset entry) -> 1 (row 3) -> 0 -> 0 over the settling: two changes, while
    # z2 stays put and the final outputs still match the spec.
    impl = build(
        {
            1: {"0": "[1],00", "1": "3,10"},
            2: {"0": "1,--", "1": "[2],00"},
            3: {"0": "1,--", "1": "2,00"},
        },
        outputs=("z1", "z2"),
    )
    result = implements(spec, impl)
    assert result.ok is False
    assert result.counterexample is not None
    assert result.counterexample.to_dict() == {
        "trace": ["1"],
        "kind": HAZARD,
        "output": "z1",
        "outcome": None,
    }


# --- the search order --------------------------------------------------------


def test_a_depth_two_mismatch_keeps_the_column_trace() -> None:
    # The reset step passes for both input bits; the failure is two steps out, and the
    # trace is the sequence of columns applied after the reset (SEMANTICS §8.5).
    spec = build(
        {
            1: {"00": "[1],0", "10": "2,-", "01": "3,-"},
            2: {"00": "1,-", "10": "[2],0", "11": "[2],0"},
            3: {"00": "1,-", "01": "[3],0"},
        },
        reset=(1, "00"),
        inputs=("x1", "x2"),
    )
    impl = build(
        {
            1: {"00": "[1],0", "10": "2,-", "01": "3,-"},
            2: {"00": "1,-", "10": "[2],0", "11": "[2],1"},
            3: {"00": "1,-", "01": "[3],0"},
        },
        reset=(1, "00"),
        inputs=("x1", "x2"),
    )
    result = implements(spec, impl)
    assert result.ok is False
    assert result.counterexample is not None
    assert result.counterexample.to_dict() == {
        "trace": ["10", "11"],
        "kind": OUTPUT_MISMATCH,
        "output": "z",
        "outcome": None,
    }


def test_the_first_bit_index_wins_a_tie() -> None:
    # Both input changes fail at depth one; bit 0 is tried first (§8.4).
    spec = build(
        {
            1: {"00": "[1],0", "10": "2,-", "01": "3,-"},
            2: {"00": "1,-", "10": "[2],0"},
            3: {"00": "1,-", "01": "[3],0"},
        },
        reset=(1, "00"),
        inputs=("x1", "x2"),
    )
    impl = build(
        {
            1: {"00": "[1],0", "10": "2,-", "01": "3,-"},
            2: {"00": "1,-", "10": "[2],1"},
            3: {"00": "1,-", "01": "[3],1"},
        },
        reset=(1, "00"),
        inputs=("x1", "x2"),
    )
    result = implements(spec, impl)
    assert result.ok is False
    assert result.counterexample is not None
    assert result.counterexample.trace == ("10",)
    assert result.counterexample.kind == OUTPUT_MISMATCH


# --- preconditions -----------------------------------------------------------


def test_same_names_different_behaviour_does_not_raise() -> None:
    # The precondition is about names and order only.
    result = implements(build(TOGGLE), build({1: {"0": "[1],0"}, 2: {"0": "[2],0"}}))
    assert result.ok is False  # the change fails, but it is a counterexample, not an error


def test_requires_identical_input_names() -> None:
    with pytest.raises(ValueError, match="identical inputs and outputs"):
        implements(build(TOGGLE), build(TOGGLE, inputs=("y",)))


def test_requires_identical_output_names() -> None:
    with pytest.raises(ValueError, match="identical inputs and outputs"):
        implements(build(TOGGLE), build(TOGGLE, outputs=("q",)))


# --- properties --------------------------------------------------------------


@CRITERION
@given(table=flow_tables(2, 2, 6, complete=True))
def test_a_random_complete_table_implements_itself(table: FlowTable) -> None:
    """M3's exit criterion: `equiv(T, T)` over 1000 random tables."""
    result = implements(table, table)
    assert result.ok is True
    assert result.counterexample is None
    assert equivalent(table, table) is True


@SLOW
@given(table=flow_tables(2, 2, 6))
def test_any_table_implements_itself(table: FlowTable) -> None:
    assert implements(table, table).ok is True


def renamed(table: FlowTable, mapping: dict[int, int]) -> FlowTable:
    """The same table with its states renamed (an isomorphism)."""
    rows: dict[int, dict[str, Cell]] = {}
    for state, row in table.rows.items():
        rows[mapping[state]] = {
            column: Cell(
                tuple(Choice(mapping[choice.next], choice.outputs) for choice in cell.choices)
            )
            for column, cell in row.items()
        }
    return FlowTable(
        name=f"{table.name}_renamed",
        inputs=table.inputs,
        outputs=table.outputs,
        reset=(mapping[table.reset[0]], table.reset[1]),
        rows=rows,
    )


@SLOW
@given(table=flow_tables(2, 2, 5))
def test_renaming_states_preserves_equivalence(table: FlowTable) -> None:
    mapping = {
        state: 1000 + rank for rank, state in enumerate(sorted(table.states(), reverse=True))
    }
    other = renamed(table, mapping)
    assert implements(table, other).ok is True
    assert implements(other, table).ok is True
    assert equivalent(table, other) is True


# --- the one piece of §5 logic that equiv.py mirrors -------------------------


@SLOW
@given(table=flow_tables(2, 2, 5))
def test_hazard_predicate_agrees_with_ft007(table: FlowTable) -> None:
    """§8.4 check 3 mirrors §5's FT007, so the two must agree output by output.

    A diagnostic carries only ``(state, dst_col)``, which two transitions can share, so
    the comparison is aggregated over the whole walk rather than matched per transition.
    """
    result = explore(table)
    reported = _ft007(table, result)
    mine = [
        table.outputs[index]
        for transition in result.transitions
        if transition.result.kind is Outcome.STABLE
        for index in range(len(table.outputs))
        if _hazardous(
            table,
            transition.src_state,
            transition.src_col,
            transition.dst_col,
            transition.result.path,
            index,
        )
    ]
    assert sorted(diagnostic.message.split("'")[1] for diagnostic in reported) == sorted(mine)
    assert len(reported) == len(mine)
