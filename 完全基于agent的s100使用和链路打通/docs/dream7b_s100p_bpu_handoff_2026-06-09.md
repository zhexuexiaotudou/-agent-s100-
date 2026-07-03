# Dream 7B S100P BPU Handoff - 2026-06-09

This document summarizes the current two-day Dream 7B on S100P BPU deployment effort. It is a handoff for new teacher instructions and future implementation work. Do not treat any identifier in this document as inferred; every command, path, report field, and JSON key below was copied from repository files or runtime reports inspected during this task.

## Objective

Continue using Dream 7B, not a substitute model, on the S100P BPU/128TOPS path. The current implementation route is segmented S100 HBM execution, with NAS-backed artifacts and probes that verify artifact inventory, runtime telemetry, window-level HBM load cost, and documentation consistency.

The current state does not prove sustained 128TOPS-level average utilization. It proves that the BPU path runs, can spike `max_bpu_loading` to `100.0`, and remains dominated by HBM reload overhead.

## Repository State

Current branch:

```text
baseline/s100p-nas-baselines
```

Latest pushed commits related to the current Dream 7B resplit route:

```text
8ac0ef5 Add Dream topwindow resplit telemetry
595bf8d Add Dream resplit window cost diagnosis
8f8f58d Add Dream resplit batch telemetry gate
ba7b394 Add Dream resplit batch forward gate
f5d1394 Add Dream resplit forward runtime path
```

Existing dirty files outside the Dream 7B top-window work remain in the worktree. They were not staged for the last Dream 7B commits.

## Current Architecture

Current route:

```text
Dream HF weights
-> segmented S100 HBM compile
-> NAS artifact storage
-> S100P local HBM cache
-> dream7b-bpu-forward
-> dream7b-bpu-resplit-batch-forward
-> telemetry and window-cost probes
```

Primary runtime wrapper files:

```text
scripts/probes/dream7b_segmented_hbm_python_forward.py
scripts/dream7b-bpu-resplit-forward.sh
scripts/dream7b-bpu-resplit-batch-forward.sh
```

Primary reusable check files:

```text
scripts/probes/dream7b_bpu_resplit_hbm_artifact_inventory_probe.sh
scripts/probes/dream7b_bpu_resplit_batch_telemetry_probe.sh
scripts/probes/dream7b_bpu_resplit_window_cost_probe.sh
scripts/probes/dream7b_bpu_utilization_gap_probe.sh
scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh
scripts/probes/s100_official_qwen_fullflow_probe.sh
scripts/probes/dream7b_oellm_fullflow_feasibility_probe.sh
scripts/probes/project_docs_consistency_probe.sh
```

Current top-window runtime identifiers:

```text
RESPLIT_TOPWINDOW_ADJACENT_SEGMENTS
--topwindow-hbm-dir
resplit-topwindow-adjacent
topwindow_hbm_dir
DREAM7B_BPU_TOPWINDOW_HBM_DIR
DREAM7B_BPU_RESPLIT_SEGMENT_PLAN
```

## Verified Published Artifacts

The published top-window HBM directory is:

```text
/mnt/nas/openclaw/models/dream7b-hbm/resplit-topwindow-seq16
```

The S100P local cache directory is:

```text
/home/sunrise/.cache/openclaw/dream7b-hbm/resplit-topwindow-seq16
```

Verified top-window artifact inventory reports:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_hbm_artifact_inventory_20260606-110342/resplit_hbm_artifact_inventory_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_hbm_artifact_inventory_20260606-110343/resplit_hbm_artifact_inventory_probe.json
```

Verified fields from both inventory reports:

```text
verdict: ok_dream7b_bpu_resplit_hbm_artifact_inventory_probe
expected_specs: ['7:8', '8:10', '21:22', '22:24']
expected_hbm_count: 4
existing_hbm_count: 4
manifest_entry_count: 4
manifest_verified_count: 4
total_hbm_size_bytes: 1373714912
errors: []
warnings: []
```

## Verified Runtime Telemetry

Top-window batch telemetry report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_batch_telemetry_20260606-112018/resplit_batch_telemetry_probe.json
```

Verified fields:

```text
verdict: ok_dream7b_bpu_resplit_batch_telemetry_probe
batch_count: 16
expected_segment_plan: resplit-topwindow-adjacent
max_bpu_loading: 100.0
avg_bpu_loading: 8.946
forward_metrics.segment_plan: resplit-topwindow-adjacent
forward_metrics.segment_event_count: 256
forward_metrics.expected_segment_event_count: 256
forward_metrics.segment_sources: ['base', 'fine', 'resplit', 'topwindow']
forward_metrics.load_ms: 23476.584
forward_metrics.run_ms: 2421.61
forward_metrics.load_to_run_ratio: 9.694618
forward_metrics.amortized_load_ms_per_forward: 1467.286
forward_metrics.amortized_run_ms_per_forward: 151.351
forward_metrics.topwindow_hbm_dir: /home/sunrise/.cache/openclaw/dream7b-hbm/resplit-topwindow-seq16
errors: []
```

Top-window window-cost report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_window_cost_20260606-112223/resplit_window_cost_probe.json
```

Verified fields:

```text
verdict: ok_dream7b_bpu_resplit_window_cost_probe
batch_count: 16
expected_segment_plan: resplit-topwindow-adjacent
segment_plan: resplit-topwindow-adjacent
segment_event_count: 256
window_count: 8
total_load_ms: 23476.584
total_run_ms: 2421.61
load_to_run_ratio: 9.694618
amortized_load_ms_per_forward: 1467.2865
amortized_run_ms_per_forward: 151.350625
top_load_window: ['seg14_17', 'seg17_19'] 3505.334 8.891867
top_ratio_window: ['seg00_01', 'seg01_02'] 3334.568 18.920179
errors: []
warnings: []
```

Baseline comparison report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_window_cost_20260606-083152/resplit_window_cost_probe.json
```

