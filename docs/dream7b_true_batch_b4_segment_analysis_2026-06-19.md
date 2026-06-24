# Dream7B B=4 True-Batch Segment Analysis

- generated_at: 2026-06-19T23:27:57.878932+08:00
- parsed_segment_count: 28
- total_timed_compile_pipeline_s: 6591.3924
- compile_hbo_mean_s: 216.4392
- compile_hbo_p95_s: 238.7113
- hidden_compile_hbo_mean_s: 212.9493

## Compile Bottlenecks

| rank | segment | kind | export_s | convert_s | compile_hbo_s | timed_pipeline_s | output |
| ---: | --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | seg27_28 | final_logits | 28.4610 | 23.3548 | 284.9039 | 336.7197 | tensor<4x16x152064xf32> |
| 2 | seg00_01 | token_embedding | 29.7661 | 12.7701 | 238.7113 | 281.2475 | tensor<4x16x3584xf32> |
| 3 | seg05_06 | hidden_block | 9.5836 | 7.3102 | 222.2432 | 239.1370 | tensor<4x16x3584xf32> |
| 4 | seg09_10 | hidden_block | 9.3252 | 7.2441 | 222.4658 | 239.0351 | tensor<4x16x3584xf32> |
| 5 | seg07_08 | hidden_block | 9.4937 | 7.5327 | 221.4140 | 238.4404 | tensor<4x16x3584xf32> |
| 6 | seg13_14 | hidden_block | 9.6438 | 7.2606 | 221.1493 | 238.0537 | tensor<4x16x3584xf32> |

## Runtime Telemetry

| file | inner_order | groups | microbatches | avg_bpu | avg_nonzero_bpu | wall_ms_per_request | final_shape |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| tmp\remote_true_batch_reports\b4_mb512_segment_major_true_batch_group_major_telemetry.json | segment-major | 5 | 512 | 59.16 | 89.489 | 93.73 | [4, 16, 152064] |
| tmp\remote_true_batch_reports\b4_mb512_segment_major_instrumented_v2_true_batch_group_major_telemetry.json | segment-major | 5 | 512 | 59.031 | 89.388 | 93.833 | [4, 16, 152064] |
| tmp\remote_true_batch_reports\b4_mb512_segment_major_prealloc_true_batch_group_major_telemetry.json | segment-major | 5 | 512 | 58.441 | 87.958 | 94.678 | [4, 16, 152064] |
| tmp\remote_true_batch_reports\b4_mb512_microbatch_major_true_batch_group_major_telemetry.json | microbatch-major | 5 | 512 | 58.79 | 89.087 | 94.447 | [4, 16, 152064] |
| tmp\remote_true_batch_reports\b4_mb512_segment_major_release_gc_skip_true_batch_group_major_telemetry.json | segment-major | 5 | 512 | 59.085 | 89.679 | 94.128 | [4, 16, 152064] |
| tmp\remote_true_batch_reports\b4_mb128_segment_major_release_gc_skip_true_batch_group_major_telemetry.json | segment-major | 5 | 128 | 29.178 | 88.263 | 190.568 | [4, 16, 152064] |
| tmp\remote_true_batch_reports\b4_mb128_segment_major_load_attributed_true_batch_group_major_telemetry.json | segment-major | 5 | 128 | 29.205 | 88.621 | 190.645 | [4, 16, 152064] |
| tmp\remote_true_batch_reports\b4_mb128_segment_major_prewarm_hbm_true_batch_group_major_telemetry.json | segment-major | 5 | 128 | 17.48 | 87.838 | 315.629 | [4, 16, 152064] |
| tmp\remote_true_batch_reports\b4_mb512_segment_major_g6_true_batch_group_major_telemetry.json | segment-major | 6 | 512 | 58.954 | 89.432 | 94.101 | [4, 16, 152064] |
| tmp\remote_true_batch_reports\b4_mb512_segment_major_final_isolated_true_batch_group_major_telemetry.json | segment-major | 6 | 512 | 58.829 | 89.01 | 94.006 | [4, 16, 152064] |
| tmp\remote_true_batch_reports\b4_mb512_segment_major_g4_true_batch_group_major_telemetry.json | segment-major | 7 | 512 | 59.037 | 89.348 | 93.957 | [4, 16, 152064] |
| tmp\remote_true_batch_reports\b4_mb1536_segment_major_true_batch_group_major_telemetry.json | segment-major | 5 | 1536 | 76.789 | 89.776 | 72.249 | [4, 16, 152064] |
| tmp\remote_true_batch_reports\b4_mb3072_segment_major_true_batch_group_major_telemetry.json | segment-major | 5 | 3072 | 82.579 | 89.68 | 66.976 | [4, 16, 152064] |
| tmp\remote_true_batch_reports\b4_mb4096_segment_major_true_batch_group_major_telemetry.json | segment-major | 5 | 4096 | 84.248 | 89.694 | 65.684 | [4, 16, 152064] |

