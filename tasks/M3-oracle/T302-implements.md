# T302: Implementation relation checker

**Depends on:** T301  
**Owner:** agent

## Goal
Implement SEMANTICS §8.

## May touch
src/huffman_eda/equiv.py, tests/test_equiv.py

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**, tests/golden_pairs/**

## Spec
- `implements(a, b) -> EquivResult(ok: bool, counterexample: tuple[InputStep, ...] | None)`.
  The counterexample is the shortest input sequence from reset, found by BFS.
- `equivalent(a, b)` holds iff `implements(a, b)` and `implements(b, a)`.

## Acceptance
- All golden pairs match their expected result and counterexample.
- Property: `implements(T, T)` holds for every random complete table.
- Property: renumbering states (an isomorphism) preserves `equivalent`.