Verified baseline fields:

```text
segment_plan: resplit-adjacent
segment_event_count: 224
window_count: 7
load_to_run_ratio: 9.817642
top_load_window: ['seg07_10', 'seg10_12'] 3842.891 9.734161
top_ratio_window: ['seg00_01', 'seg01_02'] 3256.041 18.428821
```

Measured trend:

```text
original resplit load_to_run_ratio: 9.817642
top-window round 2 load_to_run_ratio: 9.694618
```

Interpretation: the targeted split direction is measurable but not enough. The system is still HBM-reload dominated.

## Teacher-Guided Fullflow Baseline

The teacher's suggested route is now represented by two probes:

```text
scripts/probes/s100_official_qwen_fullflow_probe.sh
scripts/probes/dream7b_oellm_fullflow_feasibility_probe.sh
```

The official Qwen fullflow probe fixes the supported SDK baseline to:

```text
model_name: qwen2_5-1_5b
march: nash-m
cache_len: 1024
chunk_size: 256
output_model_path: /mnt/nas/openclaw/models/s100-official-qwen-fullflow
report pattern: /mnt/nas/openclaw/reports/models/s100_official_qwen_fullflow_*
```

It writes an isolated runtime config named `qwen_fullflow_config.json` and captures `oellm_build`, `oellm_multichat`, and optional `hrt_ucp_monitor` evidence without overwriting the vendor SDK `qwen_multichat_config.json`.

The Dream feasibility probe checks the official `leap_llm` registry, summarizes `Dream` config fields, and reruns `compile_dream_with_deepseek_skeleton.sh` with the same SDK/build-host assumptions. If this blocks, the handoff artifact is the generated `dream7b_oellm_fullflow_feasibility_probe.json` with `failure_stage`, command, environment, SDK registry, Dream config summary, and full stdout/stderr paths.

This fullflow baseline is not a model switch. Dream 7B remains the main target unless the official Qwen route becomes the explicit fallback after Dream is blocked by a concrete, reproducible failure.

Current official Qwen fullflow build artifact report:

```text
/mnt/nas/openclaw/reports/models/qwen_fullflow_wsl_build_report_20260609-081247/official_qwen_fullflow_probe.json
```

Current official Qwen build artifact status:

```text
source_model_exists: true
build_host_compatible: true
host_machine: x86_64
compiled_hbm_path: /mnt/f/Project/Digua/tmp/models/s100-official-qwen-fullflow/qwen2_5-1_5b_chunk_256_cache_1024_q8.hbm
compiled_hbm_size_bytes: 1917926648
build_status: failed
build_returncode: 1
failure interpretation: HBM was emitted, then WSL host-side HBM load/link verification failed because WSL has no ION/common-buffer device.
```

Current official Qwen S100P runtime report:

```text
/mnt/nas/openclaw/reports/models/s100_official_qwen_fullflow_20260609-172710/official_qwen_fullflow_probe.json
```

Current official Qwen S100P runtime status:

```text
compiled_hbm_path: /mnt/nas/openclaw/models/s100-official-qwen-fullflow/qwen2_5-1_5b_chunk_256_cache_1024_q8.hbm
source_model_exists: true
compiled_hbm_size_bytes: 1917926648
isolated_runtime_config_written: true
runtime_attempted: true
runtime_status: failed
runtime_returncode: -11
hbm_load_success_observed: true
init_model_success_observed: true
memory_alloc_failure_observed: true
```

Current Dream OELLM migration report:

```text
/mnt/nas/openclaw/reports/models/dream7b_oellm_fullflow_feasibility_20260609-152748/dream7b_oellm_fullflow_feasibility_probe.json
```

Current Dream OELLM migration status:

```text
dream_registered_in_official_sdk: false
build_host_compatible: false
compile_status: blocked_preflight
direct_oellm_migration_supported: false
failure_stage: preflight
minimal_failure_package.stdout_path: /mnt/nas/openclaw/reports/models/dream7b_oellm_fullflow_feasibility_20260609-152748/compile_dream_with_deepseek_skeleton.stdout.txt
minimal_failure_package.stderr_path: /mnt/nas/openclaw/reports/models/dream7b_oellm_fullflow_feasibility_20260609-152748/compile_dream_with_deepseek_skeleton.stderr.txt
```

## Round 3 Compile Status

The latest published round3 split targets the former top absolute-load window:

```text
['seg14_17', 'seg17_19']
```

The intended split specs are:

```text
14:15 15:17 17:18 18:19
```

Compile report:

```text
/tmp/dream7b_topwindow_round3_compile_reports/dream7b_resplit_compile_20260608-170757/resplit_compile_probe.json
```

Verified compile fields:

```text
verdict: ok_dream7b_resplit_compile_probe
output_root: /mnt/f/Project/Digua/tmp/dream7b-resplit-hbm/topwindow-round3
seq_len: 16
specs: ['14:15', '15:17', '17:18', '18:19']
compiled_spec_count: 4
expected_spec_count: 4
hbm_success_count: 4
skipped_existing_count: 0
failed_spec_count: 0
manifest_path: /mnt/f/Project/Digua/tmp/dream7b-resplit-hbm/topwindow-round3/manifest.sha256
errors: []
warnings: []
```