## Runtime Scaling

| inner_order | groups | microbatches | load_fraction_wall | hidden_avg_ms | final_avg_ms | final_hidden_ratio |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| microbatch-major | 5 | 512 | 0.3426 |  |  |  |
| segment-major | 5 | 512 | 0.3409 | 8.096 | 20.267 | 2.503 |
| segment-major | 6 | 512 | 0.3433 | 8.0974 | 20.244 | 2.500 |
| segment-major | 6 | 512 | 0.3420 | 8.1072 | 20.275 | 2.501 |
| segment-major | 7 | 512 | 0.3421 | 8.105 | 20.233 | 2.496 |
| segment-major | 5 | 1536 | 0.1466 | 8.1007 | 20.273 | 2.503 |
| segment-major | 5 | 3072 | 0.0798 | 8.102 | 20.248 | 2.499 |
| segment-major | 5 | 4096 | 0.0612 | 8.1022 | 20.272 | 2.502 |

## Order Comparison

| inner_order | groups | microbatches | avg_bpu | nonzero_bpu | ms_per_request | load_fraction | measured_run_fraction | estimated_host_gap_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| microbatch-major | 5 | 512 | 58.79 | 89.087 | 94.447 | 0.3426 | 0.6536 | 746.613 |
| segment-major | 5 | 512 | 59.16 | 89.489 | 93.73 | 0.3409 | 0.6383 | 3982.985 |
| segment-major | 6 | 512 | 58.954 | 89.432 | 94.101 | 0.3433 | 0.6357 | 400.765 |
| segment-major | 6 | 512 | 58.829 | 89.01 | 94.006 | 0.3420 | 0.6372 | 399.149 |
| segment-major | 7 | 512 | 59.037 | 89.348 | 93.957 | 0.3421 | 0.6372 | 3988.223 |
| segment-major | 5 | 1536 | 76.789 | 89.776 | 72.249 | 0.1466 | 0.8285 | 11077.095 |
| segment-major | 5 | 3072 | 82.579 | 89.68 | 66.976 | 0.0798 | 0.8937 | 21809.293 |
| segment-major | 5 | 4096 | 84.248 | 89.694 | 65.684 | 0.0612 | 0.9384 | 406.994 |

## Slowest Runtime Segments

| rank | group | index | avg_run_ms | completed_microbatches |
| ---: | --- | ---: | ---: | ---: |
| 1 | 24:28 | 27 | 20.273 | 1536 |
| 2 | 24:28 | 27 | 20.267 | 512 |
| 3 | 24:28 | 27 | 20.272 | 4096 |
| 4 | 24:28 | 27 | 20.248 | 3072 |
| 5 | 24:28 | 27 | 20.233 | 512 |
| 6 | 0:6 | 0 | 8.535 | 4096 |
| 7 | 0:6 | 0 | 8.534 | 3072 |
| 8 | 0:6 | 0 | 8.532 | 1536 |

## Runtime Summary

- avg_bpu_gap_vs_queue_points: -8.918
- avg_nonzero_bpu_gap_vs_queue_points: -5.403
- token_avg_run_ms: 8.535
- hidden_avg_run_ms: 8.1022
- final_logits_avg_run_ms: 20.272
- final_vs_hidden_avg_run_ratio: 2.502
- total_group_load_ms: 65892.357
- total_segment_run_ms: 980838.931
- group_load_fraction_of_wall: 0.0612

## Schedule Analysis Artifact

