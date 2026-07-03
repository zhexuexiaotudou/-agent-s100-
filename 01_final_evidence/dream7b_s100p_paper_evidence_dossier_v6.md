# Dream7B/S100P v6 Paper Evidence Dossier

## Abstract-style conclusion

v6 does not validate accurate deployment and does not falsify Dream7B against BF16/PyTorch. It upgrades v5 by adding all critical threshold endpoint raw arrays and by dumping S100P `seg20..27` boundary tensors, but the decisive BF16/GGUF F16 reference gap remains (`reports/470_gate_packet_v6.json: verdict_class`).

## Methods

The workflow follows gate-based logits validation: canonical seq128 token IDs, S100P raw/dequant evidence, reference matrix rows, hybrid route diagnostics, boundary saturation localization, and final gate aggregation. Generation quality and product route gates are kept `not_run_by_design`.

## Canonical cases

`cases/canonical_seq128_cases_v6.jsonl` contains the 10 canonical seq128 cases with token ID hashes, position IDs, masks, last-token index 127, and tokenizer manifest hash (`reports/410_canonical_seq128_cases.json`).

## Endpoint evidence

`evidence/raw_endpoint_subset_v6/` now includes `input.npy`, `raw_output.npy`, `dequant_logits.npy`, and `metadata.json` for `real_x`, `/2`, `/2.25`, `/2.5`, `/2.75`, `/3`, `/3.25`, `/3.5`, `/4`, `clip_8`, `clip_6`, `clip_5`, `clip_4`, and `z_normalized` across zeros/ramp/short Chinese cases (`reports/400_evidence_hygiene_and_raw_endpoints.json`).

## Reference matrix

The live model inventory found both `dream-7b-q4km.gguf` and Dream7B HF safetensors under `/mnt/nas/openclaw/models/dream7b-hf`. The custom Dream wrapper/config/tokenizer files are present, and the model load probe passed with isolated dependencies and compatibility shims. However, verified BF16/FP32 logits were not exported, and GGUF F16/Q4_0 artifacts were not produced; therefore Q4_K_M remains a deployment-reference blocker only (`reports/420_verified_dream_bf16_wrapper.json`, `reports/430_gguf_f16_q4_reference_matrix.json`).

## Boundary saturation

S100P offline boundary dump completed for seg20..27 on the three target cases. The first observed positive int16 max occurs at seg20, seg22/24/25 hit full int16 extremes, seg26 clamps at +/-19807, and seg27 final logits are all-zero. BF16 divergence cannot be assigned without BF16 boundaries (`reports/450_seg20_27_boundary_saturation_origin.json`).

## Claim boundary

Allowed: v6 supports a late range/saturation/input-contract anomaly and fixes v5 raw endpoint packaging. Forbidden: accurate deployment, BF16 falsification, corrected-scale fix success, generation quality claims, or product route claims.
