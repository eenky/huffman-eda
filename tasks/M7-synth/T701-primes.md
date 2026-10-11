# T701: Prime implicant generation

**Depends on:** T700  
**Owner:** agent

## May touch
src/huffman_eda/synth/__init__.py, src/huffman_eda/synth/primes.py, tests/test_primes.py

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**

## Spec
Quine–McCluskey with don't-cares, taking `limit`.

## Acceptance
Property: every prime is an implicant and is not contained in another, and the union of
the primes covers the on-set. The result is checked against brute force for 5 or fewer
variables.
