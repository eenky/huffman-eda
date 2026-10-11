# T801: SystemVerilog reference model and SVA

**Depends on:** T800  
**Owner:** agent

## May touch
src/huffman_eda/export/__init__.py, src/huffman_eda/export/sv_ref.py, tests/test_sv_ref.py

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**

## Spec
Emit a self-contained SV module plus a bind file of SVA properties, as defined in §13.

## Acceptance
Generated code passes `verilator --lint-only` in CI for every golden table.