Local HBM files:

```text
F:\Project\Digua\tmp\dream7b-resplit-hbm\topwindow-round3\manifest.sha256
F:\Project\Digua\tmp\dream7b-resplit-hbm\topwindow-round3\seg14_15\dream7b_segment_14_15_seq16_q8.hbm
F:\Project\Digua\tmp\dream7b-resplit-hbm\topwindow-round3\seg15_17\dream7b_segment_15_17_seq16_q8.hbm
F:\Project\Digua\tmp\dream7b-resplit-hbm\topwindow-round3\seg17_18\dream7b_segment_17_18_seq16_q8.hbm
F:\Project\Digua\tmp\dream7b-resplit-hbm\topwindow-round3\seg18_19\dream7b_segment_18_19_seq16_q8.hbm
```

Local sizes:

```text
manifest.sha256: 440
seg14_15/dream7b_segment_14_15_seq16_q8.hbm: 226101432
seg15_17/dream7b_segment_15_17_seq16_q8.hbm: 460735160
seg17_18/dream7b_segment_17_18_seq16_q8.hbm: 226098104
seg18_19/dream7b_segment_18_19_seq16_q8.hbm: 226121656
```

Round 3 is now published to:

```text
/mnt/nas/openclaw/models/dream7b-hbm/resplit-topwindow-seq16
/home/sunrise/.cache/openclaw/dream7b-hbm/resplit-topwindow-seq16
```

`RESPLIT_TOPWINDOW_ADJACENT_SEGMENTS` now replaces `seg14_17` with `seg14_15 + seg15_17` and replaces `seg17_19` with `seg17_18 + seg18_19` when `resplit-topwindow-adjacent` is explicitly selected.

Round3 artifact inventory reports:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_hbm_artifact_inventory_20260609-152820/resplit_hbm_artifact_inventory_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_hbm_artifact_inventory_20260609-152823/resplit_hbm_artifact_inventory_probe.json
```

Verified round3 inventory fields:

```text
expected_specs: ['7:8', '8:10', '14:15', '15:17', '17:18', '18:19', '21:22', '22:24']
expected_hbm_count: 8
existing_hbm_count: 8
manifest_entry_count: 8
manifest_verified_count: 8
total_hbm_size_bytes: 2512771264
errors: []
```

Round3 telemetry report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_batch_telemetry_20260609-153118/resplit_batch_telemetry_probe.json
```

Verified round3 telemetry fields:

```text
verdict: ok_dream7b_bpu_resplit_batch_telemetry_probe
batch_count: 16
expected_segment_plan: resplit-topwindow-adjacent
forward_metrics.segment_event_count: 288
forward_metrics.segment_sources: ['base', 'fine', 'resplit', 'topwindow']
max_bpu_loading: 100.0
avg_bpu_loading: 9.628
forward_metrics.load_ms: 23166.108
forward_metrics.run_ms: 2446.735
forward_metrics.load_to_run_ratio: 9.468172
errors: []
```

Round3 window-cost report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_window_cost_20260609-153244/resplit_window_cost_probe.json
```

Verified round3 window-cost fields:

```text
verdict: ok_dream7b_bpu_resplit_window_cost_probe
segment_plan: resplit-topwindow-adjacent
segment_event_count: 288
window_count: 9
total_load_ms: 23166.108
total_run_ms: 2446.735
load_to_run_ratio: 9.468172
top_load_window.resident_segments: ['seg02_04', 'seg04_07']
top_load_to_run_ratio_window.resident_segments: ['seg00_01', 'seg01_02']
errors: []
```

Round3 utilization and acceptance reports:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_utilization_gap_20260609-153933/utilization_gap_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260609-154013/deployment_acceptance_probe.json
```

Verified round3 utilization/acceptance fields:

```text
diagnosis: hbm_reload_dominated
resplit_batch_telemetry.load_to_run_ratio: 9.468
resplit_batch_telemetry.avg_bpu_loading: 9.628
deployment_acceptance.check_count: 30
deployment_acceptance.passed_check_count: 30
deployment_acceptance.utilization_gap.ok: True
```

## Decisions

- Keep Dream 7B as the target model.
- Do not switch to Qwen or another official model as a substitute target.
- Use S100 HBM segmentation and runtime telemetry as the current path.
- Treat `max_bpu_loading: 100.0` as proof that the BPU can spike to full loading, not proof that the 128TOPS target is solved.
- Treat average utilization as blocked primarily by HBM reload overhead until window-cost evidence proves otherwise.
- Keep `resplit-adjacent` as the default segment plan.
- Use `resplit-topwindow-adjacent` only when explicitly selected through `DREAM7B_BPU_RESPLIT_SEGMENT_PLAN` or `--segment-plan`.
- Every new runtime field, command, environment variable, report path, and acceptance condition must be reflected in `README.md`, `docs/project_reference.md`, `docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md`, and `scripts/probes/project_docs_consistency_probe.sh`.

## Next Work Queue

1. Treat round3 as a measured improvement, not as a 128TOPS success claim: `load_to_run_ratio` decreased from `9.694618` to `9.468172`, while `diagnosis` remains `hbm_reload_dominated`.
2. Target the new top absolute-load pair `['seg02_04', 'seg04_07']` and keep tracking the top load/run-ratio pair `['seg00_01', 'seg01_02']`.
3. Keep `resplit-adjacent` as the default service path; run `resplit-topwindow-adjacent` only as an explicit candidate until a replacement decision has fresh acceptance evidence and rollback instructions.
4. Use the official Qwen/Dream OELLM reports to ask for an x86_64 AVX build host and the missing official Qwen HF source model before claiming the official fullflow gate is complete.

