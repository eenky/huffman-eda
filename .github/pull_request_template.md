## Kind
<!-- exactly one: spec PR (spec paths only) | implementation PR (no spec paths) | reference PR (reviewer) -->

## Task
Task file: `tasks/…`  <!-- or: Spec question #… -->

## What changed
<!-- 2–5 sentences. Cite the SEMANTICS sections implemented or added. -->

## Checklist
- [ ] Only paths allowed for this PR kind and task were modified
- [ ] `ruff check .`, `ruff format --check .`, `mypy`, `scripts/spec_policy.py verify`, `pytest -q -rs` pass
- [ ] No skip/xfail/importorskip/type: ignore/noqa/no-cover added
- [ ] Every Acceptance item is met (evidence below)
- [ ] New tests fail without this change (explain how verified)
- [ ] Every claim (unobservable, excluded, bounded, equivalent) cites the test or command showing it
- [ ] Spec PR only: new sections locked (`spec_policy.py lock`); every new golden case has `derivation` and `source`

## Acceptance evidence
<!-- One line per acceptance item, with the command and result -->

## pytest tail
```
<paste last ~15 lines of `pytest -q -rs`>
```

## Spec conflicts or open questions
<!-- "None", or link the Spec question issue -->
