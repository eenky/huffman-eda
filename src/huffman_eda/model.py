"""Flow-table IR: the L0 model. Implements docs/SEMANTICS.md §1 and the §2 schema.

The IR is immutable: every type here is a frozen dataclass and every validator runs
once, in ``__post_init__``. Nothing in this module touches the filesystem or the
terminal; parsing lives in ``io.py``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

__all__ = ["Cell", "Choice", "FlowTable", "ModelError"]

_OUTPUTS_RE = re.compile(r"^[01-]*$")
_BITS = frozenset("01")


class ModelError(ValueError):
    """An invalid construction of a flow-table IR object."""


def _choice_key(choice: Choice) -> tuple[int, str]:
    """Canonical choice order: next state, then outputs (SEMANTICS §1)."""
    return (choice.next, choice.outputs)


@dataclass(frozen=True)
class Choice:
    """One ``(next, outputs)`` alternative. Implements SEMANTICS §1."""

    next: int
    outputs: str

    def __post_init__(self) -> None:
        if not _OUTPUTS_RE.match(self.outputs):
            raise ModelError(f"choice outputs must match ^[01-]*$, got {self.outputs!r}")


@dataclass(frozen=True)
class Cell:
    """The set of choices at one entry. Implements SEMANTICS §1.

    ``choices`` is deduplicated and sorted at construction, so equal cells compare
    equal regardless of how the caller spelled them.
    """

    choices: tuple[Choice, ...] = ()

    def __post_init__(self) -> None:
        canonical = tuple(sorted(set(self.choices), key=_choice_key))
        if canonical != tuple(self.choices):
            object.__setattr__(self, "choices", canonical)

    @property
    def is_specified(self) -> bool:
        """True when the cell has at least one choice."""
        return bool(self.choices)

    @property
    def is_deterministic(self) -> bool:
        """True when the cell has exactly one choice."""
        return len(self.choices) == 1

    @property
    def next(self) -> int:
        """The next state of a deterministic cell."""
        self._require_deterministic("next")
        return self.choices[0].next

    @property
    def outputs(self) -> str:
        """The outputs of a deterministic cell."""
        self._require_deterministic("outputs")
        return self.choices[0].outputs

    def _require_deterministic(self, what: str) -> None:
        if not self.is_deterministic:
            raise ValueError(f"cell has {len(self.choices)} choices; {what} is undefined")


@dataclass(frozen=True)
class FlowTable:
    """An immutable flow table. Implements SEMANTICS §1 and §2.

    ``rows`` maps a state to its row, and a row maps a column to its cell. A state
    without a row, and a column missing from a row, are both "unspecified".
    """

    name: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    reset: tuple[int, str]
    rows: dict[int, dict[str, Cell]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "inputs", tuple(self.inputs))
        object.__setattr__(self, "outputs", tuple(self.outputs))
        object.__setattr__(self, "reset", tuple(self.reset))
        self._validate()

    def _validate(self) -> None:
        n, m = len(self.inputs), len(self.outputs)
        if n < 1:
            raise ModelError("a flow table needs at least one input")
        if len(set(self.inputs)) != n:
            raise ModelError(f"input names must be unique, got {list(self.inputs)}")
        if len(set(self.outputs)) != m:
            raise ModelError(f"output names must be unique, got {list(self.outputs)}")
        _check_column(self.reset[1], n, "reset column")
        for state, row in self.rows.items():
            for column, cell in row.items():
                _check_column(column, n, f"column key of state {state}")
                _check_outputs(cell, m, state, column)

    def states(self) -> tuple[int, ...]:
        """Every state that has a row, in increasing order (SEMANTICS §1)."""
        return tuple(sorted(self.rows))

    def columns(self) -> tuple[str, ...]:
        """All ``2**n`` columns in lexicographic order (SEMANTICS §1)."""
        width = len(self.inputs)
        return tuple(format(k, f"0{width}b") for k in range(1 << width))

    def cell(self, state: int, column: str) -> Cell:
        """The cell at ``(state, column)``; the empty cell when unspecified."""
        return self.rows.get(state, {}).get(column, Cell())

    def is_stable(self, state: int, column: str) -> bool:
        """True when ``(state, column)`` is deterministic and self-holding."""
        cell = self.cell(state, column)
        return cell.is_deterministic and cell.next == state

    def adjacent(self, column: str) -> list[tuple[int, str]]:
        """Every single-bit neighbour of ``column``, bit index ascending."""
        return [
            (i, column[:i] + ("0" if column[i] == "1" else "1") + column[i + 1 :])
            for i in range(len(column))
        ]


def _check_column(column: str, width: int, what: str) -> None:
    """A column is ``width`` characters over ``{0, 1}``."""
    if len(column) != width or any(ch not in _BITS for ch in column):
        raise ModelError(f"{what} must be {width} characters over {{0,1}}, got {column!r}")


def _check_outputs(cell: Cell, width: int, state: int, column: str) -> None:
    """Every choice's outputs are exactly ``width`` characters (SEMANTICS §2)."""
    for choice in cell.choices:
        if len(choice.outputs) != width:
            raise ModelError(
                f"state {state} column {column!r}: outputs {choice.outputs!r} must be "
                f"{width} characters"
            )
