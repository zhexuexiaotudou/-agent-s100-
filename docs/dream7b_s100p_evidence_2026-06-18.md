# Dream7B S100P Evidence Snapshot

Date: 2026-06-18

## Service Preflight

S100P host: `ubuntu`

`dream7b-default-status` reported:

- `dream7b-bpu-batch-queue.service`: active / enabled
- `segment_major_24x256_default`: `True`
- latest soak: `avg_bpu=93.037`, `failed_jobs=0`
- latest telemetry: `avg_bpu=93.014`, `failed_jobs=0`
- OpenClaw model: `dream7b-local/Dream7B-S100P-local`
- base URL: `http://127.0.0.1:18888/v1`

Gateway checks:

```json
{"ok": true, "model": "Dream7B-S100P-local", "backend": "dream7b-text"}
```

`/v1/models` listed `Dream7B-S100P-local`.

## Performance And Identity Probe

Report:

```text
/mnt/nas/openclaw/reports/ai_nas_mvp/dream7b_perf_identity_20260618-120209-292585/dream7b_perf_identity.json
```

Summary:

- verdict: `ok_dream7b_perf_identity`
- model_id_confirmed: `True`
- failed_case_count: `0`
- TTFT method: first response byte for the current non-stream gateway, so this is an upper bound rather than native token streaming.
- TTFT ms: min `222.695`, avg `34325.965`, p50 `37331.411`, p95 `54905.143`
- prefill tokens/s estimate: avg `12.867`, p50 `0.404`, p95 `50.399`
- decode tokens/s estimate: avg `33.586`, p50 `0.402`, p95 `133.081`

Self-introduction response:

```text
Hello! I'm Dream Dream7 model. How can I assist you today
```

The response object model was `Dream7B-S100P-local`.

## Edge Cloud Router Probe

Report:

```text
/mnt/nas/openclaw/reports/ai_nas_mvp/edge_cloud_router_20260618-120517-950987/edge_cloud_router.json
```

Summary:

- verdict: `ok_ai_nas_edge_cloud_router`
- route_counts: `{'local': 2, 'cloud': 1}`
- privacy_query_sent_to_cloud: `False`
- failures: `[]`

Demo routes:

| Query ID | Route | Privacy | Complexity | Local tool |
| --- | --- | --- | --- | --- |
| `simple_local` | `local` | `high` | `simple` | `ai_nas_case_packet` |
| `privacy_local` | `local` | `high` | `simple` | `ai_nas_case_packet` |
| `complex_cloud` | `cloud` | `none` | `complex` | `None` |

## Dispatcher Checks

S100P allowlisted dispatcher accepted:

```bash
scripts/probes/ai_nas_allowlisted_tool.sh ai_nas_edge_cloud_router
scripts/probes/ai_nas_allowlisted_tool.sh dream7b_perf_identity --mock
```

Windows-side Bash dispatcher validation was not possible because the local WSL image lacks `/bin/bash`; S100P/Linux validation passed.

## Product Guardrail Snapshot

Update: 2026-06-19 12:14 CST.

Report:

```text
tmp/product_guardrail_snapshots/dream7b_product_guardrail_snapshot_20260619-121459/dream7b_product_guardrail_snapshot.json
```

Summary:

- verdict: `ok_dream7b_product_guardrail_snapshot`
- `dream7b-bpu-batch-queue.service`: active / enabled
- service description: `Dream 7B BPU batch queue service (segment-major load-once 24x256 default)`
- rollback script: present locally and on NAS
- queue-batch guardrail baseline:
  - report: `/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_phase_timing_20260614-005702/phase_timing_probe.json`
  - avg_bpu_loading: `93.166`
  - avg_nonzero_bpu_loading: `95.097`
  - failed_job_count: `0`
- latest B=4 true-batch research point:
  - telemetry count in local analysis: `5`
  - latest point: `B=4`, segment-major, `3072` microbatches
  - avg_bpu gap versus queue baseline: `-10.587` points
  - avg_nonzero_bpu gap versus queue baseline: `-5.417` points
  - final logits average runtime: `20.248 ms`
  - hidden-block average runtime: `8.102 ms`

Guardrail decision:

```text
default_service_unchanged: true
true_batch_not_promoted: true
queue_batch_should_remain_default: true
```

This keeps the production default on queue-batch while preserving B=4 true-batch
as a research artifact.

## Operational SLO Rollup

Update: 2026-06-22 12:22 CST.

Report:

```text
tmp/product_guardrail_snapshots/operational_slo_rollup_contract_20260622-122150-357901/operational_slo_rollup_contract.json
```

Summary:

- verdict: `ok_ai_nas_operational_slo_rollup_contract`
- total contracts: `15`
- required accepted: `13/13`
- blockers: `0`
- warnings: `1`
- warning detail: `concurrency_stability:limited_production_evidence`
- SLO limited evidence triage: `ok_ai_nas_slo_limited_evidence_triage`; triaged `true`, release blocker `false`, queue-batch default remains `true`, true-batch promotion remains blocked, concurrency verdict `limited_ai_nas_concurrency_stability`, dialog-health fixture errors `4`
- gateway listener ownership: accepted, listener PID equals systemd MainPID, orphan listener detected `false`
- gateway listener drift gate: accepted, live listener still equals systemd MainPID, live orphan listener detected `false`, live health `true`
- default service freshness gate: accepted, failed checks `0`, packet age `0.132 minutes`
- first-response SLO tier guard: accepted, fast-path max first content `2.575 ms`, SSE first-progress p50 `278.387 ms`, backend explicit first-content p50 `20771.222 ms`, backend latency not true-batch work `true`
- first-response warning triage: accepted, source warning `warning_dream7b_first_response_packet_content_latency`, warning triaged `true`, quickpath first-content delta `-20768.668 ms`, backend latency not true-batch work `true`, runtime/compile started `false/false`
- queue-batch default gate: `queue_batch_service_remains_default=true`, `do_not_promote_true_batch=true`
- partial-batch flush readiness: aggregate `true`, live service summary `false`, standalone partial-batch probe `true`, queue-health snapshot `true`, source `partial_batch_probe`, probe run `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/runs/20260620-105816`, `12323.576 ms/request`
- B=4 per-run evidence matrix: `ok_dream7b_b4_per_run_evidence_matrix`, `23` total samples, `20` successful, `3` failed capacity/runtime samples preserved, top slowest segment `seg27_final_logits` at rate `1.0`, standard B=4 runtime sweep status `blocked_duplicate`; runtime gate and next-action pack both consume the matrix with `runtime_experiment_gate_uses_per_run_matrix=true` and `next_action_pack_uses_per_run_matrix=true`
- runtime refactor work-order gate: `ok_dream7b_b4_runtime_refactor_work_order`, `5` work orders, `1` allowed local design-only item, source anchor missing count `0`, hidden-materialize design contract `ok_dream7b_b4_hidden_materialize_design_contract`, hidden-materialize telemetry contract `ok_dream7b_b4_hidden_materialize_telemetry_contract`, default runtime change `false`, S100P runtime `false`, compile start `false`
- duplicate true-batch sweep guard: `nas_inventory_prevents_duplicate_sweeps=true`, `nas_inventory_b4_json_mirrored=true`, `nas_remote_b4_group_major_report_json_count=24`, `group_order_partition_prevents_duplicate_sweeps=true`, `segment_group_schedule_scorecard_ok=true`, `segment_group_schedule_blocks_runtime_compile_sweeps=true`, `runtime_source_implementation_map_ok=true`, `runtime_source_implementation_map_blocks_runtime_compile_defaults=true`, `runtime_refactor_work_order_ok=true`, `runtime_refactor_work_order_blocks_runtime_compile_defaults=true`, `hidden_materialize_design_contract_ok=true`, `hidden_materialize_design_contract_blocks_runtime_compile_defaults=true`, `hidden_materialize_telemetry_contract_ok=true`, `hidden_materialize_telemetry_contract_blocks_runtime_compile_defaults=true`, `scheduler_overhead_deprioritizes_python_gap_tuning=true`, `runtime_instrumentation_ready=true`, `hbm_load_accounting_contract_ok=true`, `bottleneck_closure_model_ok=true`
- production readiness gate: `limited_ai_nas_production_readiness_gate` at `tmp/product_guardrail_snapshots/production_readiness_gate_20260621-012215-536950/production_readiness_gate.json`; this refresh used existing remote Personal inventory evidence and a non-existing local sqlite path to avoid the current local SQLite `disk I/O error`
- tail latency: P95 `28.3858 ms`, P99 `34.2741 ms`, failed samples `0`
- continuous task soak: throughput `40.912 jobs/s`, queue wait P95 `117.373 ms`, failed jobs `0`
- queue backpressure: interactive queue wait P95 `56.8974 ms`, unfinished jobs `0`
- BPU headroom: average utilization `93.4667%`, P95 `94.0%`, P01 headroom `6.0%`
- model recovery drill: recovery P95 `540.8823 ms`, recovered count `2`

Audit:

```text
network_call_performed: false
service_restart_performed: false
kill_performed: false
delete_performed: false
move_performed: false
overwrite_performed: false
```

## Operator Portal Contract

Update: 2026-06-22 12:22 CST.

Report:

```text
tmp/product_guardrail_snapshots/operator_portal_contract_20260622-122200-562359/operator_portal_contract.json
```

Static portal artifact:

```text
tmp/product_guardrail_snapshots/operator_portal_contract_20260622-122200-562359/operator_portal.html
```

Summary:

- verdict: `ok_ai_nas_operator_portal_contract`
- result_count: `4`
- payment_node_count: `2`
- copy_suggestion_count: `4`
- approval_row_count: `3`
- ready_approval_count: `2`
- needs_repair_count: `1`
- failure_count: `0`
- execution_performed: `false`

Requirement checks passed for query visibility, related files, evidence, amount/date/payment nodes, copy suggestions,
approval queue, operator decision controls, one-click report link, audit status, production readiness, long-soak watcher,
Dream7B interaction, Dream7B service guardrails, Dream7B HBM load accounting visibility, Dream7B bottleneck closure visibility, Dream7B last-token candidate/validation visibility, operational SLO,
Dream7B final-logits leverage visibility, objective traceability, dependency bundle, and production runbook.

