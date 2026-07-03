# Task 720 Export Full Truth Reference

- schema: `dream7b_s100p_v9_720_export_full_truth_reference`
- created_at_utc: `2026-07-01T12:03:42.215079+00:00`
- full_truth_available: `false`
- truth_row_type: `none`
- blocked_report: `evidence/full_reference_v9/blocked_full_truth_reference.json`
- blocking_or_failure_reasons:
  - S100P full HF forward reached model-load stage in v8 isolated modern runtime but produced no logits before the evidence-run timeout; no GGUF F16 artifact/tool was found locally or on NAS during prior inventory.
- next_minimal_experiments:
  - On S100P, run a longer full-reference job with the isolated modern runtime or provide a GGUF F16 runner/artifact; then place per-case logits under evidence/full_reference_v9/{case}/full_truth_logits.npy.
