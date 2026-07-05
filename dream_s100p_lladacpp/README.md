# Dream7B S100P llada.cpp-Style Research Track

Created: 2026-07-04T11:14:10.683800+00:00

This directory is an isolated Dream7B research track. It does not modify the
current Qwen + OpenClaw AI-NAS product path, the OpenClaw foreground, or ports
18888/18889.

## Current Verdict

`bpu_operator_alignment_failed_review_required`

The route has moved past the original truth-set blocker. It now has a complete
31-row HF/PyTorch truth set, a passing validation gate, and a passing
truth-replay block-driver gate. The next blocker is BPU operator alignment:
there is no true per-op BPU output checksum table with layout and scale records
for embedding, position/RoPE, lm_head, and the other required operators.

## Completed In This Track

- Phase 0 baseline lock: `reports/30000_baseline_lock.*`
- Phase 1 llada.cpp-to-S100P translation plan:
  `reports/30010_lladacpp_to_s100p_requirements.*`
- Phase 2 hold gate: `reports/30020_pytorch_truth_export_gate.*`
- Continue baseline: `reports/30200_continue_baseline_lock.*`
- Full 31-row truth export: `reference/full_truth_31.jsonl`,
  `reference/full_truth_31_manifest.json`, and `reports/30210_full_truth_31_export_gate.*`
- Full truth validation: `reports/30220_full_truth_31_validation_gate.*`
- PyTorch truth replay block driver: `reports/30230_pytorch_block_driver_gate.*`
- BPU operator review blocker: `reports/30240_bpu_operator_alignment_gate.*`
- Final review packet:
  `../01_final_evidence/dream7b_s100p_lladacpp_style_continue_gate_packet.*`
- Config skeletons for model identity, block runtime, quantization, BPU operator
  manifest, and memory layout.

## Safety Boundary

- No generation quality run.
- No OpenClaw foreground route.
- No default Qwen replacement.
- No 18888/18889 route modification.
- No BPU deployment claim until PyTorch truth, per-op/layer alignment, runtime,
  and fixed-task gates pass.

## Next Command

To reproduce the latest continue gates:

```powershell
py -3 -B tools\build_dream_s100p_lladacpp_continue.py --baseline-only
& .\tmp\v21_torch_env\Scripts\python.exe -B dream_s100p_lladacpp\reference\truth_case_builder.py
& .\tmp\v21_torch_env\Scripts\python.exe -B dream_s100p_lladacpp\reference\export_full_truth_31.py
& .\tmp\v21_torch_env\Scripts\python.exe -B dream_s100p_lladacpp\reference\validate_truth_rows.py
& .\tmp\v21_torch_env\Scripts\python.exe -B dream_s100p_lladacpp\reference\pytorch_block_driver.py
py -3 -B tools\build_dream_s100p_lladacpp_continue.py --finalize
```
