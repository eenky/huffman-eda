"""The encoded flow table. Implements docs/SEMANTICS.md §10.1-§10.2 (T501).

Codes are plain integers here and bit strings only in the returned ``EncodedTable``: integer
arithmetic is what the race and dichotomy machinery compares.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TypeAlias

from huffman_eda.model import FlowTable
from huffman_eda.validate import validate

__all__ = [
    "PRECONDITION_RULES",
    "AssignmentError",
    "EncodedTable",
    "Entry",
    "LimitExceeded",
    "check_precondition",
    "code_map",
    "defined_codes",
    "encode",
]

# The rules SEMANTICS §10.1 requires to be absent: an unusable reset (FT000), a cell with more
# than one choice (FT001), and FT003/FT004, which together say the table is not normal.
PRECONDITION_RULES: tuple[str, ...] = ("FT000", "FT001", "FT003", "FT004")

#: One §10.2 entry: ``(next code, outputs, stable)``. Absent means unspecified (or undefined).
Entry: TypeAlias = tuple[str, str, bool]


class AssignmentError(ValueError):
    """A table that does not satisfy the SEMANTICS §10.1 precondition.

    ``rules`` is the sorted tuple of the violated FT IDs, so a caller can say exactly which
    prerequisite is missing rather than only that one is.
    """

    def __init__(self, rules: tuple[str, ...]) -> None:
        self.rules: tuple[str, ...] = tuple(sorted(rules))
        joined = ", ".join(self.rules) if self.rules else "none"
        super().__init__(f"table does not satisfy the SEMANTICS §10.1 precondition: {joined}")


class LimitExceeded(RuntimeError):
    """A bounded search gave up instead of running forever (SEMANTICS §10.8 ``limit``)."""


class InjectiveError(ValueError):
    """SA004: the assignment is not injective, or a code does not fit the given width."""


def check_precondition(table: FlowTable) -> None:
    """Raise ``AssignmentError`` unless ``table`` satisfies SEMANTICS §10.1.

    Like §9's precondition, this asks the ordinary validator rather than re-deriving the four
    rules, so §10 and §5 can never disagree about what an unusable reset or a non-normal table is.
    """
    found = {diagnostic.rule for diagnostic in validate(table).diagnostics}
    violated = tuple(sorted(found & set(PRECONDITION_RULES)))
    if violated:
        raise AssignmentError(violated)


def bits_for(codes: Mapping[int, int], count: int) -> int:
    """Enough variables for every code, and for ``count`` distinct ones (§10.4)."""
    highest = max(codes.values(), default=0)
    return max(highest.bit_length(), (count - 1).bit_length(), 1)


@dataclass(frozen=True, slots=True)
class EncodedTable:
    """§10.2: a flow table whose states carry codes.

    ``entries`` is keyed by code, then column. A code no state has, and a column no entry
    mentions, are both "undefined": their behaviour is don't-care (§11 completes it).
    """

    name: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    states: tuple[int, ...]
    columns: tuple[str, ...]
    codes: dict[int, str]
    bits: int
    reset: tuple[str, str]
    entries: dict[str, dict[str, Entry]] = field(default_factory=dict)

    def state_of(self, code: str) -> int | None:
        """The state that carries ``code``, or None when the code is undefined."""
        for state, value in self.codes.items():
            if value == code:
                return state
        return None


def code_map(table: FlowTable, codes: Mapping[int, int], bits: int | None = None) -> dict[int, str]:
    """§10.2: the state-to-code map, as bit strings, checked for injectivity (SA004)."""
    states = table.states()
    missing = [state for state in states if state not in codes]
    if missing:
        raise InjectiveError(f"SA004: no code given for state(s) {missing}")
    values = [codes[state] for state in states]
    if min(values) < 0 or len(set(values)) != len(values):
        raise InjectiveError(f"SA004: codes must be distinct and non-negative, got {values}")
    width = bits if bits is not None else bits_for(codes, len(states))
    if max(values) >= 2**width:
        raise InjectiveError(f"SA004: code {max(values)} does not fit in {width} variable(s)")
    return {state: format(codes[state], f"0{width}b") for state in states}


def encode(table: FlowTable, codes: Mapping[int, int], *, bits: int | None = None) -> EncodedTable:
    """§10.2: give every state of ``table`` a code."""
    check_precondition(table)
    mapping = code_map(table, codes, bits)
    width = len(next(iter(mapping.values())))
    blank = "-" * len(table.outputs)
    entries: dict[str, dict[str, Entry]] = {mapping[state]: {} for state in table.states()}
    for state in table.states():
        for column in table.columns():
            cell = table.cell(state, column)
            if not cell.is_specified:
                continue
            target = cell.next
            entries[mapping[state]][column] = (
                (mapping[target], cell.outputs, True)
                if target == state
                else (mapping[target], blank, False)
            )
    return EncodedTable(
        name=table.name,
        inputs=tuple(table.inputs),
        outputs=tuple(table.outputs),
        states=table.states(),
        columns=table.columns(),
        codes=mapping,
        bits=width,
        reset=(mapping[table.reset[0]], table.reset[1]),
        entries=entries,
    )


def defined_codes(encoded: EncodedTable) -> frozenset[str]:
    """The codes some state carries (§10.2)."""
    return frozenset(encoded.codes.values())
