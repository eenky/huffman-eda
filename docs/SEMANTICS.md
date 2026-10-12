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

## 9+. Reserved

| Section | Milestone | Topic |
|---|---|---|
| 9 | M4 | Compatibility, closed covers, reduced tables |
| 10 | M5 | Encoded tables, races, critical races |
| 11 | M6 | Gate netlist IR and ternary simulation |
| 12 | M7 | Hazard-free covers under SIC |
| 13 | M8 | HDL export and SVA properties |
