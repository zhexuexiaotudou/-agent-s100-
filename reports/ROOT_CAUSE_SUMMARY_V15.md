# Root Cause Summary v15

v15 strengthens the seg00_01 contract-fault hypothesis. Targeted NAS/compiler-cache search found the seq128 B=1 HBM artifacts but no matching source ONNX/HBIR/HBO or quant table. HRT dump variants in bin/txt/npy expose hbir.mul input, GatherND output, hbir.add input-0, and hbir.add output, but still do not expose hbir.mul output or add input-1. HF source shows token embedding followed by RoPE usage inside decoder attention rather than a learned absolute-position add at the embedding boundary. The exact operator-level root cause remains vendor-artifact blocked.
