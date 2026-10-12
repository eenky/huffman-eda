"""Unit tests for explore() (T104)."""

from __future__ import annotations

from collections.abc import Mapping

from huffman_eda.explore import explore
from huffman_eda.model import Cell, Choice, FlowTable
from huffman_eda.semantics import Outcome

Spec = int | tuple[int, ...] | None


def table_of(
    rows: Mapping[int, Mapping[str, Spec]],
    inputs: tuple[str, ...] = ("x",),
    reset: tuple[int, str] = (1, "0"),
) -> FlowTable:
    """A table with no outputs: state -> column -> next state(s), or None if unspecified."""
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
    return FlowTable(name="e", inputs=inputs, outputs=(), reset=reset, rows=built)


TWO_INPUT = table_of(
    {
        # Only three stable entries exist, so the walk stays small enough to eyeball.
        1: {"00": 1, "10": 2, "01": 3},
        2: {"10": 2},
        3: {"01": 3},
    },
    inputs=("x1", "x2"),
    reset=(1, "00"),
)


# --- reset handling ----------------------------------------------------------


def test_missing_reset_row_gives_an_empty_result() -> None:
    table = table_of({1: {"0": 1}}, reset=(7, "0"))
    result = explore(table)
    assert result.reset_ok is False
    assert result.stable == () and result.visited == () and result.transitions == ()


def test_unstable_reset_gives_an_empty_result() -> None:
    table = table_of({1: {"0": 2}, 2: {"0": 2}}, reset=(1, "0"))
    assert explore(table).reset_ok is False


def test_specified_but_unstable_reset_row_still_fails() -> None:
    table = table_of({1: {"0": 1}, 2: {"0": 2}}, reset=(1, "1"))
    assert explore(table).reset_ok is False


# --- the walk ----------------------------------------------------------------


def test_stable_entries_include_the_reset_and_are_sorted() -> None:
    result = explore(TWO_INPUT)
    assert result.reset_ok is True
    assert result.stable == ((1, "00"), (2, "10"), (3, "01"))


def test_transition_count_is_n_times_the_stable_count() -> None:
    result = explore(TWO_INPUT)
    assert len(result.transitions) == len(TWO_INPUT.inputs) * len(result.stable)


def test_transitions_follow_the_specified_bfs_order() -> None:
    result = explore(TWO_INPUT)
    assert [(t.src_state, t.src_col, t.dst_col) for t in result.transitions] == [
        (1, "00", "10"),
        (1, "00", "01"),
        (2, "10", "00"),
        (2, "10", "11"),
        (3, "01", "11"),
        (3, "01", "00"),
    ]


def test_input_bits_are_probed_in_increasing_order() -> None:
    result = explore(TWO_INPUT)
    first = [t.dst_col for t in result.transitions[:2]]
    assert first == ["10", "01"]  # bit 0 flipped first


def test_a_settled_state_is_enqueued_only_once() -> None:
    # settle(3,"1") lands back on (2,"1"), which is already enqueued, so the walk stops
    # after three probes instead of revisiting it.
    table = table_of({1: {"0": 1, "1": 2}, 2: {"1": 2, "0": 3}, 3: {"0": 3, "1": 2}})
    result = explore(table)
    assert result.stable == ((1, "0"), (2, "1"), (3, "0"))
    assert [(t.src_state, t.src_col, t.dst_col) for t in result.transitions] == [
        (1, "0", "1"),
        (2, "1", "0"),
        (3, "0", "1"),
    ]


def test_visited_records_every_path_state_at_the_new_column() -> None:
    # 2 -> 3 -> 4 settles stable at 4, so all three are visited in column "1".
    table = table_of({1: {"0": 1, "1": 2}, 2: {"1": 3}, 3: {"1": 4}, 4: {"1": 4}})
    result = explore(table)
    assert (1, "1") in result.visited
    assert {(2, "1"), (3, "1"), (4, "1")} <= set(result.visited)


def test_nondeterministic_result_is_recorded_but_does_not_extend_the_walk() -> None:
    table = table_of({1: {"0": 1, "1": (2, 3)}, 2: {"1": 2}, 3: {"1": 3}})
    result = explore(table)
    assert result.stable == ((1, "0"),)
    assert len(result.transitions) == len(table.inputs)
    assert result.transitions[0].result.kind is Outcome.NONDET
    assert result.visited == ((1, "0"), (1, "1"))


def test_oscillation_is_recorded_and_does_not_extend_the_walk() -> None:
    table = table_of({1: {"0": 1, "1": 2}, 2: {"1": 1}})
    result = explore(table)
    assert result.transitions[0].result.kind is Outcome.OSCILLATION
    assert result.stable == ((1, "0"),)
