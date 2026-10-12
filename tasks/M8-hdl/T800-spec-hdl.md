# T800: Spec: §13 HDL export and SVA and golden

**Depends on:** M7  
**Owner:** author agent (spec PR), approved by reviewer agent

## Spec PR checklist
- Define the SystemVerilog behavioral reference model of a flow table: how settling is
  modeled with no clock (for example, an event loop with an iteration bound).
- Define the SVA properties: the SIC environment assumption on input changes; outputs and
  state are stable before the next input change; and a "no X on state after settle" check.
- Define the structural Verilog subset (generic gates; an optional sky130 mapping table)
  and the delay annotations used in cosimulation.
- Choose the CI simulator (Icarus is the default; XEZIM is an optional backend).
