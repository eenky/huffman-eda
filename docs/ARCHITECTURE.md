# Architecture

## IR levels

| Level | Module | Produced by | Checked by |
|---|---|---|---|
| L0 Flow table | `model.py` | `io.py` (YAML/JSON/Markdown) | `validate.py` rules |
| L1 Reduced flow table | `model.py` (same IR) | `minimize/` | `equiv.py` (L0 behavior oracle) |
| L2 Encoded table | `encoded.py` | `assign/` | race analysis + `equiv.py` on the decoded table |
| L3 Gate netlist | `netlist.py` | `synth/` | `ternary.py` vs L0 behavior |
| L4 HDL | `export/` | `export/` | cosimulation vs L0 behavior |

Every pass is a pure function from one IR to the next. Every check is independent of the
pass it checks: it must not import the pass's internals.

## Package layout (target)

```
src/huffman_eda/
  diagnostics.py      # contract (exists)
  model.py            # M1 T101
  io.py               # M1 T102, M2 T204
  semantics.py        # M1 T103: settle
  explore.py          # M1 T104
  rules/static.py     # M1 T105
  rules/dynamic.py    # M1 T106
  validate.py         # M1 T106
  gray.py, render.py  # M2 T201
  graph_export.py     # M2 T202
  cli.py              # M2 T203
  equiv.py            # M3
  minimize/           # M4
  encoded.py, assign/ # M5
  netlist.py, ternary.py   # M6
  synth/              # M7
  export/             # M8
tests/
  golden/             # PROTECTED reference cases
  strategies.py       # M3 T301: Hypothesis strategies for random tables
```

## Design rules

- The IR is immutable (frozen pydantic models / frozen dataclasses).
- The core performs no I/O. Only `io.py`, `render.py`, `graph_export.py`, `cli.py`, and
  `export/` touch files or the terminal.
- Output is deterministic: every set is sorted before it leaves a function.
- Algorithms with exponential worst cases (cycle covers, closed covers, prime implicants)
  take an explicit size limit and raise `LimitExceeded`. They never silently degrade.
