"""T501: the encoded table and the race analysis (SEMANTICS §10.1-§10.3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from huffman_eda.assign import (
    AssignmentError,
    check_precondition,
    critical_races,
    defined_codes,
    encode,
)
from huffman_eda.io import load_table
from huffman_eda.model import Cell, Choice, FlowTable
from huffman_eda.validate import validate

GOLDEN = Path("tests/golden_assign/figure_3_8_bad_encoding/table.yaml")


def chain() -> FlowTable:
    """1 -> 2 -> 3 under x0, each row stable somewhere, so §10.1 holds."""
    return FlowTable(
        name="chain",
        inputs=("x0",),
        outputs=("z0",),
        reset=(1, "0"),
        rows={
            1: {"0": Cell((Choice(1, "0"),)), "1": Cell((Choice(2, "-"),))},
            2: {"0": Cell((Choice(1, "-"),)), "1": Cell((Choice(2, "0"),))},
        },
    )


def test_golden_race_set_is_what_the_book_describes() -> None:
    """The book's bad assignment on Figure 3.8: one critical transition, two orders."""
    table = load_table(GOLDEN)
    races = critical_races(encode(table, {1: 0b00, 2: 0b01, 3: 0b10, 4: 0b11}))
    assert [(d.rule, d.state, d.column, d.path) for d in races] == [
        ("SA002", 2, "10", (1, 0, 2)),
        ("SA002", 2, "10", (1, 3, 2)),
        ("SA002", 1, "11", (0, 1, 3)),
        ("SA002", 1, "11", (0, 2, 3)),
        ("SA002", 2, "11", (1, 0, 2)),
        ("SA002", 2, "11", (1, 3, 2)),
    ]


def test_a_one_bit_per_transition_assignment_has_no_critical_race() -> None:
    """One bit changes, so there is no race: 1=00, 2=01 with 1 -> 2 under x0."""
    table = FlowTable(
        name="one-bit",
        inputs=("x0",),
        outputs=("z0",),
        reset=(1, "0"),
        rows={
            1: {"0": Cell((Choice(1, "0"),)), "1": Cell((Choice(2, "-"),))},
            2: {"0": Cell((Choice(1, "-"),)), "1": Cell((Choice(2, "1"),))},
        },
    )
    assert critical_races(encode(table, {1: 0b00, 2: 0b01})) == []


def test_state_1_is_the_all_zero_code_and_codes_are_injective() -> None:
    table = load_table(GOLDEN)
    encoded = encode(table, {1: 0b00, 2: 0b11, 3: 0b10, 4: 0b01})
    assert encoded.codes == {1: "00", 2: "11", 3: "10", 4: "01"}
    assert defined_codes(encoded) == {"00", "11", "10", "01"}
    assert encoded.reset == ("00", "00")
    assert encoded.bits == 2
    with pytest.raises(ValueError, match="SA004"):
        encode(table, {1: 0b00, 2: 0b00, 3: 0b10, 4: 0b01})


def test_encode_checks_the_precondition_first() -> None:
    bad = FlowTable(
        name="non-normal",
        inputs=("x0",),
        outputs=("z0",),
        reset=(1, "0"),
        rows={
            1: {"0": Cell((Choice(2, "-"),)), "1": Cell((Choice(1, "0"),))},
            2: {"0": Cell((Choice(1, "-"),)), "1": Cell((Choice(2, "0"),))},
        },
    )
    assert {d.rule for d in validate(bad).diagnostics} >= {"FT004"}
    with pytest.raises(AssignmentError) as info:
        check_precondition(bad)
    assert "FT004" in info.value.rules
    with pytest.raises(AssignmentError):
        encode(bad, {1: 0b00, 2: 0b01})