## Teacher Instruction Intake

Use this section to map the next teacher instruction onto the current state.

If the teacher asks whether Dream 7B is already using 128TOPS, answer:

```text
No. The BPU path runs and can reach max_bpu_loading 100.0 in sampled telemetry, but average loading remains low because the route is HBM-reload dominated.
```

If the teacher asks what is being optimized now, answer:

```text
We are reducing per-window HBM reload overhead by splitting the worst load windows into smaller HBM shards and verifying each change with artifact inventory, batch telemetry, and window-cost reports.
```

If the teacher asks what the latest experiment showed, answer:

```text
The round3 split specs 14:15, 15:17, 17:18, and 18:19 were published and tested. The new load_to_run_ratio is 9.468172 versus the previous 9.694618, so reload overhead improved, but the diagnosis remains hbm_reload_dominated.
```

## Current Qwen/Dream Migration Acceptance

Qwen2.5-1.5B `cache_len: 512`, `chunk_size: 128` is now the official runnable LLM baseline for the Dream migration method, replacing 1024/256 as the main comparison. The verified HBM is `/mnt/nas/openclaw/models/s100-official-qwen-fullflow/cache_len_512_chunk_128/qwen2_5-1_5b_chunk_128_cache_512_q8.hbm`. `/mnt/nas/openclaw/reports/models/s100_official_qwen_fullflow_20260609-210514/official_qwen_fullflow_probe.json` records `runtime_completed: true`, `runtime_returncode: 0`, `memory_alloc_failure_observed: false`, `nonzero_bpu_loading_sample_count: 6`, `max_bpu_loading: 98.0`, `avg_bpu_loading: 2.222`, and `Performance prefill: 1024.00tokens/s    decode: 25.57tokens/s`. The diagnosis report `/mnt/nas/openclaw/reports/models/s100_qwen15_common_buffer_diagnosis_20260609-211000/s100_qwen15_common_buffer_diagnosis_20260609.md` keeps 1024/256 as a high-context failure boundary, not as the Dream migration baseline.

Dream official OELLM migration remains blocked at registry/model-adapter discovery. `/mnt/nas/openclaw/reports/models/dream7b_oellm_fullflow_feasibility_20260609-223754/dream7b_oellm_fullflow_feasibility_probe.json` records `build_host_compatible: true`, `dream_registered_in_official_sdk: false`, `compile_status: blocked_registry_missing`, `failure_stage: registry_missing`, `compiled_hbm_count: 0`, `direct_oellm_migration_supported: false`, `missing_adapter_evidence.registry_missing: true`, `missing_adapter_evidence.required_adapter: official leap_llm model_factory registration and Dream/DreamModel adapter`, and `unable_to_attempt_direct_official_compile_reason`. The minimal failure package points to Dream source/config `/mnt/f/Project/Digua/tmp/dream_hf/config.json` and includes `model_type: Dream`, `architectures: ['DreamModel']`, `hidden_size: 3584`, `num_hidden_layers: 28`, `num_attention_heads: 28`, `num_key_value_heads: 4`, `vocab_size: 152064`, `mask_token_id: 151666`, `torch_dtype: bfloat16`, and `use_cache: true`, plus the SDK registry list.

The latest segmented Dream refresh is archived at `/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_hbm_artifact_inventory_20260609-224012/resplit_hbm_artifact_inventory_probe.json`, `/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_hbm_artifact_inventory_20260609-224035/resplit_hbm_artifact_inventory_probe.json`, `/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_batch_telemetry_20260609-224100/resplit_batch_telemetry_probe.json`, `/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_window_cost_20260609-224142/resplit_window_cost_probe.json`, `/mnt/nas/openclaw/reports/models/dream7b_bpu_utilization_gap_20260609-224156/utilization_gap_probe.json`, and `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260609-224157/deployment_acceptance_probe.json`. It verifies `expected_hbm_count: 8`, `existing_hbm_count: 8`, `manifest_verified_count: 8`, `total_hbm_size_bytes: 2512771264`, `avg_bpu_loading: 8.97`, `forward_metrics.load_to_run_ratio: 9.678265`, `load_to_run_ratio: 9.678265`, `diagnosis: hbm_reload_dominated`, `check_count: 30`, and `passed_check_count: 30`. Because `9.678265` does not improve on the current best `9.468172`, the status remains HBM-reload dominated.

## Current Official 7B Fallback Check

The official DeepSeek-R1-Distill-Qwen-7B fallback is staged but not runnable on the current S100P memory layout. `scripts/probes/s100_official_deepseek7b_baseline_probe.sh` writes an isolated config and does not overwrite vendor examples or change ION/performance-mode settings. Latest report:

```text
/mnt/nas/openclaw/reports/models/s100_official_deepseek7b_baseline_20260610-023455/deepseek7b_baseline_probe.json
```

Key fields:

```text
hbm_path: /mnt/nas/openclaw/models/s100-official-deepseek-r1-distill-qwen-7b/DeepSeek_R1_Distill_Qwen_7B_1024.hbm
hbm_size_bytes: 7928846896
runtime_status: failed
runtime_returncode: 1
runtime_completed: False
hbm_load_success_observed: False
init_model_success_observed: False
memory_alloc_failure_observed: True
bpu_alloc_request_bytes: 7928846896
decision: official_7b_runtime_blocked_common_buffer
```

