# T402: Maximal and prime compatibles

**Depends on:** T401  
**Owner:** agent

## May touch
src/huffman_eda/minimize/compatibles.py, tests/test_compatibles.py

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**

## Spec
- Maximal compatibles via Bron–Kerbosch with pivoting on the compatibility graph.
- Prime compatibles per §9, with their class sets (implied compatibles).
- Both take `limit` and raise `LimitExceeded`.

## Acceptance
Golden sets match. Property: every maximal compatible is a clique and is not contained in
another.
