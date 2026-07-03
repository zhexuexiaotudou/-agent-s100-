# Task 900 Repeat Full Truth Reference

- schema: `dream7b_s100p_v11_900_repeat_full_truth_reference`
- created_at_utc: `2026-07-01T19:15:50.433147+00:00`
- repeat_truth_rows: `3/3`
- top1_agreement_rows: `3/3`
- median_relative_l2: `0.0`
- blocking_or_failure_reasons:
  - FP32 or genuinely independent-host repeat truth was not executed because no such ready high-memory/runtime asset is available in the current workspace/NAS evidence; v11 provides a same-S100P BF16 repeat instead.
- next_minimal_experiments:
  - For publication robustness, repeat FP32 or BF16 on a genuinely independent high-memory host when available.