Dream7B service guardrails are now visible in the Portal and backed by latest `dream7b_product_decision_packet`,
`dream7b_fast_path_regression`, `dream7b_product_guardrail_snapshot`, and
`dream7b_default_service_freshness_gate` evidence. The Portal HTML includes `gateway_fast_ready`,
`default_status_contract_ready`, `default_rollback_dry_run_ready`,
`gateway_listener_matches_systemd_main_pid`, `gateway_orphan_listener_detected`,
`gateway_listener_drift_gate`, `gateway_listener_drift_live_matches_systemd_main_pid`,
`runtime_experiment_gate`, `s100p_runtime_experiment_now`, `allowed_s100p_runtime_experiments`,
`partial_batch_flush_ready`, `partial_batch_flush_live_summary_ready`,
`partial_batch_flush_probe_ready`, `partial_batch_flush_health_snapshot_ready`,
`partial_batch_flush_readiness_source`,
`per_run_evidence_matrix`, `per_run_matrix_runs`, `per_run_matrix_top_segment`,
`per_run_matrix_standard_sweep_status`,
`runtime_gate_blockers`, `next_nonduplicate_runtime_candidate`, `segment_stability_audit`,
`runtime_gate_admission_evidence_ready`, `runtime_gate_admission_projected_saved_ms_per_request`,
`runtime_gate_admission_standard_sweeps_blocked`,
`runtime_command_guard`, `runtime_command_guard_standard_sweeps_blocked`,
`runtime_command_guard_would_start_runtime`,
`stable_primary_bottleneck`, `final_logits_rank1_rate`, `do_not_run_hidden_order_sweeps_now`,
`segment_drag_breakdown`, `segment_drag_final_vs_hidden_mean_ratio`,
`segment_drag_top_group_by_accounted_ms`,
`group_order_candidates`, `group_order_best_nonbaseline_delta_ms_per_request`,
`group_partition_planner`, `group_partition_run_new_partition_now`,
`group_inner_order_value_audit`, `group_inner_order_run_more_sweeps_now`,
`group_inner_order_best_nonbaseline_delta_ms_per_request`,
`group_inner_order_top_value_lever`,
`group_switch_accounting`, `group_switch_gap_ms_per_request`,
`scheduler_overhead_budget`, `deprioritize_python_inter_segment_gap_tuning`,
`tuning_decision_matrix`, `tuning_preferred_group_policy`, `tuning_preferred_inner_order`,
`tuning_primary_code_target`, `tuning_next_s100p_runtime_experiment_allowed`,
`tuning_primary_code_target_projected_saved_ms_per_request`,
`tuning_primary_code_target_not_bpu_promotion_proof`,
`tuning_standard_sweeps_blocked_by_final_logits_leverage`,
`tuning_next_compile_allowed`,
`final_logits_leverage_model`, `final_logits_leverage_projection_saved_ms_per_request`,
`final_logits_leverage_projection_capture_pct`, `final_logits_leverage_not_bpu_promotion_proof`,
`runtime_instrumentation_ready`, `runtime_instrumentation_contract`, `runtime_instrumentation_deployment`,
`runtime_instrumentation_remote_probe_sha256`,
`post_instrumentation_telemetry_gate`, `post_instrumentation_telemetry_ready`,
`input_output_overhead_quantified`, `do_not_claim_input_output_overhead_yet`,
`allow_one_post_instrumentation_baseline_measurement`,
`post_instrumentation_overhead_analysis`, `input_prepare_ms_per_request`,
`output_postprocess_ms_per_request`, `hidden_materialize_ms_per_request`,
`final_logits_compute_still_primary`,
`post_instrumentation_segment_attribution`, `post_segment_primary_single_segment_bottleneck`,
`post_segment_group_size_tuning_implication`, `post_segment_inner_order_tuning_implication`,
`segment_group_schedule_scorecard`, `segment_group_primary_schedule_bottleneck`,
`segment_group_primary_code_target`, `segment_group_preferred_group_policy`,
`segment_group_preferred_inner_order`, `segment_group_run_more_standard_sweeps_now`,
`segment_group_run_s100p_runtime_now`, `segment_group_start_compile_now`,
`segment_group_compile_preflight_only_now`,
`hidden_buffer_reuse_decision`, `hidden_buffer_reuse_default`,
`preallocate_hidden_experimental_flag_only`, `reuse_buffer_implementation_measured_slower`,
`hidden_materialize_design_contract_ok`, `hidden_materialize_telemetry_contract_ok`,
`last_token_candidate`, `last_token_readiness_verdict`, `last_token_compile_ready`,
`last_token_runtime_validation_ready`, `last_token_remote_manifest_verified`,
`last_token_experiment_gate`, `last_token_validation_plan`, `last_token_validation_compare`,
`last_token_compare_decision`, `compile_commit_headroom_gb`, `compile_do_not_start_compile_now`,
`compile_command_guard`, `compile_command_guard_b8_full_compile_blocked`,
`compile_command_guard_would_start_compile`, `next_action_admission_pack`,
`next_action_would_start_runtime`, `next_action_would_start_compile`,
`true_batch_nas_inventory`, `nas_remote_b4_group_major_report_count`,
`nas_remote_b4_group_major_report_json_count`,
`nas_b4_remote_json_local_count_match`,
`nas_run_more_standard_b4_runtime_sweeps_now`, `nas_duplicate_stop_rules`,
`runtime_refactor_backlog`, `runtime_refactor_primary_target`,
`runtime_refactor_secondary_target`, `runtime_refactor_preallocate_hidden_rejected`,
`runtime_refactor_rank1_projected_saved_ms_per_request`,
`runtime_refactor_rank1_not_bpu_promotion_proof`,
`runtime_refactor_rank1_blocks_standard_sweeps`,
`runtime_refactor_do_not_change_defaults_now`, `runtime_refactor_do_not_start_s100p_now`,
`runtime_refactor_source_contract`, `runtime_refactor_source_cli_defaults_preserved`,
`runtime_refactor_source_last_token_path_supported`,
`runtime_refactor_source_telemetry_contract_ready`,
`runtime_refactor_source_protected_telemetry_field_count`,
`runtime_refactor_source_protected_telemetry_missing_count`,
`runtime_source_implementation_map`, `runtime_source_pattern_count`,
`runtime_source_missing_source_pattern_count`,
`runtime_source_primary_runtime_refactor_target`,
`runtime_source_s100p_runtime_allowed_now`,
`runtime_source_compile_start_allowed_now`,
`runtime_source_runtime_default_change_allowed_now`,
`runtime_source_standard_sweeps_blocked`,
`runtime_refactor_admission_contract`, `runtime_refactor_admission_local_report_only_allowed_now`,
`runtime_refactor_admission_default_runtime_change_allowed_now`,
`runtime_refactor_admission_s100p_runtime_allowed_now`,
`runtime_refactor_admission_compile_start_allowed_now`,
`runtime_refactor_admission_compile_preflight_only_allowed_now`,
`runtime_refactor_admission_block_standard_sweeps`,
`runtime_refactor_admission_block_prewarm_or_cache_default`,
`hbm_load_accounting_contract`, `hbm_per_segment_load_accounting_ready`,
`hbm_group_load_accounting_ready`, `hbm_prewarm_accounting_ready`,
`hbm_timing_summary_accounts_load_and_prewarm`,
`bottleneck_closure_model`, `bottleneck_closure_primary_next_code_target`,
`bottleneck_closure_final_logits_projection_saved_ms_per_request`,
`bottleneck_closure_projection_is_not_bpu_promotion_proof`,
`bottleneck_closure_requires_real_runtime_result_before_promotion`,
`first_response_slo_tier_guard`, `fast_paths_satisfy_interactive_first_content_slo`,
`sse_progress_satisfies_interactive_progress_slo`,
`backend_first_content_latency_is_not_true_batch_work`,
`slo_fast_path_max_first_content_ms`, `slo_backend_explicit_first_content_p50_ms`,
`slo_limited_evidence_triage`, `slo_limited_evidence_triaged`,
`slo_limited_evidence_release_blocker`, `slo_limited_warnings`,
`queue_batch_service_remains_default`, `do_not_promote_true_batch`,
`nas_inventory_prevents_duplicate_sweeps`,
`group_order_partition_prevents_duplicate_sweeps`, and
`scheduler_overhead_deprioritizes_python_gap_tuning`.

## Operator Portal Server Guardrails API

Update: 2026-06-21 22:37 CST.

Code path:

```text
scripts/probes/ai_nas_operator_portal_server.py
```

Runtime API:

```text
/api/latest.dream7b_service_guardrails
```

Verified API bundle summary from `PortalState.latest_bundle()`; `/api/latest.dream7b_service_guardrails`
returns the same `dream7b_service_guardrails` object:

