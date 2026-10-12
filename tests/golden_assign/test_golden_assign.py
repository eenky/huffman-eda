"""Locked golden harness for SEMANTICS §10 (state assignment).

Listed in docs/spec_lock.json: change it only through the spec workflow, and never to make a
failing implementation pass. It asserts the whole documented surface of §10.8 per case, and
skips while §10's implementation has not landed — golden tests skip only while their target
module does not exist yet (AGENTS.md). Once `huffman_eda.assign` exists, every case here must
run and pass.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from huffman_eda.equiv import implements
from huffman_eda.io import load_table

ROOT = Path(__file__).parent
CASES = sorted(p for p in ROOT.iterdir() if (p / "table.yaml").exists())
NEEDED = (
    "AssignmentError",
    "LimitExceeded",
    "assign",
    "check_precondition",
    "critical_races",
    "decode",
    "defined_codes",
    "dichotomies",
    "encode",
    "excitation",
    "tracey",
)


def _module():
    """The §10 implementation, or a skip naming what is still missing."""
    try:
        module = importlib.import_module("huffman_eda.assign")
    except ModuleNotFoundError:
        pytest.skip("huffman_eda.assign is not landed yet; §10 arrives with T501-T503")
    missing = [name for name in NEEDED if not hasattr(module, name)]
    if missing:
        pytest.skip(f"huffman_eda.assign does not export {', '.join(missing)} yet")
    return module


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.name)
def test_golden_assign(case: Path) -> None:
    module = _module()
    table = load_table(case / "table.yaml")
    want = json.loads((case / "expected.json").read_text())

    assert want.get("source"), case
    assert isinstance(want.get("derivation"), list) and want["derivation"], case

    if want["precondition"] != "ok":
        with pytest.raises(module.AssignmentError) as info:
            module.check_precondition(table)
        assert list(info.value.rules) == want["precondition"], case
        return
    module.check_precondition(table)

    if "encoding" in want:
        codes = {int(state): int(code, 2) for state, code in want["encoding"].items()}
        encoded = module.encode(table, codes)
        got = [
            {"rule": d.rule, "state": d.state, "column": d.column, "path": list(d.path)}
            for d in module.critical_races(encoded)
        ]
        assert got == want["diagnostics"], case
        assert module.defined_codes(encoded), case

    if "min_state_variables" in want:
        assignment = module.tracey(table)
        variables = len(assignment.variables)
        assert variables == want["min_state_variables"], case
        cover = [[sorted(member[0]), sorted(member[1])] for member in assignment.variables]
        listed = [[[sorted(m[0]), sorted(m[1])] for m in c] for c in want["min_covers"]]
        assert cover in listed, case
        got_codes = {str(s): format(c, f"0{variables}b") for s, c in assignment.codes.items()}
        assert got_codes == want["codes"], case

        # §10.7: the assignment is race-free (no SA002; SA003 is a reported transient, not a
        # race) and its decoding implements the original.
        encoded = module.assign(table)
        assert not [d for d in module.critical_races(encoded) if d.rule == "SA002"], case
        assert module.excitation(encoded) is not None, case
        assert implements(table, module.decode(encoded)).ok, case
