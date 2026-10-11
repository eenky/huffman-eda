# T503: Excitation and output functions and `hfe assign`

**Depends on:** T502  
**Owner:** agent

## May touch
src/huffman_eda/assign/excitation.py, tests/test_excitation.py, src/huffman_eda/cli.py

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**

## Spec
Derive `Y_i(x, y)` and `z_j(x, y)` as truth tables with don't-cares. `decode(encoded)`
gives back a flow table.

## Acceptance
**Milestone gate:** `implements(T, decode(assign(T)))` holds over 300 random tables, and
there are no critical races.
