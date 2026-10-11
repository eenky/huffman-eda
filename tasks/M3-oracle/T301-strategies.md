# T301: Hypothesis strategies for flow tables

**Depends on:** T300  
**Owner:** agent

## Goal
Generators for random tables used by every later property test.

## May touch
tests/strategies.py, tests/test_strategies.py

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**, tests/golden_pairs/**

## Spec
- `flow_tables(n_inputs, n_outputs, max_states, *, normal=False, primitive=False, complete=False)`
- `normal=True` guarantees no FT004; `primitive=True` gives exactly one stable entry
  per row; `complete=True` specifies every entry that SIC exploration reaches. Each
  flag is verified by `validate()` in the test file.
- Shrinking produces small tables.

## Acceptance
- 500 examples per flag combination; each flag's guarantee holds.
