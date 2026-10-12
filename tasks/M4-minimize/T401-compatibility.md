# T401: Compatibility (implication) table

**Depends on:** T400  
**Owner:** agent

## May touch
src/huffman_eda/minimize/__init__.py, src/huffman_eda/minimize/compat.py, tests/test_compat.py

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**

## Spec
All functions are those of SEMANTICS §9.8, in the package `huffman_eda.minimize`. Each checks §9.1 first and raises `MinimizationError` with the violated rule IDs.
Implement `MinimizationError`, `LimitExceeded`, `check_precondition`, `incompatible_pairs` (§9.2:
compare **stable** outputs only, then the implication fixpoint), `implied`, and `class_set` (§9.3).
A helper that returns, for each incompatible pair, the reason (an output conflict at column c, or
implied by pair (p',q') at column c) is welcome. It is informative only; golden data checks
the set.

## Acceptance
- `tests/golden_minimize`: the `precondition` and `incompatible_pairs` assertions pass for every
  case. The later assertions in each case may still fail until T402–T404 are done, so record
  progress in the PR.
- Property: on random tables satisfying §9.1, the set is symmetric and contains every
  output-incompatible pair, and every pair it omits has no implied pair inside it.
