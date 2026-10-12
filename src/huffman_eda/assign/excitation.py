"""Excitation and output functions, and decoding. Implements SEMANTICS §10.6 (T503)."""

from __future__ import annotations

from dataclasses import dataclass, field

from huffman_eda.assign.encoded import EncodedTable
from huffman_eda.model import Cell, Choice, FlowTable

__all__ = ["ExcitationTable", "decode", "excitation"]

#: One row of the excitation table: the next-state variable bits and the output bits. A None is
#: a don't-care — a stable entry's transient outputs are not observable (SEMANTICS §10.6).
ExcitationRow = tuple[tuple[int | None, ...], tuple[int | None, ...]]


@dataclass(frozen=True, slots=True)
class ExcitationTable:
    """§10.6: ``y_i(x, y)`` and ``z_j(x, y)``, with the don't-cares left as None."""

    name: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    state_variables: tuple[str, ...]
    entries: dict[str, dict[str, ExcitationRow]] = field(default_factory=dict)


def _bits(value: int, width: int) -> tuple[int, ...]:
    """``value`` as ``width`` bits, least significant first."""
    return tuple((value >> index) & 1 for index in range(width))


def excitation(encoded: EncodedTable) -> ExcitationTable:
    """§10.6: the excitation and output functions of an encoded table.

    Every code is covered, including the ones no state carries: those rows are don't-care, and
    completing them is §11's business.
    """
    rows: dict[str, dict[str, ExcitationRow]] = {}
    for value in range(2**encoded.bits):
        code = format(value, f"0{encoded.bits}b")
        rows[code] = {}
        for column in encoded.columns:
            entry = encoded.entries.get(code, {}).get(column)
            if entry is None:
                rows[code][column] = ((None,) * encoded.bits, (None,) * len(encoded.outputs))
            elif entry[2]:
                outputs = tuple(int(bit) for bit in entry[1])
                rows[code][column] = (_bits(value, encoded.bits), outputs)
            else:
                target = int(entry[0], 2)
                rows[code][column] = (_bits(target, encoded.bits), (None,) * len(encoded.outputs))
    return ExcitationTable(
        name=encoded.name,
        inputs=encoded.inputs,
        outputs=encoded.outputs,
        state_variables=tuple(f"y{index}" for index in range(encoded.bits)),
        entries=rows,
    )


def decode(encoded: EncodedTable) -> FlowTable:
    """§10.6: read the codes back as a flow table.

    Transient outputs come back as ``-``: they are not observables (SEMANTICS §8.2), so
    ``implements(table, decode(encode(table, codes)))`` is the assertion §10.7 makes.
    """
    by_code = {code: state for state, code in encoded.codes.items()}
    blank = "-" * len(encoded.outputs)
    rows: dict[int, dict[str, Cell]] = {}
    for state in encoded.states:
        row: dict[str, Cell] = {}
        for column in encoded.columns:
            entry = encoded.entries.get(encoded.codes[state], {}).get(column)
            if entry is None:
                continue
            target, outputs, stable = entry
            choice = Choice(next=by_code[target], outputs=outputs if stable else blank)
            row[column] = Cell(choices=(choice,))
        rows[state] = row
    return FlowTable(
        name=encoded.name,
        inputs=encoded.inputs,
        outputs=encoded.outputs,
        reset=(by_code[encoded.reset[0]], encoded.reset[1]),
        rows=rows,
    )
