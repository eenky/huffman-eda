"""Independent reference implementation of SEMANTICS §1-5 and §8.

Written from SEMANTICS.md alone. It must never import `huffman_eda`, and `huffman_eda`
must never import it (enforced by scripts/spec_policy.py). Only the reviewer identity may
change this file. It is deliberately simple and slow: clarity over speed.

Each `implemented` entry lists a SEMANTICS section the reference covers. Golden cases and
the differential test are checked only against implemented sections.
"""

from __future__ import annotations

import itertools
import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

IMPLEMENTED_SECTIONS = ("1", "2", "3", "4", "5", "8")

Choice = tuple[int, str]
Diag = tuple[str, str, int | None, str | None]


@dataclass
class RefTable:
    inputs: list[str]
    outputs: list[str]
    reset: tuple[int, str]
    rows: dict[int, dict[str, list[Choice]]]

    @property
    def n(self) -> int:
        return len(self.inputs)

    def columns(self) -> list[str]:
        return ["".join(b) for b in itertools.product("01", repeat=self.n)]

    def cell(self, s: int, c: str) -> list[Choice]:
        return self.rows.get(s, {}).get(c, [])

    def stable(self, s: int, c: str) -> bool:
        x = self.cell(s, c)
        return len(x) == 1 and x[0][0] == s

    def out(self, s: int, c: str) -> str:
        return self.cell(s, c)[0][1]


def _parse_cell(text: str, row: int) -> list[Choice]:
    text = text.strip()
    if text == "-":
        return []
    choices = set()
    for part in text.split("|"):
        target, _, outs = part.strip().partition(",")
        target = target.strip()
        m = re.fullmatch(r"\[\s*(\d+)\s*\]", target)
        state = int(m.group(1)) if m else int(target)
        if m and state != row:
            raise ValueError(f"bracketed target {state} in row {row}")
        choices.add((state, outs.strip()))
    return sorted(choices)


def load(path: Path) -> RefTable:
    d: Any = yaml.safe_load(path.read_text())
    rows = {
        int(s): {str(c): _parse_cell(str(v), int(s)) for c, v in (r or {}).items()}
        for s, r in d["rows"].items()
    }
    return RefTable(
        list(d["inputs"]), list(d["outputs"]), (int(d["reset"][0]), str(d["reset"][1])), rows
    )


# ---------------------------------------------------------------- §3 settle


def settle(t: RefTable, s: int, c: str) -> tuple[str, list[int], list[int]]:
    path, cur = [s], s
    while True:
        x = t.cell(cur, c)
        if not x:
            return "UNDEFINED", path, []
        if len(x) > 1:
            return "NONDET", path, []
        nxt = x[0][0]
        if nxt == cur:
            return "STABLE", path, []
        if nxt in path:
            return "OSCILLATION", path, path[path.index(nxt) :]
        path.append(nxt)
        cur = nxt


def _flip(c: str, i: int) -> str:
    return c[:i] + ("1" if c[i] == "0" else "0") + c[i + 1 :]


def _changes(seq: list[str]) -> int:
    vals = [v for v in seq if v != "-"]
    return sum(a != b for a, b in itertools.pairwise(vals))


# ---------------------------------------------------------------- §4 explore


def explore(t: RefTable) -> tuple[bool, list[tuple[int, str]], set[tuple[int, str]], list[Any]]:
    r, c0 = t.reset
    if r not in t.rows or not t.stable(r, c0):
        return False, [], set(), []
    stable = [(r, c0)]
    visited = {(r, c0)}
    transitions = []
    queue = deque([(r, c0)])
    while queue:
        s, c = queue.popleft()
        for i in range(t.n):
            c2 = _flip(c, i)
            res = settle(t, s, c2)
            transitions.append((s, c, c2, res))
            visited.update((p, c2) for p in res[1])
            if res[0] == "STABLE" and (res[1][-1], c2) not in stable:
                stable.append((res[1][-1], c2))
                queue.append((res[1][-1], c2))
    return True, sorted(stable), visited, transitions


# ---------------------------------------------------------------- §5 rules


