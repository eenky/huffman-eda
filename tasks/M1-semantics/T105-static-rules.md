# T105: Static rules FT001–FT004, FT008, FT009

**Depends on:** T103  
**Owner:** agent

## Goal
Implement the static rules of SEMANTICS §5.

## May touch
src/huffman_eda/rules/__init__.py, src/huffman_eda/rules/static.py, tests/test_rules_static.py

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**

## Spec
- One function per rule: `ft001(table) -> list[Diagnostic]`, and so on, plus
  `static_rules(table)`, which concatenates them.
- FT002 cycle detection: walk each column's partial successor function with a
  visited/on-stack coloring, in linear time. Do **not** use networkx or enumerate simple
  cycles. Report each cycle once at `min(cycle)`.
- Messages are human-readable and include the relevant path when there is one.

## Acceptance
- One focused hand-built table per rule, plus one table that must produce no diagnostics.
- For every golden case, the static subset of the expected diagnostics equals
  `static_rules(table)`. Assert this inside `tests/test_rules_static.py` by filtering
  the golden expected JSON on the static rule IDs.

## Out of scope
FT000, FT005, FT006, FT007 (T106).
