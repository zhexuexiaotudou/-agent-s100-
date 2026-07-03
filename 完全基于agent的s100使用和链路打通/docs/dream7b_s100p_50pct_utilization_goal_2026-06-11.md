# Dream 7B S100P Sustained Utilization Goal

## Current Status As Of 2026-06-11

The default service is still about `9.7%`, but the current rollback-safe
selected-pair large-batch candidate has crossed the 50% sustained-utilization
target without replacing the default service.

Current best 50% candidate:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_queue_telemetry_20260611-192528/cross_job_queue_telemetry_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_50pct_candidate_acceptance_20260611-193007/50pct_candidate_acceptance_probe.json
```

Key fields:

```text
job_count: 2
request_count: 192
processed_request_count: 384
failed_job_count: 0
avg_bpu_loading: 52.328
max_bpu_loading: 98.0
load_to_run_ratio: 0.778725
amortized_wall_ms_per_processed_request: 262.083
deployment_acceptance: 30 / 30
rollback_status: rollback_safe_candidate_only
default_service_replaced: False
```

This satisfies the numerical 50% candidate gate on an at-least-192-request
telemetry run. It is deliberately kept as candidate-only because the default
service replacement gate remains separate from utilization measurement.

The latest same-day default-service reproduction is the current comparison
baseline:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_cross_job_default_service_telemetry_20260611-150155/default_service_telemetry_probe.json
```

Key fields:

```text
processed_request_count: 192
failed_job_count: 0
avg_bpu_loading: 9.695
max_bpu_loading: 100.0
load_to_run_ratio: 8.817409
amortized_wall_ms_per_processed_request: 1460.823
```

The latest same-day selected-pair cross-job candidate retest is stable but only
slightly better:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_queue_telemetry_20260611-152221/cross_job_queue_telemetry_probe.json
```

Key fields:

```text
processed_request_count: 192
failed_job_count: 0
avg_bpu_loading: 9.764
max_bpu_loading: 100.0
load_to_run_ratio: 8.757816
amortized_wall_ms_per_processed_request: 1443.045
```

The same-day delta is therefore only `+0.069` percentage points of average BPU
loading and `-0.059593` load/run ratio. This is not a Phase 1 utilization
breakout.

## Historical Baseline

Latest default-service telemetry:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_cross_job_default_service_telemetry_20260610-191115/default_service_telemetry_probe.json
```

Key fields:

```text
processed_request_count: 192
failed_job_count: 0
queue_done_count: 12
avg_bpu_loading: 9.915
max_bpu_loading: 98.0
load_to_run_ratio: 8.734653
amortized_wall_ms_per_processed_request: 1441.545
```

Latest cross-job candidate service telemetry:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_candidate_service_telemetry_20260610-182409/service_telemetry_probe.json
```

Key fields:

```text
processed_request_count: 192
failed_job_count: 0
avg_bpu_loading: 10.108
max_bpu_loading: 98.0
load_to_run_ratio: 8.66679
amortized_wall_ms_per_processed_request: 1430.794
```

The best current sustained average BPU loading is therefore about `10.108%`
on the isolated candidate, while the promoted/default service is `9.915%`.

## Diagnosis

The latest utilization-gap probe still reports:

```text
diagnosis: hbm_reload_dominated
```

The model can hit high instantaneous BPU loading (`max_bpu_loading` near
`98-100%`), but sustained average utilization is held down by repeated HBM
load/reload and segment residency limits. For this reason, peak BPU loading is
not a valid 128TOPS success claim by itself.

The current diagnosis refresh is:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_utilization_gap_20260611-151217/utilization_gap_probe.json
diagnosis: hbm_reload_dominated
```

## Long-Run Goal

Target:

```text
sustained avg_bpu_loading >= 50%
```

Minimum acceptance scope:

```text
processed_request_count >= 192
failed_job_count = 0
deployment_acceptance passes
default_deployable_acceptance remains ready, or the candidate is rollback-safe
```

