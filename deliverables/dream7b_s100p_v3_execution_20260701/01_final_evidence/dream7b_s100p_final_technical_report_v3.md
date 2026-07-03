# Dream7B diffusion 在 S100P 上的 v3 分层证实/证伪定位报告

## 摘要

本轮 v3 只定位 `seg26_27 -> seg27_28` final segment input contract / layout / dtype / scale / runtime interpretation，不运行 generation quality，不启用或修改产品路由，不触碰 `18888`。最终判定保持 `deployment_blocked_against_deployment_reference_but_bf16_unresolved`。证据来自 `01_final_evidence/dream7b_s100p_gate_packet_v3.json` 字段 `verdict`、`gate_status`、`blocking_issues`。

## Gate 结果

`compile_feasible=pass`，`s100p_runtime_valid=pass`，`logits_numerically_valid=inconclusive`，`generation_quality_valid=pending`，`product_route_valid=pending`。这些字段见 `01_final_evidence/dream7b_s100p_gate_packet_v3.json` 的 `gate_status`。

## v3 定位结果

Segment IO contract audit 状态为 `pass`，`seg26_to_seg27_contract_match=pass`。如果该项仍为 inconclusive，原因是 HBRT runtime 暴露的输入 descriptor、dtype 或 input quant params 不完整；详见 `reports/110_segment_io_contract.json` 字段 `blocking_fields_missing` 与 `seg26_to_seg27_comparison`。

Final segment input sweep 状态为 `pass`，结论字段为 `{'real_hidden_constant_output': True, 'synthetic_controls_nonconstant': True, 'smallest_recovery_variant': 'real_x_div_4', 'likely_issue_class': 'input_range_or_scale', 'synthetic_nonconstant_variants': ['synthetic_zeros', 'synthetic_ones', 'synthetic_ramp', 'synthetic_last_token_impulse']}`。该结果用于判断真实 seg26 hidden 经过缩放、裁剪、z-normalize 或 dtype 变体后，是否能让 `seg27_28` 从恒定输出恢复为 nonconstant logits；详见 `reports/120_final_segment_input_sweep.json` 字段 `variants`、`smallest_recovery_variant` 和 `likely_issue_class`。

Fresh-subprocess boundary dump 状态为 `pass`，完成 case 数为 `3`，失败 case 数为 `0`。该结果用于区分上一轮 HBRT memory error 是否只是进程生命周期问题；详见 `reports/130_s100p_boundary_dump_subprocess.json` 字段 `cases`、`memory_errors`、`late_segment_constant_outputs`。

BF16/PyTorch reference 状态为 `unavailable`。本轮没有 verified Dream7B diffusion BF16 wrapper，因此不允许写 BF16 ground-truth failure；详见 `reports/140_bf16_reference_status.json` 字段 `bf16_reference_status`、`reason`、`no_bf16_ground_truth_claims_allowed`。

## 结论边界

Dream7B seq128 B=1 segmented HBM with lm_head q16 last-token logits passed compile feasibility and S100P load/run/shape checks. However, the tested BPU logits path is blocked against the available GGUF Q4_K_M deployment reference, and BF16/PyTorch ground truth is unresolved. Current evidence localizes the anomaly to the real segmented chain output path around seg26_27 -> seg27_28 or final-segment input/runtime interpretation, because isolated seg27_28 responds to synthetic hidden inputs but outputs all-zero logits for real BPU seg26 hidden states.

## 下一步最小实验

Instrument or obtain HBRT input tensor descriptors for seg27_28, including dtype, layout, and input quantization; then build a verified Dream7B BF16/PyTorch wrapper for the same seg26 hidden input.
