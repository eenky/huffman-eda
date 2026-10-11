# T403: Minimum closed cover

**Depends on:** T402  
**Owner:** agent

## May touch
src/huffman_eda/minimize/cover.py, tests/test_cover.py

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**

## Spec
Exact branch-and-bound over prime compatibles: the cover must contain every state and be
closed under class sets. Take `limit` and raise `LimitExceeded`. Return the cover and a
proof object (for each class set, the cover member containing it) for independent
checking.

## Acceptance
Golden minimum sizes match. Property: the returned cover passes an independent
`check_closed_cover`, and for tables with 6 or fewer states, brute force confirms
minimality.
