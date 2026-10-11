## Task
<!-- e.g. T103: settle() -->
Task file: `tasks/…`

## What changed
<!-- 2–5 sentences. Cite the SEMANTICS sections implemented. -->

## Checklist
- [ ] Only paths listed under **May touch** were modified
- [ ] No protected paths touched (tests/golden, test_golden.py, SEMANTICS.md, AGENTS.md, .github)
- [ ] `ruff check .` and `ruff format --check .` pass
- [ ] `mypy` (strict) passes
- [ ] `pytest -q -rs` passes; no new skip/xfail/type: ignore
- [ ] Every task Acceptance item is met (list each below)
- [ ] New tests fail without this change (explain how verified)
- [ ] No new runtime dependencies (or listed in task)

## Acceptance evidence
<!-- One line per acceptance item, with the command and result -->

## pytest tail
```
<paste last ~15 lines of `pytest -q -rs`>
```

## Spec conflicts or open questions
<!-- "None", or describe and link the Spec question issue -->