Conclusion: DeepSeek 7B cannot be presented as the current deployable 7B fallback. It needs vendor confirmation on required S100P memory layout or runtime settings. Qwen2.5-1.5B `512/128` remains the verified official runnable fallback; Dream remains the target through segmented HBM.

## Current Reload Optimization Closure

The next support and optimization line is now explicit:

```text
docs/dream7b_vendor_support_package_2026-06-10.md
scripts/probes/dream7b_bpu_reload_optimization_probe.sh
```

The vendor package asks only two external questions: what S100P memory layout or runtime settings are required to load `DeepSeek_R1_Distill_Qwen_7B_1024.hbm`, and whether Dream/DreamModel has an official `oellm_build/leap_llm` adapter path.

The fresh top-window reload run is:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_batch_telemetry_20260610-030740/resplit_batch_telemetry_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_window_cost_20260610-030820/resplit_window_cost_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_telemetry_20260610-031613/selected_pair_telemetry_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_utilization_gap_20260610-031818/utilization_gap_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260610-031818/deployment_acceptance_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_reload_optimization_20260610-031828/reload_optimization_probe.json
```

Key fields:

```text
avg_bpu_loading: 8.811
max_bpu_loading: 100.0
forward_metrics.load_to_run_ratio: 9.524202
forward_metrics.wall_ms: 26007.248
diagnosis: hbm_reload_dominated
check_count: 30
passed_check_count: 30
selected_pair: [1, 8]
selected_pair_covers_all_segments: True
selected_pair.wall_ms: 22982.452
selected_pair.avg_bpu_loading: 8.984
selected_pair_wall_delta_ratio_vs_resplit: 0.116306
selected_pair_avg_bpu_delta_vs_resplit: 0.173
final_decision: utilization_progress_candidate
substantial_improvement_observed: True
best_load_to_run_ratio: 9.468172
ratio_delta_vs_best: 0.05603
```

Strategy status:

```text
file_prefetch_or_local_hbm_cache: bounded_prefetch_only
persistent_pair_cache: blocked_by_residency_boundary
persistent_segment_cache: blocked_by_residency_boundary
persistent_triplet_topology: topology_stable_but_forward_blocked
selected_pair_cross_job_cache: batch16_wall_candidate
window_scheduling_resplit_topwindow: not_better_than_current_best
bpu_core_scheduling: core0_only
```

Conclusion: selected-pair resident execution is now a guarded utilization-progress candidate because batch16 wall time and average BPU loading improve against the latest top-window run. Do not replace the default service yet; the next step is sustained selected-pair service telemetry plus rollback-gated promotion testing.

## 2026-06-10 Sustained Selected-Pair Service Follow-Up

The sustained candidate service run is:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_candidate_service_telemetry_20260610-032523/systemd_telemetry_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_utilization_gap_20260610-032709/utilization_gap_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260610-032709/deployment_acceptance_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_reload_optimization_20260610-032926/reload_optimization_probe.json
```

Key fields:

```text
processed_request_count: 48
batch_counts: [16, 16, 16]
amortized_wall_ms_per_processed_request: 1445.673
avg_bpu_loading: 8.371
max_bpu_loading: 98.0
load_to_run_ratio: 9.859028
wall_ms_delta_ratio_vs_default_systemd: 0.130546
candidate_avg_bpu_loading_not_worse_than_default_systemd: False
diagnosis: hbm_reload_dominated
check_count: 30
passed_check_count: 30
final_decision: guarded_sustained_wall_time_candidate
sustained_service_decision: guarded_sustained_wall_time_candidate
default_service_replacement_decision: do_not_replace_default_service_yet
wall_delta_ratio_vs_resplit_per_request: 0.110603
avg_bpu_delta_vs_resplit: -0.44
avg_bpu_delta_vs_selected_pair_single: -0.613
```

Conclusion: selected-pair candidate service now has 48-request sustained evidence and is a rollback-gated wall-time candidate. It is still not a default-service replacement because average BPU loading falls versus the latest top-window run and versus the older default systemd baseline, and the diagnosis remains `hbm_reload_dominated`.

## 2026-06-10 Default-Service Promotion Gate

The default-service replacement gate is:

```text
scripts/probes/dream7b_bpu_selected_pair_service_promotion_gate_probe.sh
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_service_promotion_gate_20260610-141720/selected_pair_service_promotion_gate_probe.json
```

Gate result:

```text
verdict: ok_dream7b_bpu_selected_pair_service_promotion_gate_probe
promotion_allowed: False
promotion_decision: block_default_service_replacement
default_service_replaced: False
candidate_service_isolated_from_default: True
processed_request_count: 48
candidate_load_to_run_ratio: 9.859028
wall_delta_ratio_vs_default_systemd: 0.130546
wall_delta_ratio_vs_resplit_per_request: 0.110603
avg_bpu_delta_vs_default_systemd: -1.245
avg_bpu_delta_vs_resplit: -0.44
utilization_diagnosis: hbm_reload_dominated
```

Promotion blockers:

```text
promotion_average_bpu_not_worse_vs_default
promotion_average_bpu_improved_vs_resplit
promotion_load_to_run_not_worse_than_best
promotion_not_hbm_reload_dominated
reload_gate_allows_default_replacement
```

Rollback commands embedded in the gate report:

