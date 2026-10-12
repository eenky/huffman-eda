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
from huffman_eda.validate import validate
from reference import huffman_ref as ref

ROOT = Path(__file__).parent
GOLDEN = sorted(p for p in (ROOT / "golden").iterdir() if (p / "table.yaml").exists())
PAIRS = sorted(p for p in (ROOT / "golden_pairs").iterdir() if (p / "a.yaml").exists())
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
