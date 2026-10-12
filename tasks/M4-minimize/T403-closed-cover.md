# T403: Minimum closed cover

**Depends on:** T402  
**Owner:** agent

## May touch
src/huffman_eda/minimize/cover.py, tests/test_cover.py

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**

## Spec
All functions are those of SEMANTICS §9.8, in the package `huffman_eda.minimize`. Each checks §9.1 first and raises `MinimizationError` with the violated rule IDs.
Implement `is_closed_cover` (§9.4) and `min_closed_cover`: an exact branch-and-bound over prime
compatibles that returns a minimum closed cover in canonical order, taking `limit`.

## Acceptance
- The `min_cover_size`, `min_closed_covers` and `not_closed` assertions pass for every golden case.
- Property: on random tables satisfying §9.1 with at most 6 states, the returned cover's size
  equals the minimum found by exhaustive search over all compatibles (not just primes).
