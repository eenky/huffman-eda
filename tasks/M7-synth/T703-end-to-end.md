# T703: Netlist emission and end-to-end flow (`hfe synth`)

**Depends on:** T702  
**Owner:** agent

## May touch
src/huffman_eda/synth/emit.py, src/huffman_eda/flow.py, tests/test_flow.py, src/huffman_eda/cli.py

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**

## Spec
`synthesize(table) = emit(cover(assign(minimize(table))))`. Each stage runs its oracle,
and the flow stops at the first failure with that stage's diagnostics.

## Acceptance
**Milestone gate:** every golden table from M1, M4, and M5 that is complete under SIC
synthesizes and passes `check_netlist`; a property test over 200 random tables does the
same.
