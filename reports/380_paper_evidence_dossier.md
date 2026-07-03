# Dream7B/S100P v5 Paper Evidence Dossier

## 1. Abstract-style conclusion

Dream7B seq128 segmented HBM on S100P is **not numerically validated for deployment**. It passes compile and board runtime shape gates, but current logits validity is blocked against the available GGUF Q4_K_M deployment reference while BF16/PyTorch, GGUF F16, and GGUF Q4_0 references remain unavailable (`reports/370_gate_packet_v5.json: verdict_class`, `reports/320_gguf_reference_matrix.json: reference_matrix_summary`).

## 2. Related-work bridge

The llada.cpp / llama.cpp-npu thread is used as a method reference only: build a reference matrix, split accelerator and CPU/HF diagnostics, and audit quant/dequant/layout boundaries. Qualcomm or mobile-NPU backend code is not ported to S100P (`reports/330_hybrid_routes.json: route_*`).

## 3. Methods: gate-based deployment validation

The v5 gate sequence separates compile feasibility, S100P runtime validity, reference matrix validity, logits numerical validity, root-cause localization, generation quality, and product routing. Generation quality and product routing remain `not_run_by_design` (`reports/370_gate_packet_v5.json: gate_status`).

## 4. Experimental setup

The target is Dream7B seq128 B=1 segmented HBM with final `seg27_28` q16 last-token logits and output shape `[1, 152064]`. The S100P runtime row records HBRT `3.13.6_(4.7.5 HBRT)` from prior raw/dequant evidence (`reports/300_unified_baseline_reproduction.json: s100p_runtime_hbrt_hbm`).

## 5. Reference matrix results

Only GGUF Q4_K_M and S100P raw/dequant rows are available. The v4 reference matrix reports mean cosine `0.0` between GGUF Q4_K_M and S100P BPU, with S100P raw final logits all-zero for 10 cases (`reports/320_gguf_reference_matrix.json: reference_matrix_summary`). This blocks deployment-reference agreement but does not prove BF16 failure.

## 6. S100P segmented HBM runtime results

The v3/v4 packages reproduce compile and S100P board run/shape validity, including final shape `[1, 152064]`. Full-chain S100P raw final logits are all-zero for tested cases, so output dequant/layout variants cannot recover correctness (`reports/300_unified_baseline_reproduction.json: baseline_sources`, `reports/320_gguf_reference_matrix.json: reference_matrix_summary`).

## 7. Final segment input-contract sweep

Dense v5 sweeps on S100P refined the coarse v3 `/4` recovery. In zeros, ramp, and short Chinese cases, `real_x` and `x/2` remain all-zero; the first nonzero divisor is consistently `x/2.75`, and the first nonzero clip threshold is `+/-6` (`reports/350_final_segment_threshold_contract.json: threshold_summary`).

| case | first nonzero divisor | first nonzero clip |
| --- | --- | --- |
| ramp | real_x_div_2p75 | real_x_clip_6 |
| short_chinese_prompt_padded | real_x_div_2p75 | real_x_clip_6 |
| zeros | real_x_div_2p75 | real_x_clip_6 |

These nonzero outputs are diagnostic only; no corrected-scale variant is validated against BF16 or GGUF F16 (`reports/350_final_segment_threshold_contract.json: blocking_or_failure_reasons`).

## 8. Hybrid routes

Route A (`BPU seg0..26 -> CPU/HF lm_head`) and Route B (`HF seg26 -> BPU seg27_28`) are blocked because the verified HF/PyTorch Dream wrapper and HF boundary activations are unavailable. Route C corrected-scale variants executed as offline S100P diagnostics only (`reports/330_hybrid_routes.json: route_*`).

## 9. Root-cause analysis

The strongest current localization is a late hidden range/scale or producer-consumer input-contract mismatch around `seg26_27 -> seg27_28`. Seg26 raw tensors show observed clamp at `+/-19807`, dequant abs_max about `16.296787`, and final segment all-zero behavior until the input magnitude is reduced (`reports/340_seg20_26_scale_saturation_audit.json: seg26_saturation_counts_from_raw_npy`, `reports/350_final_segment_threshold_contract.json: input_contract_hypothesis`).

## 10. Limitations

BF16/PyTorch ground truth, GGUF F16, GGUF Q4_0, HF seg26 boundary activations, and seg20..23 raw boundary tensors are missing or blocked (`reports/310_hf_bf16_dream_wrapper.json: blocking_or_failure_reasons`, `reports/320_gguf_reference_matrix.json: missing_artifacts`, `reports/340_seg20_26_scale_saturation_audit.json: available_boundaries`).

## 11. Next experiments

The minimal next experiments are to build the verified Dream BF16 wrapper, export GGUF F16/Q4_0 logits for the same seq128 cases, compare corrected-scale variants to those references, and dump seg20..23 boundaries (`reports/370_gate_packet_v5.json: next_minimal_experiments`).

## 12. Claim boundary table

| Claim | Status |
| --- | --- |
| Compile and S100P runtime shape validity | allowed |
| Logits accurate deployment | forbidden |
| BF16 falsification | forbidden until BF16 wrapper exists |
| Q4_K_M deployment-reference block | allowed |
| generation quality | not run by design |
| product route 18888/18889 | not run by design |