```text
sudo systemctl stop dream7b-bpu-selected-pair-candidate.service
sudo systemctl disable dream7b-bpu-selected-pair-candidate.service
sudo systemctl restart dream7b-bpu-batch-queue.service
systemctl is-active dream7b-bpu-batch-queue.service
systemctl is-enabled dream7b-bpu-batch-queue.service
```

Conclusion: do not replace `dream7b-bpu-batch-queue.service`. The selected-pair service is useful as an isolated candidate path, but the current hard gate blocks promotion until average BPU loading, load/run, and the `hbm_reload_dominated` diagnosis improve.

## 2026-06-10 Promotion Blocker Diagnosis

The blocker diagnosis report is:

```text
scripts/probes/dream7b_bpu_promotion_blocker_diagnosis_probe.sh
/mnt/nas/openclaw/reports/models/dream7b_bpu_promotion_blocker_diagnosis_20260610-145739/promotion_blocker_diagnosis_probe.json
```

Diagnosis fields:

```text
verdict: ok_dream7b_bpu_promotion_blocker_diagnosis_probe
promotion_decision: keep_candidate_only_until_blockers_clear
candidate_load_to_run_ratio: 9.859028
load_to_run_delta_vs_best: 0.390856
load_to_run_delta_vs_resplit: 0.334826
service_avg_bpu_loading: 8.371
avg_bpu_delta_vs_resplit: -0.44
wall_delta_ratio_vs_resplit_per_request: 0.110603
top_load_to_run_ratio_window.resident_segments: ['seg00_01', 'seg01_02']
top_load_to_run_ratio_window.load_to_run_ratio: 18.585073
top_load_window.resident_segments: ['seg02_04', 'seg04_07']
top_load_window.load_ms: 3562.79
max_resident_segment_count_observed: 3
successful_seeded_quad_count: 0
recommended_resplit_segment_indexes: [0, 9, 4, 6]
```

Next optimization order:

```text
1. prefix_micro_window_reload_reduction
2. seg02_04_seg04_07_window_cost_reduction
3. resident_capacity_boundary_experiment
4. core0_only_scheduling_control
```

Conclusion: the blocker is no longer vague. The service path improves wall time, but load/run and average BPU still fail promotion. The next experiment should attack prefix/top-load window reload cost and then rerun sustained telemetry plus the hard promotion gate.

## 2026-06-10 Final Optimization Acceptance

The final acceptance report is:

```text
scripts/probes/dream7b_final_optimization_acceptance_probe.sh
/mnt/nas/openclaw/reports/models/dream7b_final_optimization_acceptance_20260610-161744/final_optimization_acceptance_probe.json
```

Final acceptance fields:

```text
verdict: ok_dream7b_final_optimization_acceptance_probe
final_goal_satisfied: True
final_decision: dream7b_bpu_optimized_candidate_complete_candidate_only
deployment_route_closed: True
substantial_improvement_observed: True
utilization_statement_compliant: True
promotion_gate_closed: True
dream_oellm_registry_missing: True
qwen_fallback_verified: True
deepseek7b_blocked_common_buffer: True
candidate_service_only: True
default_service_replaced: False
selected_pair_wall_delta_ratio_vs_resplit: 0.116306
sustained_wall_delta_ratio_vs_resplit_per_request: 0.110603
sustained_wall_delta_ratio_vs_default_systemd: 0.130546
sustained_request_count: 48
```

Conclusion: the current Dream 7B deployment optimization goal is satisfied as a candidate-only BPU route. The evidence proves reproducibility, acceptance, rollback gating, official-route/fallback conclusions, and measured wall-time improvement. It explicitly does not authorize replacing `dream7b-bpu-batch-queue.service`.

## 2026-06-10 Normal-Use Candidate Acceptance

The normal-use acceptance report is:

```text
scripts/probes/dream7b_bpu_normal_use_acceptance_probe.sh
/mnt/nas/openclaw/reports/models/dream7b_bpu_normal_use_acceptance_20260610-170005/normal_use_acceptance_probe.json
```

Normal-use fields:

```text
verdict: ok_dream7b_bpu_normal_use_acceptance_probe
normal_use_ready: True
unmet_requirements: []
stable_sustained_service: True
preferred_96_request_sustained_observed: True
deployment_acceptance_clean: True
performance_floor_met: True
reload_relief_observed: True
deployable_rollback_safe: True
utilization_claim_compliant: True
```

Sustained-service evidence:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_candidate_service_telemetry_20260610-165645/systemd_telemetry_probe.json
processed_request_count: 48
batch_counts: [16, 16, 16]
failed_job_count: 0
amortized_wall_ms_per_processed_request: 1448.877
avg_bpu_loading: 8.578
max_bpu_loading: 96.0
wall_delta_ratio_vs_resplit_per_request: 0.102517
wall_delta_ratio_vs_default_systemd: 0.128619
load_to_run_ratio: 9.863791
```

The preferred 96-request stability evidence is:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_candidate_service_telemetry_20260610-163241/systemd_telemetry_probe.json
```

