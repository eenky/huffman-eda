# T103: settle()

**Depends on:** T101  
**Owner:** agent

## Goal
Implement SEMANTICS §3 exactly.

## May touch
src/huffman_eda/semantics.py, tests/test_semantics.py

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**

## Spec
- `class Outcome(Enum): STABLE, OSCILLATION, UNDEFINED, NONDET`
- `@dataclass(frozen=True) SettleResult(kind, path: tuple[int, ...], cycle: tuple[int, ...] = ())`
  with property `final` (the last element of path; meaningful for STABLE).
- `settle(table, s, c) -> SettleResult`, O(len(path)), iterative with no recursion.

## Acceptance
- Unit tests built by hand (not from golden) for each outcome, including: start already
  stable; a 3-cycle entered from a tail (`path` includes the tail and `cycle` excludes it);
  undefined via a missing row; nondeterministic in the middle of a chain.
- Hypothesis test (a local small strategy is fine until T301): `path` elements are
  distinct; for STABLE, `is_stable(final, c)`; for OSCILLATION, `cycle` is a suffix of
  `path` and `next(cycle[-1], c) == cycle[0]`.

## Out of scope
Exploration (T104).
