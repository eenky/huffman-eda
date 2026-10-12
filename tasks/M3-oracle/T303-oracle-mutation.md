# T303: Mutation tests for the oracle and `hfe equiv`

**Depends on:** T302  
**Owner:** agent

## Goal
Show that the oracle catches real bugs before trusting it to check passes.

## May touch
tests/test_equiv_mutation.py, src/huffman_eda/cli.py

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**, tests/golden_pairs/**

## Spec
- Mutation operators on a complete normal table: flip one specified output bit on a
  reachable stable entry; redirect one reachable unstable entry to a different stable
  state in the same column. Each mutant's expected verdict is fixed by its class, before
  the oracle is asked (SEMANTICS §8.7): flips and distinguishing redirects must be killed,
  shortcut redirects must be accepted, and every other redirect is counted but not gated.
- `hfe equiv A B` prints the counterexample trace and exits 1 when the relation fails.

## Acceptance
- Over 300 random tables, every gated mutant verdict matches §8.7. Class-(d) kill and
  survive counts are printed in the test output. Classification uses only the table and
  `settle`, never `equiv.py`.