```text
status: ready
product_verdict: ok_dream7b_product_decision_packet
fast_path_verdict: ok_dream7b_fast_path_regression
guardrail_verdict: ok_dream7b_product_guardrail_snapshot
freshness_verdict: ok_dream7b_default_service_freshness_gate
freshness_failed_checks: []
first_response_slo_tier_guard_verdict: ok_dream7b_first_response_slo_tier_guard
first_response_slo_fast_path_ready: true
first_response_slo_progress_ready: true
first_response_backend_not_true_batch_work: true
first_response_slo_fast_path_max_first_content_ms: 2.575
first_response_slo_first_progress_p50_ms: 278.387
first_response_slo_backend_explicit_first_content_p50_ms: 20771.222
first_response_slo_runtime_started: false
first_response_slo_compile_started: false
group_inner_order_value_audit_verdict: ok_dream7b_b4_group_inner_order_value_audit
group_inner_order_run_more_sweeps_now: false
group_inner_order_current_primary_levers: false
group_inner_order_best_nonbaseline_delta_ms_per_request: 0.227
group_inner_order_capacity_probe_only_candidate_count: 11065
group_inner_order_top_value_lever: seg27_28_last_token_logits_or_output_avoidance
group_inner_order_next_runtime_allowed_now: false
group_inner_order_next_compile_allowed_now: false
queue_batch_service_remains_default: true
do_not_promote_true_batch: true
queue_partial_batch_flush_ready: true
queue_partial_batch_flush_live_summary_ready: false
queue_partial_batch_flush_probe_ready: true
queue_partial_batch_flush_health_snapshot_ready: true
queue_partial_batch_flush_readiness_source: partial_batch_probe
queue_partial_batch_probe_run_dir: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/runs/20260620-105816
queue_partial_batch_probe_ms_per_request: 12323.576
nas_inventory_prevents_duplicate_sweeps: true
nas_remote_group_major_report_json_count: 52
nas_remote_b4_group_major_report_json_count: 24
nas_b4_remote_json_local_count_match: true
nas_missing_report_json_dirs: dream7b_true_batch_group_major_telemetry_20260620-003333_mb192_b64, dream7b_true_batch_group_major_telemetry_20260620-004037_mb1_b64
workstream_remote_b4_group_major_report_json_count: 24
group_order_partition_prevents_duplicate_sweeps: true
scheduler_overhead_deprioritizes_python_gap_tuning: true
segment_group_schedule_scorecard_verdict: ok_dream7b_b4_segment_group_schedule_scorecard
segment_group_primary_schedule_bottleneck: seg27_28_final_logits
segment_group_primary_code_target: seg27_28_last_token_logits_or_output_avoidance
segment_group_preferred_group_policy: keep_existing_5_group_segment_major_default
segment_group_preferred_inner_order: segment-major
segment_group_run_more_standard_sweeps_now: false
segment_group_run_s100p_runtime_now: false
segment_group_start_compile_now: false
segment_group_compile_preflight_only_now: true
segment_group_final_excess_to_group_switch_gap_ratio: 122.539
runtime_experiment_gate_verdict: blocked_dream7b_b4_runtime_experiment_gate_no_s100p_run_now
s100p_runtime_experiment_now: false
allowed_s100p_runtime_experiments: []
next_nonduplicate_runtime_candidate: seg27_28_last_token_logits
runtime_gate_post_segment_blocks_standard_group_sweeps: true
runtime_gate_post_segment_group_size_tuning_implication: keep_existing_5_group_segment_major_default
runtime_gate_post_segment_inner_order_tuning_implication: keep_segment_major
segment_stability_audit_verdict: ok_dream7b_b4_segment_stability_audit
stable_primary_bottleneck: seg27_28_final_logits
final_logits_rank1_rate: 1.0
final_logits_cv_positive_excess: 0.001996
do_not_run_hidden_order_sweeps_now: true
segment_drag_breakdown_verdict: ok_dream7b_b4_segment_drag_breakdown
segment_drag_analyzed_run_count: 19
segment_drag_latest_microbatch_count: 4096
segment_drag_final_avg_run_ms: 20.272
segment_drag_hidden_mean_avg_run_ms: 8.1022
segment_drag_final_vs_hidden_mean_ratio: 2.5021
segment_drag_final_excess_ms_per_request: 3.04246
segment_drag_token_excess_ms_per_request: 0.10821
segment_drag_top_group_by_accounted_ms: 0:6
segment_drag_top_group_contains_final_logits: false
segment_drag_top_segments: seg27_28 final_logits, seg00_01 token_embedding, seg05_06 hidden_block
group_order_verdict: ok_dream7b_b4_group_order_candidate_analysis
group_order_baseline: mb512_segment_major_5g_baseline
group_order_segment_major_preferred: true
group_order_best_nonbaseline_variant: mb512_segment_major_g7_even
group_order_best_nonbaseline_delta_ms_per_request: 0.227
group_order_no_variant_beats_baseline: true
group_order_more_mb512_sweeps_deprioritized: true
group_partition_verdict: ok_dream7b_b4_group_partition_planner
group_partition_candidate_count: 155457
group_partition_run_new_partition_now: false
group_partition_top_capacity_probe_groups: 0:2,2:6,6:11,11:16,16:21,21:26,26:28
group_partition_top_capacity_probe_peak_delta_pct: -40.827
group_switch_accounting_verdict: ok_dream7b_b4_group_switch_accounting
group_switch_gap_ms_per_request: 0.024841
group_release_ms_per_request: 0.011831
unaccounted_gap_ms_per_request: 0.01301
latest_gap_intra_segment_run_gap_ms_per_request: 0.061106
final_excess_to_switch_gap_ratio: 122.48
group_release_and_unaccounted_gap_not_primary: true
scheduler_overhead_budget_verdict: ok_dream7b_b4_scheduler_overhead_budget
scheduler_primary_code_target: seg27_28_last_token_logits_or_output_avoidance
scheduler_final_excess_to_group_switch_gap: 122.477
scheduler_final_excess_to_intra_segment_gap: 49.79
deprioritize_python_inter_segment_gap_tuning: true
runtime_instrumentation_ready: true
runtime_instrumentation_contract_verdict: ok_dream7b_true_batch_runtime_instrumentation_contract
runtime_instrumentation_deployment_verdict: ok_dream7b_true_batch_runtime_instrumentation_deployment_contract
runtime_instrumentation_default_cli_changed: false
runtime_instrumentation_runtime_order_changed: false
runtime_instrumentation_remote_probe_sha256: 1cc812c43dea8b56ee010fbc73d909c4cb0b9b865dea37cb0e998972d9c168ed
runtime_instrumentation_active_true_batch_python: 0.0
runtime_instrumentation_active_compile_true_batch: 0.0
hbm_load_accounting_ready: true
hbm_load_accounting_contract_verdict: ok_dream7b_true_batch_hbm_load_accounting_contract
hbm_per_segment_load_accounting_ready: true
hbm_group_load_accounting_ready: true
hbm_prewarm_accounting_ready: true
hbm_timing_summary_accounts_load_and_prewarm: true
hbm_prewarm_hbm_default_changed: false
hbm_accounting_runtime_started: false
hbm_accounting_compile_started: false
bottleneck_closure_ready: true
bottleneck_closure_model_verdict: ok_dream7b_b4_bottleneck_closure_model
bottleneck_closure_primary_next_code_target: seg27_28_last_token_logits
bottleneck_closure_final_logits_projection_saved_ms_per_request: 2.852297
bottleneck_closure_hbm_group_load_ms_per_request: 4.02175
bottleneck_closure_release_plus_unaccounted_group_gap_ms_per_request: 0.024841
bottleneck_closure_projection_is_not_bpu_promotion_proof: true
bottleneck_closure_requires_real_runtime_result_before_promotion: true
post_instrumentation_telemetry_gate_verdict: ok_dream7b_b4_post_instrumentation_telemetry_ready
post_instrumentation_success_count: 1
post_instrumentation_telemetry_ready: true
input_output_overhead_quantified: true
do_not_claim_input_output_overhead_yet: false
allow_one_post_instrumentation_baseline_measurement_when_s100p_budget_available: false
post_instrumentation_overhead_analysis_verdict: ok_dream7b_b4_post_instrumentation_overhead_analysis
post_instrumentation_input_prepare_ms_per_request: 0.057071
post_instrumentation_output_postprocess_ms_per_request: 1.691877
post_instrumentation_hidden_materialize_ms_per_request: 1.278005
post_instrumentation_final_output_postprocess_ms_per_request: 0.09065
post_instrumentation_final_excess_ms_per_request_vs_hidden: 3.044
post_instrumentation_final_logits_compute_still_primary: true
post_instrumentation_secondary_local_runtime_code_target: hidden_materialize_buffer_reuse
post_instrumentation_segment_attribution_verdict: ok_dream7b_b4_post_instrumentation_segment_attribution
post_segment_primary_single_segment_bottleneck: seg27_28_final_logits
post_segment_final_compute_excess_ms_per_request: 3.044
post_segment_top_group_by_segment_total: 0:6
post_segment_top_group_contains_final_logits: false
post_segment_group_size_tuning_implication: keep_existing_5_group_segment_major_default
post_segment_inner_order_tuning_implication: keep_segment_major
final_logits_leverage_model_verdict: ok_dream7b_b4_final_logits_leverage_model
final_logits_leverage_projection_saved_ms_per_request: 2.852297
final_logits_leverage_projection_capture_pct: 93.75
final_logits_leverage_latest_projected_latency_reduction_pct: 4.342
final_logits_leverage_latest_nonzero_shortfall_points: 9.318
final_logits_leverage_low_load_nonzero_shortfall_points: 8.201
final_logits_leverage_not_bpu_promotion_proof: true
last_token_candidate: seg27_28_last_token_logits
last_token_readiness_verdict: blocked_dream7b_b4_last_token_compile
last_token_compile_ready: false
last_token_runtime_validation_ready: false
last_token_target_shape: [4, 1, 152064]
last_token_saved_ms_projection: 2.852297
last_token_remote_manifest_verified: false
last_token_remote_hbm_exists: false
last_token_experiment_gate_verdict: blocked_dream7b_b4_last_token_experiment_gate
last_token_gate_blockers: last_token_compile_not_ready, last_token_manifest_not_ready, last_token_runtime_validation_not_ready
last_token_gate_experiment_ready: false
last_token_validation_plan_verdict: blocked_dream7b_b4_last_token_runtime_validation_plan
last_token_validation_plan_generated_at: 2026-06-21T15:53:30.380590+08:00
last_token_validation_ready: false
last_token_validation_blockers: last_token_manifest_not_ready
last_token_validation_final_hbm_root_exists: false
last_token_validation_hbm_exists: false
last_token_validation_manifest_exists: false
last_token_validation_manifest_verified: false
last_token_validation_hbm_path: /mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b4-last-token-final/seg27_28/dream7b_segment_27_28_seq16_b4_q8_last_token_logits.hbm
last_token_validation_compare_verdict: blocked_dream7b_b4_last_token_validation_compare_missing_result
last_token_compare_decision: await_last_token_runtime_result
last_token_candidate_result_exists: false
last_token_preflight_commit_headroom_gb: 3.69
last_token_preflight_commit_headroom_deficit_gb: 60.31
compile_remaining_deficit_after_reclaim_gb: 42.05
compile_do_not_start_compile_now: true
true_batch_nas_inventory_verdict: ok_dream7b_true_batch_nas_inventory
nas_remote_group_major_report_count: 54
nas_remote_b4_group_major_report_count: 24
nas_local_b4_json_count: 24
nas_b4_hbm_count: 28
nas_b4_manifest_count: 28
nas_run_more_standard_b4_runtime_sweeps_now: false
nas_duplicate_stop_rules: 5 entries
workstream_overlap_audit_verdict: ok_dream7b_workstream_overlap_audit
workstream_queue_work_duplicates_true_batch_rental: false
workstream_standard_true_batch_runtime_blocked: true
runtime_refactor_backlog_verdict: ok_dream7b_b4_runtime_refactor_backlog
runtime_refactor_primary_target: final_logits_last_token_path
runtime_refactor_secondary_target: alternative_hidden_materialize_avoidance_without_preallocated_copyto
runtime_refactor_preallocate_hidden_rejected: true
runtime_refactor_rank1_projected_saved_ms_per_request: 2.852297
runtime_refactor_rank1_not_bpu_promotion_proof: true
runtime_refactor_rank1_blocks_standard_sweeps: true
runtime_refactor_ready_local_count: 2
runtime_refactor_do_not_change_defaults_now: true
runtime_refactor_do_not_start_s100p_now: true
runtime_refactor_top_items: final_logits_last_token_path, alternative_hidden_materialize_avoidance, segment_loop_bookkeeping
runtime_refactor_admission_contract_verdict: ok_dream7b_b4_runtime_refactor_admission_contract
runtime_refactor_admission_local_report_only_allowed_now: true
runtime_refactor_admission_design_only_hidden_materialize_allowed_now: true
runtime_refactor_admission_default_runtime_change_allowed_now: false
runtime_refactor_admission_s100p_runtime_allowed_now: false
runtime_refactor_admission_compile_start_allowed_now: false
runtime_refactor_admission_compile_preflight_only_allowed_now: true
runtime_refactor_admission_block_standard_sweeps: true
runtime_refactor_admission_block_prewarm_or_cache_default: true
quick_ready_first_content_ms: 2.501
quick_ready_execution_path: gateway_fast_ready
default_rollback_dry_run_ready: true
gateway_listener_ownership_verdict: ok_dream7b_gateway_listener_ownership
gateway_listener_pid: 4084603
gateway_main_pid: 4084603
gateway_listener_matches_systemd_main_pid: true
gateway_orphan_listener_detected: false
gateway_listener_health_ok: true
gateway_listener_drift_gate_verdict: ok_dream7b_gateway_listener_drift_gate
gateway_listener_drift_live_matches_systemd_main_pid: true
gateway_listener_drift_live_orphan_detected: false
gateway_listener_drift_live_health_ok: true
gateway_listener_drift_warning_count: 0
```

