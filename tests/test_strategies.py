"""Tests for the random-table strategies (T301).

Each flag's guarantee is checked against `validate()` and against the structural property
it names, and each guarantee is paired with a control: a `find()` for a table *without*
the flag where the corresponding rule does fire, so the guarantee cannot pass vacuously.
"""

from __future__ import annotations

import hypothesis.strategies as st
import pytest
from hypothesis import HealthCheck, find, given, settings
from strategies import columns_for, flow_tables

from huffman_eda.explore import explore
from huffman_eda.model import FlowTable
from huffman_eda.validate import validate

FLAGS: list[dict[str, bool]] = [
    {},
    {"normal": True},
    {"primitive": True},
    {"complete": True},
    {"normal": True, "primitive": True},
    {"normal": True, "complete": True},
    {"primitive": True, "complete": True},
    {"normal": True, "primitive": True, "complete": True},
]

N_INPUTS, N_OUTPUTS, MAX_STATES = 2, 2, 6

SLOW = settings(
    max_examples=500,
    deadline=None,
    database=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)


def rules_of(table: FlowTable) -> set[str]:
    return {diagnostic.rule for diagnostic in validate(table).diagnostics}


def stable_entries(table: FlowTable, state: int) -> int:
    return sum(1 for column in table.columns() if table.is_stable(state, column))


def _any_table(table: FlowTable) -> bool:
    """Trivially true: with this condition `find()` returns the minimal example."""
    return isinstance(table, FlowTable)


# --- the guarantees ----------------------------------------------------------


@pytest.mark.parametrize("flags", FLAGS, ids=lambda f: "+".join(sorted(f)) or "plain")
@SLOW
@given(data=st.data())
def test_flag_guarantees_hold(data: st.DataObject, flags: dict[str, bool]) -> None:
    table = data.draw(flow_tables(N_INPUTS, N_OUTPUTS, MAX_STATES, **flags))
    rules = rules_of(table)

    if flags.get("normal"):
        assert "FT004" not in rules
        # Normal entries settle straight into a stable entry, so no column can hold a
        # multi-state cycle: the §5 rule that would catch a broken generation.
        assert "FT002" not in rules
    if flags.get("primitive"):
        assert all(stable_entries(table, state) == 1 for state in table.states())
        # One stable entry per row is at least one, so the FT008 warning cannot fire.
        assert "FT008" not in rules
    if flags.get("complete"):
        assert {"FT003", "FT005"} & rules == set()
        assert explore(table).reset_ok


# --- the controls: without the flag the rule really does fire ----------------


def test_normal_guarantee_is_not_vacuous() -> None:
    table = find(
        flow_tables(N_INPUTS, N_OUTPUTS, MAX_STATES),
        lambda candidate: "FT004" in rules_of(candidate),
        settings=SLOW,
    )
    assert "FT004" in rules_of(table)


def test_primitive_guarantee_is_not_vacuous() -> None:
    table = find(
        flow_tables(N_INPUTS, N_OUTPUTS, MAX_STATES),
        lambda candidate: any(
            stable_entries(candidate, state) != 1 for state in candidate.states()
        ),
        settings=SLOW,
    )
    assert any(stable_entries(table, state) != 1 for state in table.states())


@pytest.mark.parametrize("rule", ["FT002", "FT003", "FT005", "FT008"])
def test_the_other_rules_behind_the_flags_really_fire_without_them(rule: str) -> None:
    # Every rule the guarantees lean on is reachable without its flag, so a guarantee that
    # stopped holding would fail the assertions above instead of passing silently.
    find(
        flow_tables(N_INPUTS, N_OUTPUTS, MAX_STATES),
        lambda candidate: rule in rules_of(candidate),
        settings=SLOW,
    )


# --- shape, shrinking and the precondition -----------------------------------


@SLOW
@given(table=flow_tables(3, 1, 9))
def test_tables_are_well_formed(table: FlowTable) -> None:
    assert table.columns() == columns_for(3)
    assert 1 <= len(table.states()) <= 9
    assert table.inputs == ("x1", "x2", "x3")
    assert table.outputs == ("z1",)
    # Every state has a row, and every cell holds at most one choice.
    assert table.states() == tuple(range(1, len(table.states()) + 1))
    for state in table.states():
        for column in table.columns():
            assert len(table.cell(state, column).choices) <= 1


@SLOW
@given(table=flow_tables(N_INPUTS, 0, MAX_STATES, complete=True))
def test_a_table_without_outputs_is_fine(table: FlowTable) -> None:
    assert table.outputs == ()
    assert all(
        table.cell(state, column).outputs == ""
        for state in table.states()
        for column in table.columns()
        if table.cell(state, column).is_specified
    )


def test_shrinking_reaches_the_smallest_table() -> None:
    # The condition is satisfied by every table, so what comes back is the strategy's
    # minimal example: shrinking really does drive the state count to its floor.
    plain = find(flow_tables(N_INPUTS, N_OUTPUTS, MAX_STATES), _any_table, settings=SLOW)
    assert len(plain.states()) == 1

    # Four columns, so a complete table cannot shrink below one state per column.
    complete = find(
        flow_tables(N_INPUTS, N_OUTPUTS, MAX_STATES, complete=True), _any_table, settings=SLOW
    )
    assert len(complete.states()) == 4


def test_complete_rejects_an_impossible_size() -> None:
    with pytest.raises(ValueError, match="max_states=2 < 2\\*\\*2=4"):
        flow_tables(2, 1, 2, complete=True)
