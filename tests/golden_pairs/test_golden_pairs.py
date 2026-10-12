"""Golden harness for SEMANTICS §8. PROTECTED (lives under tests/golden_pairs/)."""

import json
from pathlib import Path
from typing import Any

import pytest

HERE = Path(__file__).parent
CASES = sorted(p for p in HERE.iterdir() if p.is_dir() and (p / "a.yaml").exists())


def _check(result: Any, want: dict[str, Any]) -> None:
    assert result.ok is want["ok"]
    if want["counterexample"] is None:
        assert result.counterexample is None
    else:
        assert result.counterexample is not None
        assert result.counterexample.to_dict() == want["counterexample"]


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.name)
def test_golden_pair(case: Path) -> None:
    io = pytest.importorskip("huffman_eda.io")
    equiv = pytest.importorskip("huffman_eda.equiv")
    a = io.load_table(case / "a.yaml")
    b = io.load_table(case / "b.yaml")
    expected = json.loads((case / "expected.json").read_text())
    _check(equiv.implements(a, b), expected["implements_ab"])
    _check(equiv.implements(b, a), expected["implements_ba"])
    want_equiv = expected["implements_ab"]["ok"] and expected["implements_ba"]["ok"]
    assert equiv.equivalent(a, b) is want_equiv
