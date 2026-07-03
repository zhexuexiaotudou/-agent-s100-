# Dream7B S100P Diffusion Research Packet

- generated_at: `2026-07-01T01:46:04.685281+08:00`
- verdict: `blocked_pending_dream7b_logits_quality_generation_product_gates`
- falsification_layer: `None`

## Gate Status

| Gate | Status | Evidence / next requirement |
| --- | --- | --- |
| `compile_feasible` | `pass` | tar=tmp\cloud_seq128_results\dream7b_seq128_b1_lmheadq16_lasttoken_hbm_20260623.tar, tar_size_bytes=8567367680, expected_sha256=c0e7d6c31af17871cf550ceec88c1bf1ec8de33f30f4d75a9f7b31aa1b73e1b1, actual_sha256=c0e7d6c31af17871cf550ceec88c1bf1ec8de33f30f4d75a9f7b31aa1b73e1b1, sha256_checked=True, summary=tmp\cloud_seq128_results\seq128_b1_lmheadq16_lasttoken_summary.json, manifest=tmp\cloud_seq128_results\seq128_b1_lmheadq16_lasttoken_hbm_manifest.tsv |
| `s100p_runtime_valid` | `pass` | runtime_report_json=tmp\product_guardrail_snapshots\dream7b_seq128_s100p_runtime_gate_20260701-014346\seq128_s100p_runtime_gate.json |
| `logits_numerically_valid` | `pending` | CPU/BF16 or GGUF reference vs BPU dequantized logits/top-k/cosine/entropy report. |
| `generation_quality_valid` | `pending` | pre-registered prompt battery output with no garbled/token-leak/empty replies. |
| `product_route_valid` | `pending` | 18889 isolation, foreground fallback to 18888, rollback, health, queue drain, latency and failure-rate logs. |

## Seq128 Artifact

- tar: `tmp\cloud_seq128_results\dream7b_seq128_b1_lmheadq16_lasttoken_hbm_20260623.tar`
- expected_sha256: `c0e7d6c31af17871cf550ceec88c1bf1ec8de33f30f4d75a9f7b31aa1b73e1b1`
- actual_sha256: `c0e7d6c31af17871cf550ceec88c1bf1ec8de33f30f4d75a9f7b31aa1b73e1b1`
- manifest_rows: `28`
- total_hbm_bytes: `8567319904`

## Negative Controls

- `seq16_prompt_tail_truncation`: exists=`True`, required_text_present=`True`; seq16 BPU single-request chat is structurally blocked by fixed 16-token window, 12-token prompt tail, and 4 mask slots.
- `seq16_bpu_logits_garbage`: exists=`True`, required_text_present=`True`; seq16 BPU logits produced garbage text versus GGUF/CPU on the same 16-token input.
- `late_layer_int16_saturation`: exists=`True`, required_text_present=`True`; late-layer hidden states saturated int16 in seg21_24 and seg24_26.
- `lm_head_q8_uncalibrated`: exists=`True`, required_text_present=`True`; q8 lm_head without calibration compressed logits; seq128 package therefore uses lm_head q16 last-token head.
- `two_track_product_boundary`: exists=`True`, required_text_present=`True`; 18888 remains protected foreground GGUF route; BPU/true-batch remains isolated until all quality and product gates pass.

## Boundary

- `do_not_overwrite_18888`
- `do_not_enable_foreground_bpu_route`
- `do_not_delete_seq16_queue_baseline`
- `do_not_compile_seq256_before_seq128_board_evidence`
