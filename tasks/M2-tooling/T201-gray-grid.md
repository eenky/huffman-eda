# T201: Gray order and grid renderer

**Depends on:** T102  
**Owner:** agent

## Goal
Human-readable flow table display per SEMANTICS §7.

## May touch
src/huffman_eda/gray.py, src/huffman_eda/render.py, tests/test_gray.py, tests/test_render.py, tests/snapshots/**

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**

## Spec
- `gray_columns(n) -> list[str]` for any n >= 1.
- `render_text(table) -> str`: plain-text grid, the deterministic snapshot target.
- `render_rich(table) -> rich.table.Table`: stable entries in bold, unspecified as `-`,
  nondeterministic choices joined with ` | `.

## Acceptance
- `gray_columns(2) == ["00","01","11","10"]`; for n in 1..6, consecutive columns
  (including wraparound) differ in exactly one bit and all 2^n appear.
- Snapshot tests of `render_text` for every golden case, stored under `tests/snapshots/`.