- current_report_md: tmp\b4_runtime_schedule_analysis_20260619\dream7b_true_batch_b4_schedule_analysis_current.md
- current_report_json: tmp\b4_runtime_schedule_analysis_20260619\dream7b_true_batch_b4_schedule_analysis_current.json
- instrumented_probe_report_json: tmp\remote_true_batch_reports\b4_mb128_segment_major_instrumented_true_batch_group_major_telemetry.json
- prealloc_ab_report_md: tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_prealloc_hidden_ab_20260619.md
- group_split_report_md: tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_mb128_group_split_20260619.md
- final_logits_breakdown_md: tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_final_logits_breakdown_20260619.md
- segment_drag_breakdown_md: tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_segment_drag_breakdown_20260619.md
- final_logits_candidate_sizing_md: tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_final_logits_candidate_sizing_20260619.md
- hbm_load_breakdown_md: tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_hbm_load_breakdown_20260619.md
- scaling_saturation_analysis_md: tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_scaling_saturation_analysis_20260619.md
- group_switch_accounting_md: tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_group_switch_accounting_20260619.md
- runtime_capacity_boundary_md: tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_runtime_capacity_boundary_20260620.md
- group_order_candidate_analysis_md: tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_group_order_candidate_analysis_20260620.md
- group_partition_planner_md: tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_group_partition_planner_20260620.md
- true_batch_nas_inventory_md: tmp\b4_runtime_schedule_analysis_20260619\dream7b_true_batch_nas_inventory_20260620.md
- last_token_compile_readiness_md: tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_last_token_compile_readiness_20260619.md
- compile_capacity_plan_md: tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_compile_capacity_plan_20260619.md
- last_token_final_logits_experiment_md: tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_last_token_final_logits_experiment_20260619.md
- last_token_validation_compare_md: tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_last_token_validation_compare_20260620.md
- 512 microbatch segment-major versus microbatch-major, using the current gap-field 5-group baseline: -0.584 ms/request, +0.352 avg BPU points, +0.468 nonzero BPU points.
- 512 microbatch even 6-group versus current 5-group segment-major: +0.238 ms/request, -0.188 avg BPU points, -0.123 nonzero BPU points.
- 512 microbatch final-isolated 6-group versus current 5-group segment-major: +0.143 ms/request, -0.313 avg BPU points, -0.545 nonzero BPU points.
- 512 microbatch 7-group versus current 5-group segment-major: +0.094 ms/request, -0.105 avg BPU points, -0.207 nonzero BPU points.
- group/order candidate analysis, using the best mb512 5-group segment-major baseline at 93.73 ms/request: no observed non-baseline group/order variant beats baseline; the least-bad non-baseline is 7-group at +0.227 ms/request, so more mb512 boundary sweeps are deprioritized.
- 128 microbatch skip-GC release policy versus the latest collect baseline: -1.563 ms/request, +0.326 avg BPU points, -0.29 nonzero BPU points, total group-release time -32.548 ms.
- 128 microbatch HBM prewarm versus latest collect baseline: +123.498 ms/request wall, -2479.499 ms group-load, +65754.965 ms prewarm read time for 7093.533 MiB, so prewarm is not a default path.
- 512 to 4096 microbatches raises avg BPU by 25.106 points, but nonzero BPU changes by only 0.139 points.
- At 4096 microbatches, B=4 remains -8.918 avg BPU points and -5.403 nonzero BPU points versus the queue baseline.
- Asymptotic projection: if active/nonzero BPU stays near 89.694, fixed-load amortization alone still cannot reach a 93 avg BPU gate.

## NAS / Local Runtime Inventory

- report: tmp\b4_runtime_schedule_analysis_20260619\dream7b_true_batch_nas_inventory_20260620.md
- verdict: ok_dream7b_true_batch_nas_inventory.
- NAS true-batch group-major records: 53 total; B=4 contributes 23.
- NAS batch coverage: b2=8, b4=23, b8=2, b16=4, b32=1, b64=15.
- Local B=4 mirror: 23 telemetry JSON files, matching the 23 NAS B=4 group-major records.
- Local B=4 outcomes: 20 successful, 3 failed capacity probes.
- B=4 HBM completeness: 28 HBM files and 28 manifests under the NAS B=4 root.
- Last-token final candidate: no NAS files and no local candidate telemetry yet.
- Interpretation: standard B=4 true-batch runtime history is already covered by NAS records and the local mirror; current S100P work should not repeat those sweeps.
- Decision: do not run more standard B=4 runtime sweeps now; use the existing NAS/local inventory before proposing any S100P experiment.
- Remaining non-duplicate work: last-token final logits single-segment compile after local commit/pagefile readiness, then mb512 validation, then dream7b_b4_last_token_validation_compare.py before any broader sweep.

## Runtime Experiment Gate

- report: tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_runtime_experiment_gate_20260620.md
- verdict: blocked_dream7b_b4_runtime_experiment_gate_no_s100p_run_now.
- s100p_runtime_experiment_now: false.
- allowed_experiments: [].
- standard B=4 coverage: NAS B=4 group-major reports 23; local B=4 telemetry JSON files 23; successful/failed 20/3.
- service gate: ready, with ok default-service freshness gate and ok operational SLO rollup freshness requirement.
- last-token candidate: compile_ready false, manifest_ready false, runtime_validation_ready false, candidate_result_exists false.
- partition candidate: planner searched 155457 contiguous partitions, but run_new_partition_now is false; top lower-HBM shape stays capacity-probe-only after the memory plan changes.
- blockers: standard B=4 sweeps already covered by NAS/local inventory; last-token compile, manifest, and runtime validation are not ready; group partition planner deprioritizes a new partition run.
- decision: do not start a new S100P B=4 runtime experiment now. The next non-duplicate runtime candidate remains seg27_28_last_token_logits after compile/pagefile readiness and remote manifest verification.

## Runtime Scheduling Instrumentation

