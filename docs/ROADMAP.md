# Roadmap

Each milestone opens with a **spec task** (`Tx00`), owned by the repository owner. An
agent may draft it, but it merges only with the `spec-approved` label because it edits
`docs/SEMANTICS.md` and `tests/golden/`. Implementation tasks follow and are agent-owned.

Before each spec task, read the matching chapter of the book. Write that milestone's golden
cases from the book's worked examples.

| Milestone | Goal | Exit criterion |
|---|---|---|
| M0 Bootstrap | Scaffold, CI, rules, M1 spec | Done in the initial commit |
| M1 Semantics | IR, parser, settle, explore, rules FT000 to FT009 | `pytest tests/test_golden.py -rs` passes with 0 skipped |
| M2 Tooling | Gray grid, graph export, CLI, Markdown import | `hfe validate` exit codes match SEMANTICS §6 on all golden cases |
| M3 Oracle | Random tables, behavioral equivalence, counterexamples | `equiv(T, T)` holds for 1000 random tables; seeded mutants are caught |
| M4 Minimization | Compatibles, prime compatibles, minimum closed cover | Every reduced table implements its original (property test) |
| M5 State assignment | Race analysis, race-free assignment, excitation table | No critical races; decoded behavior implements the original |
| M6 Ternary simulation | Netlist IR, Eichelberger A/B, netlist-vs-table check | Detects every seeded hazard and race in the M6 golden cases |
| M7 Hazard-free logic | Prime implicants, SIC hazard-free covers, netlist emission | End-to-end flow table to netlist passes ternary check on all golden cases |
| M8 HDL | SV reference model + SVA, structural Verilog, cosim | Cosim of structural vs reference passes in CI with Icarus |

## Task index

| ID | Title | Depends on | Owner |
|---|---|---|---|
| T000 | Bootstrap (scaffold, CI, AGENTS, SEMANTICS §1–7, golden) | none | done |
| T101 | Flow table IR | T000 | agent |
| T102 | Cell parser and YAML/JSON loader | T101 | agent |
| T103 | settle() | T101 | agent |
| T104 | explore() | T103 | agent |
| T105 | Static rules FT001–FT004, FT008, FT009 | T103 | agent |
| T106 | Dynamic rules FT000, FT005–FT007, validate() | T104, T105 | agent |
| T201 | Gray order and grid renderer | T102 | agent |
| T202 | Behavior graph export (DOT, JSON) | T104 | agent |
| T203 | CLI `hfe` | T106, T201, T202 | agent |
| T204 | Markdown table import | T102 | agent |
| T300 | Spec: §8 equivalence + golden pairs | M2 | owner |
| T301 | Hypothesis strategies for flow tables | T300 | agent |
| T302 | Implementation relation checker | T301 | agent |
| T303 | Mutation tests for the oracle + `hfe equiv` | T302 | agent |
| T400 | Spec: §9 minimization + golden | M3 | owner |
| T401 | Compatibility (implication) table | T400 | agent |
| T402 | Maximal and prime compatibles | T401 | agent |
| T403 | Minimum closed cover | T402 | agent |
| T404 | Reduced table construction + `hfe minimize` | T403 | agent |
| T500 | Spec: §10 state assignment + golden | M4 | owner |
| T501 | Encoded table IR and critical race detection | T500 | agent |
| T502 | Race-free assignment (Tracey/USTT) | T501 | agent |
| T503 | Excitation and output functions + `hfe assign` | T502 | agent |
| T600 | Spec: §11 netlists and ternary simulation + golden | M5 | owner |
| T601 | Gate netlist IR and loader | T600 | agent |
| T602 | Ternary simulation (Algorithms A and B) | T601 | agent |
| T603 | Netlist-vs-flow-table checker + `hfe tsim` | T602 | agent |
| T700 | Spec: §12 hazard-free covers + golden | M6 | owner |
| T701 | Prime implicant generation | T700 | agent |
| T702 | SIC hazard-free cover selection | T701 | agent |
| T703 | Netlist emission and end-to-end flow + `hfe synth` | T702 | agent |
| T800 | Spec: §13 HDL and SVA + golden | M7 | owner |
| T801 | SystemVerilog reference model + SVA | T800 | agent |
| T802 | Structural Verilog export | T800 | agent |
| T803 | Cosimulation testbench generator and CI job | T801, T802 | agent |
