# REVIEWER.md

Instructions for the **reviewer agent**. Run it as a separate agent: a different GitHub
identity (`vars.REVIEWER_LOGIN`), a separate session with no shared memory with the author
agent, and if possible a different model. Its value comes from being independent.
Independence is broken if it reads the author's reasoning before forming its own.

## What you own

- `reference/huffman_ref.py`: an independent implementation of SEMANTICS
- `tests/test_reference_diff.py`: the differential test that binds production, golden data,
  and the reference together
- approving or rejecting every PR (the repository requires one approval from a non-author)

You never change `src/` or non-reference tests. You never approve your own PRs.

## How to write the reference

1. Read **only** `docs/SEMANTICS.md`. Do not open `src/`, implementation PRs, or the
   author's PR description before your reference implementation passes its own tests.
2. Optimize for obviousness, not speed: direct transcriptions of the definitions, brute
   force where the spec allows it, and no clever data structures.
3. Never import `huffman_eda`, and never let `src/` import `reference` (the policy check
   enforces both).
4. Add the section number to `IMPLEMENTED_SECTIONS`, then extend
   `tests/test_reference_diff.py` with:
   - the reference reproducing every golden case for that section
   - production agreeing with the reference on seeded random inputs and single-change
     mutants (fixed seeds, no Hypothesis)
5. Before merging a reference extension, show that the guard works: plant at least three
   distinct bugs locally (in a copy of production code, in a golden value, and in your own
   reference), and confirm each one fails the differential test. List them in the PR.

## Reviewing a spec PR (`spec(Tx00): ...`)

Approve only if every item holds:

- [ ] It changes only spec paths (the policy check shows P2 is green).
- [ ] Every new section is complete. You can implement it without guessing, and each
      open choice is stated, with its reason.
- [ ] Each book-sourced golden case matches **your own independent transcription** of the
      cited page and figure. Compare the cell grids mechanically, not by eye.
- [ ] Each golden `derivation` is correct when re-derived by hand.
- [ ] Your reference extension for the new section exists in its own PR. Run against the
      spec PR's branch locally, it reproduces every new golden expectation exactly.
- [ ] The section is consistent with every frozen section it builds on.

Merge order: your reference PR merges first. It may skip new cases only by listing them as
pending in its PR description. Then the spec PR merges, and then the implementation tasks
start.

If you disagree with the spec, request changes and explain using a minimal table. Never
"fix" it yourself.

## Reviewing an implementation PR

- [ ] It touches only the task's **May touch** paths, and the policy check is green.
- [ ] Every Acceptance item has evidence in the PR, and the evidence matches CI.
- [ ] New tests would fail without the change. Spot-check by reverting one hunk locally.
- [ ] Every claim in the PR ("unobservable", "excluded", "bounded") cites a test that
      demonstrates it.
- [ ] Nothing in the PR changes behavior in a section other than the one the task
      implements.

## Corrections to frozen ground truth

If a frozen section or an existing golden case is wrong:

1. Open a PR that corrects it, together with your reference, and links the Spec question.
2. Explain the error with a minimal table, and show the corrected expectation from both
   your reference and a hand derivation.
3. The PR cannot pass the policy check until the owner applies `owner-approved`. This is
   the only routine action that needs the owner. Keep these PRs minimal and self-explanatory.
