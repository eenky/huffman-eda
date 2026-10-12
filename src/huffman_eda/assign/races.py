"""Races and critical races. Implements SEMANTICS §10.3 (T501).

A transition that changes several state variables races. It is critical when the settled state
depends on the order the variables change in, and merely undefined (SA003) when some order passes
through a code no state carries — that code's behaviour is a don't-care, not a mistake.
"""

from __future__ import annotations

import itertools

from huffman_eda.assign.encoded import EncodedTable
from huffman_eda.diagnostics import Diagnostic

__all__ = ["critical_races"]

_BLANK = "-"


def _flip(code: str, positions: tuple[int, ...]) -> str:
    """``code`` with the bits at ``positions`` inverted."""
    bits = list(code)
    for index in positions:
        bits[index] = "1" if bits[index] == "0" else "0"
    return "".join(bits)


def critical_races(encoded: EncodedTable) -> list[Diagnostic]:
    """§10.3: the SA002 and SA003 diagnostics, sorted by (column, state, path).

    Each carries ``state`` (the source state) and ``column``, and its ``path`` holds code values
    rather than states: the unstable code, the intermediate code that order passes through, and
    the transition's target code.
    """
    by_code = {code: state for state, code in encoded.codes.items()}
    found: list[Diagnostic] = []
    for column in encoded.columns:
        for state in encoded.states:
            entry = encoded.entries.get(encoded.codes[state], {}).get(column)
            if entry is None or entry[2]:
                continue
            unstable, target = encoded.codes[state], entry[0]
            differing = [i for i in range(encoded.bits) if unstable[i] != target[i]]
            for size in range(1, len(differing)):
                for subset in itertools.combinations(differing, size):
                    via = _flip(unstable, subset)
                    path = (int(unstable, 2), int(via, 2), int(target, 2))
                    if via not in by_code:
                        found.append(
                            Diagnostic(
                                rule="SA003",
                                severity="warning",
                                state=state,
                                column=column,
                                message=(
                                    f"transient through undefined code {via}: "
                                    f"state {state} column {column!r} settles nowhere"
                                ),
                                path=path,
                            )
                        )
                        continue
                    landing, seen = via, set()
                    while landing in by_code and landing not in seen:
                        seen.add(landing)
                        step = encoded.entries[landing].get(column)
                        if step is None or step[2]:
                            break
                        landing = step[0]
                    if landing != target:
                        found.append(
                            Diagnostic(
                                rule="SA002",
                                severity="error",
                                state=state,
                                column=column,
                                message=(
                                    f"critical race: state {state} column {column!r} settles in "
                                    f"{landing} through {via}, not in {target}"
                                ),
                                path=path,
                            )
                        )
    found.sort(key=lambda diagnostic: (diagnostic.column, diagnostic.state, diagnostic.path))
    return found