## Phase Gates

### Phase 0: Reproduce Baseline

Re-run the current default-service telemetry and confirm the baseline remains
within the same band:

```text
avg_bpu_loading ~= 9.9%
load_to_run_ratio ~= 8.7
processed_request_count >= 192
failed_job_count = 0
```

Phase 0 rerun on 2026-06-11:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_cross_job_default_service_telemetry_20260611-150155/default_service_telemetry_probe.json
```

Key fields:

```text
processed_request_count: 192
failed_job_count: 0
queue_done_count: 12
queue_failed_count: 0
avg_bpu_loading: 9.695
max_bpu_loading: 100.0
load_to_run_ratio: 8.817409
amortized_wall_ms_per_processed_request: 1460.823
amortized_total_load_ms_per_processed_request: 1308.211
amortized_run_ms_per_processed_request: 148.367
```

Interpretation: the current default service reproduces the same utilization band
as the 2026-06-10 baseline, but does not improve it. The 50% target remains a
long-run optimization goal rather than a current claim.

Phase 0 acceptance refresh:

```text
utilization_gap: /mnt/nas/openclaw/reports/models/dream7b_bpu_utilization_gap_20260611-151217/utilization_gap_probe.json
deployment_acceptance: /mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260611-151810/deployment_acceptance_probe.json
default_deployable_acceptance: /mnt/nas/openclaw/reports/models/dream7b_bpu_default_deployable_acceptance_20260611-151843/default_deployable_acceptance_probe.json
```

Current acceptance status:

```text
utilization_gap.verdict: ok_dream7b_bpu_utilization_gap_probe
utilization_gap.diagnosis: hbm_reload_dominated
deployment_acceptance.verdict: ok_dream7b_bpu_deployment_acceptance_probe
deployment_acceptance.check_count: 30
deployment_acceptance.passed_check_count: 30
default_deployable_acceptance.verdict: ok_dream7b_bpu_default_deployable_acceptance_probe
default_deployable_acceptance.default_deployable_ready: False
default_deployable_acceptance.default_deployable_status: blocked_candidate_only
```

The deployment checks pass after updating the acceptance reader to tolerate the
promoted cross-job default service. The default-deployable gate still blocks a
new "utilization improvement" claim because average loading is below the default
deployment threshold and the run is still HBM-reload dominated.

### Phase 1: First Sustained Utilization Breakout

Claim only when:

```text
avg_bpu_loading >= 15%
load_to_run_ratio <= 7.0
processed_request_count >= 192
failed_job_count = 0
```

Phase 1 candidate retest on 2026-06-11:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_queue_telemetry_20260611-152221/cross_job_queue_telemetry_probe.json
```

Key fields:

```text
processed_request_count: 192
failed_job_count: 0
job_count: 12
request_count: 16
avg_bpu_loading: 9.764
max_bpu_loading: 100.0
load_to_run_ratio: 8.757816
amortized_wall_ms_per_processed_request: 1443.045
amortized_total_load_ms_per_processed_request: 1291.582
amortized_run_ms_per_processed_request: 147.478
selected_pair: [1, 8]
selected_segments: ['seg02_04', 'seg24_26']
```

Delta versus the 2026-06-11 default-service baseline:

```text
avg_bpu_loading_delta: +0.069 percentage points
load_to_run_ratio_delta: -0.059593
amortized_wall_ms_delta_per_processed_request: -17.778
phase1_avg_ge_15: False
phase1_load_ratio_le_7: False
```

Interpretation: cross-job selected-pair execution is stable and slightly better
than the same-day default-service rerun, but the improvement is far below the
Phase 1 gate. This remains useful as a baseline candidate, not as a utilization
breakout.

