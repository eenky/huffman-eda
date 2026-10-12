"""T503: excitation, decoding, and the §10.7 milestone gate (SEMANTICS §10.6-§10.7)."""

from __future__ import annotations

import itertools
import random

from huffman_eda.assign import assign, critical_races, decode, encode, excitation, tracey
from huffman_eda.equiv import implements
from huffman_eda.model import Cell, Choice, FlowTable


def normal(rng: random.Random, states: int = 4, inputs: int = 1) -> FlowTable:
    """A random normal table: every unstable entry targets a stable state of its column."""
    columns = ["".join(bits) for bits in itertools.product("01", repeat=inputs)]
    stable = {c: set(rng.sample(range(1, states + 1), rng.choice([2, 3]))) for c in columns}
    stable[columns[0]].add(1)
    rows = {}
    for state in range(1, states + 1):
        rows[state] = {
            c: Cell(
                (
                    Choice(
                        state if state in stable[c] else rng.choice(sorted(stable[c])),
                        rng.choice("01"),
                    ),
                )
            )
            for c in columns
        }
    return FlowTable(
        "random", tuple(f"x{i}" for i in range(inputs)), ("z0",), (1, columns[0]), rows
    )


def test_milestone_gate_implements_decode_assign() -> None:
    """§10.7: assigning, then decoding, gives back a table that implements the original."""
    rng = random.Random(50301)
    for _ in range(300):
        table = normal(rng)
        encoded = assign(table)
        result = implements(table, decode(encoded))
        assert result.ok, (table.rows, table.reset, result)


def test_assign_is_race_free_on_the_same_tables() -> None:
    rng = random.Random(50302)
    for _ in range(300):
        table = normal(rng)
        assert not [d for d in critical_races(assign(table)) if d.rule == "SA002"]


def test_excitation_covers_every_code_and_leaves_dont_cares() -> None:
    rng = random.Random(50303)
    table = normal(rng)
    assignment = tracey(table)
    encoded = encode(table, assignment.codes, bits=len(assignment.variables))
    excited = excitation(encoded)
    assert excited.state_variables == tuple(f"y{i}" for i in range(encoded.bits))
    assert set(excited.entries) == {
        format(value, f"0{encoded.bits}b") for value in range(2**encoded.bits)
    }
    for row in excited.entries.values():
        for next_bits, outputs in row.values():
            assert len(next_bits) == encoded.bits
            assert len(outputs) == len(encoded.outputs)
