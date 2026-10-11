# T702: SIC hazard-free cover selection

**Depends on:** T701  
**Owner:** agent

## May touch
src/huffman_eda/synth/cover.py, tests/test_hf_cover.py

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**

## Spec
Compute the required cubes per §12, then solve the exact minimum cover in which every
required cube lies inside a single chosen implicant. Return a certificate mapping each
required cube to its implicant.

## Acceptance
Golden sizes match. An independent checker validates the certificate.
