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
  state in the same column. For each mutant, `implements(original, mutant)` must be
  false, unless the mutation is provably unobservable (the test explains how it decides).
- `hfe equiv A B` prints the counterexample trace and exits 1 when the relation fails.

## Acceptance
- At least 95% mutation kill rate over 300 random tables; every surviving mutant is
  justified as unobservable by an assertion in the test.
