# T102: Cell parser and YAML/JSON loader

**Depends on:** T101  
**Owner:** agent

## Goal
Parse the file format and cell grammar of SEMANTICS §2 into the T101 IR.

## May touch
src/huffman_eda/io.py, tests/test_io.py, tests/data/** (non-golden test inputs)

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**

## Spec
- `parse_cell(text: str, row: int, m: int) -> Cell`
- `load_table(path: Path) -> FlowTable`, choosing YAML or JSON by suffix
  (`.yaml`/`.yml`/`.json`).
- `dump_table(table: FlowTable) -> str` (YAML). `load(dump(T)) == T` for every
  table. Stable choices are emitted bracketed, and columns are written in lexicographic
  order, always quoted.
- `ParseError(ValueError)` with attributes `row`, `column`, `text`, `reason`.
- Must reject: unquoted/non-string column keys (YAML `01:` becomes int 1); a bracketed
  target that differs from the row; wrong output length; `outs` present when m = 0;
  empty choices like `"2,0|"`; a `-` target inside a multi-choice cell.

## Acceptance
- `tests/test_io.py`: one test per accept and reject case above; round-trip on every
  `tests/golden/*/table.yaml`.
- `pytest tests/test_golden.py -rs` still skips only the tests that need T103+ modules.

## Out of scope
Markdown table import (T204).
