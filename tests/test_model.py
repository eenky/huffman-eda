"""Unit tests for the flow-table IR (T101)."""

from __future__ import annotations

import pytest

from huffman_eda.model import Cell, Choice, FlowTable, ModelError


def table(
    inputs: tuple[str, ...] = ("x",),
    outputs: tuple[str, ...] = ("z",),
    reset: tuple[int, str] | None = None,
    rows: dict[int, dict[str, Cell]] | None = None,
) -> FlowTable:
    """A minimal valid table, overridden per test."""
    return FlowTable(
        name="t",
        inputs=inputs,
        outputs=outputs,
        reset=reset if reset is not None else (1, "0" * len(inputs)),
        rows=rows if rows is not None else {1: {"0" * len(inputs): Cell((Choice(1, "0"),))}},
    )


# --- Choice -----------------------------------------------------------------


def test_choice_rejects_bad_outputs() -> None:
    with pytest.raises(ModelError, match="outputs"):
        Choice(1, "x")
    with pytest.raises(ModelError):
        Choice(1, "0,")


@pytest.mark.parametrize("outputs", ["0", "1", "-", "01-", "---"])
def test_choice_accepts_output_alphabet(outputs: str) -> None:
    assert Choice(2, outputs).outputs == outputs


# --- Cell -------------------------------------------------------------------


def test_cell_dedupes_and_sorts_choices() -> None:
    cell = Cell((Choice(2, "-"), Choice(1, "0"), Choice(2, "-")))
    assert cell.choices == (Choice(1, "0"), Choice(2, "-"))


def test_cell_sorts_same_target_by_outputs() -> None:
    assert Cell((Choice(1, "1"), Choice(1, "0"))).choices == (Choice(1, "0"), Choice(1, "1"))


def test_empty_cell_is_unspecified() -> None:
    cell = Cell()
    assert not cell.is_specified
    assert not cell.is_deterministic


def test_cell_next_and_outputs_require_determinism() -> None:
    assert Cell((Choice(3, "0"),)).next == 3
    assert Cell((Choice(3, "0"),)).outputs == "0"
    for cell in (Cell(), Cell((Choice(1, "0"), Choice(2, "0")))):
        with pytest.raises(ValueError):
            _ = cell.next
        with pytest.raises(ValueError):
            _ = cell.outputs


# --- stability --------------------------------------------------------------


def test_stability_is_derived_from_the_cell() -> None:
    # 1 holds in column 0, moves to 2 in column 1; 2 does the reverse.
    rows = {
        1: {"0": Cell((Choice(1, "0"),)), "1": Cell((Choice(2, "-"),))},
        2: {"0": Cell((Choice(1, "-"),)), "1": Cell((Choice(2, "1"),))},
    }
    t = table(rows=rows)
    assert t.is_stable(1, "0")
    assert not t.is_stable(1, "1")
    assert t.is_stable(2, "1")
    assert not t.is_stable(2, "0")
    assert t.cell(1, "1").next == 2


def test_nondeterministic_cell_is_not_stable() -> None:
    t = table(rows={1: {"0": Cell((Choice(1, "0"), Choice(2, "0")))}})
    assert not t.is_stable(1, "0")


def test_missing_row_and_missing_column_are_unspecified() -> None:
    t = table(rows={1: {"0": Cell((Choice(1, "0"),))}})
    assert t.cell(9, "0") == Cell()
    assert t.cell(1, "1") == Cell()
    assert not t.is_stable(9, "0")
    assert not t.is_stable(1, "1")


# --- FlowTable accessors ----------------------------------------------------


def test_states_are_sorted_row_keys() -> None:
    t = table(rows={3: {}, 1: {}, 2: {}})
    assert t.states() == (1, 2, 3)


def test_columns_are_all_columns_lexicographic() -> None:
    assert table(inputs=("a", "b")).columns() == ("00", "01", "10", "11")
    assert table().columns() == ("0", "1")


def test_adjacent_flips_one_bit_at_a_time() -> None:
    assert table(inputs=("a", "b")).adjacent("00") == [(0, "10"), (1, "01")]
    assert table(inputs=("a", "b")).adjacent("11") == [(0, "01"), (1, "10")]


# --- construction validation ------------------------------------------------


def test_rejects_no_inputs() -> None:
    with pytest.raises(ModelError, match="at least one input"):
        table(inputs=())


def test_rejects_duplicate_input_names() -> None:
    with pytest.raises(ModelError, match="input names must be unique"):
        table(inputs=("x", "x"), reset=(1, "00"))


def test_rejects_duplicate_output_names() -> None:
    with pytest.raises(ModelError, match="output names must be unique"):
        table(outputs=("z", "z"))


@pytest.mark.parametrize(
    "column",
    ["", "00", "0x", "2"],
)
def test_rejects_invalid_reset_column(column: str) -> None:
    with pytest.raises(ModelError, match="reset column"):
        table(reset=(1, column))


@pytest.mark.parametrize("column", ["", "00", "0x", "2"])
def test_rejects_invalid_column_key(column: str) -> None:
    with pytest.raises(ModelError, match="column key"):
        table(rows={1: {column: Cell((Choice(1, "0"),))}})


def test_rejects_choice_outputs_of_the_wrong_width() -> None:
    with pytest.raises(ModelError, match="must be 1 characters"):
        table(rows={1: {"0": Cell((Choice(1, "00"),))}})
    with pytest.raises(ModelError, match="must be 2 characters"):
        table(outputs=("z", "w"), rows={1: {"0": Cell((Choice(1, "0"),))}})


def test_zero_width_outputs_only_when_m_is_zero() -> None:
    # SEMANTICS §2: `outs` is forbidden when m == 0, so the choice's outputs are "".
    t = table(outputs=(), rows={1: {"0": Cell((Choice(1, ""),))}})
    assert t.outputs == ()
    with pytest.raises(ModelError, match="must be 0 characters"):
        table(outputs=(), rows={1: {"0": Cell((Choice(1, "-"),))}})


def test_state_without_a_row_is_allowed() -> None:
    # 2 is referenced as a next state but has no row: legal, per T101.
    t = table(rows={1: {"0": Cell((Choice(2, "0"),))}})
    assert t.states() == (1,)
    assert t.cell(2, "0") == Cell()


def test_reset_row_may_be_missing() -> None:
    t = table(reset=(7, "0"), rows={1: {"0": Cell((Choice(1, "0"),))}})
    assert t.reset == (7, "0")
    assert not t.is_stable(7, "0")
