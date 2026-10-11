# SEMANTICS (normative, PROTECTED)

This document is the single source of truth for what the tools compute. If code, a task
file, and this document disagree, this document wins. Changes require a PR labeled
`spec-approved` from the repository owner. Sections 1 to 7 cover Milestones 1 and 2.
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

## 8. Reserved

| Section | Milestone | Topic |
|---|---|---|
| 8 | M3 | Behavioral equivalence and implementation relation |
| 9 | M4 | Compatibility, closed covers, reduced tables |
| 10 | M5 | Encoded tables, races, critical races |
| 11 | M6 | Gate netlist IR and ternary simulation |
| 12 | M7 | Hazard-free covers under SIC |
| 13 | M8 | HDL export and SVA properties |
