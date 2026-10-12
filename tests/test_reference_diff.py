"""Differential test: production vs the independent reference. PROTECTED (hash-locked).

1. The reference must reproduce every golden expectation. A wrong golden case fails here,
   whoever wrote it.
2. Production must agree with the reference on seeded random tables and on single-cell
   mutants of them, for every section in reference.IMPLEMENTED_SECTIONS.

Fully deterministic: fixed seeds, no Hypothesis.
"""

from __future__ import annotations

import itertools
import json
import random
import re
from pathlib import Path

import pytest

from huffman_eda.equiv import implements
from huffman_eda.explore import explore
from huffman_eda.io import load_table
from huffman_eda.minimize import (
    MinimizationError,
    check_precondition,
    incompatible_pairs,
    is_closed_cover,
    maximal_compatibles,
    min_closed_cover,
    minimize,
    prime_compatibles,
    reduce,
)
from huffman_eda.model import Cell, Choice, FlowTable
from huffman_eda.validate import validate
from reference import huffman_ref as ref
from reference import minimize_ref as mref

ROOT = Path(__file__).parent
GOLDEN = sorted(p for p in (ROOT / "golden").iterdir() if (p / "table.yaml").exists())
PAIRS = sorted(p for p in (ROOT / "golden_pairs").iterdir() if (p / "a.yaml").exists())
MINIMIZE = sorted((ROOT / "golden_minimize").glob("*/table.yaml"))
N_TABLES = 600
SEED = 20261011


def _diag(d: dict[str, object]) -> tuple[object, ...]:
    return (d["rule"], d["severity"], d["state"], d["column"])


@pytest.mark.parametrize("case", GOLDEN, ids=lambda p: p.name)
def test_reference_reproduces_golden(case: Path) -> None:
    t = ref.load(case / "table.yaml")
    want = json.loads((case / "expected.json").read_text())
    assert ref.validate(t) == {_diag(d) for d in want["diagnostics"]}
    assert ref.explore(t)[1] == sorted((s, c) for s, c in want["stable_reachable"])


@pytest.mark.parametrize("case", PAIRS, ids=lambda p: p.name)
def test_reference_reproduces_golden_pairs(case: Path) -> None:
    a, b = ref.load(case / "a.yaml"), ref.load(case / "b.yaml")
    want = json.loads((case / "expected.json").read_text())
    for key, (s, i) in (("implements_ab", (a, b)), ("implements_ba", (b, a))):
        ok, cex = ref.implements(s, i)
        assert ok is want[key]["ok"]
        assert cex == want[key]["counterexample"]


def _random_yaml(rng: random.Random, shape: tuple[int, int, int] | None = None) -> str:
    n, m, ns = shape or (rng.randint(1, 3), rng.randint(0, 2), rng.randint(1, 5))
    cols = ["".join(b) for b in itertools.product("01", repeat=n)]
    rows: dict[int, dict[str, str]] = {}
    for s in range(1, ns + 1):
        row: dict[str, str] = {}
        for c in cols:
            x = rng.random()
            if x < 0.12:
                continue
            if x < 0.2:
                row[c] = "-"
                continue
            choices = []
            for _ in range(2 if rng.random() < 0.04 else 1):
                nxt = rng.randint(1, ns + 1) if rng.random() < 0.7 else s
                outs = "".join(rng.choice("01-") for _ in range(m))
                tgt = f"[{s}]" if nxt == s else str(nxt)
                choices.append(tgt + ("," + outs if m else ""))
            row[c] = "|".join(choices)
        rows[s] = row
    s0, c0 = rng.randint(1, ns), rng.choice(cols)
    if rng.random() < 0.85:
        outs = "".join(rng.choice("01") for _ in range(m))
        rows[s0][c0] = f"[{s0}]" + ("," + outs if m else "")
    lines = [
        "name: r",
        "inputs: [" + ", ".join(f"x{i}" for i in range(n)) + "]",
        "outputs: [" + ", ".join(f"z{j}" for j in range(m)) + "]",
        f'reset: [{s0}, "{c0}"]',
        "rows:",
    ]
    for s, row in rows.items():
        cells = ", ".join(f'"{c}": "{v}"' for c, v in row.items())
        lines.append(f"  {s}: {{{cells}}}")
    return "\n".join(lines) + "\n"


