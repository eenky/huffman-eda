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
- `implements(a, b) -> EquivResult`, where `EquivResult(ok: bool, counterexample:
  Counterexample | None)` and `Counterexample(trace, kind, output, outcome)` are the §8.5
  shapes (`Counterexample.to_dict()` is exactly what `expected.json` holds). This
  supersedes the earlier `tuple[InputStep, ...]` sketch in this file: §8.4 fixes the
  counterexample as the first failure in a fixed breadth-first order, so it is the
  shortest trace and is unique; §8.5 drops the separate `InputStep` type.
- `equivalent(a, b)` holds iff `implements(a, b)` and `implements(b, a)`.
- §8.1's precondition (identical inputs and outputs) raises `ValueError`.

## Acceptance
- All golden pairs match their expected result and counterexample.
- Property: `implements(T, T)` holds for every random complete table.
- Property: renumbering states (an isomorphism) preserves `equivalent`.
