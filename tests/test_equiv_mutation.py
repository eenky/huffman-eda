"""Mutation tests for the oracle and `hfe equiv` (T303).

Verdicts are fixed by **class**, before the oracle is asked, using only the table and
`settle` (SEMANTICS §8.7). The test never learns the expected answer from the code under
test, and there is no percentage threshold: every gated verdict must match exactly.

For mutants of a complete, normal table `T`:

(a) flip of one **specified** output bit on a reachable stable entry (the reset entry is one
    of them) — must be killed;
(b) shortcut redirect, `t' = t`, where `t` is the stable state the entry settles to —
    `implements(T, M)` must hold, and `implements(M, T)` is not asserted;
(c) distinguishing redirect, the outputs of `(t', c')` incompatible with `(t, c')` — must be
    killed;
(d) every other redirect — counted and printed, never gated, because such a mutant can be
    genuinely equivalent (the equivalent-mutant problem).

The random tables are complete and **normal**. A shortcut (class (b)) needs the entry's
settling path to be longer than one hop, and `normal` means "no FT004" (SEMANTICS §5), which
excludes exactly those chains — so no class (b) mutant can be drawn from them. Class (b) is
covered by the two chain fixtures below instead, which are deliberately non-normal; they ride
in every batch, so the class-presence assertions cannot go vacuous.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import hypothesis.strategies as st
from hypothesis import HealthCheck, given, settings
from strategies import flow_tables
from typer.testing import CliRunner

from huffman_eda.cli import app
from huffman_eda.equiv import implements
from huffman_eda.explore import explore
from huffman_eda.io import dump_table, parse_cell
from huffman_eda.model import Cell, Choice, FlowTable
from huffman_eda.semantics import Outcome, settle

SLOW = settings(
    # Five batches of BATCH tables is the 300 the task asks for, in chunks Hypothesis can
    # generate: a single 300-table draw is refused as too large to produce.
    max_examples=5,
    deadline=None,
    database=None,
    suppress_health_check=[
        HealthCheck.too_slow,
        HealthCheck.filter_too_much,
        HealthCheck.large_base_example,
    ],
)

RUNNER = CliRunner()
N_INPUTS, N_OUTPUTS, MAX_STATES = 2, 2, 5
BATCH = 60
# Class (a) and (c) are gated on normal tables, which is the domain SEMANTICS §5 keeps clean
# of FT004 warnings; class (b) needs a chain and so comes from the fixtures instead.
TABLES = flow_tables(N_INPUTS, N_OUTPUTS, MAX_STATES, normal=True, complete=True)

KILLED, ACCEPTED, UNGATED = "killed", "accepted", "ungated"


def build(
    rows: dict[int, dict[str, str]],
    *,
    reset: tuple[int, str] = (1, "0"),
    inputs: tuple[str, ...] = ("x",),
    outputs: tuple[str, ...] = ("z",),
    name: str = "t",
) -> FlowTable:
    """Build a table from §2 cell strings, so the fixtures read like the YAML files."""
    return FlowTable(
        name=name,
        inputs=inputs,
        outputs=outputs,
        reset=reset,
        rows={
            state: {
                column: parse_cell(text, state, len(outputs), column)
                for column, text in row.items()
            }
            for state, row in rows.items()
        },
    )


@dataclass(frozen=True)
class Mutant:
    """A mutated copy of a table, with the §8.7 class that fixes its expected verdict."""

    table: FlowTable
    operator: str
    klass: str
    verdict: str
    entry: tuple[int, str]
    detail: str


def _incompatible(spec_outputs: str, impl_outputs: str) -> bool:
    """§8.2 at one entry: some bit spec specifies that impl answers differently."""
    return any(
        spec_bit != "-" and impl_bit != spec_bit
        for spec_bit, impl_bit in zip(spec_outputs, impl_outputs, strict=True)
    )


def mutants(table: FlowTable) -> Iterator[Mutant]:
    """Every mutant with its class, decided here rather than by the oracle."""
    reachable = explore(table)

    for state, column in reachable.stable:
        cell = table.cell(state, column)
        for index, bit in enumerate(cell.outputs):
            if bit == "-":
                continue  # (a) only specified bits are flipped
            flipped = (
                cell.outputs[:index] + ("0" if bit == "1" else "1") + cell.outputs[index + 1 :]
            )
            yield Mutant(
                _with_cell(table, state, column, Cell((Choice(state, flipped),))),
                "flip",
                "a",
                KILLED,
                (state, column),
                f"{table.outputs[index]} {bit}->{flipped[index]}",
            )

    for state, column in reachable.visited:
        cell = table.cell(state, column)
        if not cell.is_deterministic or cell.next == state:
            continue
        settled = settle(table, state, column)
        if settled.kind is not Outcome.STABLE:
            continue  # normal tables always settle, but a class needs a defined `t`
        for target in sorted(
            other
            for other in table.states()
            if other != cell.next and table.is_stable(other, column)
        ):
            if target == settled.final:
                klass, verdict = "b", ACCEPTED
            elif _incompatible(
                table.cell(settled.final, column).outputs, table.cell(target, column).outputs
            ):
                klass, verdict = "c", KILLED
            else:
                klass, verdict = "d", UNGATED
            yield Mutant(
                _with_cell(table, state, column, Cell((Choice(target, cell.outputs),))),
                "redirect",
                klass,
                verdict,
                (state, column),
                f"{cell.next} -> {target}",
            )


def _with_cell(table: FlowTable, state: int, column: str, cell: Cell) -> FlowTable:
    rows = {other: dict(row) for other, row in table.rows.items()}
    rows[state][column] = cell
    return FlowTable(
        name=f"{table.name}_mutant",
        inputs=table.inputs,
        outputs=table.outputs,
        reset=table.reset,
        rows=rows,
    )


# --- the gate ----------------------------------------------------------------


@SLOW
@given(tables=st.lists(TABLES, min_size=BATCH - 2, max_size=BATCH - 2))
def test_every_gated_verdict_matches(tables: list[FlowTable]) -> None:
    """Every class (a)/(b)/(c) verdict must match; class (d) is only counted."""
    # Classes (a) and (c) come from the drawn tables; class (b) cannot, so the two chain
    # fixtures ride in every batch and the presence assertions below stay non-vacuous. (A
    # settling chain is rare: ~3.8% of random tables, and ~10% of 60-table batches contain no
    # redirect class at all — they are tables whose reachable entries all self-loop.)
    batch = [*tables, build(VIA), build(VIA_DISAGREEING)]
    seen: Counter[str] = Counter()
    ungated: Counter[str] = Counter()
    for table in batch:
        for mutant in mutants(table):
            seen[mutant.klass] += 1
            ok = implements(table, mutant.table).ok
            if mutant.verdict is UNGATED:
                ungated["accepted" if ok else "killed"] += 1
                continue
            assert ok is (mutant.verdict is ACCEPTED), (
                f"class ({mutant.klass}) {mutant.operator} at {mutant.entry} "
                f"({mutant.detail}) came back {'accepted' if ok else 'killed'} but §8.7 says "
                f"{mutant.verdict}"
            )

    for klass in ("a", "b", "c"):
        assert seen[klass] > 0, f"no class ({klass}) mutant was generated"
    print(
        f"\n§8.7 over {sum(seen.values())} mutants: "
        f"a={seen['a']} b={seen['b']} c={seen['c']} d={seen['d']} "
        f"(class (d): {ungated['killed']} killed, {ungated['accepted']} accepted)"
    )


# --- the classes on one hand-built table -------------------------------------


# The unstable entry (2,"0") reaches the stable (3,"0") through the via state 4, so its
# redirects are a shortcut (straight to 3) and an unclassified one (to the stable 1).
VIA = {
    1: {"0": "[1],0", "1": "2,-"},
    2: {"0": "4,-", "1": "[2],-"},
    3: {"0": "[3],0", "1": "[3],0"},
    4: {"0": "3,-", "1": "[4],-"},
}

# The same table with z = 1 at (3,"0"), which makes the redirect to 1 distinguishing.
VIA_DISAGREEING = {
    1: {"0": "[1],0", "1": "2,-"},
    2: {"0": "4,-", "1": "[2],-"},
    3: {"0": "[3],1", "1": "[3],0"},
    4: {"0": "3,-", "1": "[4],-"},
}


def _classify(table: FlowTable, klass: str, detail: str) -> Mutant:
    found = [
        mutant for mutant in mutants(table) if mutant.klass == klass and mutant.detail == detail
    ]
    assert found, f"no class ({klass}) mutant {detail} in this table"
    return found[0]


def test_a_shortcut_is_accepted_and_a_plain_redirect_is_ungated() -> None:
    table = build(VIA)
    shortcut = _classify(table, "b", "4 -> 3")
    unclassified = _classify(table, "d", "4 -> 1")
    assert _classify(table, "a", "z 0->1"), 'the (1,"0") output flip is a class (a) mutant'
    assert shortcut.verdict is ACCEPTED
    assert implements(table, shortcut.table).ok is True
    assert unclassified.verdict is UNGATED
    # Ungated means "not asserted either way": this one happens to be killed, which is
    # permitted but never required.
    assert implements(table, unclassified.table).ok is False


def test_a_distinguishing_redirect_is_killed() -> None:
    """Control: the same redirect against a disagreeing output at t becomes class (c)."""
    table = build(VIA_DISAGREEING)
    distinguishing = _classify(table, "c", "4 -> 1")
    assert distinguishing.verdict is KILLED
    assert _classify(table, "b", "4 -> 3"), "the shortcut is still a shortcut"
    assert implements(table, distinguishing.table).ok is False


# --- hfe equiv ---------------------------------------------------------------


def _write(tmp_path: Path, name: str, table: FlowTable) -> Path:
    path = tmp_path / name
    path.write_text(dump_table(table), encoding="utf-8")
    return path


TOGGLE = {1: {"0": "[1],0", "1": "2,-"}, 2: {"0": "1,-", "1": "[2],1"}}
GLITCH = {1: {"0": "[1],0", "1": "3,1"}, 2: {"0": "1,-", "1": "[2],1"}, 3: {"0": "1,-", "1": "2,0"}}


def test_equiv_reports_a_holding_relation(tmp_path: Path) -> None:
    spec = _write(tmp_path, "a.yaml", build(TOGGLE))
    impl = _write(tmp_path, "b.yaml", build(TOGGLE))
    result = RUNNER.invoke(app, ["equiv", str(spec), str(impl)])
    assert result.exit_code == 0, result.output
    assert "holds" in result.output
    assert "equivalent: yes" in result.output


def test_equiv_prints_the_counterexample_and_exits_one(tmp_path: Path) -> None:
    spec = _write(tmp_path, "a.yaml", build(TOGGLE))
    impl = _write(tmp_path, "b.yaml", build(GLITCH))
    result = RUNNER.invoke(app, ["equiv", str(spec), str(impl)])
    assert result.exit_code == 1, result.output
    assert "fails" in result.output
    assert "trace: 1" in result.output
    assert "kind:  HAZARD" in result.output
    assert "output: z" in result.output


def test_equiv_reports_the_error_kinds(tmp_path: Path) -> None:
    spec = _write(tmp_path, "a.yaml", build(TOGGLE))
    oscillating = _write(
        tmp_path,
        "b.yaml",
        build({1: {"0": "[1],0", "1": "2,0"}, 2: {"0": "1,0", "1": "1,0"}}),
    )
    result = RUNNER.invoke(app, ["equiv", str(spec), str(oscillating)])
    assert result.exit_code == 1
    assert "kind:  IMPL_NOT_STABLE" in result.output
    assert "outcome: OSCILLATION" in result.output


def test_equiv_reports_a_reset_counterexample(tmp_path: Path) -> None:
    spec = _write(tmp_path, "a.yaml", build(TOGGLE))
    impl = _write(tmp_path, "b.yaml", build(TOGGLE, reset=(1, "1")))
    result = RUNNER.invoke(app, ["equiv", str(spec), str(impl)])
    assert result.exit_code == 1
    assert "kind:  RESET" in result.output
    assert "<empty> (the reset itself)" in result.output


def test_equiv_exits_two_on_mismatched_io(tmp_path: Path) -> None:
    spec = _write(tmp_path, "a.yaml", build(TOGGLE))
    impl = _write(tmp_path, "b.yaml", build(TOGGLE, inputs=("y",)))
    result = RUNNER.invoke(app, ["equiv", str(spec), str(impl)])
    assert result.exit_code == 2
    assert "identical inputs and outputs" in result.output


def test_equiv_exits_two_on_a_parse_error(tmp_path: Path) -> None:
    spec = _write(tmp_path, "a.yaml", build(TOGGLE))
    broken = tmp_path / "broken.yaml"
    broken.write_text(
        "name: t\ninputs: [x]\noutputs: [z]\nreset: [1, 0]\nrows: {}\n", encoding="utf-8"
    )
    result = RUNNER.invoke(app, ["equiv", str(spec), str(broken)])
    assert result.exit_code == 2
    assert "reset column" in result.output
