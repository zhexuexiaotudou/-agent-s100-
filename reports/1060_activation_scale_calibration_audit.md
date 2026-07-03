# Activation Scale Calibration Audit

- first_metric_divergence_by_case: `{'zeros': 0, 'ramp': 0, 'short_chinese_prompt_padded': 0}`
- first_saturation_like_boundary_by_case: `{'zeros': 12, 'ramp': 12, 'short_chinese_prompt_padded': 12}`
- simple_scale_factor_restores_hf_suffix: `false`

## Blocking / Failure Reasons
- No simple post-hoc scale factor is supported as logits-correctness recovery across canonical cases.
