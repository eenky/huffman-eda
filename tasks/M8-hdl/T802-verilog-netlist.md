# T802: Structural Verilog export

**Depends on:** T800  
**Owner:** agent

## May touch
src/huffman_eda/export/verilog.py, tests/test_verilog_export.py

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**

## Spec
Netlist IR to structural Verilog using generic primitives, with an optional cell-mapping
table.

## Acceptance
Lint passes for every M7 golden netlist; the netlist-to-Verilog round trip preserves gate
counts.
