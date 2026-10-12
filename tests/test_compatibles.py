"""T402: maximal and prime compatibles (§9.3).

The `maximal_compatibles` and `prime_compatibles` assertions from `tests/golden_minimize`
(mirrored, since that harness asserts all of §9.8 per case), plus unit and property tests.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import HealthCheck, assume, given, settings
from strategies import flow_tables

from huffman_eda.explore import explore
from huffman_eda.io import load_table
from huffman_eda.minimize import (
    LimitExceeded,
    MinimizationError,
    incompatible_pairs,
    maximal_compatibles,
    prime_compatibles,
)
from huffman_eda.model import Cell, Choice, FlowTable
from huffman_eda.validate import validate

GOLDEN = Path(__file__).parent / "golden_minimize"
CASES = sorted(p for p in GOLDEN.iterdir() if p.is_dir() and (p / "table.yaml").exists())

SLOW = settings(
    max_examples=200,
    deadline=None,
    database=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)


def build(rows: dict[int, dict[str, str]], *, reset: tuple[int, str] = (1, "0")) -> FlowTable:
    """A one-input, one-output table from ``{state: {column: "next,out"}}`` shorthand."""
    return FlowTable(
        name="t",
        inputs=("x",),
        outputs=("z",),
        reset=reset,
        rows={
            state: {
                column: Cell((Choice(int(spec.split(",")[0]), spec.split(",")[1]),))
                for column, spec in row.items()
            }
            for state, row in rows.items()
        },
    )


def precondition_ok(table: FlowTable) -> bool:
    """True when ``table`` satisfies §9.1, judged by §4/§5 alone."""
    rules = {d.rule for d in validate(table).diagnostics}
    return explore(table).reset_ok and not rules & {"FT000", "FT001", "FT003", "FT004"}


def as_lists(collections: tuple[frozenset[int], ...]) -> list[list[int]]:
    """Golden expectations are lists of sorted lists."""
    return [sorted(states) for states in collections]


def holds_incompatible_pair(
    member: frozenset[int], incompatible: frozenset[tuple[int, int]]
) -> bool:
    """True when a candidate compatible holds one of the incompatible pairs of §9.2."""
    return any((min(p, q), max(p, q)) in incompatible for p in member for q in member if p < q)


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.name)
def test_golden_maximal_and_prime(case: Path) -> None:
    """The §9.8 assertions T402 owns, run in CI; the locked harness stays authoritative."""
    table = load_table(case / "table.yaml")
    want = json.loads((case / "expected.json").read_text())
    if want["precondition"] != "ok":
        with pytest.raises(MinimizationError):
            maximal_compatibles(table)
        return
    assert as_lists(maximal_compatibles(table)) == want["maximal_compatibles"]
    assert as_lists(prime_compatibles(table)) == want["prime_compatibles"]


def test_hand_checked_compatibles_of_a_two_clique_table() -> None:
    """Both maximal compatibles are prime here, and neither is the other's subset."""
    # 1 and 3 are incompatible (outputs 1 vs 0 in column "1"), likewise 2 and 4, so the
    # compatibility graph is two disjoint edges. Nothing merges across them.
    table = build(
        {
            1: {"0": "3,0", "1": "1,1"},
            2: {"0": "4,0", "1": "2,1"},
            3: {"0": "3,0", "1": "4,0"},
            4: {"0": "4,0", "1": "4,0"},
        },
        reset=(1, "1"),
    )
    assert {(min(p, q), max(p, q)) for p, q in incompatible_pairs(table)} == {
        (1, 3),
        (1, 4),
        (2, 3),
        (2, 4),
    }
    assert as_lists(maximal_compatibles(table)) == [[1, 2], [3, 4]]


def test_results_are_in_canonical_order_and_deduplicated() -> None:
    """§9.5: compatibles are ordered by their sorted state tuples, once each."""
    table = load_table(GOLDEN / "collapse_to_one" / "table.yaml")
    for found in (maximal_compatibles(table), prime_compatibles(table)):
        assert list(found) == sorted(found, key=lambda states: sorted(states))
        assert len(set(found)) == len(found)


def test_a_tiny_limit_is_refused() -> None:
    """An exponential search that cannot finish raises instead of running forever."""
    table = load_table(GOLDEN / "collapse_to_one" / "table.yaml")
    with pytest.raises(LimitExceeded):
        maximal_compatibles(table, limit=0)
    with pytest.raises(LimitExceeded):
        prime_compatibles(table, limit=1)


def test_every_function_checks_the_precondition() -> None:
    """§9.8: the §9.1 precondition comes first, so a non-normal table never gets searched."""
    table = load_table(GOLDEN / "non_normal_rejected" / "table.yaml")
    for call in (lambda: maximal_compatibles(table), lambda: prime_compatibles(table)):
        with pytest.raises(MinimizationError) as caught:
            call()
        assert caught.value.rules == ("FT004",)


@SLOW
@given(table=flow_tables(2, 2, 5, normal=True))
def test_maximal_compatibles_are_compatible_and_cover_every_state(table: FlowTable) -> None:
    """A maximal compatible holds no incompatible pair and cannot take one more state."""
    assume(precondition_ok(table))
    incompatible = incompatible_pairs(table)
    found = maximal_compatibles(table)
    for member in found:
        assert not holds_incompatible_pair(member, incompatible)
        for state in table.states():
            if state in member:
                continue
            assert any((min(state, other), max(state, other)) in incompatible for other in member)
    for state in table.states():
        assert any(state in member for member in found)


@SLOW
@given(table=flow_tables(2, 2, 5, normal=True))
def test_every_maximal_compatible_is_prime(table: FlowTable) -> None:
    """§9.3: maximality implies primeness, because no bigger compatible exists to match Γ."""
    assume(precondition_ok(table))
    assert set(maximal_compatibles(table)) <= set(prime_compatibles(table))


@SLOW
@given(table=flow_tables(2, 2, 5, normal=True))
def test_primes_are_compatibles_and_cover_every_state(table: FlowTable) -> None:
    """Every prime holds no incompatible pair, and every state is in one (maximals are prime)."""
    assume(precondition_ok(table))
    incompatible = incompatible_pairs(table)
    primes = set(prime_compatibles(table))
    for member in primes:
        assert not holds_incompatible_pair(member, incompatible)
    for state in table.states():
        assert any(state in member for member in primes)


def test_a_compatible_with_an_empty_class_set_is_not_prime() -> None:
    """Γ(C') ⊆ Γ(C) excludes C: state 2 has no cells at all, so Γ({2}) = Γ({1,2}) = ∅."""
    # 1 holds in column "0" and 2 has no row of cells, so 2 can be merged into {1,2}
    # without adding a class. {2} is a compatible but not prime; the maximal {1,2} is.
    table = build({1: {"0": "1,0"}, 2: {}}, reset=(1, "0"))
    assert as_lists(maximal_compatibles(table)) == [[1, 2]]
    assert as_lists(prime_compatibles(table)) == [[1, 2]]
