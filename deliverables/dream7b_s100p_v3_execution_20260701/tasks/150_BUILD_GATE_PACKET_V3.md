# Task 150 — Build v3 gate packet

## Required tool

Create or update:

```text
tools/build_dream7b_s100p_gate_packet_v3.py
```

Start from `tools_scaffold/build_dream7b_s100p_gate_packet_v3.py` if useful.

## Inputs

Read all available v2 and v3 reports, especially:

- `01_final_evidence/dream7b_s100p_gate_packet_v2.json`
- `reports/105_package_hygiene_v3.json`
- `reports/110_segment_io_contract.json`
- `reports/120_final_segment_input_sweep.json`
- `reports/130_s100p_boundary_dump_subprocess.json`
- `reports/140_bf16_reference_status.json`
- previous v2 reports in `reports/000` through `reports/100`

## Gate rules

### Gate 0: compile_feasible

Pass only if artifact manifest is complete and hashes are verified or excluded artifacts are explicitly documented.

### Gate 1: s100p_runtime_valid

Pass only if representative segments and full chain run on S100P with expected final shape and no resource exhaustion in the tested runtime gate.

### Gate 2: logits_numerically_valid

- Pass only if BPU logits match BF16 reference above thresholds and deployment reference mismatch is either absent or technically explained.
- Fail if BPU mismatches BF16 after input alignment and dequant/contract are verified.
- Inconclusive if BF16 reference is unavailable or input contract remains unresolved.
- Blocked if artifacts are missing.

Thresholds:

- semantic-case top1 agreement >= 0.80
- ref top1 in BPU top5 >= 0.95
- mean cosine >= 0.95
- normalized entropy not near 1 for nontrivial semantic cases
- no all-zero or constant logits unless expected by diagnostic case design

### Gate 3: generation_quality_valid

Pending unless Gate 2 passes and generation quality actually ran.

### Gate 4: product_route_valid

Pending unless Gate 3 passes and isolated product route validation actually ran.

## Final verdict classes

```text
A. accurate_deployment_supported
B. deployment_falsified_against_bf16_reference
C. deployment_blocked_against_deployment_reference_but_bf16_unresolved
D. inconclusive_due_to_missing_artifact_reference_or_input_alignment
```

## Outputs

- `01_final_evidence/dream7b_s100p_gate_packet_v3.json`
- `01_final_evidence/dream7b_s100p_gate_packet_v3.md`
- `01_final_evidence/dream7b_s100p_final_technical_report_v3.md`

## Must include

- verdict
- gate table
- evidence table
- blocking issue list
- first divergent segment or `unknown`
- segment contract status
- final segment input sweep conclusion
- BF16 reference status
- deployment reference status
- next minimal experiment if inconclusive
- safe paper claim boundary
