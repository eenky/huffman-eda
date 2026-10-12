"""Golden harness for SEMANTICS §9. PROTECTED (spec path, hash-locked)."""

import json
from pathlib import Path
from typing import Any

import pytest

HERE = Path(__file__).parent
CASES = sorted(p for p in HERE.iterdir() if p.is_dir() and (p / "table.yaml").exists())


def _sets(xs: Any) -> list[list[int]]:
    return [sorted(x) for x in xs]


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.name)
def test_golden_minimize(case: Path) -> None:
    io = pytest.importorskip("huffman_eda.io")
    mz = pytest.importorskip("huffman_eda.minimize")
    equiv = pytest.importorskip("huffman_eda.equiv")
    table = io.load_table(case / "table.yaml")
    want = json.loads((case / "expected.json").read_text())

    if want["precondition"] != "ok":
        with pytest.raises(mz.MinimizationError) as err:
            mz.check_precondition(table)
        assert list(err.value.rules) == want["precondition"]
        with pytest.raises(mz.MinimizationError):
            mz.minimize(table)
        return

    assert sorted(map(list, mz.incompatible_pairs(table))) == want["incompatible_pairs"]
    assert _sets(mz.maximal_compatibles(table)) == want["maximal_compatibles"]
    assert _sets(mz.prime_compatibles(table)) == want["prime_compatibles"]

    cover = mz.min_closed_cover(table)
    assert len(cover) == want["min_cover_size"]
    assert _sets(cover) in want["min_closed_covers"]
    assert mz.is_closed_cover(table, cover)

    for bad in want.get("not_closed", []):
        bad_cover = tuple(frozenset(c) for c in bad)
        assert not mz.is_closed_cover(table, bad_cover), bad
        with pytest.raises(ValueError):
            mz.reduce(table, bad_cover)

    red = want["reduced"]
    reduced = mz.reduce(table, tuple(frozenset(c) for c in red["cover"]))
    assert list(reduced.reset) == red["reset"]
    assert sorted(reduced.states()) == sorted(int(s) for s in red["rows"])
    m = len(table.outputs)
    for s, row in red["rows"].items():
        for column in reduced.columns():
            expected = io.parse_cell(row.get(column, "-"), int(s), m)
            assert reduced.cell(int(s), column) == expected, (s, column)

    assert equiv.implements(table, reduced).ok
    assert equiv.implements(table, mz.minimize(table)).ok
