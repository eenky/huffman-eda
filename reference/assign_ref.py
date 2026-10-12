"""Independent reference for SEMANTICS §10 (state assignment).

Written from the §10 text alone, not from the implementation. Brute force over every injective
assignment and every candidate cover: obvious rather than fast, for tables of up to about 6
states. Never imports huffman_eda.

Where §10 makes a choice the text fixes it: an undefined transient is SA003 and not a race, the
all-zero state is state 1, and the minimum cover taken is the first in canonical order.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable, Mapping

from reference.huffman_ref import RefTable, validate

Dichotomy = tuple[frozenset[int], frozenset[int]]
Entry = tuple[str, str, bool]  # (next code, outputs, stable)
PRE = ("FT000", "FT001", "FT003", "FT004")


def violated_precondition(t: RefTable) -> list[str]:
    """§10.1: the rule IDs that make T ineligible, sorted ([] if eligible)."""
    return sorted({d[0] for d in validate(t)} & set(PRE))


def states(t: RefTable) -> list[int]:
    return sorted(t.rows)


def bits_of(code: int, k: int) -> str:
    return format(code, f"0{k}b")


def code_map(t: RefTable, assignment: Mapping[int, int], k: int) -> dict[int, str]:
    return {s: bits_of(assignment[s], k) for s in states(t)}


def encode(t: RefTable, assignment: Mapping[int, int], k: int) -> dict[str, dict[str, Entry]]:
    """§10.2: {code: {column: (next code, outputs, stable)}}; undefined codes have no key."""
    cd = code_map(t, assignment, k)
    out: dict[str, dict[str, Entry]] = {}
    for s in states(t):
        row: dict[str, Entry] = {}
        for c in t.columns():
            cell = t.cell(s, c)
            if not cell:
                continue
            nxt, outs = cell[0]
            if nxt == s:
                row[c] = (cd[s], outs, True)
            else:
                row[c] = (cd[nxt], "-" * len(t.outputs), False)
        out[cd[s]] = row
    return out


def defined_codes(t: RefTable, assignment: Mapping[int, int], k: int) -> frozenset[str]:
    return frozenset(code_map(t, assignment, k).values())


def races(
    t: RefTable, assignment: Mapping[int, int], k: int
) -> list[tuple[str, int, str, tuple[int, ...]]]:
    """§10.3: (rule, state, column, path) per diagnostic, sorted by (column, state, path)."""
    cd = code_map(t, assignment, k)
    by_code = {v: s for s, v in cd.items()}
    found: list[tuple[str, int, str, tuple[int, ...]]] = []
    for c in t.columns():
        for s in states(t):
            cell = t.cell(s, c)
            if not cell:
                continue
            tgt = cell[0][0]
            if tgt == s:
                continue
            a, b = cd[s], cd[tgt]
            diff = [i for i in range(k) if a[i] != b[i]]
            for r in range(1, len(diff)):
                for subset in itertools.combinations(diff, r):
                    y = list(a)
                    for i in subset:
                        y[i] = "1" if y[i] == "0" else "0"
                    via = "".join(y)
                    if via not in by_code:
                        found.append(("SA003", s, c, (int(a, 2), int(via, 2), int(b, 2))))
                        continue
                    here, seen = via, set()
                    while here in by_code and here not in seen:
                        seen.add(here)
                        u = by_code[here]
                        u_cell = t.cell(u, c)
                        if not u_cell or u_cell[0][0] == u:
                            break
                        here = cd[u_cell[0][0]]
                    if here != b:
                        found.append(("SA002", s, c, (int(a, 2), int(via, 2), int(b, 2))))
    found.sort(key=lambda x: (x[2], x[1], x[3]))
    return found


def race_free(t: RefTable, assignment: Mapping[int, int], k: int) -> bool:
    return not any(rule == "SA002" for rule, _, _, _ in races(t, assignment, k))


def assignments(t: RefTable, k: int) -> Iterable[dict[int, int]]:
    """Every injective assignment into k variables."""
    for codes in itertools.permutations(range(2**k), len(states(t))):
        yield {s: codes[i] for i, s in enumerate(states(t))}


def race_free_assignments(t: RefTable, k: int) -> list[dict[int, int]]:
    return [a for a in assignments(t, k) if race_free(t, a, k)]


def minimum_variables(t: RefTable) -> int:
    """§10.4 by brute force, over injective assignments with 1, 2, ... variables."""
    n = len(states(t))
    for k in range(1, n + 1):
        if 2**k < n:
            continue
        if race_free_assignments(t, k):
            return k
    raise AssertionError("one variable per state is always race-free")


# ------------------------------------------------------- dichotomies (§10.4, §10.5)


def d(left, right) -> Dichotomy:
    return (frozenset(left), frozenset(right))


def compatible(p: Dichotomy, q: Dichotomy) -> bool:
    return not (p[0] & q[1]) and not (p[1] & q[0])


def covers(p: Dichotomy, q: Dichotomy) -> bool:
    """§10.4, as an unordered pair, so both orientations of q are covered."""
    return (q[0] <= p[0] and q[1] <= p[1]) or (q[0] <= p[1] and q[1] <= p[0])


def seeds(t: RefTable) -> set[Dichotomy]:
    """§10.5 steps 1-2, with state 1 fixed to the all-zero code."""
    out = {d([a], [b]) for a, b in itertools.permutations(states(t), 2)}
    for c in t.columns():
        for s1, s3 in itertools.product(states(t), repeat=2):
            cell1, cell3 = t.cell(s1, c), t.cell(s3, c)
            if not cell1 or not cell3:
                continue
            s2, s4 = cell1[0][0], cell3[0][0]
            if s2 == s4 or (s1 == s2 and s3 == s4):
                continue
            out |= {
                d([s1, s2], [s3]),
                d([s1, s2], [s4]),
                d([s1], [s3, s4]),
                d([s2], [s3, s4]),
                d([s3], [s1, s2]),
                d([s4], [s1, s2]),
                d([s3, s4], [s1]),
                d([s3, s4], [s2]),
            }
    proper = {x for x in out if x[0] and x[1] and not (x[0] & x[1])}
    return {x for x in proper if 1 not in x[1]}


def prime_dichotomies(t: RefTable) -> set[Dichotomy]:
    """§10.5 step 2: unions of maximal pairwise-compatible sets of seeds."""
    seed_list = sorted(seeds(t), key=lambda x: (sorted(x[0]), sorted(x[1])))
    linked = {a: {b for b in seed_list if b != a and compatible(a, b)} for a in seed_list}
    cliques: list[list[Dichotomy]] = []

    def extend(current: list[Dichotomy], candidates: set[Dichotomy]) -> None:
        if not candidates:
            cliques.append(list(current))
            return
        for a in sorted(candidates, key=lambda x: (sorted(x[0]), sorted(x[1]))):
            extend([*current, a], {b for b in candidates if b in linked[a] and b != a})
            candidates = candidates - {a}

    extend([], set(seed_list))
    unions = {
        d(frozenset().union(*[s[i] for s in clique]), frozenset().union(*[s[j] for s in clique]))
        for clique in cliques
        for i, j in [(0, 1)]
    }
    return {p for p in unions if not any(q != p and covers(q, p) for q in unions)}


def cover_order(candidate: Iterable[Dichotomy]) -> list[tuple[tuple[int, ...], tuple[int, ...]]]:
    return [
        (tuple(sorted(m[0])), tuple(sorted(m[1])))
        for m in sorted(candidate, key=lambda x: (sorted(x[0]), sorted(x[1])))
    ]


def minimum_covers(t: RefTable) -> list[list[Dichotomy]]:
    """Every minimum cover, each canonically ordered, the list in canonical order."""
    seed_list = seeds(t)
    primes = sorted(prime_dichotomies(t), key=lambda x: (sorted(x[0]), sorted(x[1])))
    for size in range(1, len(primes) + 1):
        found = [
            list(combo)
            for combo in itertools.combinations(primes, size)
            if all(any(covers(p, s) for p in combo) for s in seed_list)
        ]
        if found:
            found.sort(key=cover_order)
            return found
    raise AssertionError("the uniqueness seeds alone need every state told apart")


def tracey(t: RefTable) -> tuple[dict[int, int], list[Dichotomy]]:
    """§10.5: the codes of the canonical-first minimum cover, and that cover."""
    cover = minimum_covers(t)[0]
    codes = {}
    for s in states(t):
        value = 0
        for i, member in enumerate(cover):
            value |= (1 if s in member[1] else 0) << i
        codes[s] = value
    return codes, cover


def decode(t: RefTable, assignment: Mapping[int, int], k: int) -> RefTable:
    """§10.6: read the codes back as a flow table."""
    rows: dict[int, dict[str, list[tuple[int, str]]]] = {}
    for s in states(t):
        row: dict[str, list[tuple[int, str]]] = {}
        for c in t.columns():
            cell = t.cell(s, c)
            if not cell:
                continue
            nxt, outs = cell[0]
            row[c] = [(nxt, outs if nxt == s else "-" * len(t.outputs))]
        rows[s] = row
    r, c0 = t.reset
    return RefTable(list(t.inputs), list(t.outputs), (r, c0), rows)
