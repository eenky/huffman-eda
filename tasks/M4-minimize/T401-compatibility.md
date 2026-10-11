# T401: Compatibility (implication) table

**Depends on:** T400  
**Owner:** agent

## May touch
src/huffman_eda/minimize/__init__.py, src/huffman_eda/minimize/compat.py, tests/test_compat.py

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**

## Spec
`compatibility(table) -> CompatTable` with every pair's status and, for each
incompatible pair, the reason chain (an output conflict or an implied incompatible pair).
Iterate to a fixed point as in §9.

## Acceptance
Golden incompatible-pair sets match. Property: compatibility is reflexive and symmetric,
and output-conflicting pairs are always incompatible.
