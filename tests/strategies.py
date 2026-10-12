"""Hypothesis strategies for random flow tables (T301).

Every later property test draws its tables from here, so the generators are the one place
that knows how to build a table with a given structural guarantee. The three flags are
about SEMANTICS §5's rules, not about the shape of the file:

``normal``
    No FT004: every specified unstable entry settles straight into a stable entry, so no
    entry points at a specified entry that is still unstable. (An entry may be left
    unspecified, which is what keeps the generator always feasible.)
``primitive``
    Exactly one stable entry per row.
``complete``
    Every entry the SIC exploration can reach is specified, so FT003 and FT005 cannot
    fire, and the reset entry is specified and stable.

The guarantees are the contract: ``tests/test_strategies.py`` checks each against
``validate()``, and also checks that dropping the flag really does let the rule fire.
"""

from __future__ import annotations

import itertools

import hypothesis.strategies as st

from huffman_eda.model import Cell, Choice, FlowTable

__all__ = ["columns_for", "flow_tables"]

_OUTPUT_CHARS = "01-"


def columns_for(n_inputs: int) -> tuple[str, ...]:
    """Every column of an ``n_inputs`` table, in ``FlowTable.columns()`` order."""
    return tuple("".join(bits) for bits in itertools.product("01", repeat=n_inputs))


def flow_tables(
    n_inputs: int,
    n_outputs: int,
    max_states: int,
    *,
    normal: bool = False,
    primitive: bool = False,
    complete: bool = False,
) -> st.SearchStrategy[FlowTable]:
    """Random ``FlowTable``s with ``n_inputs``, ``n_outputs`` and at most ``max_states``.

    Every state gets a row, cells hold at most one choice, and the columns are the full
    ``2**n_inputs`` set. ``complete=True`` requires ``max_states >= 2**n_inputs``: a
    complete table needs a stable entry in every column.
    """
    if complete and max_states < 2**n_inputs:
        raise ValueError(
            f"complete=True needs one state per column: max_states={max_states} < "
            f"2**{n_inputs}={2**n_inputs}"
        )
    return _flow_tables(
        n_inputs, n_outputs, max_states, normal=normal, primitive=primitive, complete=complete
    )


@st.composite
def _flow_tables(
    draw: st.DrawFn,
    n_inputs: int,
    n_outputs: int,
    max_states: int,
    *,
    normal: bool,
    primitive: bool,
    complete: bool,
) -> FlowTable:
    columns = columns_for(n_inputs)
    lowest = len(columns) if complete else 1  # complete needs a state per column
    n_states = draw(st.integers(min_value=lowest, max_value=max_states))
    states = list(range(1, n_states + 1))
    outputs = st.text(alphabet=_OUTPUT_CHARS, min_size=n_outputs, max_size=n_outputs)

    if primitive:
        # A home column per state: the state is stable exactly there, so every row has
        # exactly one stable entry. The first columns are anchored to distinct states so
        # that (with complete) every column has something to settle into.
        stable: dict[str, set[int]] = {column: set() for column in columns}
        for index, state in enumerate(draw(st.permutations(states))):
            home = columns[index] if index < len(columns) else draw(st.sampled_from(columns))
            stable[home].add(state)
    else:
        # Per column, the states that are stable there. Complete needs at least one per
        # column so that nothing has to settle into an unspecified entry.
        minimum = 1 if complete else 0
        stable = {
            column: set(draw(st.sets(st.sampled_from(states), min_size=minimum)))
            for column in columns
        }

    rows: dict[int, dict[str, Cell]] = {}
    for state in states:
        row: dict[str, Cell] = {}
        for column in columns:
            settle_targets = sorted(stable[column])
            if state in stable[column]:
                row[column] = Cell((Choice(state, draw(outputs)),))
                continue
            if not complete and not draw(st.booleans()):
                continue  # unspecified: the cell stays empty (semantics: unspecified)
            # normal: an unstable entry may only point at a stable entry, so the column
            # needs one; without it the entry has to stay unspecified. An unstable entry
            # must not point at its own row, which would make it stable after all.
            targets = settle_targets if normal else [other for other in states if other != state]
            if not targets:
                continue
            row[column] = Cell((Choice(draw(st.sampled_from(targets)), draw(outputs)),))
        rows[state] = row

    if complete:
        # The walk has to start somewhere: pick a state that is stable somewhere.
        stable_somewhere = sorted({state for column in columns for state in stable[column]})
        reset_state = draw(st.sampled_from(stable_somewhere))
        reset_column = next(column for column in columns if reset_state in stable[column])
    else:
        reset_state = draw(st.sampled_from(states))
        reset_column = draw(st.sampled_from(columns))

    return FlowTable(
        name="rand",
        inputs=tuple(f"x{i}" for i in range(1, n_inputs + 1)),
        outputs=tuple(f"z{i}" for i in range(1, n_outputs + 1)),
        reset=(reset_state, reset_column),
        rows=rows,
    )
