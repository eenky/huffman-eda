"""Unit and property tests for settle() (T103)."""

from __future__ import annotations

from collections.abc import Mapping

import hypothesis.strategies as st
from hypothesis import given

from huffman_eda.model import Cell, Choice, FlowTable
from huffman_eda.semantics import Outcome, SettleResult, settle

Spec = int | tuple[int, ...] | None


def table_of(rows: Mapping[int, Mapping[str, Spec]]) -> FlowTable:
    """Build a one-input, no-output table: state -> column -> next state(s).

    ``None`` is an unspecified cell; a tuple is a nondeterministic cell.
    """
    built: dict[int, dict[str, Cell]] = {}
    for state, row in rows.items():
        built[state] = {}
        for column, spec in row.items():
            if spec is None:
                built[state][column] = Cell()
            elif isinstance(spec, tuple):
                built[state][column] = Cell(tuple(Choice(n, "") for n in spec))
            else:
                built[state][column] = Cell((Choice(spec, ""),))
    return FlowTable(name="s", inputs=("x",), outputs=(), reset=(1, "0"), rows=built)


# --- one test per outcome ----------------------------------------------------


def test_start_already_stable() -> None:
    result = settle(table_of({1: {"0": 1}}), 1, "0")
    assert result == SettleResult(Outcome.STABLE, (1,))
    assert result.final == 1
    assert result.cycle == ()


def test_transient_chain_then_stable() -> None:
    result = settle(table_of({1: {"0": 2}, 2: {"0": 3}, 3: {"0": 3}}), 1, "0")
    assert result == SettleResult(Outcome.STABLE, (1, 2, 3))
    assert result.final == 3


def test_three_cycle_entered_from_a_tail() -> None:
    rows = {1: {"0": 2}, 2: {"0": 3}, 3: {"0": 4}, 4: {"0": 2}}
    result = settle(table_of(rows), 1, "0")
    assert result.kind is Outcome.OSCILLATION
    assert result.path == (1, 2, 3, 4)
    assert result.cycle == (2, 3, 4)  # the tail 1 is excluded
    assert result.final == 4


def test_self_cycle_is_an_oscillation_of_one_state() -> None:
    result = settle(table_of({1: {"0": 2}, 2: {"0": 1}}), 2, "0")
    assert result.kind is Outcome.OSCILLATION
    assert result.cycle == (2, 1)


def test_undefined_via_a_missing_row() -> None:
    result = settle(table_of({1: {"0": 2}}), 1, "0")
    assert result == SettleResult(Outcome.UNDEFINED, (1, 2))
    assert result.final == 2


def test_undefined_via_a_missing_column() -> None:
    result = settle(table_of({1: {"1": 1}}), 1, "0")
    assert result == SettleResult(Outcome.UNDEFINED, (1,))


def test_nondeterministic_in_the_middle_of_a_chain() -> None:
    result = settle(table_of({1: {"0": 2}, 2: {"0": (2, 3)}}), 1, "0")
    assert result == SettleResult(Outcome.NONDET, (1, 2))
    assert result.final == 2


def test_nondeterministic_at_the_start() -> None:
    result = settle(table_of({1: {"0": (1, 2)}}), 1, "0")
    assert result == SettleResult(Outcome.NONDET, (1,))


# --- properties --------------------------------------------------------------

_nxt: st.SearchStrategy[Spec] = st.one_of(
    st.none(),
    st.integers(min_value=1, max_value=4),
    st.tuples(st.integers(1, 4), st.integers(1, 4)),
)
_rows: st.SearchStrategy[dict[int, dict[str, Spec]]] = st.dictionaries(
    st.integers(min_value=1, max_value=3),
    st.dictionaries(st.sampled_from(["0", "1"]), _nxt, max_size=2),
    max_size=3,
)


@given(rows=_rows, start=st.integers(min_value=1, max_value=4), column=st.sampled_from(["0", "1"]))
def test_settle_invariants(rows: dict[int, dict[str, Spec]], start: int, column: str) -> None:
    table = table_of(rows)
    result = settle(table, start, column)

    assert result.path[0] == start
    assert len(set(result.path)) == len(result.path), "path states are distinct"
    assert result.final == result.path[-1]

    if result.kind is Outcome.STABLE:
        assert table.is_stable(result.final, column)
        assert result.cycle == ()
    if result.kind is Outcome.OSCILLATION:
        assert result.cycle == result.path[len(result.path) - len(result.cycle) :]
        assert table.cell(result.cycle[-1], column).next == result.cycle[0]
    if result.kind is Outcome.UNDEFINED:
        assert not table.cell(result.final, column).is_specified
    if result.kind is Outcome.NONDET:
        assert not table.cell(result.final, column).is_deterministic