- probe_updated: scripts\probes\dream7b_true_batch_group_major_telemetry_probe.py
- remote_probe_path: /mnt/nas/openclaw/scripts/probes/dream7b_true_batch_group_major_telemetry_probe.py
- remote_backup_path: /mnt/nas/openclaw/scripts/probes/dream7b_true_batch_group_major_telemetry_probe.py.bak_20260619_runtime_gap
- added fields: total_segment_total_ms, total_segment_overhead_ms, total_group_release_ms, measured_active_ms, estimated_unaccounted_gap_ms.
- added per-segment load attribution: loaded_segments with load_ms, hbm_path, hbm_size_bytes, and hbm_size_mib for each loaded HBM.
- added prewarm policy knob: --prewarm-hbm, defaulting to false, with total_hbm_prewarm_ms and total_hbm_prewarm_mib recorded separately from group_load_ms.
- added release policy knob: --release-gc-mode collect|skip, defaulting to collect for baseline compatibility.
- added segment-major gap fields: inter_segment_first_run_gap_ms and intra_segment_run_gap_ms, so Python scheduling gaps are measured separately from runtime.run and hidden materialization.
- semantic change: estimated_host_gap_ms now subtracts measured active time, not only runtime.run time, so segment-major Python-side segment overhead is not misclassified as host gap.
- B=4 mb128 validation verdict: ok_dream7b_true_batch_group_major_telemetry.
- B=4 mb128 validation summary: group_load_fraction 0.6772, measured_active_fraction 0.3188, segment_overhead_fraction 0.0090, group_release_fraction 0.0019, unaccounted_gap_fraction 0.0021.
- B=4 mb128 absolute overheads: total_segment_overhead_ms 889.417, total_group_release_ms 187.099, estimated_unaccounted_gap_ms 206.245.
- B=4 mb128 load-attributed follow-up: ok, 190.645 ms/request, avg BPU 29.205, nonzero BPU 88.621; group load segments are now directly attributed.
- B=4 mb128 skip-GC follow-up: ok, 190.568 ms/request, avg BPU 29.178, nonzero BPU 88.263; versus the latest gap-field collect baseline it saved 1.563 ms/request.
- B=4 mb512 skip-GC follow-up: ok, 94.128 ms/request, avg BPU 59.085, nonzero BPU 89.679; versus the mb512 gap-field collect baseline it was 0.265 ms/request slower and reduced avg BPU by 0.057 points, so skip-GC stays a profiling knob rather than a default runtime candidate.
- mb512 skip-GC report_json: tmp\remote_true_batch_reports\b4_mb512_segment_major_release_gc_skip_true_batch_group_major_telemetry.json
- B=4 mb128 gap-field follow-up: ok, 192.131 ms/request, avg BPU 28.852, nonzero BPU 88.553; inter-segment first-run gap is 0.001943 ms/request and intra-segment run gap is 0.059676 ms/request.
- gap-field report_json: tmp\remote_true_batch_reports\b4_mb128_segment_major_gap_fields_true_batch_group_major_telemetry.json
- B=4 mb512 gap-field follow-up: ok, 93.863 ms/request, avg BPU 59.142, nonzero BPU 89.555; inter-segment first-run gap is 0.000724 ms/request and intra-segment run gap is 0.061106 ms/request.
- mb512 gap-field report_json: tmp\remote_true_batch_reports\b4_mb512_segment_major_gap_fields_true_batch_group_major_telemetry.json
- B=4 mb768 gap-field capacity probe: failed while loading seg02_03 with BPU memory allocation failure; processed_request_count 0.
- B=4 mb1024 gap-field capacity probe: failed after completing group 0:6, while loading seg10_11 with BPU memory allocation failure; processed_request_count 0.
- runtime capacity boundary: latest gap-instrumented success is mb512; first gap-instrumented failure is mb768, so do not continue gap microbatch sweeps above the current success boundary until the memory/runtime plan changes.

## Hidden Buffer Preallocation A/B

- probe_flag: --preallocate-hidden
- no_prealloc_v2_report_json: tmp\remote_true_batch_reports\b4_mb512_segment_major_instrumented_v2_true_batch_group_major_telemetry.json
- prealloc_report_json: tmp\remote_true_batch_reports\b4_mb512_segment_major_prealloc_true_batch_group_major_telemetry.json
- A/B report: tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_prealloc_hidden_ab_20260619.md
- reuse validation: prealloc reused hidden buffers 13824 times at B=4 mb512.
- observed delta: prealloc wall_ms +1729.121, ms/request +0.845, avg BPU -0.59 points, nonzero BPU -1.43 points.
- hidden materialization delta: total_hidden_materialize_ms +1414.194, hidden_materialize_ms_per_item +0.1023, hidden_materialize_ms_per_request +0.690524.
- decision: keep preallocation as an experimental flag; do not make it the default from the mb512 evidence.

## Group Split Capacity Probe