def _mutate(rng: random.Random, text: str) -> str:
    spans = [m.span(1) for m in re.finditer(r'": "([^"]*)"', text)]
    if not spans:
        return text
    a, b = rng.choice(spans)
    found = re.search(r"outputs: \[(.*)\]", text)
    outs_m = found.group(1) if found else ""
    m = len([o for o in outs_m.split(",") if o.strip()])
    ns = len(re.findall(r"^  \d+:", text, flags=re.M))
    new = str(rng.randint(1, ns)) + (
        "," + "".join(rng.choice("01-") for _ in range(m)) if m else ""
    )
    return text[:a] + new + text[b:]


def test_production_agrees_with_reference(tmp_path: Path) -> None:
    rng = random.Random(SEED)
    pa, pb = tmp_path / "a.yaml", tmp_path / "b.yaml"
    for k in range(N_TABLES):
        text = _random_yaml(rng)
        pa.write_text(text)
        t, rt = load_table(pa), ref.load(pa)
        got = {(d.rule, d.severity, d.state, d.column) for d in validate(t).diagnostics}
        assert got == ref.validate(rt), f"validate differs on table {k}:\n{text}"
        assert sorted(explore(t).stable) == ref.explore(rt)[1], f"explore differs:\n{text}"

        pb.write_text(_mutate(rng, text))
        try:
            u = load_table(pb)
        except ValueError:
            continue
        ru = ref.load(pb)
        for spec, impl, rspec, rimpl in ((t, u, rt, ru), (u, t, ru, rt)):
            res = implements(spec, impl)
            ok, cex = ref.implements(rspec, rimpl)
            got_cex = res.counterexample.to_dict() if res.counterexample else None
            assert (res.ok, got_cex) == (ok, cex), (
                f"implements differs:\n{text}\n---\n{pb.read_text()}"
            )


# ---------------------------------------------------------------- §9 (minimization)


@pytest.mark.parametrize("table_path", MINIMIZE, ids=lambda p: p.parent.name)
def test_reference_reproduces_golden_minimize(table_path: Path) -> None:
    t = ref.load(table_path)
    want = json.loads((table_path.parent / "expected.json").read_text())
    if want["precondition"] != "ok":
        assert mref.violated_precondition(t) == want["precondition"]
        return
    assert mref.violated_precondition(t) == []

    def sets(xs: list[frozenset[int]]) -> list[list[int]]:
        return [sorted(x) for x in xs]

    assert sorted(map(list, mref.incompatible_pairs(t))) == want["incompatible_pairs"]
    assert sets(mref.maximal_compatibles(t)) == want["maximal_compatibles"]
    assert sets(mref.prime_compatibles(t)) == want["prime_compatibles"]
    covers = mref.min_closed_covers(t)
    assert [sets(k) for k in covers] == want["min_closed_covers"]
    assert len(covers[0]) == want["min_cover_size"]
    for bad in want.get("not_closed", []):
        assert not mref.is_closed_cover(t, [frozenset(c) for c in bad]), bad
        with pytest.raises(ValueError):
            mref.reduce(t, [frozenset(c) for c in bad])
    red = mref.reduce(t, [frozenset(c) for c in want["reduced"]["cover"]])
    assert list(red.reset) == want["reduced"]["reset"]
    for s, row in want["reduced"]["rows"].items():
        for column in red.columns():
            text = row.get(column)
            cell = red.cell(int(s), column)
            if text is None:
                assert cell == []
            else:
                nxt, _, outs = text.partition(",")
                assert cell == [(int(nxt.strip("[]")), outs)], (s, column)
    assert ref.implements(t, red)[0]


def _random_normal(rng: random.Random) -> ref.RefTable:
    n, m, ns = rng.randint(1, 2), rng.randint(1, 2), rng.randint(2, 5)
    cols = ["".join(b) for b in itertools.product("01", repeat=n)]
    stable = {c: [s for s in range(1, ns + 1) if rng.random() < 0.45] for c in cols}
    rows: dict[int, dict[str, list[tuple[int, str]]]] = {s: {} for s in range(1, ns + 1)}
    for c in cols:
        for s in range(1, ns + 1):
            alphabet = "01" if s in stable[c] else "01-"
            outs = "".join(rng.choice(alphabet) for _ in range(m))
            if s in stable[c]:
                rows[s][c] = [(s, outs)]
            elif stable[c] and rng.random() < 0.8:
                rows[s][c] = [(rng.choice(stable[c]), outs)]
    s0, c0 = rng.randint(1, ns), rng.choice(cols)
    rows[s0][c0] = [(s0, "".join(rng.choice("01") for _ in range(m)))]
    return ref.RefTable([f"x{i}" for i in range(n)], [f"z{j}" for j in range(m)], (s0, c0), rows)


