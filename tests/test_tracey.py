"""T502: dichotomies and the assignment procedure (SEMANTICS §10.4-§10.5)."""

from __future__ import annotations

import itertools
import random

from huffman_eda.assign import LimitExceeded, assign, critical_races, dichotomies, encode, tracey
from huffman_eda.model import Cell, Choice, FlowTable


def normal(rng: random.Random, states: int = 4, inputs: int = 1) -> FlowTable:
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


def test_tracey_is_race_free_on_300_random_normal_tables() -> None:
    rng = random.Random(50201)
    for _ in range(300):
        table = normal(rng)
        assignment = tracey(table)
        encoded = encode(table, assignment.codes, bits=len(assignment.variables))
        races = [d for d in critical_races(encoded) if d.rule == "SA002"]
        assert races == [], (table.rows, table.reset, races)


def test_every_seed_is_separated_by_some_variable() -> None:
    rng = random.Random(50202)
    for _ in range(50):
        table = normal(rng)
        assignment = tracey(table)
        seeds = dichotomies(table).seeds
        assert {seed for seed, _ in assignment.certificate} == set(seeds)
        assert len(assignment.variables) == len(set(assignment.variables))


def test_a_bounded_search_gives_up_loudly() -> None:
    rng = random.Random(50203)
    table = normal(rng, states=5)
    try:
        tracey(table, limit=1)
    except LimitExceeded:
        return
    raise AssertionError("limit=1 must give up")


def test_assign_is_encode_of_tracey() -> None:
    rng = random.Random(50204)
    table = normal(rng)
    assignment = tracey(table)
    assert (
        assign(table).codes == encode(table, assignment.codes, bits=len(assignment.variables)).codes
    )
