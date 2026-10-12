# AGENTS.md

Rules for any coding agent working in this repository. Read this file, then
`docs/SEMANTICS.md`, `docs/ARCHITECTURE.md`, and your assigned task file, **before**
writing code.

## What this project is

A verification-first toolkit for asynchronous sequential circuits under the Huffman model
in fundamental mode. Every transformation (minimize, assign, synthesize, export) is
checked by an independent oracle. You are building one small, well-specified piece at a
time.

## Roles

Two agents work here, each as its own GitHub App (`hfe-author[bot]`, `hfe-reviewer[bot]`),
using a token minted from its own key by `scripts/app_token.sh`. Never use any other
credentials. The separation is enforced by `scripts/spec_policy.py`, which runs from `main`
and cannot be changed by either agent. It is also enforced by GitHub itself: the author app
has no `workflows` permission, and only the reviewer app can post `reviewer-verdict`.

| Role | Identity | May change | Never changes |
|---|---|---|---|
| **Author** (you, unless told otherwise) | `vars.AUTHOR_LOGIN` | `src/`, `tests/` (non-golden), spec (`docs/SEMANTICS.md`, `docs/spec_lock.json`, new golden cases), `tasks/`, `docs/ROADMAP.md`, `docs/ARCHITECTURE.md` | `reference/`, `tests/test_reference_diff.py`, governance |
| **Reviewer** (see REVIEWER.md) | `vars.REVIEWER_LOGIN` | `reference/`, `tests/test_reference_diff.py`, corrections to frozen ground truth (owner-approved only) | `src/`, `tests/` |
| **Owner** | `vars.OWNER_LOGIN` | anything | |

Governance files are `.github/**`, `AGENTS.md`, `REVIEWER.md`, `scripts/spec_policy.py`,
`scripts/app_token.sh`, `scripts/reviewer_verdict.sh`, and `scripts/setup_governance.sh`.
Only the owner changes them.

Every PR needs three green checks on its current head commit: `test`, `spec-policy`, and
`reviewer-verdict`. The last is posted only by the reviewer app, and it never applies to the
reviewer's own PRs (see below). A push creates a new head commit with no verdict, so every
push needs a fresh review. The author enables auto-merge (`gh pr merge --auto --squash`)
and never merges by any other route. Never add or remove the `owner-approved` label.

## Two kinds of PR, never mixed

1. **Spec PR** (milestone spec tasks `Tx00`, and spec questions). It may change only
   `docs/SEMANTICS.md`, `docs/spec_lock.json`, new golden cases, `tasks/`, and
   `docs/ROADMAP.md`. Title: `spec(Tx00): ...`.
2. **Implementation PR** (every other task). It must not touch any spec path.

The policy check (P2) rejects a PR that mixes the two. When a task needs a spec change,
stop and open the spec PR first. The implementation PR waits until that is merged.

## Rules for spec PRs

- **New sections only.** Write the next reserved section of SEMANTICS (`## 9. ...`). Sections
  listed in `docs/spec_lock.json` are frozen. Changing one, or an existing golden file,
  fails the policy check unless the owner applies `owner-approved`. If you think frozen
  ground truth is wrong, open a *Spec question* issue with a minimal failing table and stop.
- **Lock what you add.** Before opening the PR, run
  `python scripts/spec_policy.py lock --section <N>` for each new section.
- **Golden cases are append-only.** Each new case's `expected.json` needs:
  - a non-empty `derivation` list explaining every expected entry
  - a `source` field: `"synthetic"`, or `"book: p.<page>, <figure/example id>"`
- **Book-sourced cases come from the source, never from memory.** Transcribe only from the
  page images or PDF the owner provides. Never commit page images or book text to this
  public repo: commit only your transcription of the table, and cite the page and figure.
  The reviewer transcribes the same figure independently and compares the two.
- **Decisions are explicit.** When the book leaves a choice open (as with don't-cares in
  §8), state the choice and the reason in the spec text, so the reviewer can check it.
- A spec PR merges only after the reviewer's reference implementation reproduces every
  new golden expectation (see REVIEWER.md).

## The workflow for an implementation task