The `/api/latest` bundle and Goal Progress table now also include `dream7b_service_guardrails` with default-service
freshness state, so the live Portal surface no longer depends only on the older `dream7b_perf_identity` report for
Dream7B status and does not hide the true-batch non-promotion guard.

## Dream7B Gateway Listener Recovery

Update: 2026-06-20 18:10 CST.

Observed state:

```text
dream7b-local-openai-gateway.service: activating (auto-restart), ExecMainStatus=1
```

Root cause:

```text
127.0.0.1:18888 was already held by orphan root process:
4021543 /usr/bin/python3 /root/.openclaw/workspace/scripts/dream7b_local_openai_gateway.py
```

Action:

```text
terminated only the orphan listener process on port 18888
```

Post-recovery state:

```text
dream7b-bpu-batch-queue.service: active / enabled
dream7b-local-openai-gateway.service: active
openclaw-gateway.service: active
18888 listener: python3 pid 4084603
health: {"ok": true, "model": "Dream7B-S100P-local", "backend": "dream7b-text"}
```

Follow-up ownership guardrail:

```text
tmp/product_guardrail_snapshots/dream7b_gateway_listener_ownership_20260620-181657/dream7b_gateway_listener_ownership.json
```

Summary:

- verdict: `ok_dream7b_gateway_listener_ownership`
- gateway main PID: `4084603`
- 18888 listener PID: `4084603`
- listener matches systemd MainPID: `true`
- orphan listener detected: `false`
- gateway health: `ok`

Production gap:

```text
Production still needs a live web/chat surface backed by the mounted NAS and OpenClaw session auth; this contract verifies the required user-facing information model.
```

## Product Decision Packet

Update: 2026-06-22 12:22 CST.

Report:

```text
tmp/product_guardrail_snapshots/dream7b_product_decision_packet_20260622-122135/dream7b_product_decision_packet.json
```

Summary:

