# T204: Markdown table import

**Depends on:** T102  
**Owner:** agent

## Goal
Make it fast for the owner to transcribe book tables. Parse a Markdown table into the IR.

## May touch
src/huffman_eda/io.py, tests/test_io_markdown.py, src/huffman_eda/cli.py (add `hfe import`)

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**

## Spec
A `.md` file with YAML front matter (`name`, `inputs`, `outputs`, `reset`) and one table:

```
| state | 00 | 01 | 11 | 10 |
|---|---|---|---|---|
| 1 | [1],0 | 2,- | - | 3,- |
```
- Header columns may appear in any order (Gray order is typical) and are validated as
  columns.
- Cells use the SEMANTICS §2 grammar. `|` inside a cell must be escaped as `\|`.
- `hfe import FILE.md -o FILE.yaml`

## Acceptance
- Round trip: render each golden table to Markdown in the test, import it, and compare
  with the original.
