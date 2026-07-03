# Harness Stage 1 Gate Report

- verdict: `ok_harness_stage1_gates`
- generated_at: `2026-07-02T23:28:15.876525+08:00`
- passed_gate_count: `5/5`

## Gates

- `workspace_isolation_gate` verdict `ok_workspace_isolation_gate` passed `81/81`
- `tool_exposure_minimization_gate` verdict `ok_tool_exposure_minimization_gate` passed `37/37`
- `memory_boundary_gate` verdict `ok_memory_boundary_gate` passed `11/11`
- `runtime_trace_completeness_gate` verdict `ok_runtime_trace_completeness_gate` passed `19/19`
- `cloud_egress_redaction_gate` verdict `ok_cloud_egress_redaction_gate` passed `12/12`

## Failures

- none

## Boundaries

- production_mainline_replaced: `False`
- dispatcher_bypassed: `False`
- arbitrary_script_path_enabled: `False`
- dream7b_foreground_attached: `False`
- protected_ports_modified: `[]`
