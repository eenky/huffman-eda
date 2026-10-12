# T500: Spec: §10 state assignment and golden

**Depends on:** M4  
**Owner:** author agent (spec PR), approved by reviewer agent

## Spec PR checklist (read the book's state-assignment chapter first)
- Define the encoded table: state variables, codes, and the excitation entry for each
  (code, column).
- Define races, and critical races: for an unstable transition from code a to code b,
  every code reachable by flipping the differing bits in any order must lead to b's
  stable entry. Decide which delay model the definition assumes (arbitrary finite delays
  on state variables).
- Define the race-free assignment problem (dichotomies per column, Tracey/USTT) and the
  optimality target.
- Golden: book examples with expected critical races for a given bad assignment, and the
  minimum number of state variables.
