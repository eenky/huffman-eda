# T106: Dynamic rules FT000, FT005–FT007, validate()

**Depends on:** T104, T105  
**Owner:** agent

## Goal
Implement the dynamic rules and the `validate()` entry point (SEMANTICS §5–6).

## May touch
src/huffman_eda/rules/dynamic.py, src/huffman_eda/validate.py, tests/test_rules_dynamic.py

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**

## Spec
- `dynamic_rules(table, result: ExploreResult) -> list[Diagnostic]`
- `validate(table) -> Report`, which uses `Report.build`.
- FT007 checks monotonicity per output bit after removing `-`. The message names the
  output signal and the source column.

## Acceptance
- **Milestone gate:** `pytest tests/test_golden.py -rs` passes with **0 skipped**.
- Unit tests for FT000 (missing reset row; unstable reset), and FT007 with m = 2 where only
  one output is non-monotonic.

## Out of scope
CLI (T203).
