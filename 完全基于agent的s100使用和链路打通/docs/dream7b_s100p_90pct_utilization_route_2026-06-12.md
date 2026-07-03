# Dream 7B S100P 90 Percent Utilization Route

## Current Position

The Dream 7B S100P BPU route has moved from a one-off telemetry candidate into
an isolated long-running service candidate.

Installed candidate services:

```text
dream7b-bpu-selected-pair-cross-job-candidate-50pct.service
dream7b-bpu-segment-major-load-once-candidate.service
```

Service command confirms the 50% candidate settings:

```text
queue_dir: /mnt/nas/openclaw/queues/dream7b-bpu-selected-pair-cross-job-candidate-50pct
output_dir: /mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_candidate_50pct_service
max_batch_size: 192
max_batch_size_limit: 256
default_service_replaced: false
```

Rollback remains:

```bash
sudo systemctl disable --now dream7b-bpu-selected-pair-cross-job-candidate-50pct.service
sudo systemctl disable --now dream7b-bpu-segment-major-load-once-candidate.service
```

The default service is still separate:

```text
dream7b-bpu-batch-queue.service
```

## Verified Service Results

30-minute direct candidate soak:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_50pct_candidate_soak_20260611-224510/50pct_candidate_soak_probe.json
```

Key result:

```text
elapsed_sec: 1904
iteration_count: 18
processed_request_count: 6912
failed_job_count: 0
avg_bpu_loading: 52.359
max_iteration_load_to_run_ratio: 0.784137
```

Service-level canary and backlog sweep:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_50pct_service_backlog_sweep_summary_20260612-112113/50pct_service_backlog_sweep_summary_probe.json
```

Backlog sweep:

```text
job_count=2:  processed=384,  failed=0, avg_bpu=51.363, load_to_run=0.781743
job_count=4:  processed=768,  failed=0, avg_bpu=53.086, load_to_run=0.751983
job_count=8:  processed=1536, failed=0, avg_bpu=53.416, load_to_run=0.737577
job_count=12: processed=2304, failed=0, avg_bpu=53.459, load_to_run=0.734513
```

Decision:

```text
backlog_plateau_below_70_percent
```

Interpretation: increasing queue backlog is useful for service hardening, but
it is not enough to reach `70-80%`. The last jump from 8 jobs to 12 jobs only
adds `0.043` percentage points of average BPU loading.

Continuous prefetch service run:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_50pct_candidate_service_continuous_prefetch_20260612-121446/50pct_candidate_service_continuous_prefetch_probe.json
```

Key result:

```text
verdict: ok_dream7b_bpu_50pct_candidate_service_continuous_prefetch_probe
decision: continuous_prefetch_plateau_below_70_percent
total_job_count: 24
target_pending_jobs: 12
processed_request_count: 4608
failed_job_count: 0
runner_summary_count: 2
avg_bpu_loading: 53.583
avg_bpu_delta_vs_baseline: 0.124
aggregate_load_to_run_ratio: 0.732649
load_to_run_ratio_delta_vs_baseline: -0.001864
amortized_wall_ms_per_processed_request: 262.137
```

Interpretation: true producer/consumer refill removed the obvious batch-to-batch
queue gap, but it did not materially improve sustained utilization. The
remaining blocker is inside the runner/load/resident-segment path, not the
outer queue feeder.

Segment-major load-once probe:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_load_once_forward_20260612-124719/segment_major_load_once_forward_probe.json
```

Key result:

```text
verdict: ok_dream7b_bpu_segment_major_load_once_forward_probe
decision: segment_major_load_once_meets_90pct_ratio_gate
job_count: 12
batch_count: 192
processed_forward_count: 2304
load_event_count: 10
job_major_equivalent_load_event_count: 98
load_event_reduction_ratio: 0.897959
total_load_ms: 23540.674
total_run_ms: 339117.559
wall_ms: 375051.824
load_to_run_ratio: 0.069417
amortized_wall_ms_per_forward: 162.783
peak_live_mib: 504.0
avg_bpu_loading: 87.021
max_bpu_loading: 100.0
errors: []
warnings: []
```

Interpretation: the main repo-level bottleneck was not queue refill; it was
the job-major runner repeatedly loading non-resident segments. Segment-major
load-once scheduling loads each of the 10 segments once for the whole 12x192
run instead of the job-major equivalent of 98 load events. This reaches the
ratio gate for the 90% route in an offline probe.

