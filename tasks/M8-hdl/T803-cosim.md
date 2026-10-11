# T803: Cosimulation testbench generator and CI job

**Depends on:** T801, T802  
**Owner:** agent

## May touch
src/huffman_eda/export/tb.py, tests/test_cosim.py, sim/**

## Must not touch
tests/golden/**, tests/test_golden.py, docs/SEMANTICS.md, AGENTS.md, .github/**
(The owner adds the CI job, since `.github/` is protected. Propose its YAML in the PR.)

## Spec
Generate SIC stimulus covering every transition in `explore()`, drive both the reference
model and the structural netlist with random gate delays, and compare after each settle.

## Acceptance
**Milestone gate:** cosim passes for every golden table under Icarus with 20 random delay
seeds, and a seeded hazardous netlist fails it.