def test_reference_minimization_is_sound() -> None:
    """§9.7 on the reference itself: every minimum cover and the singleton cover."""
    rng = random.Random(SEED + 9)
    checked = 0
    while checked < 150:
        t = _random_normal(rng)
        if mref.violated_precondition(t):
            continue
        checked += 1
        singletons = [frozenset([s]) for s in mref.states(t)]
        for cover in [*mref.min_closed_covers(t), singletons]:
            ok, cex = ref.implements(t, mref.reduce(t, cover))
            assert ok, (t.rows, t.reset, cover, cex)


# ------------------------------------------------- §9 production vs the reference


def _to_production(t: ref.RefTable) -> FlowTable:
    """The same table as production sees it: built from the reference's structure."""
    return FlowTable(
        name="r",
        inputs=tuple(t.inputs),
        outputs=tuple(t.outputs),
        reset=tuple(t.reset),
        rows={
            s: {
                c: Cell(tuple(Choice(nxt, outs) for nxt, outs in t.cell(s, c)))
                for c in t.columns()
                if t.cell(s, c)
            }
            for s in mref.states(t)
        },
    )


def _production_shape(t: FlowTable) -> tuple[object, dict[int, dict[str, object]]]:
    """A table's behaviour as data, so production and the reference compare directly."""
    cells = {
        s: {
            c: tuple((choice.next, choice.outputs) for choice in t.cell(s, c).choices)
            for c in t.columns()
            if t.cell(s, c).choices
        }
        for s in t.states()
    }
    return tuple(t.reset), cells


def _reference_shape(t: ref.RefTable) -> tuple[object, dict[int, dict[str, object]]]:
    """The reference's table in the same shape."""
    cells = {
        s: {c: tuple(t.cell(s, c)) for c in t.columns() if t.cell(s, c)} for s in mref.states(t)
    }
    return tuple(t.reset), cells


def _mutate_one_cell(rng: random.Random, t: ref.RefTable) -> None:
    """A single-change mutant: one cell's target, outputs, or presence, and nothing else."""
    places = [(s, c) for s in mref.states(t) for c in t.columns() if t.cell(s, c)]
    if not places:
        return
    s, c = rng.choice(places)
    nxt, outs = t.cell(s, c)[0]
    which = rng.random()
    if which < 0.4:
        t.rows[s][c] = [(rng.randint(1, max(mref.states(t))), outs)]
    elif which < 0.8 and outs:
        j = rng.randrange(len(outs))
        t.rows[s][c] = [(nxt, outs[:j] + rng.choice("01-") + outs[j + 1 :])]
    else:
        del t.rows[s][c]


@pytest.mark.parametrize("mutant", [False, True], ids=["random", "single-change-mutant"])
def test_production_agrees_with_reference_on_minimization(mutant: bool) -> None:
    """§9: production and the reference agree on every eligible table, verdict included.

    Seeded, no Hypothesis, same generator as the reference's own soundness check. The
    comparison covers the eligibility verdict, the incompatibility set, maximal and prime
    compatibles, the minimum cover, `reduce` on every cover either side calls minimal, and
    the reduced tables cell by cell.
    """
    rng = random.Random(SEED + (23 if mutant else 22))
    checked = 0
    for _ in range(600):
        if checked >= 60:
            break
        t = _random_normal(rng)
        if mutant:
            _mutate_one_cell(rng, t)
        table = _to_production(t)

        rules = mref.violated_precondition(t)
        try:
            check_precondition(table)
        except MinimizationError as error:
            assert list(error.rules) == rules, (t.rows, t.reset)
            continue
        else:
            assert rules == [], (t.rows, t.reset)
        checked += 1

        context = (t.rows, t.reset)
        assert incompatible_pairs(table) == mref.incompatible_pairs(t), context
        assert list(maximal_compatibles(table)) == mref.maximal_compatibles(t), context
        assert list(prime_compatibles(table)) == mref.prime_compatibles(t), context

        covers = mref.min_closed_covers(t)
        cover = min_closed_cover(table)
        assert len(cover) == len(covers[0]), context
        assert list(cover) in covers, context
        assert is_closed_cover(table, cover), context

        singletons = [frozenset([s]) for s in mref.states(t)]
        for each in [*covers, cover, singletons]:
            assert is_closed_cover(table, each) == mref.is_closed_cover(t, each), context
            assert _production_shape(reduce(table, each)) == _reference_shape(
                mref.reduce(t, each)
            ), (context, each)

        for member in covers[0]:
            smaller = [c for c in covers[0] if c != member]
            assert is_closed_cover(table, smaller) == mref.is_closed_cover(t, smaller), context

        assert _production_shape(minimize(table)) == _reference_shape(mref.reduce(t, cover)), (
            context
        )
