# Gate Packet v5

- verdict_class: `C_deployment_blocked_against_deployment_reference_but_bf16_unresolved`
- verdict: Dream7B seq128 segmented HBM on S100P remains blocked at logits numerical validity against the available GGUF Q4_K_M deployment reference. BF16/PyTorch, GGUF F16, and GGUF Q4_0 references are unresolved, so BF16 falsification or accurate deployment support cannot be claimed.
- Gate 4: `fail_against_gguf_q4_k_m_inconclusive_against_bf16`
- Gate 6/7: `not_run_by_design` / `not_run_by_design`
- threshold: `{'coarse_v3_first_recovery': 'real_x_div_4', 'dense_v5_first_nonzero_divisor_all_cases': 'real_x_div_2p75', 'dense_v5_first_nonzero_clip_all_cases': 'real_x_clip_6', 'real_x_and_div_2_allzero_all_cases': True, 'x_div_3_div_3p5_div_4_clip_4_z_normalized_nonzero_all_cases': True, 'reference_correctness_status': 'blocked_reference_logits_unavailable_for_corrected_variants'}`
