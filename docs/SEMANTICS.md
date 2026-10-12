# SEMANTICS (normative, PROTECTED)

This document is the single source of truth for what the tools compute. If code, a task
file, and this document disagree, this document wins. Changes require a PR labeled
`spec-approved` from the repository owner. Sections 1 to 8 cover Milestones 1 to 3.
Sections for later milestones are added by that milestone's spec task.

## 1. Notation

- A flow table has `n >= 1` primary inputs `inputs[0..n-1]` and `m >= 0` primary outputs.
- A **column** is a string of `n` characters over `{0,1}`. Character `i` is the value of
  `inputs[i]`, so the leftmost character is `inputs[0]`.
- `adj(c, i)` is column `c` with character `i` flipped. Columns `c` and `c'` are
  adjacent iff they differ in exactly one character (Hamming distance 1).
- States are positive integers. `rows` maps a state to its row. A state may be referenced
  as a next state without having a row. Such a state's entries are all unspecified.
- A **total state** or **entry** is a pair `(s, c)`. `cell(s, c)` is the cell at that
  entry. It is the empty cell if `s` has no row or the row omits `c`.
- A **cell** is a finite set of **choices** `(next, outputs)`, where `outputs` is a
  string of `m` characters over `{0,1,-}`.
  - *unspecified*: zero choices
  - *deterministic*: exactly one choice; `next(s,c)` denotes its next state
  - *nondeterministic*: two or more choices
- `(s, c)` is **stable** iff `cell(s, c)` is deterministic and `next(s, c) = s`.

## 2. File format

YAML (canonical) or JSON with the same schema:

```yaml
name: example            # string
inputs: [x1, x2]         # n >= 1 unique names
outputs: [z]             # m >= 0 unique names
reset: [1, "00"]         # [state, column]
rows:
  1: {"00": "[1],0", "01": "2,-"}
  2: {"00": "1,-", "01": "[2],1", "11": "-"}
```

- Row keys are integers. In JSON they are strings of decimal digits.
- Column keys **must be quoted strings**, because unquoted `01` is the integer 1 in YAML.
  The loader rejects any non-string column key with a `ParseError`.
- An omitted column is unspecified. The cell `"-"` is unspecified.

Cell grammar (whitespace allowed between tokens):

```
cell    := '-' | choice ( '|' choice )*
choice  := target ( ',' outs )?
target  := '[' INT ']' | INT
outs    := exactly m characters from {0,1,-}
```

- `outs` is required iff `m > 0` and forbidden iff `m = 0`.
- A bracketed target must equal the row's state, otherwise it is a `ParseError`.
  Brackets are only a notation check: stability is always derived from section 1.
- Identical choices are deduplicated.
- Any violation is a `ParseError` carrying the row, column, and offending text.

## 3. settle(T, s, c)

Follows the column-`c` successor function from state `s`. This is how the circuit's
internal state evolves while the input is held at `c` (fundamental mode).

```
path := (s); cur := s
loop:
  x := cell(cur, c)
  if x unspecified:        return UNDEFINED(path)        # stopped at cur
  if x nondeterministic:   return NONDET(path)           # stopped at cur
  t := next(cur, c)
  if t == cur:             return STABLE(path)           # final = cur
  if t in path:            return OSCILLATION(path, cycle = path[index(t):])
  path := path + (t); cur := t
```

`path` lists distinct states in visit order, starting with `s`. If `(s,c)` is stable,
the result is `STABLE((s,))`.

## 4. explore(T)

Enumerates the behavior of `T` under single-input-change (SIC) fundamental mode from
`reset = (r, c0)`.

- If `r` has no row or `(r, c0)` is not stable: `reset_ok = false`, and all sets below
  are empty.
- Otherwise do a breadth-first search over stable total states, starting at `(r, c0)`.
  The queue is FIFO, and the bit index `i` is visited in increasing order. For each
  dequeued stable `(s, c)` and each `i`:
  - `c' := adj(c, i)` and `R := settle(T, s, c')`
  - record `Transition(src_state=s, src_col=c, dst_col=c', result=R)`
  - add `(p, c')` to `visited` for every `p` in `R.path`
  - if `R` is `STABLE` with final `t` and `(t, c')` has not been seen, enqueue it
