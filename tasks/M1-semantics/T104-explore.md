# T104: explore()

**Depends on:** T103  
**Owner:** agent

## Goal
Implement SEMANTICS §4 exactly.

## May touch
src/huffman_eda/explore.py, tests/test_explore.py

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**

## Spec
- `@dataclass(frozen=True) Transition(src_state, src_col, dst_col, result: SettleResult)`
- `@dataclass(frozen=True) ExploreResult(reset_ok: bool, stable: tuple[tuple[int,str],...], visited: tuple[tuple[int,str],...], transitions: tuple[Transition, ...])`.
  `stable` and `visited` are sorted; `transitions` stay in recording order.
- `explore(table) -> ExploreResult`

## Acceptance
- `pytest tests/test_golden.py -k stable_reachable` passes with no skips.
- Unit tests: reset not stable gives an empty result; transition count is n times the
  number of stable states; the BFS order of transitions is as specified.

## Out of scope
Diagnostics (T105, T106).
