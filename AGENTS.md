# AGENTS.md

Rules for any coding agent working in this repository. Read this file, then
`docs/SEMANTICS.md`, `docs/ARCHITECTURE.md`, and your assigned task file, **before**
writing code.

## What this project is

A verification-first toolkit for asynchronous sequential circuits under the Huffman model
in fundamental mode. Every transformation (minimize, assign, synthesize, export) is
checked by an independent oracle. You are building one small, well-specified piece at a
time.

## The workflow

1. You are assigned **exactly one** task file: `tasks/M<k>-*/T<id>-*.md`.
2. Create a branch named `task/T<id>-<slug>` from the latest `main`.
3. Implement only what the task asks for. Touch only the paths listed under
   **May touch**.
4. Run the Definition of Done locally. All of it must pass.
5. Open a PR titled `T<id>: <task title>` using the PR template. Fill in every
   checklist item honestly.
6. When CI fails or a review comment arrives, fix it **on the same branch**. Never open a
   second PR for the same task.
7. Stop when the PR is green and every review thread is resolved. A human merges.

## Protected paths (never edit)

- `tests/golden/**`
- `tests/test_golden.py`
- `docs/SEMANTICS.md`
- `AGENTS.md`
- `.github/**`

CI fails any PR that touches these without the owner's `spec-approved` label. If you
believe one of them is wrong, **stop**. Open an issue using the *Spec question* template.
Include a minimal table, what the spec says, what you think it should say, and why.
Do not work around the spec in code.

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
- Never add `skip`, `xfail`, or `# type: ignore`, and never weaken an assertion, to make CI
  pass. If a test seems wrong, raise a Spec question.
- Never add a runtime dependency unless the task lists it.
- Never print from core modules. Return `Diagnostic` objects or raise typed exceptions.
- Never implement a later task's scope "while you're there".

## Definition of Done (every task)

```bash
pip install -e ".[dev]"
ruff check .
ruff format --check .
mypy
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
