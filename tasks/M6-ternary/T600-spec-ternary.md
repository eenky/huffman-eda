# T600: Spec: §11 netlists and ternary simulation and golden

**Depends on:** M5  
**Owner:** owner

## Owner checklist
- Define the gate netlist IR: gate types, feedback wires as the state variables of the
  Huffman model, and the file format.
- Define ternary simulation (Eichelberger): Algorithm A (changing inputs set to X,
  propagate to fixpoint) and Algorithm B (inputs set to new values, propagate to
  fixpoint). Define the delay model under which an X result means "a hazard or critical
  race is possible".
- Define what a netlist correctly implementing a flow table means, in terms of §8.
- Golden: small netlists with known static hazards, critical races, and one clean
  circuit, each with the expected verdict per transition.
