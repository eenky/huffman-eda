"""Golden-reference harness. PROTECTED: agents must not edit this file.

Tests skip until the modules they need exist. Milestone 1 is complete only when
`pytest tests/test_golden.py -rs` reports zero skips.
"""

import json
from pathlib import Path
from typing import Any

import pytest

GOLDEN = Path(__file__).parent / "golden"
CASES = sorted(p for p in GOLDEN.iterdir() if p.is_dir())


def _key(d: dict[str, Any]) -> tuple[str, str, int, str]:
    state = -1 if d["state"] is None else d["state"]
    column = "" if d["column"] is None else d["column"]
    return (d["rule"], d["severity"], state, column)


def _expected(case: Path) -> dict[str, Any]:
    return json.loads((case / "expected.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.name)
def test_golden_diagnostics(case: Path) -> None:
    io = pytest.importorskip("huffman_eda.io")
    validate = pytest.importorskip("huffman_eda.validate")
    table = io.load_table(case / "table.yaml")
    report = validate.validate(table)
    got = sorted(d.key() for d in report.diagnostics)
    want = sorted(_key(d) for d in _expected(case)["diagnostics"])
    assert got == want


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.name)
def test_golden_stable_reachable(case: Path) -> None:
    io = pytest.importorskip("huffman_eda.io")
    explore = pytest.importorskip("huffman_eda.explore")
    table = io.load_table(case / "table.yaml")
    result = explore.explore(table)
    got = sorted((s, c) for s, c in result.stable)
    want = sorted((s, c) for s, c in _expected(case)["stable_reachable"])
    assert got == want