- g4_capacity_failed_report_json: tmp\remote_true_batch_reports\b4_mb128_segment_major_g4_capacity_failed_true_batch_group_major_telemetry.json
- g6_report_json: tmp\remote_true_batch_reports\b4_mb128_segment_major_g6_true_batch_group_major_telemetry.json
- g6_mb512_report_json: tmp\remote_true_batch_reports\b4_mb512_segment_major_g6_true_batch_group_major_telemetry.json
- final_isolated_mb512_report_json: tmp\remote_true_batch_reports\b4_mb512_segment_major_final_isolated_true_batch_group_major_telemetry.json
- report: tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_mb128_group_split_20260619.md
- 4-group plan tested: 0:7,7:14,14:21,21:28.
- 4-group result: failed while loading seg06_07 with HBRT4_STATUS_RESOURCE_EXHAUSTED / Memory alloc failed.
- 6-group plan tested: 0:5,5:10,10:15,15:20,20:24,24:28.
- 6-group result: ok at B=4 mb128, 190.436 ms/request, avg BPU 29.233, nonzero BPU 88.062.
- 6-group versus 5-group at mb128: -0.161 ms/request, +0.128 avg BPU points, +0.018 nonzero BPU points.
- 6-group mb512 follow-up result: ok, 94.101 ms/request, avg BPU 58.954, nonzero BPU 89.432.
- 6-group versus current 5-group at mb512: +0.238 ms/request, -0.188 avg BPU points, -0.123 nonzero BPU points.
- final-isolated mb512 follow-up result: ok, 94.006 ms/request, avg BPU 58.829, nonzero BPU 89.01.
- final-isolated versus current 5-group at mb512: +0.143 ms/request, -0.313 avg BPU points, -0.545 nonzero BPU points.
- decision: do not run long mb512 4-group experiments; 5-group remains the safer default, and group-boundary isolation of final logits does not beat the baseline.

## Final Logits Breakdown

- report: tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_final_logits_breakdown_20260619.md
- analyzed successful segment-major runs: 13.
- latest default sample: b4_mb4096_segment_major_true_batch_group_major_telemetry.json.
- latest final_avg_run_ms: 20.272.
- latest hidden_mean_avg_run_ms: 8.1022.
- latest final_vs_hidden_avg_run_ratio: 2.5021.
- latest final_segment_total_fraction_of_all_segment_total: 0.083758.
- latest final_group_range: 24:28.
- latest final_group_load_vs_non_final_mean_ratio: 0.9548.
- latest final_group_segment_total_vs_non_final_mean_ratio: 0.9094.
- interpretation: final logits is a per-segment runtime outlier, but the final group itself is not a group-load outlier; tuning should isolate the logits segment rather than only reshuffle group boundaries.

## Final Output Attribution

- report: tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_final_output_attribution_20260619.md
- verdict: ok_dream7b_b4_final_output_attribution.
- latest default sample: b4_mb4096_segment_major_true_batch_group_major_telemetry.json.
- latest_final_run_ms_per_request: 5.06795.
- latest_final_segment_overhead_ms_per_request: 0.094674.
- latest_final_excess_ms_per_request_if_hidden_speed: 3.042462.
- queue_raw_final_overhead_ms_per_request: 0.257113.
- queue_raw_final_shape_ms_per_request: 0.001636.
- queue_raw_final_state_clear_ms_per_request: 0.120661.
- decision: Python/output overhead is already small; next runtime work should reduce final logits compute or avoid full-vocab output.

## Final Logits Candidate Sizing

- report: tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_final_logits_candidate_sizing_20260619.md
- verdict: ok_dream7b_b4_final_logits_candidate_sizing.
- current_final_shape: [4, 16, 152064].
- candidate_target_shape: [4, 1, 152064].
- output_element_reduction_vs_current: 16.0x.
- current_f32_output_mib_per_request: 9.28125.
- last_token_f32_output_mib_per_request: 0.580078.
- measured_final_segment_overhead_ms_per_request: 0.094674.
- measured_final_excess_ms_per_request_if_hidden_speed: 3.042462.
- projection_only_saved_ms_per_request: 2.852297.
- projection_only_final_run_ms_per_request: 2.215703.
- implementation status: compiler and runtime probe now support opt-in last-token mode.
- next experiment: compile seg27_28_last_token_logits into /mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b4-last-token-final and run a runtime probe that loads only seg27_28 from that final_hbm_root while keeping the other 27 segments from the existing B=4 root.
- latest compile readiness: blocked_dream7b_b4_last_token_compile; compile_ready false; runtime_validation_ready false.
- latest compile blockers: windows_compile_preflight_failed, insufficient_windows_commit_headroom, large_private_process_present, remote_last_token_manifest_missing.
- last-token experiment gate: blocked_dream7b_b4_last_token_experiment_gate; code_support_ready true; experiment_ready false.
- gate blockers: last_token_compile_not_ready, last_token_manifest_not_ready, last_token_runtime_validation_not_ready.
- runtime validation plan: blocked_dream7b_b4_last_token_runtime_validation_plan; queue_idle true; services_ready true; runtime_tools_ready true; lock_busy false; blocker last_token_manifest_not_ready.
- validation command: tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_last_token_runtime_validation_plan_20260620.md records the exact mb512 segment-major 5-group command with --final-hbm-root and --final-logits-mode last-token.
- validation compare gate: blocked_dream7b_b4_last_token_validation_compare_missing_result; candidate result does not exist yet, so no last-token runtime win is asserted.
- validation compare baseline: tmp\remote_true_batch_reports\b4_mb512_segment_major_gap_fields_true_batch_group_major_telemetry.json, 93.863 ms/request, avg BPU 59.142, nonzero BPU 89.555, final shape [4, 16, 152064].
- validation compare required candidate: tmp\remote_true_batch_reports\b4_mb512_segment_major_last_token_true_batch_group_major_telemetry.json with final shape [4, 1, 152064], final_logits_mode last-token, 2048 processed requests, 0 failed jobs.
- latest local compile preflight: Windows commit headroom is 1.56 GB versus the 64 GB compile guard, a 62.44 GB deficit.
- largest private process: F:\Program\Anaconda\envs\tf2\python.exe, pid 261928, private 18.26 GB.
- remote last-token HBM manifest: missing and not verified.
- compile capacity plan: closing the tf2 process would project commit headroom to only 19.82 GB, still 44.18 GB below the guard.
- pagefile query status: current non-elevated WMI pagefile usage/settings queries fail with permission denied, so the current pagefile allocation is not asserted in this refreshed report.
- recommended compile-unblock capacity: after closing the large process, increase commit limit/pagefile by at least 44.18 GB, or about 52.18 GB with the recorded 8 GB safety margin.

