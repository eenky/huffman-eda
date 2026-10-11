# T202: Behavior graph export (DOT, JSON)

**Depends on:** T104  
**Owner:** agent

## Goal
Export `explore()` results so behavior can be inspected visually and diffed.

## May touch
src/huffman_eda/graph_export.py, tests/test_graph_export.py

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**

## Spec
- `to_json(result) -> dict`: nodes are the stable total states; edges are transitions
  with the input bit flipped, the outcome kind, and the transient path.
- `to_dot(table, result) -> str`: one node per stable total state labeled `s@c / outs`.
  STABLE edges are solid; failing outcomes go to a red sink node named by kind.
- Output is deterministic (sorted).

## Acceptance
- Snapshot tests on every golden case. The JSON output validates against a JSON Schema
  in the test file.
