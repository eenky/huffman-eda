# T501: Encoded table IR and critical race detection

**Depends on:** T500  
**Owner:** agent

## May touch
src/huffman_eda/encoded.py, src/huffman_eda/assign/__init__.py, src/huffman_eda/assign/races.py, tests/test_races.py

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**

## Spec
`encode(table, codes) -> EncodedTable`; `critical_races(encoded) -> list[Diagnostic]`
using new rule IDs `SA001`, and so on, as defined in §10.

## Acceptance
Golden race sets match. Property: an assignment that changes only one bit per transition
has no critical races.
