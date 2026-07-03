# Root Cause Summary v14

v14 strengthens the `seg00_01` root-cause locus with exact HRT-visible tensors: token ids, position ids, GatherND output, add input-0, and add output. The remaining unresolved part is the hidden `hbir.mul` output and add input-1/constant path. HF source shows token embedding followed by RoPE shared inside decoder layers, not a learned absolute-position add at the embedding boundary. Therefore the current evidence supports a `seg00_01` graph/input/quant contract problem, but exact operator-level attribution still requires compiler/HBO source graph and quant metadata.
