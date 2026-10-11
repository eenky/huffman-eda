# T101: Flow table IR

**Depends on:** T000  
**Owner:** agent

## Goal
Implement the immutable flow-table IR defined in SEMANTICS §1.

## May touch
src/huffman_eda/model.py, tests/test_model.py

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**

## Spec
- `Choice(next: int, outputs: str)`: frozen; `outputs` matches `^[01-]*$`.
- `Cell(choices: tuple[Choice, ...] = ())`: frozen; choices deduplicated and sorted
  by `(next, outputs)` at construction. Properties: `is_specified`,
  `is_deterministic`, `next` (raises `ValueError` unless deterministic),
  `outputs` (same rule).
- `FlowTable(name, inputs, outputs, reset, rows)`: frozen.
  - `rows: dict[int, dict[str, Cell]]`
  - Construction validates: `len(inputs) >= 1`; input and output names unique; every
    column key has length n over {0,1}; every choice's outputs has length m; the reset
    column is a valid column. It does **not** require the reset row to exist (that is
    FT000) or next states to have rows (that is FT003).
  - Methods: `states()` (sorted row keys), `columns()` (all 2^n columns, lexicographic),
    `cell(s, c)` (empty `Cell()` when missing), `is_stable(s, c)`,
    `adjacent(c) -> list[tuple[int, str]]` (bit index i ascending, flipped column).
- Raise `ModelError(ValueError)` with a clear message on invalid construction.

## Acceptance
- `pytest tests/test_model.py` covers: dedupe/sort of choices, stability derivation,
  missing-row cells, `adjacent("00") == [(0, "10"), (1, "01")]`, and every validation error.
- mypy strict clean.

## Out of scope
Parsing text (T102), settle (T103).