Post-blocker reload experiment:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_batch_telemetry_20260610-165429/resplit_batch_telemetry_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_window_cost_20260610-165513/resplit_window_cost_probe.json
forward_metrics.load_to_run_ratio: 9.443895
load_to_run_ratio: 9.443895
previous_load_to_run_ratio: 9.774037
top_ratio_improved: True
top_load_improved: True
overall_load_to_run_improved: True
```

Conclusion: Dream 7B is now a normal-use selected-pair candidate service on S100P under the current 48-request minimum gate, with a separate 96-request stability report. Keep the default service unchanged and retain rollback commands from the promotion gate; the 128TOPS wording must still say `hbm_reload_dominated` because sustained average BPU loading and load/run remain below promotion targets.

## 2026-06-10 Default-Deployable Final Gate

Final acceptance probe:

```text
scripts/probes/dream7b_bpu_default_deployable_acceptance_probe.sh
/mnt/nas/openclaw/reports/models/dream7b_bpu_default_deployable_acceptance_20260610-173758/default_deployable_acceptance_probe.json
```

Sustained service evidence:

```text
processed_request_count: 192
failed_job_count: 0
preferred_sustained_observed: True
amortized_wall_ms_per_processed_request: 1450.4
avg_bpu_loading: 8.476
load_to_run_ratio: 9.873488
performance_pass_count: 1
min_performance_pass_count: 3
```

Final gate result:

```text
verdict: ok_dream7b_bpu_default_deployable_acceptance_probe
default_deployable_ready: False
default_deployable_status: blocked_candidate_only
deployment_acceptance_clean: True
promotion_allowed: False
```

Promotion and reload reports:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_service_promotion_gate_20260610-173049/selected_pair_service_promotion_gate_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_reload_optimization_20260610-173049/reload_optimization_probe.json
promotion_decision: block_default_service_replacement
default_service_replacement_decision: do_not_replace_default_service_yet
utilization_diagnosis: hbm_reload_dominated
```

Remaining blockers:

```text
service_performance_pass_count_below_3
service_avg_bpu_below_default_deploy_threshold
service_load_to_run_above_default_deploy_threshold
promotion_average_bpu_not_worse_vs_default
promotion_average_bpu_improved_vs_resplit
promotion_load_to_run_not_worse_than_best
promotion_not_hbm_reload_dominated
reload_gate_allows_default_replacement
```

Cross-job reuse remains the strongest optimization lead:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_reuse_20260610-172408/selected_pair_cross_job_reuse_probe.json
processed_forward_count: 128
load_to_run_ratio: 8.895442
amortized_wall_ms_per_forward: 1448.768
load_ms_delta_ratio_vs_service: 0.10225
cross_job_wall_time_improved: True
performance_pass_count: 2
```

Conclusion: the 192-request run proves the selected-pair service is stable, but it is still not default-deployable. Cross-job reuse shows that load/run can be pushed under 9.0 when selected-pair workers are reused across jobs, so the next meaningful engineering step is turning that prototype into an isolated service and rerunning the same final gate. Until then, keep `dream7b-bpu-batch-queue.service` as the default and keep the deployment wording `hbm_reload_dominated`.

## 2026-06-10 Cross-Job Queue Runner Candidate

Implementation:

```text
scripts/dream7b_bpu_selected_pair_cross_job_queue_runner.py
scripts/probes/dream7b_bpu_selected_pair_forward_path_probe.sh
DREAM7B_BPU_SELECTED_PAIR_TOKENS_BATCHES_BY_JOB_JSON
DREAM7B_BPU_SELECTED_PAIR_JOB_COUNT: 12
```

6x16 queue-runner result:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_queue_runner_20260610-175302/cross_job_queue_summary.json
verdict: ok_dream7b_bpu_selected_pair_cross_job_queue_runner
processed_job_count: 6
processed_request_count: 96
failed_job_count: 0
load_to_run_ratio: 8.890613
amortized_wall_ms_per_processed_request: 1438.937
amortized_total_load_ms_per_processed_request: 1309.349
amortized_run_ms_per_processed_request: 147.273
selected_pair_covers_all_segments: True
```

12x16 queue-runner result:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_queue_runner_20260610-175739/cross_job_queue_summary.json
processed_job_count: 12
processed_request_count: 192
failed_job_count: 0
load_to_run_ratio: 8.904793
amortized_wall_ms_per_processed_request: 1459.145
selected_pair_covers_all_segments: True
```

Refreshed gates:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260610-180307/deployment_acceptance_probe.json
verdict: ok_dream7b_bpu_deployment_acceptance_probe
check_count: 30
passed_check_count: 30
errors: []

/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_service_promotion_gate_20260610-180307/selected_pair_service_promotion_gate_probe.json
verdict: ok_dream7b_bpu_selected_pair_service_promotion_gate_probe
promotion_allowed: False
promotion_decision: block_default_service_replacement

/mnt/nas/openclaw/reports/models/dream7b_bpu_default_deployable_acceptance_20260610-180307/default_deployable_acceptance_probe.json
verdict: ok_dream7b_bpu_default_deployable_acceptance_probe
default_deployable_ready: False
default_deployable_status: blocked_candidate_only
cross_job_queue_candidate.preferred_sustained_observed: True
cross_job_queue_candidate.performance_pass_count: 1
cross_job_queue_candidate.load_to_run_ratio: 8.904793
cross_job_queue_candidate.amortized_wall_ms_per_processed_request: 1459.145
```

Conclusion: cross-job queue reuse is no longer just an offline probe. It has a queue-runner candidate that can process 96 and 192 requests without failed jobs and pushes load/run below 9.0. It still cannot be promoted because the 192-request wall time regresses and the candidate does not provide three performance passes. The next concrete target is a systemd-isolated cross-job queue candidate plus telemetry sampling, with attention to why 6x16 improves wall time while 12x16 does not.

## 2026-06-10 Cross-Job Candidate Service Promotion

Installed isolated service:

