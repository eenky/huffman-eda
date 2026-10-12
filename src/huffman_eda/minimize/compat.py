"""Compatibility, implication and class sets. Implements docs/SEMANTICS.md §9.1-§9.3.

This is the half of ``huffman_eda.minimize`` that T401 owns: the §9.1 precondition, the
§9.2 incompatible-pair fixpoint, and the §9.3 implied sets and class sets. The search
half (§9.4-§9.6, T402-T404) reaches callers through the package ``__init__``, so nothing
here depends on it.
"""

from __future__ import annotations

from huffman_eda.model import FlowTable
from huffman_eda.validate import validate

__all__ = [
    "PRECONDITION_RULES",
    "LimitExceeded",
    "MinimizationError",
    "check_precondition",
    "class_set",
    "implied",
    "incompatibility_reasons",
    "incompatible_pairs",
]

# The rules SEMANTICS §9.1 requires to be absent: an unusable reset (FT000), a cell with
# more than one choice (FT001), and FT003/FT004, which together say the table is not
# normal. FT002 is deliberately absent: a successor cycle implies FT004, so §9.1 already
# excludes it.
PRECONDITION_RULES: tuple[str, ...] = ("FT000", "FT001", "FT003", "FT004")

#: An unordered state pair, always stored as ``(p, q)`` with ``p < q``.
Pair = tuple[int, int]


class MinimizationError(ValueError):
    """A table that does not satisfy the SEMANTICS §9.1 precondition.

    ``rules`` is the sorted tuple of the violated rule IDs, so a caller can say exactly
    which prerequisite is missing rather than only that one is.
    """

    def __init__(self, rules: tuple[str, ...]) -> None:
        self.rules: tuple[str, ...] = tuple(sorted(rules))
        joined = ", ".join(self.rules) if self.rules else "none"
        super().__init__(f"table does not satisfy the SEMANTICS §9.1 precondition: {joined}")


class LimitExceeded(RuntimeError):
    """A bounded search gave up instead of running forever (SEMANTICS §9.8 ``limit``)."""


def check_precondition(table: FlowTable) -> None:
    """Raise ``MinimizationError`` unless ``table`` satisfies SEMANTICS §9.1.

    The check asks the ordinary validator rather than re-deriving the four rules, so §9
    and §5 can never disagree about what an unusable reset or a non-normal table is.
    """
    found = {diagnostic.rule for diagnostic in validate(table).diagnostics}
    violated = tuple(sorted(found & set(PRECONDITION_RULES)))
    if violated:
        raise MinimizationError(violated)


def _order(p: int, q: int) -> Pair:
    """The pair ``(p, q)`` written with ``p < q``."""
    return (p, q) if p < q else (q, p)


def _pairs(states: tuple[int, ...]) -> list[Pair]:
    """Every unordered state pair, in canonical order."""
    return [(p, q) for index, p in enumerate(states) for q in states[index + 1 :]]


def _agree(left: str, right: str) -> bool:
    """True when no output bit is specified differently on both sides (SEMANTICS §9.2)."""
    return all(a == b or a == "-" or b == "-" for a, b in zip(left, right, strict=True))


def _stable_outputs(table: FlowTable, state: int, column: str) -> str | None:
    """The outputs at ``(state, column)``, or None when the entry is not stable.

    Only stable entries take part in §9.2, because transient outputs are not observables
    (§8.2) and the reduced table does not keep them (§9.6).
    """
    return table.cell(state, column).outputs if table.is_stable(state, column) else None


def _conflict_column(table: FlowTable, p: int, q: int) -> str | None:
    """A column where both ``p`` and ``q`` are stable and their outputs disagree."""
    for column in table.columns():
        left = _stable_outputs(table, p, column)
        right = _stable_outputs(table, q, column)
        if left is not None and right is not None and not _agree(left, right):
            return column
    return None


def incompatibility_reasons(table: FlowTable) -> dict[Pair, str]:
    """Why each incompatible pair is incompatible. Informative; §9.8 checks only the set.

    A pair is either in conflict at a column (both entries stable, outputs disagree) or
    *implied*: some column takes its two states to a pair that is itself incompatible.
    """
    check_precondition(table)
    pairs = _pairs(table.states())
    reasons: dict[Pair, str] = {}
    for p, q in pairs:
        column = _conflict_column(table, p, q)
        if column is not None:
            reasons[(p, q)] = f"outputs differ at column {column}"
    # Fixpoint: keep adding implied pairs until adding one changes nothing (SEMANTICS
    # §9.2's "least set ... closed under implication").
    changed = True
    while changed:
        changed = False
        for pair in pairs:
            if pair in reasons:
                continue
            for column in table.columns():
                first, second = table.cell(pair[0], column), table.cell(pair[1], column)
                if not (first.is_specified and second.is_specified):
                    continue
                if first.next == second.next:
                    continue
                target = _order(first.next, second.next)
                if target in reasons:
                    reasons[pair] = f"implied by {target} at column {column}"
                    changed = True
                    break
    return reasons


def incompatible_pairs(table: FlowTable) -> frozenset[Pair]:
    """The least implication-closed superset of the output-incompatible pairs (SEMANTICS §9.2).

    Pairs are unordered and always written ``p < q``.
    """
    return frozenset(incompatibility_reasons(table))


def _implied(table: FlowTable, states: frozenset[int], column: str) -> frozenset[int]:
    """``N(C,c)`` without re-checking the precondition; the public entry point checks once."""
    cells = (table.cell(state, column) for state in states)
    return frozenset(cell.next for cell in cells if cell.is_specified)


def implied(table: FlowTable, states: frozenset[int], column: str) -> frozenset[int]:
    """``N(C,c) = { next(x,c) : x in C, (x,c) specified }`` (SEMANTICS §9.3)."""
    check_precondition(table)
    return _implied(table, states, column)


def class_set(table: FlowTable, states: frozenset[int]) -> frozenset[frozenset[int]]:
    """``Γ(C)``: the implied sets of size >= 2 that leave ``C`` (SEMANTICS §9.3)."""
    check_precondition(table)
    found = set()
    for column in table.columns():
        target = _implied(table, states, column)
        if len(target) >= 2 and not target <= states:
            found.add(target)
    return frozenset(found)