- verdict: `ok_dream7b_product_decision_packet`
- production default: `queue_batch`
- B=4 true-batch status: `research_artifact_not_promoted`
- `dream7b-bpu-batch-queue.service`: active / enabled
- `dream7b-local-openai-gateway.service`: active / enabled
- rollback script: present on NAS
- recovery contract: `dream7b-default-status json` is parseable and reports active/enabled segment-major default; rollback dry-run returned `dry_run=1; no changes applied`
- status script sha256: `67a957abd62581547c248fd22a1c4d13ae33d0653de35e67898b7e0e440dcadb`
- rollback script sha256: `911d5bb43fe5844c17eaed3d18eecd3cee1257f834e855505327dd2db376bf80`
- gateway listener ownership: `ok_dream7b_gateway_listener_ownership`
- gateway listener PID equals systemd MainPID: `4084603`
- gateway orphan listener detected: `false`
- gateway listener drift gate: `ok_dream7b_gateway_listener_drift_gate`
- gateway listener drift live PID match: `true`
- gateway listener drift live orphan detected: `false`
- gateway listener drift warnings: `0`
- partial-batch flush readiness: aggregate `true`; live service summary `false`; standalone partial-batch probe `true`; queue-health snapshot `true`; readiness source `partial_batch_probe`
- partial-batch probe evidence: run `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/runs/20260620-105816`, pending count `2`, effective max job count `2`, processed requests `2`, `12323.576 ms/request`
- scheduler overhead budget: `ok_dream7b_b4_scheduler_overhead_budget`
- scheduler primary code target: `seg27_28_last_token_logits_or_output_avoidance`
- final excess to group-switch-gap ratio: `122.477`
- final excess to intra-segment-gap ratio: `49.79`
- Python inter-segment gap tuning: deprioritized until final-logits candidate changes the active path
- runtime instrumentation contract: `ok_dream7b_true_batch_runtime_instrumentation_contract`; `scripts/probes/dream7b_true_batch_group_major_telemetry_probe.py` contract now validates `22` fields covering input prepare, output postprocess, `group_loop_ms`, group load/release, `loaded_segments`, inter/intra-segment gaps, `final_logits_mode`, `final_hbm_root`, `expected_final_shape`, and `final_shape` without changing default CLI behavior or runtime order
- runtime instrumentation evidence: `tmp\b4_runtime_schedule_analysis_20260619\dream7b_true_batch_runtime_instrumentation_contract_20260621.json`
- remote runtime instrumentation deployment: `ok_dream7b_true_batch_runtime_instrumentation_deployment_contract`; NAS probe `/mnt/nas/openclaw/scripts/probes/dream7b_true_batch_group_major_telemetry_probe.py` now has input/postprocess instrumentation with sha256 `1cc812c43dea8b56ee010fbc73d909c4cb0b9b865dea37cb0e998972d9c168ed`
- remote instrumentation backup: `/mnt/nas/openclaw/scripts/probes/dream7b_true_batch_group_major_telemetry_probe.py.bak_20260621-004652_pre_input_postprocess_instrumentation`; deployment evidence `tmp\b4_runtime_schedule_analysis_20260619\dream7b_true_batch_runtime_instrumentation_deployment_contract_20260621.json`; active true-batch runtime `0`, active compile `0`
- HBM load accounting contract: `ok_dream7b_true_batch_hbm_load_accounting_contract`; evidence `tmp\b4_runtime_schedule_analysis_20260619\dream7b_true_batch_hbm_load_accounting_contract_20260621.json`; per-segment load accounting, group-load accounting, prewarm accounting, and timing-summary load/prewarm accounting are all ready; `prewarm_hbm_default_changed=false`; runtime started `false`, compile started `false`
- bottleneck closure model: `ok_dream7b_b4_bottleneck_closure_model`; evidence `tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_bottleneck_closure_model_20260621.json`; latest B=4 mb4096 is `65.684 ms/request`, avg BPU gap to queue `-8.918` points, and nonzero BPU shortfall for 93 avg remains `9.318` points
- closure ranking: `seg27_28_last_token_logits` projection saves `2.852297 ms/request`; HBM group-load residency ceiling is `4.02175 ms/request`; release plus unaccounted group gap is only `0.024841 ms/request`; small Python/gap/postprocess optimizations combined are `3.545443 ms/request`
- closure decision: keep primary code target `seg27_28_last_token_logits`; group size / inner order are not current primary levers; all projections remain not BPU-promotion proof and require a real runtime result before promotion
- post-instrumentation telemetry gate: `ok_dream7b_b4_post_instrumentation_telemetry_ready`; evidence `tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_post_instrumentation_telemetry_gate_20260621.json`; successful post-instrumentation B=4 telemetry `1`
- post-instrumentation telemetry: `tmp\remote_true_batch_reports\b4_mb512_segment_major_post_instrumentation_20260621_true_batch_group_major_telemetry.json`; mb512 segment-major 5-group baseline, `94.681 ms/request`, avg BPU `58.363`, nonzero BPU `88.879`
- post-instrumentation overhead analysis: `ok_dream7b_b4_post_instrumentation_overhead_analysis`; evidence `tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_post_instrumentation_overhead_analysis_20260621.json`; input prepare `0.057071 ms/request`, output postprocess `1.691877 ms/request`, hidden materialize `1.278005 ms/request`, final logits output postprocess `0.09065 ms/request`, final excess versus hidden `3.044 ms/request`
- post-instrumentation decision: input prepare is not primary, output postprocess is not primary, hidden materialize buffer reuse has a measured ceiling, and final logits compute/output avoidance remains the primary code target
- post-instrumentation segment attribution: `ok_dream7b_b4_post_instrumentation_segment_attribution`; evidence `tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_post_instrumentation_segment_attribution_20260621.json`; top single segment is `seg27_28_final_logits` at `5.166791 ms/request`, final compute excess remains `3.044 ms/request`, top group by segment total is `0:6` and does not contain final logits, so group-size policy remains `keep_existing_5_group_segment_major_default` and inner order remains `keep_segment_major`
- segment/group schedule scorecard: `ok_dream7b_b4_segment_group_schedule_scorecard`; evidence `tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_segment_group_schedule_scorecard_20260621.json`; primary schedule bottleneck `seg27_28_final_logits`; primary code target `seg27_28_last_token_logits_or_output_avoidance`; preferred group policy `keep_existing_5_group_segment_major_default`; preferred inner order `segment-major`; run more standard group/inner-order sweeps `false`; run S100P runtime now `false`; start compile now `false`; compile preflight-only now `true`
- B=4 per-run evidence matrix: `ok_dream7b_b4_per_run_evidence_matrix`; evidence `tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_per_run_evidence_matrix_20260622.json`; `23` total runs, `20` successful runs, `3` failed capacity/runtime samples preserved; top slowest segment `seg27_final_logits` in `19/19` successful runs with segment timing; mb512 segment-major is `-0.584 ms/request` versus microbatch-major; mb512 g6, g7, and final-isolated group variants are `+0.238`, `+0.094`, and `+0.143 ms/request` versus the gap-field baseline; standard B=4 runtime sweep status remains `blocked_duplicate`
- segment/group quantified gap: final logits compute excess `3.044 ms/request`, final-to-top-hidden compute excess ratio `96.635`, final-excess-to-group-switch-gap ratio `122.539`, best nonbaseline group/order delta `+0.227 ms/request`; scorecard top target remains `seg27_28_last_token_logits_or_output_avoidance`
- hidden-buffer reuse decision: `ok_dream7b_b4_hidden_buffer_reuse_decision`; evidence `tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_hidden_buffer_reuse_decision_20260621.json`; existing `--preallocate-hidden` reused `13824` buffers but increased latency by `0.845 ms/request` and hidden materialize by `0.690524 ms/request`, so `hidden_buffer_reuse_default=false` and `preallocate_hidden_experimental_flag_only=true`
- hidden-materialize design contract: `ok_dream7b_b4_hidden_materialize_design_contract`; evidence `tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_hidden_materialize_design_contract_20260622.json`; `5` design rows, `2` allowed design/report-only rows, source anchor missing count `0`; current preallocate-hidden/copyto path remains rejected, `next_design_only_item=scale_none_no_copy_handoff`, `next_report_only_item=hidden_materialize_telemetry_only`, and default runtime change, S100P runtime, and compile start are all `false`
- hidden-materialize telemetry contract: `ok_dream7b_b4_hidden_materialize_telemetry_contract`; evidence `tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_hidden_materialize_telemetry_contract_20260622.json`; runtime source now reports `output_quant_scale_none_count`, `output_dtype_counts`, `output_dtype_by_segment`, `output_c_contiguous_count`, `output_c_contiguous_by_segment`, `hidden_materialize_candidate_mode_counts`, and `hidden_materialize_candidate_mode_by_segment`; source anchor missing count `0`; telemetry source ready `true`; default runtime change, S100P runtime, and compile start remain `false`
- runtime refactor backlog: `ok_dream7b_b4_runtime_refactor_backlog`; primary target `final_logits_last_token_path`; rank-1 projected saving `2.852297 ms/request`; rank-1 remains latency-only and not BPU-promotion proof; standard group/inner-order sweeps remain blocked; secondary research target `alternative_hidden_materialize_avoidance_without_preallocated_copyto`; current `--preallocate-hidden` path is rejected by evidence and remains experimental; local-only/refactor candidates `2`; runtime defaults and S100P runtime experiments remain blocked now
- runtime refactor source contract: `ok_dream7b_b4_runtime_refactor_source_contract`; CLI defaults preserved `true`; last-token path supported `true`; telemetry contract ready `true`; protected telemetry fields `22`, missing `0`; runtime order changed `false`; experimental preallocate/prewarm flags remain explicit defaults
- runtime source implementation map: `ok_dream7b_b4_runtime_source_implementation_map`; evidence `tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_runtime_source_implementation_map_20260621.json`; product packet check `runtime_source_implementation_map_ok=true`; mapped `6` implementation areas and `40` source markers with `0` missing; allowed-now areas are local report-only telemetry checks and design-only hidden-materialize notes; duplicate or blocked areas are group scheduling, prewarm/cache, release-GC/group-switch, and last-token runtime validation until manifest/runtime gates open
- runtime refactor work order: `ok_dream7b_b4_runtime_refactor_work_order`; evidence `tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_runtime_refactor_work_order_20260622.json`; product packet checks `runtime_refactor_work_order_ok=true`, `hidden_materialize_design_contract_ok=true`, and `hidden_materialize_telemetry_contract_ok=true`; `5` work orders, source anchor missing count `0`, next local work `alternative_hidden_materialize_avoidance`, hidden-materialize next design item `scale_none_no_copy_handoff`, next evidence gate `run one existing B=4 telemetry command later to populate scale/dtype/contiguity fields`, primary future runtime candidate `final_logits_last_token_path`; default runtime change, S100P runtime, and compile start all remain `false`
- runtime refactor admission contract: `ok_dream7b_b4_runtime_refactor_admission_contract`; local report-only refactor allowed now `true`; design-only hidden-materialize avoidance allowed now `true`; default runtime code change `false`; S100P runtime experiment `false`; compile start `false`; compile preflight-only `true`; standard group/inner-order sweeps blocked `true`; prewarm/cache default blocked `true`; failed checks `0`
- tuning decision matrix: `ok_dream7b_b4_tuning_decision_matrix`; primary code target `seg27_28_last_token_logits_or_output_avoidance`; projected saving `2.852297 ms/request`; target remains not BPU-promotion proof; standard group/inner-order sweeps remain blocked by final-logits leverage; S100P runtime and compile remain disallowed now
- runtime experiment admission gate: `blocked_dream7b_b4_runtime_experiment_gate_no_s100p_run_now`; admission evidence ready `true`; final-logits leverage, runtime-refactor, tuning-matrix, and per-run matrix gates all ready; per-run matrix rows `23` total, `20` ok, `3` failed, top segment `seg27_final_logits @ 1.0`, standard sweep status `blocked_duplicate`; admission projected saving `2.852297 ms/request`; admission keeps true-batch promotion and standard group/inner-order sweeps blocked
- runtime command guard: `ok_dream7b_b4_runtime_command_guard`; guard active `true`; standard B=4 true-batch sweep commands blocked `true`; default command admitted `false`; would start runtime `false`; last-token validation command remains gated until runtime gate opens
- compile command guard: `ok_dream7b_b4_compile_command_guard`; guard active `true`; only B=4 `seg27_28` last-token compile shape is allowed; B=8/full compile blocked `true`; current command admitted `false`; would start compile `false`; blocked now by readiness `true` and capacity `true`
- next-action admission pack: `ok_dream7b_b4_next_action_admission_pack`; allowed-now actions `2`, preflight-only actions `1`, blocked actions `4`; would start runtime `false`; would start compile `false`; per-run matrix gate ready `true`, top segment `seg27_final_logits @ 1.0`, standard sweep status `blocked_duplicate`; only future true-batch runtime candidate is `seg27_28_last_token_logits_after_manifest_ready`
- last-token experiment gate: `blocked_dream7b_b4_last_token_experiment_gate`
- last-token code support ready: `true`
- last-token gate blockers: `last_token_compile_not_ready`, `last_token_manifest_not_ready`, `last_token_runtime_validation_not_ready`
- last-token runtime validation plan: `blocked_dream7b_b4_last_token_runtime_validation_plan`
- last-token runtime validation ready: `false`
- last-token runtime validation blockers: `last_token_manifest_not_ready`
- last-token runtime validation S100P state: refreshed read-only at `2026-06-21T15:53:30+08:00`; queue_idle `true`, services_ready `true`, runtime_tools_ready `true`, lock_busy `false`
- last-token runtime validation command: recorded for mb512, segment-major, 5-group run with `--final-hbm-root` and `--final-logits-mode last-token`
- last-token validation compare: `blocked_dream7b_b4_last_token_validation_compare_missing_result`; candidate telemetry is not present yet, so no last-token runtime win is asserted
- last-token validation compare baseline: `b4_mb512_segment_major_gap_fields_true_batch_group_major_telemetry.json`, `93.863 ms/request`, avg BPU `59.142`, nonzero BPU `89.555`
- last-token compile preflight: commit headroom `3.69 GB`, deficit `60.31 GB`, largest private process `F:\Program\Anaconda\envs\tf2\python.exe`, pid `261928`, private `18.26 GB`
- last-token compile capacity: after closing that large private process, projected headroom is `21.95 GB`; remaining deficit is `42.05 GB`; recommended additional commit limit with safety is `50.05 GB`; compile remains blocked
- last-token remote manifest: final HBM root exists `false`, final HBM exists `false`, manifest exists `false`, manifest verified `false`; expected HBM path `/mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b4-last-token-final/seg27_28/dream7b_segment_27_28_seq16_b4_q8_last_token_logits.hbm`
- final-logits leverage model: `ok_dream7b_b4_final_logits_leverage_model`; projected saving `2.852297 ms/request`, which captures `93.75%` of measured final-logits excess
- final-logits leverage ceiling: latest mb4096 projected wall time `62.831703 ms/request`, latency reduction `4.342%`
- final-logits BPU caveat: latest nonzero BPU still falls short by `9.318` points for a 93 average, and by `8.201` points under the low-load projection; this projection is not BPU-promotion proof
- final-logits validation rule: require real last-token telemetry before promotion; keep standard group/inner-order sweeps blocked until the active runtime profile changes
- runtime experiment gate: `blocked_dream7b_b4_runtime_experiment_gate_no_s100p_run_now`
- S100P runtime experiment now: `false`
- allowed S100P runtime experiments: `[]`
- runtime gate post-segment blocker: `post_instrumentation_segment_attribution_blocks_group_order_sweeps`; post-segment attribution keeps standard group/order sweeps blocked with `keep_existing_5_group_segment_major_default` and `keep_segment_major`
- next non-duplicate runtime candidate: `seg27_28_last_token_logits`
- runtime gate reason: standard B=4 sweeps are duplicate, the one post-instrumentation baseline measurement has completed, and last-token candidate is still not ready
- segment stability audit: `ok_dream7b_b4_segment_stability_audit`
- stable primary bottleneck: `seg27_28_final_logits`
- segment drag breakdown: `ok_dream7b_b4_segment_drag_breakdown`; latest B=4 mb4096 final logits `20.272 ms` versus hidden mean `8.1022 ms`, ratio `2.5021`; final excess `3.04246 ms/request`; token excess `0.10821 ms/request`; top accounted group `0:6`, not the final group
- final logits rank-1 rate: `1.0` across `19` analyzed B=4 runs
- final logits positive-excess CV: `0.001996`
- final-to-token positive-excess ratio: `28.472`
- final-to-max-hidden positive-excess ratio: `847.625`
- hidden-order sweep guard: `do_not_run_hidden_order_sweeps_now=true`
- latest B=4 analysis telemetry count: `23`
- successful B=4 telemetry count: `20`
- failed capacity probe count: `3`
- latest B=4 point: `4096` microbatches, `16384` processed requests
- latest B=4 avg BPU: `84.248`
- latest B=4 nonzero BPU: `89.694`
- latest B=4 wall time: `65.684 ms/request`
- B=4 gap versus queue baseline: `-8.918` avg BPU points, `-5.403` nonzero BPU points
- mb512 even 6-group versus current 5-group: `+0.238 ms/request`, `-0.188` avg BPU points, `-0.123` nonzero BPU points
- mb512 final-isolated 6-group versus current 5-group: `+0.143 ms/request`, `-0.313` avg BPU points, `-0.545` nonzero BPU points
- mb512 7-group versus current 5-group: `+0.094 ms/request`, `-0.105` avg BPU points, `-0.207` nonzero BPU points
- group/order candidate analysis with best mb512 5-group baseline: no observed non-baseline variant beats baseline; 7-group is the least-bad non-baseline at `+0.227 ms/request`, so more mb512 boundary sweeps are deprioritized
- release GC skip versus latest collect at mb128: `-1.563 ms/request`, `+0.326` avg BPU points, `-0.29` nonzero BPU points, total group-release time `-32.548 ms`
- release GC skip versus mb512 gap-field collect: `+0.265 ms/request`, `-0.057` avg BPU points, `+0.124` nonzero BPU points, total group-release time `-34.574 ms`; not a primary lever and not a default runtime candidate
- HBM load attribution: per-segment load telemetry is ready; token embedding load `7267.292 ms` and final logits load `6694.141 ms` are the two largest segment loads, but the largest load group is `0:6`, not the final group
- HBM prewarm: group-load improves by `-2479.499 ms`, but explicit pre-read costs `65754.965 ms` for `7093.533 MiB` and worsens wall time by `+123.498 ms/request`; `prewarm_hbm_default=false`
- preallocate hidden default: `false`; latest mb512 A/B was worse by `+0.845 ms/request`, `-0.59` avg BPU points, `-1.43` nonzero BPU points, and `+1414.194 ms` hidden materialization
- long 4-group experiment: disabled by evidence; B=4 4-group load failed at `seg06_07` with memory allocation failure
- gap-field capacity probes: mb768 failed at `seg02_03`; mb1024 failed after group `0:6` while loading `seg10_11`; both had `processed_request_count=0`
- runtime capacity boundary: latest gap-instrumented success is `mb512`; first gap-instrumented failure is `mb768`; do not continue gap microbatch sweeps above the success boundary until the memory/runtime plan changes
- group/order candidate gate: segment-major preferred over microbatch-major; keep `g7_even_lower_peak_hbm` only as a targeted capacity probe if the memory plan changes
- group partition planner: `ok_dream7b_b4_group_partition_planner`; searched `155457` contiguous partitions and set `run_new_partition_now=false`
- planner top capacity probe: `0:2,2:6,6:11,11:16,16:21,21:26,26:28`, max group HBM `1078.566 MiB`, `-40.827%` versus baseline, estimated release delta `+0.036512 ms/request`
- planner observed nonbaseline result: best observed nonbaseline is still slower by `+0.227 ms/request`, so new partitions are capacity probes only after the memory plan changes, not normal tuning sweeps
- group/inner-order value audit: `ok_dream7b_b4_group_inner_order_value_audit`; 4/4 observed nonbaseline variants are slower-or-equal than the mb512 5-group segment-major baseline, the best nonbaseline is `mb512_segment_major_g7_even` at `+0.227 ms/request`, and `run_more_group_size_or_inner_order_sweeps_now=false`
- group/inner-order remaining value: `11065` lower-HBM partition candidates are kept as capacity probes only after the memory plan changes; top value remains `seg27_28_last_token_logits_or_output_avoidance`, with group-size and inner-order marked non-primary
- true-batch NAS inventory: `ok_dream7b_true_batch_nas_inventory`; current live evidence `tmp\b4_runtime_schedule_analysis_20260619\dream7b_true_batch_nas_inventory_20260621_live.json` has `54` true-batch group-major report directories and `52` actual telemetry JSON files
- live NAS JSON coverage note: the two report directories without telemetry JSON are B=64-only (`dream7b_true_batch_group_major_telemetry_20260620-003333_mb192_b64`, `dream7b_true_batch_group_major_telemetry_20260620-004037_mb1_b64`); B=4 remains `24` report directories and `24` telemetry JSON files mirrored by `24` local B=4 JSON files
- live NAS B=4 duplicate decision: B=4 coverage is unchanged and `b4_remote_json_local_count_match=true`, so current queue-batch/product work still does not duplicate prior true-batch rental work; the missing JSON directories are outside the B=4 duplicate gate
- B=4 HBM inventory: `28` HBM files and `28` manifests under the NAS B=4 root
- standard B=4 runtime sweeps: `run_more_standard_b4_runtime_sweeps_now=false`; mb512 baseline, microbatch-major, g6/g7/final-isolated group variants, prealloc/prewarm/release-GC, and gap-field capacity probes are already covered
- workstream overlap audit: `ok_dream7b_workstream_overlap_audit`; report `tmp\product_guardrail_snapshots\dream7b_workstream_overlap_audit_20260621-133133\dream7b_workstream_overlap_audit.json`
- workstream current focus: `queue_batch_product_guardrail_and_nonduplicate_gate`
- queue-batch work duplicates prior true-batch rental: `false`
- standard true-batch runtime now: blocked as duplicate
- tuning decision matrix: `ok_dream7b_b4_tuning_decision_matrix`; evidence `tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_tuning_decision_matrix_20260621.json`
- tuning preferred group policy: `keep_existing_5_group_segment_major_default`
- tuning preferred inner order: `segment-major`
- tuning primary code target: `seg27_28_last_token_logits_or_output_avoidance`
- tuning next S100P runtime experiment allowed: `false`
- tuning next compile allowed: `false`
- microbatch-only sweeps: deprioritized by the scaling saturation gate
- mb6144 stopping rule: do not run until the final-logits candidate or another active-BPU path changes the runtime profile
- next runtime candidate: `seg27_28_last_token_logits`
- scaling saturation projection: if nonzero BPU remains `89.694`, projected avg BPU at 6144/8192/12288 stays below the 93 gate; projected max is `87.729`
- low-load required nonzero BPU for 93 avg: `97.895`
- group switch gap: `0.024841 ms/request` at mb4096, with release `0.011831 ms/request` and unaccounted gap `0.01301 ms/request`
- group load amortization: `4.02175 ms/request` at mb4096; this is fixed HBM group-load cost, not an active-BPU fix
- residual segment overhead excluding hidden materialization: `0.505405 ms/request`
- gap-instrumented B=4 mb512 sample: `b4_mb512_segment_major_gap_fields_true_batch_group_major_telemetry.json`, `93.863 ms/request`, avg BPU `59.142`, nonzero BPU `89.555`
- measured Python scheduling gaps in that sample: inter-segment first-run gap `0.000724 ms/request`, intra-segment run gap `0.061106 ms/request`, residual after measured gaps `0.44394 ms/request`
- final logits excess versus group switch gap: `122.48x`
- final logits: `20.272 ms` average versus hidden-block `8.1022 ms`, ratio `2.5021`
- final output attribution: `ok_dream7b_b4_final_output_attribution`
- latest final run: `5.06795 ms/request`
- latest final output overhead outside `runtime.run`: `0.094674 ms/request`
- latest final excess if hidden speed: `3.042462 ms/request`
- final output recommended next: compile/runtime path that reduces final logits compute or avoids full-vocab output
- segment bottleneck scorecard: `ok_dream7b_b4_segment_bottleneck_scorecard`
- scorecard primary runtime lever: `final_logits_compute_or_output_avoidance`
- scorecard preferred group policy: `5_group_segment_major_default`
- scorecard top action: `target_final_logits_compute_or_output_avoidance`
- scorecard stability: `19` successful segment-major runs analyzed; `10` default collect runs show final-logits positive-excess mean `3.04195 ms/request` with stdev `0.00538`
- scorecard final logits excess: `3.04043 ms/request`; token embedding active-run excess: `0.10679 ms/request`; max hidden-block excess: `0.00296 ms/request`
- scorecard group/order finding: no observed mb512 non-baseline variant beats the 5-group segment-major baseline; microbatch-major is `+0.717 ms/request`, g7 even is `+0.227 ms/request`
- last-token final candidate: `implementation_ready_not_compiled`
- last-token candidate target shape: `[4, 1, 152064]` versus current `[4, 16, 152064]`
- last-token candidate output element reduction: `16.0x`
- projection-only estimated saving: `2.852297 ms/request`
- remote probe readiness: `--final-hbm-root` and `--final-logits-mode` are available on S100P
- last-token experiment gate: `blocked_dream7b_b4_last_token_experiment_gate`; code_support_ready `true`; experiment_ready `false`
- last-token runtime validation plan: `blocked_dream7b_b4_last_token_runtime_validation_plan`; validation_ready `false`; blockers `last_token_manifest_not_ready`
- last-token runtime validation state: queue_idle `true`; services_ready `true`; runtime_tools_ready `true`; lock_busy `false`
- last-token runtime validation expected shape: `[4, 1, 152064]`; microbatch_count `512`; processed_request_count `2048`
- last-token validation compare: `blocked_dream7b_b4_last_token_validation_compare_missing_result`; expected candidate path `tmp\remote_true_batch_reports\b4_mb512_segment_major_last_token_true_batch_group_major_telemetry.json`
- last-token validation compare decision: `await_last_token_runtime_result`; structural_ok `false`, performance_ok `false` because the candidate result is missing
- last-token inventory status: no NAS last-token-final files and no local last-token candidate telemetry yet
- last-token compile readiness: `blocked_dream7b_b4_last_token_compile`
- compile_ready: `false`; runtime_validation_ready: `false`
- readiness blockers: `windows_compile_preflight_failed`, `insufficient_windows_commit_headroom`, `large_private_process_present`, `remote_last_token_manifest_missing`
- alternate final HBM manifest: not present yet; next gate is compile manifest verification followed by mb512 runtime validation
- local compile preflight: commit headroom `3.69 GB` versus `64 GB` guard, deficit `60.31 GB`; largest private process is `F:\Program\Anaconda\envs\tf2\python.exe` at `18.26 GB`
- compile capacity plan: closing the tf2 process would project commit headroom to `21.95 GB`, still `42.05 GB` below the guard
- pagefile/commit capacity: non-elevated WMI pagefile usage/settings queries currently fail with permission denied; recommended additional commit limit with safety is `50.05 GB`, for a projected commit limit around `109.08 GB`
- operational SLO rollup: `13/13` required contracts accepted, blockers `0`, warnings `1`; warning `concurrency_stability:limited_production_evidence` is triaged with release blocker `false`; includes `dream7b_gateway_listener_ownership`, `dream7b_gateway_listener_drift_gate`, Dream7B default-service duplicate-sweep guards, `runtime_instrumentation_ready=true`, `hbm_load_accounting_contract_ok=true`, `bottleneck_closure_model_ok=true`, `hidden_materialize_design_contract_ok=true`, `hidden_materialize_telemetry_contract_ok=true`, `dream7b_first_response_slo_tier_guard`, and `dream7b_default_service_freshness_gate`
- operator portal contract: result count `4`, failures `0`, execution performed `false`; HBM load accounting visibility requirement `true`
- first-response fast status: `ok_dream7b_first_response_fast_status_packet`
- first-response SLO tier guard: `ok_dream7b_first_response_slo_tier_guard`; fast paths satisfy interactive first-content SLO `true`, SSE progress satisfies interactive progress SLO `true`, and backend first-content latency is tracked separately from true-batch work `true`
- first-response SLO tier evidence: fast-path max first content `2.575 ms`, SSE first-progress p50 `278.387 ms`, explicit backend first-content p50 `20771.222 ms`; this guard started no runtime and no compile
- first-response warning triage: `ok_dream7b_first_response_warning_triage`; source warning `warning_dream7b_first_response_packet_content_latency` is product-triaged `true`; quickpath first-content p50 `2.554 ms` versus explicit backend p50 `20771.222 ms`, delta `-20768.668 ms`; backend first-content latency remains a separate product backlog and is not a B=4 true-batch promotion gate; runtime/compile started `false/false`
- SLO limited evidence triage: `ok_ai_nas_slo_limited_evidence_triage`; limited warning `concurrency_stability:limited_production_evidence` is triaged `true` with release blocker `false`; concurrency stability remains observational/limited with verdict `limited_ai_nas_concurrency_stability`, failure count `0`, dialog-health fixture errors `4`; runtime/compile started `false/false`
- fast-path regression: `ok_dream7b_fast_path_regression`
- localized status fast path: ready
- localized status first content: `2.554 ms`
- localized status improvement: `-33167.758 ms`
- regression quick-ready first content: `2.501 ms`
- regression identity first content: `2.575 ms`
- regression localized status first content: `2.554 ms`
- queue health snapshot: `ok_dream7b_queue_health_snapshot`
- queue health report: `tmp\product_guardrail_snapshots\dream7b_queue_health_snapshot_20260621-020844\dream7b_queue_health_snapshot.json`
- queue health current services: queue active/enabled, gateway active/enabled, OpenClaw gateway active
- queue health listener ownership: listener PID `4084603` matches gateway systemd MainPID
- queue health queue idle: pending `0`, processing `0`
- queue health no true-batch/compile process: `true`
- queue health latest text queue run: `ok_dream7b_bpu_text_queue_run`, job_status `done`, `24398.37 ms/request`
- queue health partial-batch flush evidence: run `20260620-105816`, pending at start `2`, processed `2`, `12323.576 ms/request`