```text
scripts/install_dream7b_bpu_selected_pair_cross_job_candidate_service.sh
scripts/dream7b_bpu_selected_pair_cross_job_queue_service.py
scripts/probes/dream7b_bpu_selected_pair_cross_job_queue_telemetry_probe.sh
scripts/probes/dream7b_bpu_selected_pair_cross_job_service_promotion_gate_probe.sh
dream7b-bpu-selected-pair-cross-job-candidate.service
default_service_name: dream7b-bpu-batch-queue.service
default_service_replaced: false
```

Service telemetry:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_candidate_service_telemetry_20260610-182409/service_telemetry_probe.json
verdict: ok_dream7b_bpu_selected_pair_cross_job_candidate_service_telemetry_probe
processed_request_count: 192
failed_job_count: 0
load_to_run_ratio: 8.66679
avg_bpu_loading: 10.108
max_bpu_loading: 98.0
amortized_wall_ms_per_processed_request: 1430.794
selected_pair_covers_all_segments: True
```

Promotion gate:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_service_promotion_gate_20260610-183109/cross_job_service_promotion_gate_probe.json
verdict: ok_dream7b_bpu_selected_pair_cross_job_service_promotion_gate_probe
promotion_allowed: True
promotion_decision: ready_for_default_service_replacement
default_service_replaced: False
promotion_blockers: []
```

Final acceptance:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_default_deployable_acceptance_20260610-183252/default_deployable_acceptance_probe.json
default_deployable_ready: False
default_deployable_status: ready_for_default_replacement_candidate_only
cross_job_service_candidate.performance_pass_count: 3
cross_job_service_candidate.ready_for_default_replacement: True
cross_job_service_candidate.default_service_replaced: False
cross_job_service_candidate.default_replaced_and_ready: False
```

Conclusion: the cross-job candidate service is the first route that clears three performance gates at 192 requests: load/run, average BPU loading, and long-stable wall time. It should be treated as ready for a controlled default-service replacement test, not as already deployed. Before replacing `dream7b-bpu-batch-queue.service`, add an explicit single-job fallback or timeout policy because the current service waits for at least two queued jobs before launching a cross-job batch.

## 2026-06-10 Single-Job Fallback Flush

The cross-job candidate now has an explicit single-request fallback path. `scripts/probes/dream7b_bpu_selected_pair_cross_job_service_fallback_probe.sh` verifies that `--single-job-flush-timeout-sec` drains one pending request instead of waiting indefinitely for a second job.

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_service_fallback_20260610-185916/cross_job_service_fallback_probe.json
verdict: ok_dream7b_bpu_selected_pair_cross_job_service_fallback_probe
single_job_fallback_ok: True
run_reason: single_job_flush_timeout
processed_request_count: 1
failed_job_count: 0
load_to_run_ratio: 155.028327
amortized_wall_ms_per_processed_request: 20577.422
```

The fallback-aware promotion gate remains open:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_service_promotion_gate_20260610-185941/cross_job_service_promotion_gate_probe.json
promotion_allowed: True
promotion_blockers: []
single_job_fallback_ok: True
```

The final acceptance gate is still candidate-only because the default service has not been intentionally replaced:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_default_deployable_acceptance_20260610-185941/default_deployable_acceptance_probe.json
default_deployable_status: ready_for_default_replacement_candidate_only
default_service_replaced: False
```

## 2026-06-10 Default Service Promotion Closure

The cross-job selected-pair route has now been promoted into the default Dream service name `dream7b-bpu-batch-queue.service`. The runtime used by the service is staged outside the temporary repo:

```text
/mnt/nas/openclaw/runtimes/dream7b-bpu-cross-job-default
```

Promotion and rollback verification:

```text
scripts/probes/dream7b_bpu_cross_job_default_promotion_probe.sh
/mnt/nas/openclaw/reports/models/dream7b_bpu_cross_job_default_promotion_20260610-190712/cross_job_default_promotion_probe.json
verdict: ok_dream7b_bpu_cross_job_default_promotion_probe
default_service_replaced: True
rollback_verified: True
errors: []
```

The promotion probe backed up the original unit, installed the promoted unit, ran a default-queue smoke request, restored the original unit once to verify rollback, and then re-applied the promoted unit.

Promoted default service telemetry:

```text
scripts/probes/dream7b_bpu_cross_job_default_service_telemetry_probe.sh
/mnt/nas/openclaw/reports/models/dream7b_bpu_cross_job_default_service_telemetry_20260610-191115/default_service_telemetry_probe.json
verdict: ok_dream7b_bpu_cross_job_default_service_telemetry_probe
processed_request_count: 192
failed_job_count: 0
queue_done_count: 12
queue_failed_count: 0
load_to_run_ratio: 8.734653
avg_bpu_loading: 9.915
max_bpu_loading: 98.0
amortized_wall_ms_per_processed_request: 1441.545
```

Replacement-time deployment acceptance:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260610-192303/deployment_acceptance_probe.json
verdict: ok_dream7b_bpu_deployment_acceptance_probe
check_count: 30
passed_check_count: 30
errors: []
```

Final acceptance:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_default_deployable_acceptance_20260610-192303/default_deployable_acceptance_probe.json
default_deployable_ready: True
default_deployable_status: ready
cross_job_default_service.performance_pass_count: 3
cross_job_service_candidate.default_replaced_and_ready: True
cross_job_service_candidate.rollback_verified: True
blockers: []
warnings: []
```

Final wording: Dream 7B is now a default-deployed S100P service with measured utilization progress. Do not claim that 128TOPS is fully saturated from `max_bpu_loading`; the defensible claim is that the default service passes sustained telemetry with improved load/run ratio, average BPU loading, and long-stable wall time.
