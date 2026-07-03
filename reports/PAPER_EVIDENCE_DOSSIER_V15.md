# Paper Evidence Dossier v15

The paper-safe conclusion is that the tested Dream7B seq128 B=1 segmented-HBM S100P path and tested BPU/hybrid routes remain logits-invalid against HF/PyTorch BF16 truth. v15 does not claim Dream7B is impossible on S100P. It identifies the minimal missing artifacts needed for closure: source graph, quant table, hbir.mul output/add input-1, and calibration ranges. Generation quality and product routes were not run.
