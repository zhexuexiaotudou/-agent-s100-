# Dream7B S100P Gate Packet V3

- verdict: `deployment_blocked_against_deployment_reference_but_bf16_unresolved`
- verdict_class: `C`
- bf16_reference_status: `unavailable`
- deployment_reference_status: `fail`

## Gate Status

| Gate | Status |
| --- | --- |
| `compile_feasible` | `pass` |
| `s100p_runtime_valid` | `pass` |
| `logits_numerically_valid` | `inconclusive` |
| `generation_quality_valid` | `pending` |
| `product_route_valid` | `pending` |

## V3 Localization

- segment_io_contract_status: `pass`
- seg26_to_seg27_contract_match: `pass`
- final_segment_input_sweep_status: `pass`
- final_segment_input_sweep_conclusion: `{'real_hidden_constant_output': True, 'synthetic_controls_nonconstant': True, 'smallest_recovery_variant': 'real_x_div_4', 'likely_issue_class': 'input_range_or_scale', 'synthetic_nonconstant_variants': ['synthetic_zeros', 'synthetic_ones', 'synthetic_ramp', 'synthetic_last_token_impulse']}`
- s100p_boundary_dump_subprocess_status: `pass`

## Blocking Issues

- `bf16_reference_unavailable_or_unverified`
- `deployment_reference_gguf_q4km_failed`

## Safe Claim Boundary

Dream7B seq128 B=1 segmented HBM with lm_head q16 last-token logits passed compile feasibility and S100P load/run/shape checks. However, the tested BPU logits path is blocked against the available GGUF Q4_K_M deployment reference, and BF16/PyTorch ground truth is unresolved. Current evidence localizes the anomaly to the real segmented chain output path around seg26_27 -> seg27_28 or final-segment input/runtime interpretation, because isolated seg27_28 responds to synthetic hidden inputs but outputs all-zero logits for real BPU seg26 hidden states.

## Next Minimal Experiment

Instrument or obtain HBRT input tensor descriptors for seg27_28, including dtype, layout, and input quantization; then build a verified Dream7B BF16/PyTorch wrapper for the same seg26 hidden input.
