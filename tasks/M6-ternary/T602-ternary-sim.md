# T602: Ternary simulation (Algorithms A and B)

**Depends on:** T601  
**Owner:** agent

## May touch
src/huffman_eda/ternary.py, tests/test_ternary.py

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**

## Spec
Ternary gate evaluation; event-driven fixpoint with a monotonicity check (A only moves
values toward X, B only away from X). Return the full ternary trace for debugging.

## Acceptance
Golden verdicts match. Property: on binary inputs with no X, the fixpoint equals plain
binary evaluation.
