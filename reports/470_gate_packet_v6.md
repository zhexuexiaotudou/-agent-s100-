# Gate Packet v6

- verdict_class: `C_deployment_blocked_against_deployment_reference_but_bf16_unresolved`
- v6 fixes v5 raw endpoint hygiene and adds seg20..27 boundary evidence. NAS HF safetensors and Dream wrapper code are present and AutoModel load was demonstrated, but logits numerical validity remains blocked against the available deployment reference and unresolved against BF16 because verified BF16/FP32 logits plus GGUF F16/Q4_0 rows are unavailable.
- Gate 6/7: `not_run_by_design` / `not_run_by_design`
