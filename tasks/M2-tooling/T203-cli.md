# T203: CLI `hfe`

**Depends on:** T106, T201, T202  
**Owner:** agent

## Goal
A Typer CLI with the exit codes of SEMANTICS §6.

## May touch
src/huffman_eda/cli.py, tests/test_cli.py

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**

## Spec
- `hfe validate FILE [--json]`
- `hfe view FILE [--plain]`
- `hfe explore FILE [--format json|dot]`
- `hfe fmt FILE [--check]` (canonical re-serialization via `dump_table`)
- Exit codes 0/1/2 exactly as specified. A ParseError prints `file:row:column: reason`
  and exits 2.

## Acceptance
- `typer.testing.CliRunner` tests: exit code for every golden case (1 iff its expected
  JSON contains an error); `--json` output equals `Report.to_dict()`; a malformed file
  gives exit 2.
