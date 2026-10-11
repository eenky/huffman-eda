# T502: Race-free assignment (Tracey/USTT)

**Depends on:** T501  
**Owner:** agent

## May touch
src/huffman_eda/assign/tracey.py, tests/test_tracey.py

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**

## Spec
Generate the dichotomies, then solve the minimum covering by partitioning variables
exactly within `limit`. Return codes plus a certificate (which variable separates each
dichotomy).

## Acceptance
Golden variable counts match. Property: `critical_races(encode(T, tracey(T)))` is empty
for 300 random normal tables.