- `stable` = every stable total state ever enqueued, including the reset.
- `visited` = the reset entry, plus every entry added above.
- `transitions` = every recorded transition, in recording order.

## 5. Rules

Each rule yields `Diagnostic(rule, severity, state, column)`. Rules FT001 to FT004,
FT008, and FT009 are **static**: they consider every entry, reachable or not. Rules
FT000 and FT005 to FT007 are **dynamic**: they come from `explore`, and only FT000 runs
when `reset_ok` is false.

| Rule | Sev | Location | Fires when |
|---|---|---|---|
| FT000 | error | (r, c0) | the reset row is missing or `(r, c0)` is not stable |
| FT001 | error | (s, c) | `cell(s,c)` is nondeterministic, for any `s` with a row |
| FT002 | error | (min(cycle), c) | for column `c`, let `f_c(s) = next(s,c)` over the deterministic entries of states with rows; once per cycle of length >= 2 of `f_c` |
| FT003 | error | (s, c) | `(s,c)` is deterministic and unstable, and `settle(T,s,c)` is `UNDEFINED` |
| FT004 | warning | (s, c) | `(s,c)` is deterministic and unstable with `t = next(s,c)`, and `cell(t,c)` is specified and `(t,c)` is not stable (a non-normal table) |
| FT005 | error | (s, c') | a transition's `R` is `UNDEFINED` with `R.path == (s,)`, meaning the environment can apply input `c'` in state `s` and the entry is unspecified |
| FT006 | info | (s, c) | `(s,c)` is specified, `s` has a row, and `(s,c)` is not in `visited` |
| FT007 | error | (s, c') | for a transition with `R = STABLE(p_0..p_k)` and some output `j`, the sequence `out_j(s,c), out_j(p_0,c'), ..., out_j(p_k,c')` with `-` removed changes value more than once |
| FT008 | warning | (s, null) | a state with a row has no stable entry in any of the `2^n` columns |
| FT009 | warning | (s, c) | `(s,c)` is stable and some output character is `-` |

Notes:
- An oscillation reaches neither FT003 nor FT004's "unspecified" branch. It is reported
  by FT002 only, plus FT004 on its unstable members.
- `out_j(s,c)` in FT007 uses the source's single choice, since the source is stable.

## 6. Reports, ordering, exit codes

- `validate(T) -> Report`: static rules plus dynamic rules, deduplicated on
  `(rule, severity, state, column)` and sorted by `Diagnostic.key()`
  (rule, severity, state with null first, column with null first).
- `hfe validate --json` prints `Report.to_dict()`.
- Exit codes for every `hfe` command:
  - `0`: no `error` diagnostics
  - `1`: at least one `error` diagnostic
  - `2`: usage error, file not found, or `ParseError`

## 7. Display

- Columns are displayed in reflected Gray-code order: column `k` is the `n`-bit binary
  form (MSB first) of `k XOR (k >> 1)`. For `n = 2` the order is `00, 01, 11, 10`.
- Rows are in increasing state order. A stable entry is shown as `[s],outs`.
- All machine-readable output (JSON, golden comparisons) uses numeric state order and
  lexicographic column order. Gray order is used for human display only.

## 8. Implementation relation

`implements(spec, impl)` decides whether flow table `impl` correctly implements flow table
`spec` under SIC fundamental mode. Every later pass is checked with it: `spec` is the
original table and `impl` is the pass output.

### 8.1 Preconditions

`spec` and `impl` must have identical `inputs` and identical `outputs` (names and order).
Otherwise `implements` raises `ValueError`. That is a usage error, not a counterexample.

### 8.2 Observables

- The observable behavior is the output vector at each **stable** total state reached
  after reset and after each input change.
- Transient outputs are not observables. They enter the relation only through the
  hazard clause (8.4, check 3).
- Output compatibility: `impl_out` is compatible with `spec_out` iff for every bit `j`,
  either `spec_out[j] = '-'` or `impl_out[j] = spec_out[j]`. An `impl` value of `-`
  where `spec` specifies a value is **incompatible**.

### 8.3 Don't-cares resolve per context

A `-` in `spec` constrains each visit independently. `impl` may produce different values
for the same `spec` entry on different runs, depending on history. This is a trace check:
it compares each input sequence's run of `spec` with the run of `impl`. There is no
requirement for a global state mapping. (Since `spec` is deterministic on every step the
relation checks, trace containment and simulation coincide here. The only real choice is
whether don't-cares are resolved per context or globally, and this section chooses per
context. State minimization needs this: one `spec` state may be covered by several
reduced states.)

### 8.4 Definition

If `explore(spec).reset_ok` is false, `implements` holds vacuously.

Otherwise, let `(rs, c0)` be the spec's reset and `(ri, ci)` the impl's reset. Then:

**Reset check.** Fails with kind `RESET` and trace `[]` if `ci != c0`, or `impl`'s reset
is missing or not stable, or the impl reset outputs are incompatible with the spec reset
outputs.

**Product exploration.** Breadth-first search over pairs `((ss, c), (si, c))` of stable
total states, starting from the reset pair. The queue is FIFO, and bit index `i` is
visited in increasing order. For each dequeued pair and each `i`:

- `c' := adj(c, i)`, `RS := settle(spec, ss, c')`, `RI := settle(impl, si, c')`
- If `RS` is not `STABLE`, the step is unconstrained: no check, no enqueue.
- Otherwise run these checks in order. The first one that fails ends the search:
  1. `IMPL_NOT_STABLE`: `RI` is not `STABLE`.
  2. `OUTPUT_MISMATCH`: the outputs of `(RI.final, c')` are incompatible with those of
     `(RS.final, c')`.
  3. `HAZARD`: impl's transition `(si, c) -> c'` violates FT007 (SEMANTICS §5) for some
     output `j`, while spec's transition `(ss, c) -> c'` does not violate FT007 for that
     same `j`. That is, impl may not introduce a dynamic output hazard that the spec does
     not already have.
- If every check passes, enqueue `((RS.final, c'), (RI.final, c'))` if it has not been
  seen.

`implements` holds iff no check fails. Because the search is breadth-first in that fixed
order, the first failure found has a shortest trace, and it is unique.

Consequences (normative, and tested):
- `implements(T, T)` holds for every table `T`, including tables with FT007 violations.
- `implements` is not symmetric. `equivalent(a, b)` means `implements(a, b)` and
  `implements(b, a)`.
- Renaming states preserves `implements`.

### 8.5 Result

```
EquivResult(ok: bool, counterexample: Counterexample | None)
Counterexample(trace: tuple[str, ...],   # columns applied after reset, in order
               kind: str,                # RESET | IMPL_NOT_STABLE | OUTPUT_MISMATCH | HAZARD
               output: str | None,       # lowest-index offending output name
                                         # (OUTPUT_MISMATCH, HAZARD, RESET-by-outputs)
               outcome: str | None)      # RI.kind name for IMPL_NOT_STABLE, else None
Counterexample.to_dict() -> {"trace": [...], "kind": ..., "output": ..., "outcome": ...}
```

### 8.6 Golden pairs

`tests/golden_pairs/<case>/{a.yaml, b.yaml, expected.json}`. `expected.json` holds
`implements_ab` = `implements(a, b)` and `implements_ba` = `implements(b, a)`, each as
`{"ok": bool, "counterexample": Counterexample.to_dict() | null}`.

### 8.7 Consequences for M3 tasks

- T302: this section replaces the `InputStep` signature in the task file.
- T303: Mutant verdicts are fixed by class, independently of `equiv.py`:
  - (a) Output flips of a specified bit on a reachable stable entry, including the reset
    entry: must be killed.
  - (b) Shortcut redirects (`t' = t`): `implements(T, M)` must hold. `implements(M, T)` is
    not asserted.
  - (c) Distinguishing redirects (the outputs of `(t', c')` are incompatible with
    `(t, c')`): must be killed.
  - (d) All other redirects: counted and reported, never gated.

  Every gated verdict must match. There is no percentage threshold.

## 9. State minimization

`minimize(T)` returns a flow table with as few states as possible that implements `T` in the
sense of §8. This is the classical theory of incompletely specified machines (compatibles,
closed covers, Grasselli–Luccio prime compatibles), restricted here so that it is sound for
*settling*. A flow table settles through several steps in one column, where a clocked machine
would take a single step per input.

### 9.1 Precondition

`minimize` and everything in this section apply only to a table `T` with:
- `explore(T).reset_ok` (no FT000),
- no FT001 (every cell has at most one choice),
- no FT003 and no FT004. Together these say `T` is **normal**: every specified, unstable
  entry `(s,c)` leads in one step to a stable entry `(next(s,c), c)`.

Otherwise each function in this section raises `MinimizationError`, whose `rules` attribute
is the sorted tuple of the violated rule IDs.

Normality is necessary, not a convenience. The golden case `non_normal_rejected` contains a
non-normal table that has a closed cover (§9.4) whose reduced table (§9.6) never reaches a
stable reset state. Under the precondition, every next state has a row, so the state set
is `S = states(T)`, the states with rows.

### 9.2 Compatibility

- States `p` and `q` are **output-compatible** iff, for every column `c` where both `(p,c)` and
  `(q,c)` are stable, their outputs agree on every bit where both specify a value. Only stable
  entries are compared, because transient outputs are not observables (§8.2) and the reduced
  table does not keep them (§9.6).
- The set `I` of **incompatible pairs** is the least set of unordered pairs `{p,q}`, `p ≠ q`, that
  contains every output-incompatible pair and is closed under implication. That is, `{p,q} ∈ I`
  whenever, for some column `c`, both `(p,c)` and `(q,c)` are specified, `next(p,c) ≠ next(q,c)`,
  and `{next(p,c), next(q,c)} ∈ I`. Compute it by iterating to a fixpoint.
- A **compatible** is a non-empty set `C ⊆ S` that contains no pair in `I`. Every singleton is a
  compatible, and every subset of a compatible is a compatible.

### 9.3 Implied sets, class sets, maximal and prime compatibles

- Implied set: `N(C,c) = { next(x,c) : x ∈ C, (x,c) specified }`.
- Class set: `Γ(C) = { N(C,c) : c a column, |N(C,c)| ≥ 2, N(C,c) ⊄ C }`.
- A **maximal compatible** is a compatible not strictly contained in another compatible.
- A **prime compatible** is a compatible `C` for which no compatible `C' ⊋ C` has
  `Γ(C') ⊆ Γ(C)` (plain set inclusion of class sets). Every maximal compatible is prime.

### 9.4 Closed covers

A set `K` of compatibles is a **closed cover** iff:
1. every state of `S` is in some member of `K`, and
2. for every `C ∈ K` and column `c` with `|N(C,c)| ≥ 2`, some `D ∈ K` satisfies `N(C,c) ⊆ D`.

A **minimum closed cover** is a closed cover of least size. At least one minimum closed
cover consists only of prime compatibles. `min_closed_cover` returns such a cover, and when
several exist, any one of them is correct. Members of a cover may overlap, and sometimes
must: see the golden case `overlap_required`.

### 9.5 Canonical order

Sets of states are ordered by comparing their sorted state tuples lexicographically. Every
function returns collections of compatibles in this order. In `reduce`, the cover member at
position `i` (1-based) becomes reduced state `i`.

### 9.6 The reduced table `reduce(T, K)`

`K` must be a closed cover of `T`. The result has the same inputs and outputs as `T`. Write
`C_i` for the `i`-th member of `K` in canonical order. Then:

- `choose(C, N) = C` if `N ⊆ C`. Otherwise it is the first member of `K`, in canonical order,
  that contains `N`. Such a member exists by closure when `|N| ≥ 2`, and by covering when
  `|N| = 1`.
- For each `C_i` and column `c`, let `N = N(C_i, c)` and `D = choose(C_i, N)`:
  - if `N` is empty, the entry is unspecified;
  - if `D = C_i`, the entry is **stable**: `[i]`, where output bit `j` is the specified value
    of `out_j(x,c)` among the members `x ∈ C_i` with `(x,c)` stable, or `-` if none
    specifies it. Output-compatibility makes this value unique;
  - otherwise the entry is `index(D)`, with every output bit `-`.
- Reset: let `r` be the reset state and `c0` the reset column. Start from the first member
  containing `r`, apply `C ← choose(C, N(C, c0))` until `C` stops changing, and use
  `(index(C), c0)` as the reset.

**Decision: transient outputs are `-`.** §8 observes only stable outputs, and a `-` can never
create a §8 `HAZARD`, since FT007 counts only specified values. Assigning transient outputs is
deferred to the hazard-free logic step (§12), where the standard rule applies: a transient
between two equal stable outputs must hold that value, and one between different stable
outputs may change only once. Both are determined by stable outputs alone, so this decision
loses nothing.

### 9.7 Correctness (normative consequence, tested)

For every `T` satisfying §9.1 and every closed cover `K` of `T`: `implements(T, reduce(T, K))`.

Proof sketch, for a single settle of `T` from stable `(s, c_prev)` into column `c`, where
the reduced table is in a class `C ∋ s`:
1. By normality, `T` ends at `t = next(s,c)`, which is stable in `c`, and every implied set in
   column `c` consists of states stable in `c`.
2. The reduced table visits `X_1 = choose(C, N(C,c)), X_2, ...`, with each `X_{k+1} ⊇ N(X_k, c)`.
   The members of `N(X_k, c)` are stable, so each maps to itself, giving
   `N(X_{k+1}, c) ⊇ N(X_k, c)`. These sets increase within `S`, so after fewer than `|S|`
   steps some `X_{k+1} ⊇ N(X_{k+1}, c)`, and `choose` keeps it. The reduced table is then
   stable.
3. `t ∈ N(C,c)`, and `t` stays in every later implied set, so the final class contains `t`.
   Its stable output agrees with `t`'s output on every bit `t` specifies (§9.2).
4. Every reduced transient output is `-`, so no `HAZARD` can occur. The same argument from `r`
   in `c0` justifies the reset.

### 9.8 API (module `huffman_eda.minimize`)

All functions check §9.1 first. Functions that are exponential in the worst case take a
keyword `limit` and raise `LimitExceeded` when it is exceeded.

```
class MinimizationError(ValueError)      # .rules: tuple[str, ...]
class LimitExceeded(RuntimeError)
check_precondition(table) -> None
incompatible_pairs(table) -> frozenset[tuple[int, int]]        # (p, q) with p < q
implied(table, states: frozenset[int], column: str) -> frozenset[int]
class_set(table, states: frozenset[int]) -> frozenset[frozenset[int]]
maximal_compatibles(table, *, limit: int = 10_000) -> tuple[frozenset[int], ...]
prime_compatibles(table, *, limit: int = 10_000) -> tuple[frozenset[int], ...]
is_closed_cover(table, cover) -> bool
min_closed_cover(table, *, limit: int = 100_000) -> tuple[frozenset[int], ...]
reduce(table, cover) -> FlowTable                              # raises ValueError if cover not closed
minimize(table, *, limit: int = 100_000) -> FlowTable          # reduce(table, min_closed_cover(table))
```

### 9.9 Golden cases

`tests/golden_minimize/<case>/{table.yaml, expected.json}`. The `expected.json` file holds one
of the following:
- for a table that fails §9.1: `{"precondition": ["FT004", ...], ...}`;
- otherwise: `"precondition": "ok"`, `incompatible_pairs`, `maximal_compatibles`,
  `prime_compatibles`, `min_cover_size`, `min_closed_covers` (every minimum closed cover made of
  prime compatibles, each in canonical order), and `reduced` (the `cover`, `rows` in cell
  notation, and `reset` of `reduce(T, cover)` for one of those covers). It may also hold
  `not_closed`: covers of `S` that are not closed, for which `is_closed_cover` must return
  false and `reduce` must raise `ValueError`.

Every case also carries `derivation` and `source`.

## 10+. Reserved

| Section | Milestone | Topic |
|---|---|---|
| 10 | M5 | Encoded tables, races, critical races |
| 11 | M6 | Gate netlist IR and ternary simulation |
| 12 | M7 | Hazard-free covers under SIC |
| 13 | M8 | HDL export and SVA properties |
