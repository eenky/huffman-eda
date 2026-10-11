# T603: Netlist-vs-flow-table checker and `hfe tsim`

**Depends on:** T602  
**Owner:** agent

## May touch
src/huffman_eda/check_netlist.py, tests/test_check_netlist.py, src/huffman_eda/cli.py

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**

## Spec
For every SIC transition reachable in the flow table, run Algorithms A and B on the
netlist, then compare the final state and outputs against the flow table. Report
diagnostics `TS001`, and so on, as defined in §11.

## Acceptance
**Milestone gate:** every seeded hazard and race in the golden netlists is detected, and
the clean netlist passes.
