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

## Round 3 Compile Status

The latest not-yet-published split targets the current top absolute-load window:

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

Round 3 is compiled but not yet published to:

```text
/mnt/nas/openclaw/models/dream7b-hbm/resplit-topwindow-seq16
/home/sunrise/.cache/openclaw/dream7b-hbm/resplit-topwindow-seq16
```

It also has not yet been added to `RESPLIT_TOPWINDOW_ADJACENT_SEGMENTS`, and no post-round3 telemetry/window-cost report exists yet.

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

1. Publish the four round3 HBM files to NAS and S100P local cache.
2. Extend the top-window manifest to include:

```text
14:15 15:17 17:18 18:19
```

3. Run `dream7b-bpu-resplit-hbm-artifact-inventory-probe` with expected specs:

```text
7:8 8:10 14:15 15:17 17:18 18:19 21:22 22:24
```

4. Update `RESPLIT_TOPWINDOW_ADJACENT_SEGMENTS` so `seg14_17` becomes `seg14_15 + seg15_17`, and `seg17_19` becomes `seg17_18 + seg18_19`.
5. Run batch-16 telemetry with:

```text
DREAM7B_BPU_RESPLIT_SEGMENT_PLAN=resplit-topwindow-adjacent
DREAM7B_BPU_RESPLIT_BATCH_TELEMETRY_EXPECTED_SEGMENT_PLAN=resplit-topwindow-adjacent
```

6. Run `dream7b-bpu-resplit-window-cost-probe` with the correct expected event count after the segment plan is updated.
7. Compare the new `load_to_run_ratio` against `9.694618`.
8. Update README, project reference, progress doc, and docs consistency probe.
9. Commit and push only the Dream 7B related files.

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

If the teacher asks what the next experiment is, answer:

```text
Publish and test the compiled round3 split specs 14:15, 15:17, 17:18, and 18:19, then compare the new load_to_run_ratio against 9.694618.
```