1. You are assigned **exactly one** task file: `tasks/M<k>-*/T<id>-*.md`.
2. Branch `task/T<id>-<slug>` from the latest `main`.
3. Implement only that task, touching only the paths listed under **May touch**.
4. Run the Definition of Done locally. All of it must pass.
5. Open the PR using the template, enable auto-merge, and ask the reviewer agent to review it
   (link the PR in the reviewer's queue).
6. Fix CI failures and review comments **on the same branch**.
7. When the reviewer opens a reference PR, review it as a peer. Check that it reads only
   SEMANTICS, imports nothing from `src/`, has no weakened assertions, and that its planted-bug
   evidence is real. Then `gh pr review <n> --approve` and add the `peer-reviewed` label.
   Approve only what you have checked.
8. Every claim in a PR (a mutant is unobservable, a case is excluded, a bound is sound)
   must cite the test or command that demonstrates it.

## Protected ground truth

Agents can never weaken these, and the policy check enforces it mechanically:

- frozen SEMANTICS sections and locked files (hashes in `docs/spec_lock.json`)
- existing golden files (append-only)
- the reference implementation and the differential test (reviewer only)
- governance files (owner only)

## Source-of-truth order

1. `docs/SEMANTICS.md`
2. the task file
3. `docs/ARCHITECTURE.md`
4. existing code

If two of these conflict, follow the higher one and point out the conflict in the PR
description.

## Never do these

- Never transcribe figures, tables, or examples from the textbook from memory. Golden data
  comes only from the owner.
- Never add `skip`, `xfail`, `importorskip`, `# type: ignore`, `# noqa`, or `pragma: no cover`,
  and never weaken an assertion. The policy check (P7) rejects the markers. If a test seems
  wrong, raise a Spec question.
- Never add a runtime dependency unless the task lists it.
- Never print from core modules. Return `Diagnostic` objects or raise typed exceptions.
- Never implement a later task's scope "while you're there".

## Definition of Done (every task)

```bash
pip install -e ".[dev]"
ruff check .
ruff format --check .
mypy
python scripts/spec_policy.py verify
pytest -q -rs
```

Plus the task's own **Acceptance** commands. Paste the tail of the `pytest -q -rs`
output into the PR.

## Code standards

- Python 3.11+. Use `from __future__ import annotations`. Must pass `mypy --strict`.
- IR types are immutable: pydantic v2 models with `frozen=True`, or frozen dataclasses.
- Core functions are pure and deterministic. Sort every set before returning it: states
  numerically, columns lexicographically (Gray order is for display only).
- Every public function has a docstring that cites the SEMANTICS section it implements,
  for example `"""Implements SEMANTICS §3."""`.
- Exponential algorithms take a `limit` argument and raise `LimitExceeded`.

## Testing standards

- Every task adds unit tests in `tests/test_<module>.py`.
- From M3 onward, every pass also adds a Hypothesis property test against its oracle
  (use `tests/strategies.py`).
- A new test must fail without your change. Say in the PR how you confirmed that.
- Golden tests skip only while their target module does not exist yet. Once a module
  exists, its golden tests must run and pass.

## Commits and PRs

- Conventional commits that include the task ID: `feat(T103): implement settle`,
  `test(T103): …`, `fix(T103): …`.
- Keep a PR under about 400 changed lines, excluding tests. If a task can't fit, say so
  in a Spec question and propose a split.
- When relevant, include the output of `hfe validate --json` on a golden case.

## Glossary

| Term | Meaning here |
|---|---|
| Huffman model | Combinational logic plus feedback delays. State is held on feedback wires, with no clock. |
| Fundamental mode | Inputs change only when the circuit is stable. |
| SIC | Single input change: one input bit changes at a time. |
| MIC | Multiple input change. Out of scope until a task introduces it. |
| Total state / entry | A pair `(state, column)`. |
| Stable entry | A deterministic entry whose next state is its own row (shown as `[s]`). |
| Transient | The unstable entries visited while settling after an input change. |
| Normal flow table | Every unstable entry leads directly to a stable entry (no FT004). |
| Primitive flow table | Exactly one stable entry per row. |
| Compatible states | States that can be merged without conflicting outputs or next states (M4). |
| Critical race | A state-variable race whose outcome depends on delays (M5). |
| Ternary simulation | Simulation over {0, 1, X} that detects hazards and races (M6). |