## Segment Drag Breakdown

- report: tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_segment_drag_breakdown_20260619.md
- verdict: ok_dream7b_b4_segment_drag_breakdown.
- analyzed successful segment-major runs: 19.
- default 5-group collect run count: 10.
- latest default sample: b4_mb4096_segment_major_true_batch_group_major_telemetry.json.
- latest hidden_mean_avg_run_ms: 8.1022.
- latest hidden_stdev_avg_run_ms: 0.0104.
- latest final_avg_run_ms: 20.272.
- latest final_vs_hidden_mean_ratio: 2.5021.
- latest final_excess_ms_per_request_if_hidden_speed: 3.04246.
- default collect final_excess mean/stdev: 3.04195 / 0.00538 ms/request.
- all segment-major final_excess mean/stdev: 3.04043 / 0.00607 ms/request.
- latest token_avg_run_ms: 8.535.
- latest token_excess_ms_per_request_if_hidden_speed: 0.10821.
- slowest segment across runs: segment 27 final logits, mean 20.2659 ms, mean positive excess 3.04097 ms/request.
- second slowest segment across runs: segment 0 token embedding, mean 8.5285 ms, mean positive excess 0.10661 ms/request.
- hidden segment cluster: hidden stdev is only 0.0104 ms in the latest default run, so hidden-block inner reordering has little headroom.
- latest largest accounted group: 0:6, not the final group; final logits is the segment outlier, not a final-group HBM-load outlier.
- scheduling implication: final-logits group-boundary isolation was tested and did not beat the 5-group baseline; prioritize reducing/avoiding final-logits compute or output movement rather than more boundary sweeps.

## Group Switch Accounting

- report: tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_group_switch_accounting_20260619.md
- verdict: ok_dream7b_b4_group_switch_accounting.
- latest default sample: b4_mb4096_segment_major_true_batch_group_major_telemetry.json.
- group_load_ms_per_request: 4.02175.
- group_switch_gap_ms_per_request: 0.024841.
- group_release_ms_per_request: 0.011831.
- unaccounted_gap_ms_per_request: 0.01301.
- segment_overhead_ms_per_request: 1.771654.
- hidden_materialize_ms_per_request: 1.266249.
- segment_overhead_excluding_hidden_materialize_ms_per_request: 0.505405.
- final_logits_excess_ms_per_request_if_hidden_speed: 3.042462.
- final_excess_to_switch_gap_ratio: 122.48.
- latest gap-instrumented sample: b4_mb512_segment_major_gap_fields_true_batch_group_major_telemetry.json.
- gap-instrumented inter_segment_first_run_gap_ms_per_request: 0.000724.
- gap-instrumented intra_segment_run_gap_ms_per_request: 0.061106.
- gap-instrumented residual_after_measured_gaps_ms_per_request: 0.44394.
- gap-instrumented final_logits_excess_ms_per_request_if_hidden_speed: 3.039702.
- decision: group release plus unaccounted switch gap is not the main lever; only revisit group caching/load policy if a memory plan allows more HBM groups to stay resident.

## Scheduler Overhead Budget