Segment-major service telemetry:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_candidate_service_telemetry_20260612-130705/segment_major_candidate_service_telemetry_probe.json
```

Key result:

```text
verdict: ok_dream7b_bpu_segment_major_candidate_service_telemetry_probe
decision: segment_major_service_near_90pct_candidate
service_name: dream7b-bpu-segment-major-load-once-candidate.service
processed_request_count: 2304
failed_job_count: 0
done_job_count: 12
matched_result_count: 2304
avg_bpu_loading: 86.792
max_bpu_loading: 100.0
load_to_run_ratio: 0.068115
load_event_reduction_ratio: 0.897959
peak_live_mib: 504.0
errors: []
warnings: []
```

Interpretation: the offline scheduler has now been serviceized without losing
the structural load/run improvement. The service wrapper adds only a small
telemetry-level delta versus the offline run (`87.021%` to `86.792%` average
BPU loading), while keeping `load_to_run_ratio` below `0.15`.

Segment-major pilot soak:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_candidate_soak_20260612-131931/segment_major_candidate_soak_probe.json
```

Key result:

```text
verdict: ok_dream7b_bpu_segment_major_candidate_soak_probe
decision: segment_major_service_soak_near_90pct_candidate
elapsed_sec: 756
iteration_count: 2
processed_request_count: 4608
failed_job_count: 0
avg_bpu_loading: 86.701
min_iteration_avg_bpu_loading: 86.667
max_bpu_loading: 100.0
avg_load_to_run_ratio: 0.068132
max_iteration_load_to_run_ratio: 0.068203
errors: []
```

Default promotion final acceptance:

```text
docs/dream7b_s100p_default_promotion_acceptance_2026-06-12.md
scripts/probes/dream7b_default_promotion_acceptance_probe.py
/mnt/nas/openclaw/reports/models/dream7b_default_promotion_acceptance_20260612-213745/default_promotion_acceptance_probe.json
verdict: ok_dream7b_default_promotion_acceptance_probe
decision: dream7b_24x256_segment_major_default_accepted
avg_bpu_loading: 90.097
failed_job_count: 0
elapsed_sec: 1932
iteration_count: 2
load_to_run_ratio: 0.025975
copy_count: 20
errors: []
```

Interpretation: two consecutive service iterations preserve the 86-87% band
with zero failed jobs. This is a pilot soak, not the final 30-minute or 2-hour
acceptance window.

Segment-major 30-minute soak:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_candidate_soak_20260612-133613/segment_major_candidate_soak_probe.json
```

Key result:

```text
verdict: ok_dream7b_bpu_segment_major_candidate_soak_probe
decision: segment_major_service_soak_near_90pct_candidate
elapsed_sec: 1892
iteration_count: 5
processed_request_count: 11520
failed_job_count: 0
avg_bpu_loading: 86.643
min_iteration_avg_bpu_loading: 86.533
max_bpu_loading: 100.0
avg_load_to_run_ratio: 0.068719
max_iteration_load_to_run_ratio: 0.06929
avg_amortized_wall_ms_per_processed_request: 162.947
errors: []
```

Interpretation: the serviceized scheduler is now stable across a 30-minute
window. It has exceeded the original `70-80%` stage target, while the remaining
gap to `90%` is about `3.4` percentage points.

Segment-major deep aggregation experiments:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_load_once_forward_20260612-141202/segment_major_load_once_forward_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_load_once_forward_20260612-142048/segment_major_load_once_forward_probe.json
```

Key results:

```text
16x192 offline:
processed_forward_count: 3072
avg_bpu_loading: 88.312
load_to_run_ratio: 0.05209
peak_live_mib: 672.0
errors: []

24x192 offline:
processed_forward_count: 4608
avg_bpu_loading: 89.738
load_to_run_ratio: 0.034833
peak_live_mib: 1008.0
errors: []
```

Interpretation: deeper segment-major aggregation continues to reduce fixed
reload overhead and pushes the route to within `0.3` percentage points of the
90% target offline. The memory cost remains acceptable on the current board.

