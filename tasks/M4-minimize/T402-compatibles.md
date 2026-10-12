# T402: Maximal and prime compatibles

**Depends on:** T401  
**Owner:** agent

## May touch
src/huffman_eda/minimize/compatibles.py, tests/test_compatibles.py

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**

## Spec
All functions are those of SEMANTICS §9.8, in the package `huffman_eda.minimize`. Each checks §9.1 first and raises `MinimizationError` with the violated rule IDs.
Implement `maximal_compatibles` (Bron–Kerbosch with pivoting on the compatibility graph; this
is valid because compatibility is pairwise, §9.2) and `prime_compatibles` (§9.3, plain class-set
inclusion). Both take `limit` and return results in canonical order (§9.5).

## Acceptance
- The `maximal_compatibles` and `prime_compatibles` assertions pass for every golden case.
- Property: every maximal compatible is pairwise compatible and maximal under inclusion, and
  every maximal compatible is prime.