Phase 1 reload experiment planner on 2026-06-11:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_phase1_reload_experiment_planner_20260611-153934/phase1_reload_experiment_planner_probe.json
```

Planner conclusions:

```text
recommended_next_experiment: phase1_topload_resplit_compile
prefix_selected_pair_override.feasible_now: False
topload_selected_pair_override.feasible_now: False
phase1_topload_resplit_compile.feasible_now: False
```

The two no-new-HBM selected-pair shortcuts are not valid:

```text
selected pair [0,1] does not cover all fine-adjacent segments through successful triplets
selected pair [1,2] does not cover all fine-adjacent segments through successful triplets
```

The next useful experiment therefore requires new top-load split HBM artifacts:

```text
target_specs: 2:3 3:4 4:5 5:7
target_window: seg02_04 + seg04_07
current blocker: missing HBM artifacts and no compile environment on this host
```

Phase 1 segment-plan wiring and deployed dry-run on 2026-06-11:

```text
scripts/probes/dream7b_bpu_phase1_segment_plan_preflight_probe.sh
/mnt/nas/openclaw/reports/models/dream7b_bpu_phase1_segment_plan_preflight_20260611-154955/phase1_segment_plan_preflight_probe.json
/mnt/nas/openclaw/reports/models/dream7b_phase1_deployed_dryrun/segment_plan_preflight.json
```

The new `phase1-topload-adjacent` plan is wired into the deployed forward path
and dry-run verified without loading BPU runtimes. It is not runnable yet
because four HBM shards are missing:

```text
seg02_03
seg03_04
seg04_05
seg05_07
```

Live command/runtime backups were created before deploying the dry-run-capable
wrappers:

```text
/usr/local/bin/dream7b-bpu-forward.before-phase1-20260611-154904
/usr/local/bin/dream7b-bpu-resplit-batch-forward.before-phase1-20260611-154904
/usr/local/bin/dream7b-bpu-resplit-forward.before-phase1-20260611-154904
/mnt/nas/openclaw/runtimes/dream7b-bpu-forward/dream7b_segmented_hbm_python_forward.py.before-phase1-20260611-154904
```

Default execution remains on the existing promoted plan. The Phase 1 plan
requires explicit `--segment-plan phase1-topload-adjacent` or the corresponding
environment override, and currently blocks at preflight until the missing HBM
artifacts exist.

Phase 1 no-new-HBM long-session experiment on 2026-06-11:

```text
scripts/probes/dream7b_bpu_cross_job_long_session_telemetry_probe.sh
/mnt/nas/openclaw/reports/models/dream7b_bpu_cross_job_long_session_telemetry_20260611-160959/long_session_telemetry_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_cross_job_long_session_telemetry_20260611-161823/long_session_telemetry_probe.json
```

The 18-job run processed `288` requests with no failed jobs:

```text
avg_bpu_loading: 9.775
load_to_run_ratio: 8.711317
amortized_wall_ms_per_processed_request: 1450.312
phase1_gate.passed: False
```

The 24-job run processed `384` requests with no failed jobs:

```text
avg_bpu_loading: 9.696
load_to_run_ratio: 8.741708
amortized_wall_ms_per_processed_request: 1448.516
phase1_gate.passed: False
```

Interpretation: increasing selected-pair resident session length beyond the
current 12-job baseline is stable and slightly reduces load/run in the 18-job
case, but it does not create a Phase 1 breakout. The 24-job run does not improve
average BPU loading. This closes the no-new-HBM long-session path as a minor
tuning candidate only; the main next step remains compiling the four missing
top-load HBM shards.

### Phase 2: Strong Candidate

Claim only when:

```text
avg_bpu_loading >= 20%
load_to_run_ratio <= 5.0
processed_request_count >= 192
failed_job_count = 0
```

### Phase 3: 50% Sustained Utilization Target

Claim only when:

```text
avg_bpu_loading >= 50%
processed_request_count >= 192
failed_job_count = 0
deployment_acceptance passes
default_deployable_acceptance passes or rollback-safe candidate status is documented
```

## Next Optimization Direction

The next useful work should target reload overhead before trying to tune prompts
or UI integration:

1. Treat the 2026-06-11 default-service rerun as the Phase 0 baseline.
2. Compare any candidate against `avg_bpu_loading: 9.695` and
   `load_to_run_ratio: 8.817409` on at least 192 processed requests.
3. Treat the 2026-06-11 cross-job selected-pair retest as a stable but
   insufficient candidate: `avg_bpu_loading: 9.764`,
   `load_to_run_ratio: 8.757816`.
4. Treat the 18x16 long-session retest as the current best no-new-HBM candidate:
   `avg_bpu_loading: 9.775`, `load_to_run_ratio: 8.711317`,
   `processed_request_count: 288`, `failed_job_count: 0`.
5. Do not spend more effort on job-count-only scaling unless a separate runtime
   change reduces non-selected segment reloads; 24x16 regressed to
   `avg_bpu_loading: 9.696`.
6. Revisit the known expensive windows:
   - high ratio: `seg00_01` + `seg01_02`
   - high absolute load: `seg02_04` + `seg04_07`
7. Prioritize reload-cost experiments over UI or prompt changes:
   - prefix micro-window reload reduction for `seg00_01` + `seg01_02`
   - absolute-load reduction for `seg02_04` + `seg04_07`
   - resident-capacity boundary tests only with rollback-safe guards
8. Use the generated Phase 1 recovery package on an approved x86 Linux HBDK
   builder:

```bash
/mnt/nas/openclaw/reports/models/dream7b_bpu_phase1_compile_recovery_package_20260611-164453/phase1_compile_recovery_runbook.sh
```

   The package report
   `/mnt/nas/openclaw/reports/models/dream7b_bpu_phase1_compile_recovery_package_20260611-164453/phase1_compile_recovery_package_probe.json`
   has `verdict: ok_dream7b_bpu_phase1_compile_recovery_package_probe`,
   `errors: []`, confirms the Dream HF assets and S100 LLM SDK are present on
   NAS, and records that the current S100P host is `aarch64` rather than the
   required `x86_64` AVX HBDK compile host.

9. Phase 1 top-load compile and runtime result on 2026-06-11:

```text
/mnt/nas/openclaw/reports/models/dream7b_resplit_compile_20260611-104601/resplit_compile_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_phase1_segment_plan_preflight_20260611-190121/phase1_segment_plan_preflight_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_batch_telemetry_20260611-190500/resplit_batch_telemetry_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_window_cost_20260611-190552/resplit_window_cost_probe.json
```

   The Docker `linux/amd64` builder on the Windows host exposed AVX/AVX2 and
   compiled all four Phase 1 HBM shards: `2:3`, `3:4`, `4:5`, and `5:7`.
   The compile report has `verdict: ok_dream7b_resplit_compile_probe`,
   `hbm_success_count: 4`, `failed_spec_count: 0`, and the NAS manifest under
   `/mnt/nas/openclaw/models/dream7b-hbm/phase1-topload-seq16` verifies every
   generated `.hbm`.

   Runtime preflight is now clean: `phase1_ready_to_run: True`,
   `missing_segment_count: 0`, and `errors: []`. The real batch16 BPU telemetry
   is also runnable, but it is a regression rather than an optimization:
   `avg_bpu_loading: 6.706`, `max_bpu_loading: 100.0`,
   `segment_event_count: 320`, `load_to_run_ratio: 12.012308`, and
   `amortized_wall_ms_per_forward: 2024.617`. The matching window-cost report
   records `load_to_run_ratio: 12.012308`; utilization-gap still reports
   `diagnosis: hbm_reload_dominated`.

10. Do not promote `phase1-topload-adjacent`. It proves the full compile and
   deployment loop for new Dream shards, but it fails Phase 1 because average
   BPU loading drops below the current default-service baseline and load/run
   ratio worsens.
11. Next optimization should reduce reload count or HBM load cost, not just
   split more top-load windows. Valid next candidates are only those that beat
   the current same-scope baseline on average BPU loading, load/run ratio, or
   sustained wall time.