Decision:

```text
queue_should_remain_default: true
queue_health_snapshot_ok: true
workstream_overlap_audit_ok: true
true_batch_b4_status: research_artifact_not_promoted
preallocate_hidden_default: false
do_not_run_long_4_group: true
microbatch_only_sweeps_deprioritized: true
do_not_run_mb6144_until_final_logits_candidate_or_active_bpu_path_changes: true
group_release_and_unaccounted_gap_not_primary: true
release_gc_skip_not_primary: true
per_segment_hbm_load_telemetry_ready: true
hbm_load_accounting_contract_ok: true
bottleneck_closure_model_ok: true
group_boundary_tuning_alone_not_primary: true
prewarm_hbm_default: false
localized_status_fast_path_ready: true
next_runtime_candidate: seg27_28_last_token_logits
final_output_recommended_next: compile_or_runtime_path_that_reduces_final_logits_compute_or_avoids_full_vocab_output
last_token_candidate_status: implementation_ready_not_compiled
last_token_experiment_gate: blocked_dream7b_b4_last_token_experiment_gate
last_token_code_support_ready: true
last_token_experiment_ready: false
last_token_compile_ready: false
last_token_runtime_validation_ready: false
last_token_runtime_validation_plan: blocked_dream7b_b4_last_token_runtime_validation_plan
last_token_runtime_validation_plan_ready: false
last_token_runtime_validation_plan_blockers: last_token_manifest_not_ready
last_token_runtime_validation_queue_idle: true
last_token_runtime_validation_services_ready: true
last_token_runtime_validation_runtime_tools_ready: true
last_token_runtime_validation_lock_busy: false
last_token_runtime_validation_expected_shape: [4, 1, 152064]
last_token_compile_capacity_plan: blocked_dream7b_b4_compile_capacity_plan
last_token_additional_commit_limit_needed_after_reclaim_gb: 42.05
last_token_recommended_additional_commit_limit_with_safety_gb: 50.05
last_token_next_gate: compile_manifest_verification_then_mb512_runtime_validation
```