- report: tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_scheduler_overhead_budget_20260620.md
- verdict: ok_dream7b_b4_scheduler_overhead_budget.
- primary code target: `seg27_28_last_token_logits_or_output_avoidance`.
- next runtime experiment: validate `seg27_28` last-token logits or equivalent full-vocab-output avoidance at mb512 before larger sweeps.
- runtime validation readiness: S100P queue, services, runtime tools, and lock state are ready for the mb512 last-token validation command; live blockers are the missing last-token HBM manifest and the local compile gate.
- final logits active excess: `3.042462 ms/request`.
- hidden materialize budget: `1.266249 ms/request`, secondary and still experimental because existing prealloc evidence does not justify promotion.
- segment overhead excluding hidden materialize: `0.505405 ms/request`.
- gap-instrumented residual after measured gaps: `0.44394 ms/request`.
- intra-segment run gap: `0.061106 ms/request`; inter-segment first-run gap: `0.000724 ms/request`.
- group switch gap: `0.024841 ms/request`.
- final excess to group-switch-gap ratio: `122.477`; final excess to intra-segment-gap ratio: `49.79`; final excess to final Python output overhead ratio: `32.136`.
- stop rule: Python inter-segment gap tuning and additional mb512 group-boundary sweeps are deprioritized; gap-instrumented sweeps above mb512 stay blocked until the memory/runtime plan changes.

## HBM Load Breakdown

- report: tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_hbm_load_breakdown_20260619.md
- verdict: ok_dream7b_b4_hbm_load_breakdown.
- latest load-attributed sample: b4_mb128_segment_major_load_attributed_true_batch_group_major_telemetry.json.
- total_group_load_ms_per_request at mb128: 128.252936.
- token_embedding_load_ms: 7267.292, hbm_size_mib 744.139.
- final_logits_load_ms: 6694.141, hbm_size_mib 740.828.
- hidden_mean_load_ms: 1987.986, hidden_stdev_load_ms 27.73.
- final_vs_hidden_load_ratio: 3.3673.
- largest_load_group: 0:6; final_group_is_largest_load_group: false.
- HBM prewarm A/B: group-load improves by 2479.499 ms total, but prewarm itself costs 65754.965 ms and worsens wall time by 123.498 ms/request.
- decision: per-segment HBM load telemetry is now available; token embedding and final logits are load outliers, but group-boundary tuning alone remains secondary because the final group is not the largest load group and the mb512 split tests still do not beat the 5-group baseline.

## Scaling Saturation Gate

- report: tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_scaling_saturation_analysis_20260619.md
- latest observed point: 4096 microbatches, avg BPU 84.248, nonzero BPU 89.694, 65.684 ms/request.
- latest required_nonzero_bpu_for_93_avg: 99.012, which is 9.318 points above the observed nonzero BPU.
- low-load projection still requires nonzero BPU 97.895 for a 93 average gate.
- projected max avg BPU at 6144/8192/12288, if nonzero BPU stays unchanged, is 87.729.
- decision: deprioritize microbatch-only sweeps and do not run mb6144 until the last-token final-logits candidate or another active-BPU lever changes the runtime profile.
- runtime boundary stop rule: gap-instrumented runs succeed through mb512 and fail at mb768/mb1024 in the current S100P memory state; continue prioritizing the final-logits candidate instead of more gap microbatch sweeps.
- group/order candidate gate: segment-major remains preferred over microbatch-major; observed mb512 group/order variants are all within 1 ms/request of the 5-group baseline and none beats it, so keep `g7_even_lower_peak_hbm` only as a targeted capacity probe if the memory plan changes.

## Group Partition Planner

- report: tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_group_partition_planner_20260620.md
- verdict: ok_dream7b_b4_group_partition_planner.
- systematic candidates: 155457 contiguous partitions.
- baseline max group HBM: 1822.738 MiB; observed failed g4 peak: 2038.434 MiB.
- top capacity-probe-only shape: 0:2,2:6,6:11,11:16,16:21,21:26,26:28; max group HBM 1078.566 MiB, -40.827% versus baseline, estimated release delta +0.036512 ms/request.
- observed nonbaseline variants: g7 +0.227 ms/request, final-isolated +0.276, g6 +0.371; do not repeat as normal tuning sweeps.
- decision: do not run a new partition now; keep new partitions as capacity probes only after memory plan changes.

## Segment Bottleneck Scorecard

- report: tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_segment_bottleneck_scorecard_20260620.md
- verdict: ok_dream7b_b4_segment_bottleneck_scorecard.
- primary runtime lever: `final_logits_compute_or_output_avoidance`.
- preferred group policy: keep the current 5-group segment-major default.
- preferred inner order: `segment-major`.
- segment stability: 19 successful segment-major runs analyzed; 10 default collect runs show final-logits positive excess mean `3.04195 ms/request` with stdev `0.00538`.
- top segment bottleneck: segment 27 `final_logits`, mean positive excess `3.04043 ms/request`, load `13.074494 ms/request`.
- secondary residency follow-up: segment 0 `token_embedding`, load `14.19393 ms/request` but active-run excess only `0.10679 ms/request`.
- hidden-block tuning priority: low; the largest hidden-block excess is segment 12 at `0.00296 ms/request`, about `1027x` smaller than the final-logits excess.
- group/order decision: no observed mb512 non-baseline variant beats the 5-group baseline; microbatch-major is `+0.717 ms/request`, g6 even is `+0.371 ms/request`, g7 even is `+0.227 ms/request`, and final-isolated is `+0.276 ms/request`.
- stop rule: avoid more mb512 boundary sweeps and avoid gap microbatch sweeps above mb512 until the memory/runtime plan changes.
- next runtime candidate remains `seg27_28_last_token_logits`.

