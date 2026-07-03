# SEG00_01 Root Cause Status V17

seg00_01 is strongly implicated but not exactly closed. HRT/HBM inventory exposes View, GatherND, hbir.mul, and hbir.add, but not hbir.mul output/add input-1 or GatherND official scale. Domain-safe add reconstruction is blocked by scale mismatch. HF equivalent candidates do not match add output.
