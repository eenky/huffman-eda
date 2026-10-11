# T300: Spec: §8 equivalence and golden pairs

**Depends on:** M2  
**Owner:** owner

## Goal
Define precisely when table B **implements** table A under SIC fundamental mode. This is
the oracle every later pass is checked against.

## Owner checklist
- Write SEMANTICS §8. Proposed starting point, which you should refine against the book:
  explore the product of A and B from their resets. For every reachable pair and every
  input change where A settles STABLE, B must settle STABLE, and B's final outputs must
  equal A's on every output A specifies. B must have no FT007 violation on those
  transitions. Where A fails (UNDEFINED or NONDET), B is unconstrained.
- Decide whether B may resolve A's don't-cares differently in different contexts. This
  determines whether the relation is a simulation or a pure trace check.
- Add golden pairs under `tests/golden_pairs/<case>/{a.yaml,b.yaml,expected.json}`,
  including at least one non-implementation with its expected counterexample.
- Extend `.github/workflows/ci.yml` protected paths to cover `tests/golden_pairs/`.