## Default Service Freshness Gate

Update: 2026-06-22 12:22 CST.

Report:

```text
tmp/product_guardrail_snapshots/dream7b_default_service_freshness_gate_latest.json
```

Summary:

- verdict: `ok_dream7b_default_service_freshness_gate`
- product packet checked: `tmp\product_guardrail_snapshots\dream7b_product_decision_packet_20260622-122135\dream7b_product_decision_packet.json`
- product packet verdict: `ok_dream7b_product_decision_packet`; `packet_verdict_accepted=true` and `product_packet_guardrailed_warning=false`
- packet age at check: `0.132 minutes` within threshold `180.0 minutes`
- failed checks: `0`
- SLO limited evidence gate: `slo_limited_evidence_triage_ok=true`, `slo_limited_evidence_triage_starts_no_runtime_or_compile=true`; verdict `ok_ai_nas_slo_limited_evidence_triage`, triaged `true`, release blocker `false`, warning `concurrency_stability:limited_production_evidence`, concurrency verdict `limited_ai_nas_concurrency_stability`, dialog-health fixture errors `4`
- partial-batch flush gate: aggregate `true`, probe-or-health `true`, live summary state recorded `true`; packet summary records live summary `false`, probe `true`, queue-health snapshot `true`, source `partial_batch_probe`, run `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/runs/20260620-105816`, `12323.576 ms/request`
- per-run B=4 evidence matrix gate: `per_run_evidence_matrix_ok=true`, `per_run_evidence_matrix_blocks_standard_sweeps=true`, verdict `ok_dream7b_b4_per_run_evidence_matrix`, run count `23`, successful `20`, failed `3`, top segment `seg27_final_logits`, top-segment rate `1.0`, standard sweep status `blocked_duplicate`, next nonduplicate candidate `seg27_28_last_token_logits`
- NAS duplicate evidence guard: `nas_inventory_prevents_duplicate_sweeps=true`, `nas_inventory_b4_json_mirrored=true`, remote B=4 telemetry JSON `24`, local B=4 JSON `24`
- group/order duplicate sweep guard: `group_order_partition_prevents_duplicate_sweeps=true`
- group/inner-order value guard: `group_inner_order_value_audit_blocks_duplicate_sweeps=true`; best nonbaseline delta `+0.227 ms/request`, run-more-sweeps-now `false`, top value lever `seg27_28_last_token_logits_or_output_avoidance`
- segment/group schedule guard: `segment_group_schedule_scorecard_ok=true`, `segment_group_schedule_blocks_runtime_compile_sweeps=true`, primary bottleneck `seg27_28_final_logits`, primary code target `seg27_28_last_token_logits_or_output_avoidance`, preferred group policy `keep_existing_5_group_segment_major_default`, preferred inner order `segment-major`, S100P runtime now `false`, compile start now `false`
- scheduler gap tuning guard: `scheduler_overhead_deprioritizes_python_gap_tuning=true`
- runtime instrumentation guard: `runtime_instrumentation_ready=true`
- HBM load accounting guard: `hbm_load_accounting_contract_ok=true`, `hbm_load_accounting_contract_verdict=ok_dream7b_true_batch_hbm_load_accounting_contract`, per-segment/group-load/prewarm/timing-summary accounting ready `true`
- bottleneck closure guard: `bottleneck_closure_model_ok=true`, primary target `seg27_28_last_token_logits`, final-logits projection `2.852297 ms/request`, HBM group-load ceiling `4.02175 ms/request`, projection not BPU-promotion proof `true`
- workstream overlap guard: `workstream_overlap_audit_ok=true`, `workstream_queue_work_not_duplicate_true_batch=true`, `workstream_standard_true_batch_runtime_blocked=true`
- tuning matrix guard: `tuning_decision_matrix_ok=true`, `tuning_group_order_keeps_current_default=true`, `tuning_blocks_runtime_and_compile_now=true`, `tuning_matrix_uses_final_logits_leverage=true`
- final-logits leverage guard: `final_logits_leverage_model_ok=true`, `final_logits_leverage_blocks_premature_promotion=true`, `final_logits_leverage_blocks_standard_sweeps=true`
- runtime refactor guard: `runtime_refactor_backlog_rank1_final_logits=true`, `runtime_refactor_backlog_uses_leverage_model=true`, `runtime_refactor_backlog_blocks_standard_sweeps=true`
- runtime refactor source guard: `runtime_refactor_source_contract_ok=true`, `runtime_refactor_source_contract_preserves_defaults=true`, protected telemetry fields `22`, missing `0`
- runtime source implementation map guard: `runtime_source_implementation_map_ok=true`, `runtime_source_implementation_map_blocks_runtime_compile_defaults=true`, source markers `40`, missing `0`, primary target `seg27_28_last_token_logits_or_output_avoidance`, standard sweeps blocked `true`
- runtime refactor work-order guard: `runtime_refactor_work_order_ok=true`, `runtime_refactor_work_order_blocks_runtime_compile_defaults=true`, work orders `5`, allowed local work `1`, source anchor missing count `0`, primary local design item `alternative_hidden_materialize_avoidance`, primary future runtime candidate `final_logits_last_token_path`, default runtime change `false`, S100P runtime `false`, compile start `false`
- hidden-materialize design guard: `hidden_materialize_design_contract_ok=true`, `hidden_materialize_design_contract_blocks_runtime_compile_defaults=true`; verdict `ok_dream7b_b4_hidden_materialize_design_contract`, allowed design-only count `2`, source anchor missing count `0`, current preallocate-hidden rejected `true`, next design item `scale_none_no_copy_handoff`, next report-only item `hidden_materialize_telemetry_only`, default runtime change `false`, S100P runtime `false`, compile start `false`
- hidden-materialize telemetry guard: `hidden_materialize_telemetry_contract_ok=true`, `hidden_materialize_telemetry_contract_blocks_runtime_compile_defaults=true`; verdict `ok_dream7b_b4_hidden_materialize_telemetry_contract`, required telemetry fields `7`, source anchor missing count `0`, telemetry source ready `true`, default runtime change `false`, S100P runtime `false`, compile start `false`
- runtime refactor admission guard: `runtime_refactor_admission_contract_ok=true`, `runtime_refactor_admission_blocks_runtime_compile_defaults=true`, local report-only `true`, default runtime change `false`, S100P runtime `false`, compile start `false`, compile preflight-only `true`
- runtime experiment admission guard: `runtime_experiment_gate_admission_evidence_ready=true`, `runtime_experiment_gate_admission_blocks_standard_sweeps=true`, `runtime_experiment_gate_uses_per_run_matrix=true`, `runtime_gate_per_run_matrix_gate_ready=true`, runtime gate per-run top segment `seg27_final_logits`, standard sweep status `blocked_duplicate`
- runtime command guard: `runtime_command_guard_blocks_standard_sweeps=true`, `runtime_command_guard_starts_no_runtime=true`
- compile command guard: `compile_command_guard_blocks_b8_full_compile=true`, `compile_command_guard_starts_no_compile=true`
- next-action admission guard: `next_action_admission_pack_ok=true`, `next_action_pack_starts_no_runtime_or_compile=true`, `next_action_pack_uses_per_run_matrix=true`, `next_action_pack_per_run_matrix_gate_ready=true`, next-action per-run top segment `seg27_final_logits`, standard sweep status `blocked_duplicate`
- first-response SLO tier guard: `first_response_slo_tier_guard_ok=true`, `first_response_slo_starts_no_runtime_or_compile=true`
- first-response SLO tier summary: `ok_dream7b_first_response_slo_tier_guard`, fast-path max first content `2.575 ms`, SSE first-progress p50 `278.387 ms`, backend explicit first-content p50 `20771.222 ms`, backend-not-true-batch-work `true`
- first-response warning triage gate: `first_response_warning_triage_ok=true`, `first_response_warning_triage_starts_no_runtime_or_compile=true`; verdict `ok_dream7b_first_response_warning_triage`, source warning `warning_dream7b_first_response_packet_content_latency`, triaged `true`, quickpath delta `-20768.668 ms`, backend-not-true-batch-work `true`
- production default: `queue_batch`
- true-batch B=4 status: `research_artifact_not_promoted`
- SLO status: `ok_ai_nas_operational_slo_rollup_contract`, blockers `0`
- Portal status: `ok_ai_nas_operator_portal_contract`, execution_performed `false`
- guardrail status: `ok_dream7b_product_guardrail_snapshot`
- first-response fast status: `ok_dream7b_first_response_fast_status_packet`
- duplicate-sweep guard: `run_more_standard_b4_runtime_sweeps_now=false`
- remote queue service: active / enabled
- remote gateway: active / enabled
- remote OpenClaw gateway: active
- gateway listener PID matches systemd MainPID: `4084603`
- queue pending/processing: `0 / 0`
- gateway health: `ok`