## Segment Stability Audit

- report: tmp\b4_runtime_schedule_analysis_20260619\dream7b_b4_segment_stability_audit_20260620.md
- verdict: ok_dream7b_b4_segment_stability_audit.
- analyzed runs: 19; ranked segments: 28.
- stable primary bottleneck: `seg27_28_final_logits`.
- final logits rank-1 rate: `1.0`; top-2 rate: `1.0`; positive-excess CV: `0.001996`.
- final logits mean positive excess: `3.040432 ms/request`.
- token embedding mean positive excess: `0.106787 ms/request`; final-to-token excess ratio: `28.472`.
- max hidden bottleneck: segment 5, `0.003587 ms/request`; final-to-max-hidden excess ratio: `847.625`.
- decision: do not run hidden-order sweeps or standard B=4 sweeps now; keep `seg27_28_last_token_logits` as the next non-duplicate runtime candidate.

## Interpretation

- Compile side: hidden segments are tightly clustered; the first token/embedding segment and final logits segment are the main outliers.
- Runtime side: B=4 segment-major execution is valid and stable, but it remains below the queue-batch BPU loading gate.
- Inner-order comparison: at 512 microbatches, segment-major is only slightly better than microbatch-major, so loop order alone is not the missing production lever.
- Group-size comparison: at 512 microbatches, even 6-group, final-isolated 6-group, and 7-group splits all worsen wall time and BPU loading versus the 5-group baseline.
- Group partition planner: exhaustive contiguous partition search found much lower peak-HBM capacity-probe shapes, but no observed non-baseline mb512 variant beats the current 5-group baseline; do not spend normal runtime time on more group sweeps until the memory plan changes.
- Long-queue scaling: increasing from 3072 to 4096 microbatches improves average BPU loading from 82.579 to 84.248 and lowers per-request wall time from 66.976 ms to 65.684 ms, but still does not reach the queue-batch BPU gate.
- Segment breakdown: final logits is the stable run-time outlier, ranking first in 19/19 analyzed B=4 runs; tune scheduling around it separately from the hidden-block average.
- Segment drag: the final logits excess is about 3.04 ms/request in the latest mb4096 run, while token embedding excess is about 0.11 ms/request and hidden blocks are tightly clustered.
- Final output attribution: final segment overhead outside runtime.run is about 0.095 ms/request in the latest mb4096 run, so output bookkeeping is not the main lever.
- HBM load attribution: token embedding and final logits are the two large load segments, but the final group is not the largest group-load contributor; this supports treating HBM load as an amortization/memory-residency problem rather than another simple boundary split.
- HBM prewarm: explicit pre-read lowers measured runtime group-load but has a much larger read cost, so it should stay experimental rather than becoming the default load policy.
- Candidate sizing: last-token-only logits would reduce final logits elements by 16x and has a projection-only estimated saving of about 2.85 ms/request; this is the next single-segment compile to test before any more boundary sweeps.
- Last-token experiment gate: compiler wrapper, compiler script, local runtime probe, and remote S100P runtime probe all support the last-token path; the remaining blockers are compile capacity and the missing remote last-token HBM manifest.
- Last-token validation compare: the post-run comparator is now in place, but currently reports missing-result rather than a performance outcome; use it only after the single-segment HBM exists and mb512 validation has produced telemetry.
- Group switch accounting: release plus unaccounted group-switch gap is only about 0.025 ms/request at mb4096; the gap-instrumented mb512 run also shows inter-segment first-run gap about 0.0007 ms/request and intra-segment run gap about 0.0611 ms/request, while final logits excess is about 3.04 ms/request. Optimize final logits before Python gap micro-tuning.
- Scheduler overhead budget: final logits active excess is about 122x the measured group-switch gap, about 50x the intra-segment run gap, and about 32x final Python output overhead; runtime-code work should start with final-logits compute/output avoidance, not micro gap tuning.
- Gap accounting: segment-major measured-run fraction comes from per-segment run totals; microbatch-major uses group item totals, so compare host gap directionally rather than as identical instrumentation.
- Scheduling implication: group sizing can reduce load/release amortization in short runs, but the mb512 group-boundary follow-ups do not beat the 5-group baseline; next runtime work should target compile/runtime paths that reduce final-logits compute or avoid full-vocab output first.