Segment-major 24-job service telemetry:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_candidate_service_telemetry_20260612-143609/segment_major_candidate_service_telemetry_probe.json
```

Key result:

```text
verdict: ok_dream7b_bpu_segment_major_candidate_service_telemetry_probe
decision: segment_major_service_near_90pct_candidate
service_name: dream7b-bpu-segment-major-load-once-candidate-24job.service
job_count: 24
request_count: 192
processed_request_count: 4608
failed_job_count: 0
done_job_count: 24
matched_result_count: 4608
avg_bpu_loading: 89.535
max_bpu_loading: 100.0
load_to_run_ratio: 0.03538
load_event_reduction_ratio: 0.948454
amortized_wall_ms_per_processed_request: 158.212
peak_live_mib: 1008.0
errors: []
warnings: []
```

Segment-major 24-job pilot soak:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_candidate_soak_20260612-144904/segment_major_candidate_soak_probe.json
```

Key result:

```text
verdict: ok_dream7b_bpu_segment_major_candidate_soak_probe
decision: segment_major_service_soak_near_90pct_candidate
elapsed_sec: 1461
iteration_count: 2
job_count_per_iteration: 24
processed_request_count: 9216
failed_job_count: 0
avg_bpu_loading: 89.471
min_iteration_avg_bpu_loading: 89.352
max_bpu_loading: 100.0
avg_load_to_run_ratio: 0.034434
max_iteration_load_to_run_ratio: 0.034787
avg_amortized_wall_ms_per_processed_request: 157.947
errors: []
```

Interpretation: the 24-job candidate is now the strongest self-managed route.
It does not yet prove `>=90%` average BPU loading, but it is within about `0.5`
percentage points in service telemetry and remains stable across two
consecutive service iterations.

Segment-major 24-job batch-size sweep:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_candidate_service_telemetry_20260612-155626/segment_major_candidate_service_telemetry_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_candidate_service_telemetry_20260612-161133/segment_major_candidate_service_telemetry_probe.json
```

Key results:

```text
24x224 service telemetry:
service_name: dream7b-bpu-segment-major-load-once-candidate-24job-b224.service
processed_request_count: 5376
failed_job_count: 0
avg_bpu_loading: 89.9
load_to_run_ratio: 0.029034
amortized_wall_ms_per_processed_request: 157.008
peak_live_mib: 1176.0
errors: []

24x256 service telemetry:
service_name: dream7b-bpu-segment-major-load-once-candidate-24job-b256.service
processed_request_count: 6144
failed_job_count: 0
decision: segment_major_service_meets_90pct_goal
avg_bpu_loading: 90.275
load_to_run_ratio: 0.02602
amortized_wall_ms_per_processed_request: 156.603
peak_live_mib: 1344.0
errors: []
```

Segment-major 24x256 pilot soak:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_candidate_soak_20260612-162823/segment_major_candidate_soak_probe.json
```

Key result:

```text
verdict: ok_dream7b_bpu_segment_major_candidate_soak_probe
decision: segment_major_service_soak_meets_90pct_goal
elapsed_sec: 1930
iteration_count: 2
job_count_per_iteration: 24
request_count_per_job: 256
processed_request_count: 12288
failed_job_count: 0
avg_bpu_loading: 90.327
min_iteration_avg_bpu_loading: 90.311
max_bpu_loading: 100.0
avg_load_to_run_ratio: 0.025995
max_iteration_load_to_run_ratio: 0.026111
avg_amortized_wall_ms_per_processed_request: 156.628
errors: []
```

Interpretation: the self-managed repo route now has a rollback-safe candidate
that crosses the `90%` average BPU loading threshold in service telemetry and
in a two-iteration pilot soak. This satisfies the utilization target for the
current project goal. The remaining work is production hardening, not proving
that `70-80%` is reachable.

OpenClaw local Dream route validation:

```text
scripts/probes/dream7b_openclaw_candidate_validation_probe.py
/mnt/nas/openclaw/reports/models/dream7b_openclaw_candidate_validation_20260612-172108/openclaw_candidate_validation_probe.json
```

Key result:

```text
verdict: ok_dream7b_openclaw_candidate_validation_probe
primary_model: dream7b-local/Dream7B-S100P-local
dream_provider_base_url: http://127.0.0.1:18888/v1
minimax_fallback_present: true
recent_trace_has_openclaw_heartbeat: true
recent_trace_has_sort_trigger: true
default_service_replaced: false
errors: []
```

Interpretation: OpenClaw is configured to use the local Dream 7B gateway as
the primary model while preserving MiniMax as fallback. The validation also
triggered the allowlisted Personal/Movies dry-run sorter and wrote:

```text
/mnt/nas/openclaw/reports/personal-data-sort-dry-run/personal_data_sort_20260612-172108/personal_data_sort.md
```

Default-candidate handoff:

```text
docs/dream7b_s100p_90pct_default_candidate_handoff_2026-06-12.md
scripts/probes/dream7b_90pct_candidate_evidence_package_probe.py
primary_candidate: dream7b-bpu-segment-major-load-once-candidate-24job-b256.service
fallback_candidate: dream7b-bpu-segment-major-load-once-candidate-24job.service
current_default_service: dream7b-bpu-batch-queue.service
default_service_replaced: false
rollback_primary: sudo systemctl disable --now dream7b-bpu-segment-major-load-once-candidate-24job-b256.service
```

Two-hour 24x256 promotion soak:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_candidate_soak_20260612-171402/segment_major_candidate_soak_probe.json
verdict: ok_dream7b_bpu_segment_major_candidate_soak_probe
decision: segment_major_service_soak_meets_90pct_goal
elapsed_sec: 7723
iteration_count: 8
processed_request_count: 49152
failed_job_count: 0
avg_bpu_loading: 90.264
min_iteration_avg_bpu_loading: 90.155
avg_load_to_run_ratio: 0.026177
max_iteration_load_to_run_ratio: 0.027452
default_service_replaced: False
rollback_status: rollback_safe_candidate_only
errors: []
```

Final teacher/vendor evidence package:

```text
/mnt/nas/openclaw/reports/models/dream7b_90pct_candidate_evidence_package_final/evidence_package_manifest.json
verdict: ok_dream7b_90pct_candidate_evidence_package_probe
service_24x256_reaches_90: True
soak_30min_reaches_90: True
soak_2h_reaches_90: True
services_active: True
openclaw_local_dream_ok: True
docs_consistency_ok: True
errors: []
```

## 90 Percent Requirement

The current best measured service load/run ratio is:

```text
0.068115
```

The 90% utilization route requires the ratio to approach:

```text
<= 0.15
```

That means the remaining work is not just larger batching. The load/reload and
host orchestration overhead must be structurally reduced.

## Route

### Stage 1: Solidify 50% Service Candidate

Status: done.

Evidence:

```text
dream7b-bpu-selected-pair-cross-job-candidate-50pct.service
50pct service backlog sweep summary: ok
default_service_replaced: false
```

### Stage 2: Continuous Queue And Producer/Consumer Prefetch

Goal:

```text
avg_bpu_loading: 55-65%
load_to_run_ratio: <= 0.6
```

Status: tested, not enough.

The continuous prefetch probe keeps 12 jobs pending while 12 jobs are already
processing. It processed `4608` requests with zero failed jobs, but average BPU
loading only moved from `53.459%` to `53.583%`, and load/run only moved from
`0.734513` to `0.732649`.

Decision: do not spend the next major effort on outer queue refill. Keep the
probe as a regression guard, but move the utilization work to Stage 3.

### Stage 3: Resident Segment / Load-Once Work

Goal:

```text
avg_bpu_loading: 65-75%
load_to_run_ratio: <= 0.35
```

Status: serviceized short-window telemetry passed.

The selected-pair resident route reduced repeated loading compared with the
early segmented path, but still left `load_to_run_ratio` around `0.73`. The
segment-major/load-once probe changes the scheduling order from `job -> segment`
to `segment -> all jobs`, keeping intermediate states in host memory and
loading each segment once per run.

Verified result:

```text
offline_avg_bpu_loading: 87.021
offline_load_to_run_ratio: 0.069417
service_avg_bpu_loading: 86.792
service_load_to_run_ratio: 0.068115
pilot_soak_avg_bpu_loading: 86.701
pilot_soak_avg_load_to_run_ratio: 0.068132
30min_soak_avg_bpu_loading: 86.643
30min_soak_avg_load_to_run_ratio: 0.068719
24job_service_avg_bpu_loading: 89.535
24job_service_load_to_run_ratio: 0.03538
24job_pilot_soak_avg_bpu_loading: 89.471
24job_pilot_soak_avg_load_to_run_ratio: 0.034434
24x256_service_avg_bpu_loading: 90.275
24x256_service_load_to_run_ratio: 0.02602
24x256_pilot_soak_avg_bpu_loading: 90.327
24x256_pilot_soak_avg_load_to_run_ratio: 0.025995
24x256_2h_soak_elapsed_sec: 7723
24x256_2h_soak_iteration_count: 8
24x256_2h_soak_avg_bpu_loading: 90.264
24x256_2h_soak_min_iteration_avg_bpu_loading: 90.155
24x256_2h_soak_avg_load_to_run_ratio: 0.026177
24x256_2h_soak_max_iteration_load_to_run_ratio: 0.027452
peak_live_mib: 504.0
24job_peak_live_mib: 1008.0
24x256_peak_live_mib: 1344.0
```

Deployment boundary:

- preserve the `24x256` route as a passed default candidate until operator review;
- keep `24x192` as the lower-memory near-90 fallback;
- if production deployment must exceed the repo-managed service wrapper, ask the vendor
  about making this scheduling pattern native in Dream adapter / HBM layout /
  runtime memory-pool planning.

### Stage 4: Re-Split / Recompile

Goal:

```text
avg_bpu_loading: 75-85%
load_to_run_ratio: <= 0.25
```

Status: not the immediate next step unless soak shows a stable 85-87% ceiling.

Prior Phase 1 top-load split proved compile-to-runtime feasibility but was a
runtime regression. Re-splitting must now be driven by the service-level
segment-major bottleneck, not the older selected-pair service.

Next experiments:

- use service-run summaries to identify the highest remaining load windows;
- generate a new split plan that targets those windows, not only static HBM
  size;
- compile only the minimum changed segments first;
- compare against the 12x192 service baseline, not the old 16-batch baseline.

### Stage 5: Vendor/Toolchain Support For 90%

Goal:

```text
avg_bpu_loading: 85-90%+
load_to_run_ratio: <= 0.15
```

Current evidence suggests this is unlikely to be reached by queue depth alone.
The segment-major/load-once service shows repo-level scheduling can cross the
ratio gate, but official toolchain work is still needed for a production-grade
route and for reliably crossing 90% average BPU loading:

- official Dream adapter for `oellm_build`;
- HBM layout that natively supports load-once or resident scheduling;
- runtime memory pool and common-buffer planning for long-running LLM service;
- BPU-side fused attention/MLP execution for Dream architecture;
- official guidance on maximum safe resident segment/window topology.

## Current Next Decision

The 90% service-candidate target is now met, and the route has passed a
rollback-verified default-service promotion. Keep the wording tied to sustained
average BPU and load/run evidence, not to instantaneous `max_bpu_loading`.

The project can now claim:

```text
Dream 7B has rollback-safe S100P BPU segment-major/load-once service
candidates. The 12-job candidate is stable for 30 minutes at 86.643% average
BPU with zero failed jobs. The 24x192 candidate reaches 89.535% average BPU in
service telemetry and 89.471% average BPU across a 2-iteration pilot soak. The
24x256 candidate reaches 90.275% average BPU in service telemetry, 90.327%
average BPU across a 2-iteration pilot soak, and 90.264% average BPU across a
2-hour soak, all with zero failed jobs. The same 24x256 route was promoted into
dream7b-bpu-batch-queue.service through a rollback-verified default-service
promotion probe.
```

The current technical target is:

```text
complete post-promotion soak on the default queue, keep one-command rollback
available, keep health/watchdog evidence running, and prepare a vendor-facing
note asking how to make the load-once scheduling pattern native in the official
Dream/OELLM toolchain.
```

Continuous queue refill has already been tested and did not materially move the
ratio. Segment-major/load-once execution has now moved the ratio below `0.15`
in service form and below `0.03` in the 24x256 route. The remaining proof is
post-promotion default-service durability and operator demonstration, not another
outer queue-depth sweep.

Default-service promotion:

```text
scripts/probes/dream7b_bpu_segment_major_default_promotion_probe.sh
/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_default_promotion_20260612-210011/segment_major_default_promotion_probe.json
verdict: ok_dream7b_bpu_segment_major_default_promotion_probe
service_name: dream7b-bpu-batch-queue.service
queue_dir: /mnt/nas/openclaw/queues/dream7b-bpu
runtime_dir: /mnt/nas/openclaw/runtimes/dream7b-bpu-segment-major-default
default_service_replaced: True
rollback_verified: True
smoke_request_id: segment-major-default-smoke-20260612-210011
--max-batch-size 256
errors: []
```
