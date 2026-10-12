"""Independent reference for SEMANTICS §9 (state minimization).

Brute force over all subsets: obvious rather than fast, for tables of up to about 8 states.
Never imports huffman_eda.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable

from reference.huffman_ref import RefTable, validate

Cls = frozenset[int]


def violated_precondition(t: RefTable) -> list[str]:
    """§9.1: the rule IDs that make T ineligible, sorted ([] if eligible)."""
    return sorted({d[0] for d in validate(t)} & {"FT000", "FT001", "FT003", "FT004"})


def states(t: RefTable) -> list[int]:
    return sorted(t.rows)


def _next(t: RefTable, s: int, c: str) -> int | None:
    x = t.cell(s, c)
    return x[0][0] if x else None


def _output_compatible(t: RefTable, p: int, q: int) -> bool:
    for c in t.columns():
        if t.stable(p, c) and t.stable(q, c):
            for a, b in zip(t.out(p, c), t.out(q, c), strict=True):
                if "-" not in (a, b) and a != b:
                    return False
    return True


def incompatible_pairs(t: RefTable) -> set[tuple[int, int]]:
    """§9.2: least set containing output conflicts, closed under implication."""
    pairs = list(itertools.combinations(states(t), 2))
    bad = {(p, q) for p, q in pairs if not _output_compatible(t, p, q)}
    changed = True
    while changed:
        changed = False
        for p, q in pairs:
            if (p, q) in bad:
                continue
            for c in t.columns():
                a, b = _next(t, p, c), _next(t, q, c)
                if a is not None and b is not None and a != b and (min(a, b), max(a, b)) in bad:
                    bad.add((p, q))
                    changed = True
                    break
    return bad


def compatibles(t: RefTable) -> list[Cls]:
    bad = incompatible_pairs(t)
    s = states(t)
    return [
        frozenset(c)
        for r in range(1, len(s) + 1)
        for c in itertools.combinations(s, r)
        if not any(pair in bad for pair in itertools.combinations(c, 2))
    ]


def implied(t: RefTable, cls: Cls, c: str) -> Cls:
    """§9.3 N(C, c)."""
    return frozenset(n for x in cls if (n := _next(t, x, c)) is not None)


def class_set(t: RefTable, cls: Cls) -> set[Cls]:
    """§9.3 Γ(C)."""
    return {n for c in t.columns() if len(n := implied(t, cls, c)) >= 2 and not n <= cls}


def maximal_compatibles(t: RefTable) -> list[Cls]:
    comp = compatibles(t)
    return canonical(c for c in comp if not any(c < d for d in comp))


def prime_compatibles(t: RefTable) -> list[Cls]:
    comp = compatibles(t)
    return canonical(
        c for c in comp if not any(c < d and class_set(t, d) <= class_set(t, c) for d in comp)
    )


def canonical(classes: Iterable[Cls]) -> list[Cls]:
    """§9.5 order: by sorted state tuple."""
    return sorted(set(classes), key=lambda c: tuple(sorted(c)))


def is_closed_cover(t: RefTable, cover: Iterable[Cls]) -> bool:
    """§9.4."""
    k = list(cover)
    if set().union(*k) != set(states(t)):
        return False
    for cls in k:
        for c in t.columns():
            n = implied(t, cls, c)
            if len(n) >= 2 and not any(n <= d for d in k):
                return False
    return True


def min_closed_covers(t: RefTable) -> list[list[Cls]]:
    """Every minimum closed cover made of prime compatibles, each in canonical order."""
    primes = prime_compatibles(t)
    for size in range(1, len(states(t)) + 1):
        found = [
            canonical(k) for k in itertools.combinations(primes, size) if is_closed_cover(t, k)
        ]
        if found:
            return sorted(found, key=lambda k: [tuple(sorted(c)) for c in k])
    raise AssertionError("the singleton cover is always closed")


def reduce(t: RefTable, cover: Iterable[Cls]) -> RefTable:
    """§9.6."""
    k = canonical(cover)
    if not is_closed_cover(t, k):
        raise ValueError("not a closed cover")
    index = {cls: i + 1 for i, cls in enumerate(k)}

    def choose(cls: Cls, n: Cls) -> Cls:
        return cls if n <= cls else next(d for d in k if n <= d)

    m = len(t.outputs)
    rows: dict[int, dict[str, list[tuple[int, str]]]] = {}
    for cls in k:
        row: dict[str, list[tuple[int, str]]] = {}
        for c in t.columns():
            n = implied(t, cls, c)
            if not n:
                continue
            d = choose(cls, n)
            if d != cls:
                row[c] = [(index[d], "-" * m)]
                continue
            bits = []
            for j in range(m):
                vals = {t.out(x, c)[j] for x in cls if t.stable(x, c)} - {"-"}
                if len(vals) > 1:
                    raise AssertionError("output-compatibility violated")
                bits.append(vals.pop() if vals else "-")
            row[c] = [(index[cls], "".join(bits))]
        rows[index[cls]] = row
    r, c0 = t.reset
    cls = next(d for d in k if r in d)
    for _ in range(len(k) + 1):
        d = choose(cls, implied(t, cls, c0))
        if d == cls:
            return RefTable(list(t.inputs), list(t.outputs), (index[cls], c0), rows)
        cls = d
    raise AssertionError("reset did not stabilise (is the table normal?)")
