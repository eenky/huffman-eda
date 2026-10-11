# T601: Gate netlist IR and loader

**Depends on:** T600  
**Owner:** agent

## May touch
src/huffman_eda/netlist.py, tests/test_netlist.py

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**

## Spec
Immutable netlist IR and loader for the §11 format. Validate that every combinational
loop passes through a declared state variable.

## Acceptance
Every golden netlist loads; invalid netlists raise typed errors.
