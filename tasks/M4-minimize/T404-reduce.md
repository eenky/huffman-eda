# T404: Reduced table construction and `hfe minimize`

**Depends on:** T403  
**Owner:** agent

## May touch
src/huffman_eda/minimize/reduce.py, tests/test_reduce.py, src/huffman_eda/cli.py

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**

## Spec
All functions are those of SEMANTICS §9.8, in the package `huffman_eda.minimize`. Each checks §9.1 first and raises `MinimizationError` with the violated rule IDs.
Implement `reduce` (§9.6, including the canonical `choose` tie-break, transient outputs `-`, and
the reset rule) and `minimize`. Add `hfe minimize IN -o OUT`, which runs
`implements(original, reduced)` and refuses to write the output if it fails.

## Acceptance
- **Milestone gate:** `pytest tests/golden_minimize -rs` passes with 0 skipped.
- Property (§9.7): on 500 random tables satisfying §9.1 (`flow_tables(normal=True)`, then
  `assume` the precondition), `implements(T, minimize(T))` holds, as does
  `implements(T, reduce(T, K))` for the all-singletons cover K.
- `hfe minimize` exits 1 with the precondition rules on a non-normal table.
