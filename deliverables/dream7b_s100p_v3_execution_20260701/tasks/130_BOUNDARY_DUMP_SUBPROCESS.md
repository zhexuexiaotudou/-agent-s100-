# Task 130 — Robust boundary dump in fresh subprocesses

## Problem

v2 boundary dump completed `zeros` but failed on `ramp` at final segment load with HBRT memory allocation error. This may be a resource lifecycle issue, not necessarily a model logic result.

## Required tool

Create or update:

```text
tools/run_s100p_hbm_chain_dump_boundaries_subprocess.py
```

You may start from `tools_scaffold/run_s100p_hbm_chain_dump_boundaries_subprocess.py`, but must adapt command templates to the actual repo.

## Requirements

1. Each case must run in a fresh subprocess.
2. If final segment load still fails, optionally run each segment in a fresh process.
3. One failing case must not abort all cases.
4. Required cases:
   - `zeros`
   - `ramp`
   - at least one semantic prompt case
5. Required saved tensors per case:
   - seg24 raw/dequant output
   - seg25 raw/dequant output
   - seg26 raw/dequant output
   - seg27 raw/dequant final logits
6. Record runtime logs and memory errors as evidence.

## Outputs

- `reports/130_s100p_boundary_dump_subprocess.json`
- `reports/130_s100p_boundary_dump_subprocess.md`
- `evidence/s100p_boundaries_subprocess/{run_id}/{case_id}/...`

## Verdict

```json
{
  "s100p_boundary_dump_subprocess_verdict": "pass|partial|fail|inconclusive",
  "cases_completed": 0,
  "cases_failed": 0,
  "memory_errors": [],
  "late_segment_constant_outputs": []
}
```
