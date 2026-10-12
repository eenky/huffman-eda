"""T401: the §9.1 precondition, §9.2 incompatibility, and §9.3 implied/class sets.

These are the assertions T401 owns from `tests/golden_minimize` (the locked harness stays
authoritative) plus unit and property tests for the same three sections.
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
    PRECONDITION_RULES,
    MinimizationError,
    check_precondition,
    class_set,
    implied,
    incompatibility_reasons,
    incompatible_pairs,
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


def build(rows: dict[int, dict[str, str]], *, reset: tuple[int, str] = (1, "1")) -> FlowTable:
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


# A non-normal table: (1,"0") goes to 2, and (2,"0") is specified but unstable. It also
# has an FT002 successor cycle (2 -> 3 -> 2), which §9.1 does not name: a cycle implies
# FT004, so normality already excludes it.
NON_NORMAL = build(
    {
        1: {"0": "2,0", "1": "1,1"},
        2: {"0": "3,0", "1": "2,0"},
        3: {"0": "2,0", "1": "3,0"},
    }
)

# The same, plus a cell with two choices, so two §9.1 rules are violated at once.
NON_NORMAL_NONDET = FlowTable(
    name="t",
    inputs=("x",),
    outputs=("z",),
    reset=(1, "1"),
    rows={
        1: {"0": Cell((Choice(2, "0"),)), "1": Cell((Choice(1, "1"),))},
        2: {"0": Cell((Choice(3, "0"),)), "1": Cell((Choice(2, "0"),))},
        3: {
            "0": Cell((Choice(2, "0"),)),
            "1": Cell((Choice(3, "0"), Choice(1, "0"))),  # FT001
        },
    },
)

# (1,"0") settles to an unspecified entry, so settle() is UNDEFINED: FT003, not FT004.
UNSETTLED = build({1: {"0": "2,0", "1": "1,1"}, 2: {"1": "2,0"}})

# A usable-looking table whose reset state has no row: FT000.
BAD_RESET = build({1: {"0": "1,0", "1": "1,1"}, 2: {"0": "2,0", "1": "2,1"}}, reset=(9, "0"))


def violated(table: FlowTable) -> tuple[str, ...]:
    """The §9.1 rule IDs the validator reports, computed without the module under test."""
    found = {diagnostic.rule for diagnostic in validate(table).diagnostics}
    return tuple(sorted(found & set(PRECONDITION_RULES)))


def precondition_ok(table: FlowTable) -> bool:
    """True when ``table`` satisfies §9.1, judged by §4/§5 alone."""
    return explore(table).reset_ok and not violated(table)


def pairs_of(table: FlowTable) -> list[tuple[int, int]]:
    """Every unordered state pair, for the independent property checks below."""
    states = table.states()
    return [(p, q) for index, p in enumerate(states) for q in states[index + 1 :]]


def direct_conflicts(table: FlowTable) -> set[tuple[int, int]]:
    """The output-incompatible pairs of §9.2, written out from the definition."""
    found = set()
    for p, q in pairs_of(table):
        for column in table.columns():
            if not (table.is_stable(p, column) and table.is_stable(q, column)):
                continue
            bits = zip(table.cell(p, column).outputs, table.cell(q, column).outputs, strict=True)
            if any(a != b and "-" not in (a, b) for a, b in bits):
                found.add((p, q))
                break
    return found


def closure(table: FlowTable, seed: set[tuple[int, int]]) -> set[tuple[int, int]]:
    """The least implication-closed superset of ``seed``, computed independently of §9."""
    known = set(seed)
    while True:
        fresh = set()
        for p, q in pairs_of(table):
            if (p, q) in known:
                continue
            for column in table.columns():
                left, right = table.cell(p, column), table.cell(q, column)
                if not (left.is_specified and right.is_specified) or left.next == right.next:
                    continue
                if tuple(sorted((left.next, right.next))) in known:
                    fresh.add((p, q))
                    break
        if not fresh:
            return known
        known |= fresh


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.name)
def test_golden_precondition_and_incompatible_pairs(case: Path) -> None:
    """The §9.8 assertions T401 owns, run in CI; the locked harness stays authoritative."""
    table = load_table(case / "table.yaml")
    want = json.loads((case / "expected.json").read_text())
    if want["precondition"] != "ok":
        with pytest.raises(MinimizationError) as caught:
            check_precondition(table)
        assert list(caught.value.rules) == want["precondition"]
        return
    check_precondition(table)
    assert sorted(map(list, incompatible_pairs(table))) == want["incompatible_pairs"]


def test_precondition_accepts_a_normal_table() -> None:
    """A normal table with a stable reset passes §9.1."""
    check_precondition(build({1: {"0": "2,0", "1": "1,1"}, 2: {"0": "2,0", "1": "1,1"}}))


def test_precondition_names_every_violated_rule_sorted() -> None:
    """The reported tuple is sorted and complete, not just the first rule hit."""
    with pytest.raises(MinimizationError) as caught:
        check_precondition(NON_NORMAL)
    assert caught.value.rules == ("FT004",)
    with pytest.raises(MinimizationError) as both:
        check_precondition(NON_NORMAL_NONDET)
    assert both.value.rules == ("FT001", "FT004")
    with pytest.raises(MinimizationError) as unsettled:
        check_precondition(UNSETTLED)
    assert unsettled.value.rules == ("FT003",)
    with pytest.raises(MinimizationError) as reset:
        check_precondition(BAD_RESET)
    assert reset.value.rules == ("FT000",)


def test_every_public_function_checks_the_precondition() -> None:
    """§9.8: all of §9 checks §9.1 first, so a non-normal table is rejected everywhere."""
    states = frozenset({1})
    for call in (
        lambda: incompatible_pairs(NON_NORMAL),
        lambda: incompatibility_reasons(NON_NORMAL),
        lambda: implied(NON_NORMAL, states, "0"),
        lambda: class_set(NON_NORMAL, states),
    ):
        with pytest.raises(MinimizationError) as caught:
            call()
        assert caught.value.rules == ("FT004",)


def test_implied_and_class_sets_of_the_prime_not_maximal_case() -> None:
    """Γ and N on the golden table whose incompatibilities arise only through implication."""
    table = load_table(GOLDEN / "prime_not_maximal" / "table.yaml")
    assert implied(table, frozenset({1, 2}), "0") == frozenset({3, 4})
    assert implied(table, frozenset({3, 4}), "1") == frozenset({4})
    # N({1,2},"1") is {1,2} itself, so it is not a class; {3,4} has no second element to
    # send anywhere, so its class set is empty.
    assert class_set(table, frozenset({1, 2})) == frozenset({frozenset({3, 4})})
    assert class_set(table, frozenset({3, 4})) == frozenset()
    assert class_set(table, frozenset({1})) == frozenset()


def test_reasons_distinguish_conflicts_from_implications() -> None:
    """The informative helper names the column, and says when a pair is only implied."""
    table = load_table(GOLDEN / "prime_not_maximal" / "table.yaml")
    reasons = incompatibility_reasons(table)
    assert set(reasons) == set(incompatible_pairs(table))
    assert "outputs differ" in reasons[(1, 4)]
    assert "implied by (1, 4)" in reasons[(1, 3)]
    assert "implied by (2, 4)" in reasons[(2, 3)]


def test_pairs_are_unordered_with_the_smaller_state_first() -> None:
    """Pairs are canonical, so a caller never has to sort them."""
    table = load_table(GOLDEN / "prime_not_maximal" / "table.yaml")
    assert all(p < q for p, q in incompatible_pairs(table))


@SLOW
@given(table=flow_tables(2, 2, 5))
def test_check_precondition_agrees_with_the_validator(table: FlowTable) -> None:
    """§9.1 accepts exactly the tables §4/§5 find free of FT000, FT001, FT003 and FT004."""
    if precondition_ok(table):
        check_precondition(table)
        return
    with pytest.raises(MinimizationError) as caught:
        check_precondition(table)
    assert caught.value.rules == violated(table)


@SLOW
@given(table=flow_tables(2, 2, 5, normal=True))
def test_incompatible_pairs_is_the_least_closed_superset(table: FlowTable) -> None:
    """The set is exactly the closure of the output-incompatible pairs, no more, no less."""
    assume(precondition_ok(table))
    assert incompatible_pairs(table) == frozenset(closure(table, direct_conflicts(table)))


@SLOW
@given(table=flow_tables(2, 2, 5, normal=True))
def test_omitted_pairs_never_imply_an_incompatible_pair(table: FlowTable) -> None:
    """An omitted pair's successors are omitted too, which is what makes it compatible."""
    assume(precondition_ok(table))
    found = incompatible_pairs(table)
    for p, q in pairs_of(table):
        if (p, q) in found:
            continue
        for column in table.columns():
            left, right = table.cell(p, column), table.cell(q, column)
            if not (left.is_specified and right.is_specified) or left.next == right.next:
                continue
            assert tuple(sorted((left.next, right.next))) not in found
