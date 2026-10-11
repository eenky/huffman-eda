# T404: Reduced table construction and `hfe minimize`

**Depends on:** T403  
**Owner:** agent

## May touch
src/huffman_eda/minimize/reduce.py, tests/test_reduce.py, src/huffman_eda/cli.py

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**

## Spec
Build the reduced flow table from a closed cover per §9. The `hfe minimize IN -o OUT`
command runs `implements(original, reduced)` and refuses to write output if it fails.

## Acceptance
**Milestone gate:** a property test over 500 random tables: `implements(T, minimize(T))`
holds and `|states(minimize(T))| <= |states(T)|`. Golden reduced tables match up to state
renaming.
