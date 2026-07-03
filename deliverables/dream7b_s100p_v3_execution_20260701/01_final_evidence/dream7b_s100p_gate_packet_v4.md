# Dream7B S100P Gate Packet V4

- verdict: `logits_blocked_against_gguf_q4_k_m_localized_to_final_segment_input_range_or_scale_bf16_unresolved`
- verdict_class: `logits_numerical_validity_root_cause_localization_only`
- track: `llada.cpp / llama.cpp-npu inspired replication track`

## Gate Status

| Gate | Status |
| --- | --- |
| `compile_feasible` | `pass` |
| `s100p_runtime_valid` | `pass` |
| `reference_matrix_logits_compare` | `partial_q4_k_m_and_s100p_available_bf16_f16_q4_0_missing` |
| `logits_numerically_valid` | `fail_against_gguf_q4_k_m_inconclusive_against_bf16_f16_q4_0` |
| `hybrid_bpu_hidden_cpu_lmhead` | `blocked_cpu_hf_lmhead_unavailable` |
| `final_segment_input_contract_sweep` | `pass` |
| `s100p_dequant_layout_audit` | `pass_no_dequant_or_layout_variant_rescues_all_zero_raw_final_logits` |
| `generation_quality_valid` | `not_run_by_design` |
| `product_route_valid` | `not_run_by_design` |
| `route_safety` | `pass_offline_artifact_synthesis_no_18888_no_product_route` |

## Key Findings

- reference_matrix: `{'case_count': 10, 'gguf_q4_k_m_vs_s100p_bpu_mean_cosine': 0.0, 's100p_all_cases_raw_final_constant_zero': True, 'matrix_verdict': 'blocked_against_gguf_q4_k_m_bf16_f16_q4_0_unavailable'}`
- hybrid: `{'current_outcome': 'decision_rule_not_executed_cpu_hf_lmhead_unavailable', 'cpu_hf_reference_status': {'bf16_reference_status': 'unavailable', 'bf16_boundary_status': 'unavailable', 'reason': 'verified_dream7b_diffusion_forward_wrapper_not_available'}}`
- final_segment_sweep: `{'final_segment_input_sweep_verdict': 'pass', 'real_hidden_constant_output': True, 'synthetic_controls_nonconstant': True, 'smallest_recovery_variant': 'real_x_div_4', 'likely_issue_class': 'input_range_or_scale', 'raw_int16_input_status': 'fail', 'raw_int16_input_exception': "RuntimeError:Data type mismatch for input tensor '_input_0' in model 'dream_segment_27_28_last_token_logits': expected numpy dtype format 'f', but received 'h'", 'raw_uint16_input_status': 'not_run_runtime_requires_float_input', 'raw_uint16_input_reason': "HBRT rejected int16 direct input for _input_0 and reported expected numpy dtype format 'f'; uint16 direct input is not supported without a runtime override."}`
- dequant_layout_audit: `{'verdict': 'upstream_graph_or_runtime_issue_raw_constant', 'case_count': 10, 'raw_constant_cases': ['zeros', 'ramp', 'repeated_frequent_token', 'repeated_rare_token', 'alternating_two_tokens', 'short_english_prompt_padded', 'short_chinese_prompt_padded', 'openclaw_style_prompt_padded', 'exactly_128_token_synthetic_prompt', 'prompt_with_mask_tail'], 'all_final_raw_logits_zero': True, 'layout_dequant_rescue_found': False, 'interpretation': 'All tested final raw logits are already constant all-zero. Official dequant, scalar scale, zero-point handling, uint16 reinterpretation, and endian swap cannot recover nonzero logits. Late hidden states are nonzero and often saturated, so the current failure is upstream of output dequant and at or before final segment execution/output emission.'}`

## Root-Cause Localization

- most_likely_current_fault_class: `seg26_hidden_range_or_scale_vs_seg27_28_input_contract`
- supported_by: seg24..26 boundary dumps are nonzero for completed cases
- supported_by: seg27_28 output is all-zero for real seg26 hidden in full-chain and fresh-subprocess boundary dumps
- supported_by: seg27_28 responds to synthetic controls and to scaled/clipped real hidden variants
- supported_by: output dequant/layout variants cannot recover all-zero raw final logits

## Blocking Issues

- `verified Dream-7B BF16/PyTorch forward and lm_head wrapper unavailable`
- `HF/PyTorch seg26 hidden boundary unavailable`
- `GGUF F16 and Q4_0 reference logits unavailable`
- `S100P final raw logits are all-zero for current seq128 probe cases`
- `real BPU seg26 hidden at original scale and /2 causes all-zero final logits; /4 is first diagnostic recovery`

## Safe Claim Boundary

Dream7B seq128 S100P segmented HBM remains blocked at logits numerical validity. The available Q4_K_M GGUF reference disagrees with S100P final logits because S100P raw final logits are all-zero for the tested cases. The llada.cpp-inspired hybrid CPU lm_head decision rule could not be executed without a verified HF/PyTorch Dream lm_head wrapper. Independent final-segment input sweeps localize the current anomaly to seg26 hidden range/scale or the seg27_28 input contract, not to generation quality or product routing.

## Next Minimal Experiments

- Provide or build a verified Dream-7B HF/PyTorch BF16 forward wrapper and lm_head-only path for dumped seg26 hidden.
- Export GGUF F16 and GGUF Q4_0 logits for the same seq128 token-id cases.
- Obtain HBRT seg27_28 input tensor descriptors including dtype, layout, quantization, and accepted dynamic range.