def validate(t: RefTable) -> set[Diag]:
    d: set[Diag] = set()
    cols = t.columns()

    def det(s: int, c: str) -> bool:
        return len(t.cell(s, c)) == 1

    for s in t.rows:
        for c in cols:
            if len(t.cell(s, c)) > 1:
                d.add(("FT001", "error", s, c))
            if det(s, c) and not t.stable(s, c):
                if settle(t, s, c)[0] == "UNDEFINED":
                    d.add(("FT003", "error", s, c))
                nxt = t.cell(s, c)[0][0]
                if t.cell(nxt, c) and not t.stable(nxt, c):
                    d.add(("FT004", "warning", s, c))
            if t.stable(s, c) and "-" in t.out(s, c):
                d.add(("FT009", "warning", s, c))
        if not any(t.stable(s, c) for c in cols):
            d.add(("FT008", "warning", s, None))
    for c in cols:
        for s in t.rows:
            if det(s, c):
                kind, _, cycle = settle(t, s, c)
                if kind == "OSCILLATION":
                    d.add(("FT002", "error", min(cycle), c))

    ok, _, visited, transitions = explore(t)
    if not ok:
        d.add(("FT000", "error", t.reset[0], t.reset[1]))
        return d
    for s, c, c2, (kind, path, _) in transitions:
        if kind == "UNDEFINED" and path == [s]:
            d.add(("FT005", "error", s, c2))
        if kind == "STABLE":
            for j in range(len(t.outputs)):
                seq = [t.out(s, c)[j]] + [t.out(p, c2)[j] for p in path]
                if _changes(seq) > 1:
                    d.add(("FT007", "error", s, c2))
    for s in t.rows:
        for c in cols:
            if t.cell(s, c) and (s, c) not in visited:
                d.add(("FT006", "info", s, c))
    return d


# ---------------------------------------------------------------- §8 implements


def _incompatible(spec_out: str, impl_out: str) -> int | None:
    for j, (a, b) in enumerate(zip(spec_out, impl_out, strict=True)):
        if a != "-" and b != a:
            return j
    return None


def _hazard(t: RefTable, s: int, c: str, c2: str, path: list[int], j: int) -> bool:
    return _changes([t.out(s, c)[j]] + [t.out(p, c2)[j] for p in path]) > 1


def _cex(
    trace: list[str], kind: str, output: str | None = None, outcome: str | None = None
) -> dict[str, Any]:
    return {"trace": trace, "kind": kind, "output": output, "outcome": outcome}


def implements(spec: RefTable, impl: RefTable) -> tuple[bool, dict[str, Any] | None]:
    if spec.inputs != impl.inputs or spec.outputs != impl.outputs:
        raise ValueError("inputs/outputs differ")
    rs, c0 = spec.reset
    ri, ci = impl.reset
    if rs not in spec.rows or not spec.stable(rs, c0):
        return True, None
    if ci != c0 or ri not in impl.rows or not impl.stable(ri, ci):
        return False, _cex([], "RESET")
    j0 = _incompatible(spec.out(rs, c0), impl.out(ri, ci))
    if j0 is not None:
        return False, _cex([], "RESET", spec.outputs[j0])
    start = (rs, ri, c0)
    seen = {start}
    queue: deque[tuple[tuple[int, int, str], list[str]]] = deque([(start, [])])
    while queue:
        (ss, si, c), trace = queue.popleft()
        for i in range(spec.n):
            c2 = _flip(c, i)
            ks, ps, _ = settle(spec, ss, c2)
            if ks != "STABLE":
                continue
            ki, pi, _ = settle(impl, si, c2)
            tr = [*trace, c2]
            if ki != "STABLE":
                return False, _cex(tr, "IMPL_NOT_STABLE", outcome=ki)
            j = _incompatible(spec.out(ps[-1], c2), impl.out(pi[-1], c2))
            if j is not None:
                return False, _cex(tr, "OUTPUT_MISMATCH", spec.outputs[j])
            for j in range(len(spec.outputs)):
                if _hazard(impl, si, c, c2, pi, j) and not _hazard(spec, ss, c, c2, ps, j):
                    return False, _cex(tr, "HAZARD", spec.outputs[j])
            nxt = (ps[-1], pi[-1], c2)
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, tr))
    return True, None