Decision:

```text
queue_batch_service_remains_default: true
do_not_promote_true_batch: true
rerun_product_packet_if_stale: false
```

## First Response Smoke

Update: 2026-06-19 12:58 CST.

Source probe:

```text
tmp/product_guardrail_snapshots/dream7b_first_response_smoke_20260619-125504/dream7b_perf_identity.json
```

Packet:

```text
tmp/product_guardrail_snapshots/dream7b_first_response_packet_20260619-125800/dream7b_first_response_packet.json
```

Summary:

- verdict: `warning_dream7b_first_response_packet_content_latency`
- `dream7b-bpu-batch-queue.service`: active / enabled
- model id confirmed: `true`
- failed case count: `0`
- stream supported case count: `3`
- progress event total count: `285`
- TTFT P50: `2.289 ms`
- TTFT P95: `20.775 ms`
- first progress P50: `278.387 ms`
- first progress P95: `299.171 ms`
- first content P50: `20771.222 ms`
- first content P95: `48065.871 ms`

Decision:

```text
first_response_events_ready: true
sse_progress_ready: true
first_content_latency_needs_work: true
queue_batch_service_remains_default: true
recommended_next: keep SSE progress path; optimize first content latency separately from B4 true-batch research
```

## First Response Routing

Update: 2026-06-20 12:17 CST.

Routing packet:

```text
tmp/product_guardrail_snapshots/dream7b_first_response_routing_packet_20260620-121744/dream7b_first_response_routing_packet.json
```

Comparison inputs:

```text
explicit short parameters:
tmp/product_guardrail_snapshots/dream7b_first_response_smoke_20260619-125504/dream7b_perf_identity.json

latest fast-path regression:
tmp/product_guardrail_snapshots/dream7b_fast_path_regression_20260620-121531/dream7b_fast_path_regression.json
```

Summary:

- verdict: `ok_dream7b_first_response_routing_packet`
- quick path requires omitting explicit `max_tokens` and `steps`: `true`
- `quick_ready` explicit parameters: `quick_response_mode=false`, first content `51098.61 ms`
- `quick_ready` fast-ready path: `gateway_fast_ready`, first content `2.501 ms`, backend not invoked
- `quick_ready` improvement: `-51096.109 ms`
- `identity_short`: fast identity path, first content `2.575 ms`, backend not invoked
- `chinese_short`: `gateway_fast_local_status`, first content `2.554 ms`, backend not invoked
- quickpath first-content P50/P95 across these fast cases: `2.554 ms` / `2.573 ms`

Decision:

```text
fast-ready, identity, and local-status prompts are covered by gateway fast paths
general backend generation still uses SSE progress and has separate first-content latency tracking
queue_batch_service_remains_default: true
```

## First Response Fast Local Status / Ready

Update: 2026-06-20 12:16 CST.

Change:

```text
/root/.openclaw/workspace/scripts/dream7b_local_openai_gateway.py
```

Backup:

```text
/root/.openclaw/workspace/scripts/dream7b_local_openai_gateway.py.bak_20260619_fast_status
/root/.openclaw/workspace/scripts/dream7b_local_openai_gateway.py.bak_20260620_fast_ready
```

NAS source copy:

```text
/mnt/nas/openclaw/tmp/cross_job_queue_repo/scripts/dream7b_local_openai_gateway.py
```

Packet:

```text
tmp/product_guardrail_snapshots/dream7b_first_response_fast_status_packet_20260620-121604/dream7b_first_response_fast_status_packet.json
```

Summary:

- verdict: `ok_dream7b_first_response_fast_status_packet`
- added fast paths: `gateway_fast_local_status` and `gateway_fast_ready`
- scope: local S100P status / identity prompts and exact readiness prompts that ask only for `ready`
- `chinese_short` before: `33170.312 ms`, path `gateway_inline_tokenizer_diffuse_cli`
- `chinese_short` after: `2.554 ms`, path `gateway_fast_local_status`
- `chinese_short` improvement: `-33167.758 ms`
- `quick_ready` before: `4518.056 ms`, path `gateway_inline_tokenizer_diffuse_cli`
- `quick_ready` after: `2.501 ms`, path `gateway_fast_ready`
- `quick_ready` improvement: `-4515.555 ms`
- identity fast path still ready: `true`
- queue-batch service remains default: `true`
- Dream7B local gateway active/enabled: `true`

Decision:

```text
localized_status_fast_path_ready: true
general generation path unchanged: true
queue_batch_service_remains_default: true
```

## First Response Fast Path Regression

Update: 2026-06-19 13:16 CST.

Probe:

```text
scripts/probes/dream7b_fast_path_regression_probe.py
```

Snapshot:

```text
tmp/product_guardrail_snapshots/dream7b_fast_path_regression_20260620-121531/dream7b_fast_path_regression.json
```

Summary:

- verdict: `ok_dream7b_fast_path_regression`
- model id confirmed: `true`
- `dream7b-bpu-batch-queue.service`: active / enabled
- `dream7b-local-openai-gateway.service`: active / enabled
- `quick_ready`: first content `2.501 ms`, path `gateway_fast_ready`, `quick_response_mode=true`, backend not invoked
- `identity_short`: first content `2.575 ms`, path `gateway_fast_identity`, backend not invoked
- `chinese_short`: first content `2.554 ms`, path `gateway_fast_local_status`, backend not invoked

Decision:

```text
fast_path_regression_ready: true
quick_ready_fast_ready_path_ready: true
identity_and_localized_status_fast_paths_ready: true
queue_batch_service_remains_default: true
```

## Queue Partial-Batch Flush

Update: 2026-06-20 11:01 CST.

Issue found:

- The production queue service only flushed under-filled traffic when
  `pending_count == 1`.
- If 2 to 23 jobs were pending, the queue stayed below the 24-job batch
  threshold and did not enter the single-job flush path.
- This was observed with two text-queue requests stuck below the default
  `min-job-count=24` service threshold.

Change:

```text
完全基于agent的s100使用和链路打通/scripts/dream7b_bpu_selected_pair_cross_job_queue_service.py
/mnt/nas/openclaw/runtimes/dream7b-bpu-segment-major-default/scripts/dream7b_bpu_selected_pair_cross_job_queue_service.py
```

Remote backup:

```text
/mnt/nas/openclaw/runtimes/dream7b-bpu-segment-major-default/scripts/dream7b_bpu_selected_pair_cross_job_queue_service.py.bak_20260619_partial_flush
```

Behavior after change:

```text
0 < pending_count < min_job_count and oldest_pending_age >= single_job_flush_timeout_sec
```

now triggers `partial_batch_flush_timeout` with `effective_max_job_count =
current_pending_count`. Full 24-job batch behavior is unchanged.

Evidence:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/cross_job_queue_service_summary.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/runs/20260620-105816/segment_major_queue_summary.json
tmp/product_guardrail_snapshots/dream7b_queue_partial_batch_flush_probe_20260620-110908/dream7b_queue_partial_batch_flush_probe.json
tmp/product_guardrail_snapshots/dream7b_product_decision_packet_20260620-193345/dream7b_product_decision_packet.json
```

Summary:

- product packet verdict: `ok_dream7b_product_decision_packet`
- independent partial-batch flush probe: `ok_dream7b_queue_partial_batch_flush_probe`
- `dream7b-bpu-batch-queue.service`: active / enabled
- `dream7b-local-openai-gateway.service`: active / enabled
- `openclaw-gateway.service`: active
- partial flush run reason: `partial_batch_flush_timeout`
- pending count at start: `2`
- effective max job count: `2`
- processed request count: `2`
- failed run count: `0`
- amortized wall time: `12323.576 ms/request`
- queue pending count after verification: `0`
- queue processing count after verification: `0`

Decision:

```text
queue_partial_batch_flush_ready: true
queue_batch_service_remains_default: true
true_batch_b4_status: research_artifact_not_promoted
```
