# Dream 7B S100P Long-Running Candidate

## Goal

Turn the current Dream 7B S100P selected-pair `2x192` large-batch route into a
rollback-safe long-running service candidate without replacing the default
service.

Acceptance targets:

- average BPU loading stays at or above the `45-50%` band;
- failed job count is `0`;
- load/run ratio stays below `1.5`;
- default service is not replaced;
- manual rollback remains possible by not installing or by stopping the
  isolated candidate service;
- the OpenClaw recording can show Dream 7B identity, runtime logs, NAS
  `Personal/Movies`, and a dry-run organization plan.

## Current Best Evidence

Best single candidate telemetry:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_queue_telemetry_20260611-192528/cross_job_queue_telemetry_probe.json
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
```

The same run was accepted by the 50% candidate gate:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_50pct_candidate_acceptance_20260611-193007/50pct_candidate_acceptance_probe.json
```

Important boundary:

```text
rollback_status: rollback_safe_candidate_only
default_service_replaced: False
```

## Service Candidate Plan

The 50% route is packaged as a separate candidate service plan, not as a
replacement for `dream7b-bpu-batch-queue.service`.

Plan command:

```bash
cd /mnt/nas/openclaw/tmp/cross_job_queue_repo
DREAM7B_BPU_CROSS_JOB_CANDIDATE_REPO_DIR=/mnt/nas/openclaw/tmp/cross_job_queue_repo \
DREAM7B_BPU_CROSS_JOB_CANDIDATE_SERVICE_NAME=dream7b-bpu-selected-pair-cross-job-candidate-50pct.service \
DREAM7B_BPU_CROSS_JOB_CANDIDATE_MAX_BATCH_SIZE=192 \
DREAM7B_BPU_CROSS_JOB_CANDIDATE_MAX_BATCH_SIZE_LIMIT=256 \
DREAM7B_BPU_CROSS_JOB_CANDIDATE_SINGLE_JOB_FLUSH_TIMEOUT_SEC=30 \
bash scripts/install_dream7b_bpu_selected_pair_cross_job_candidate_service.sh plan \
  /mnt/nas/openclaw/queues/dream7b-bpu-selected-pair-cross-job-candidate-50pct \
  /mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_candidate_50pct_service
```

Plan result:

```text
service: dream7b-bpu-selected-pair-cross-job-candidate-50pct.service
queue_dir: /mnt/nas/openclaw/queues/dream7b-bpu-selected-pair-cross-job-candidate-50pct
output_dir: /mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_candidate_50pct_service
repo_dir: /mnt/nas/openclaw/tmp/cross_job_queue_repo
max_batch_size: 192
max_batch_size_limit: 256
default_service_replaced: false
default_service_name: dream7b-bpu-batch-queue.service
```

This plan is not installed yet. It is ready for operator-approved installation
after the soak test passes.

## Long-Running Soak

The 30-minute soak probe has been added:

```text
scripts/probes/dream7b_bpu_50pct_candidate_soak_probe.sh
```

It repeatedly runs the same `2x192` telemetry route and writes aggregate
evidence under:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_50pct_candidate_soak_<stamp>/
```

Completed S100P run:

```text
launcher_log: /mnt/nas/openclaw/reports/models/dream7b_50pct_soak_launcher_20260611-224510.log
run_dir: /mnt/nas/openclaw/reports/models/dream7b_bpu_50pct_candidate_soak_20260611-224510
```

Final files:

```text
50pct_candidate_soak_probe.json
50pct_candidate_soak_probe.md
base_reports.jsonl
iterations/
```

Final soak result:

```text
verdict: ok_dream7b_bpu_50pct_candidate_soak_probe
elapsed_sec: 1904
iteration_count: 18
processed_request_count: 6912
failed_job_count: 0
avg_bpu_loading: 52.359
min_iteration_avg_bpu_loading: 52.167
avg_load_to_run_ratio: 0.774893
max_iteration_load_to_run_ratio: 0.784137
rollback_status: rollback_safe_candidate_only
default_service_replaced: False
```

The final long-running acceptance wrapper also passed:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_long_running_candidate_acceptance_20260611-232538/long_running_candidate_acceptance_probe.md
```

Key fields:

```text
verdict: ok_dream7b_bpu_long_running_candidate_acceptance_probe
soak_elapsed_sec: 1904
soak_iteration_count: 18
soak_processed_request_count: 6912
soak_failed_job_count: 0
soak_avg_bpu_loading: 52.359
soak_max_iteration_load_to_run_ratio: 0.784137
dry_run_file_count: 20
dry_run_upload_performed: False
rollback_status: rollback_safe_candidate_only
default_service_replaced: False
errors: none
warnings: none
```

## OpenClaw NAS Dry-Run Demo

The Personal NAS organization workflow now has a dry-run allowlisted entry:

```text
personal_data_sort_dry_run_probe
scripts/probes/personal_data_sort_dry_run_probe.sh
```

Verified dry-run report through the Dream 7B local gateway:

```text
/mnt/nas/openclaw/reports/personal-data-sort-dry-run/personal_data_sort_20260611-232515/personal_data_sort.md
```

Key fields:

```text
share_name: Personal
source_root: Movies
sorted_root: Sorted
file_count: 20
copy_count: 20
dry_run: True
upload_performed: False
delete_or_move_performed: False
overwrite_source_performed: False
```

This is the recommended recording path: first show the Dream 7B local provider,
then ask OpenClaw to preview organization of `Personal/Movies`, then zoom in on
the dry-run report showing no upload or destructive action.

## Current Boundary

What is proved:

- Dream 7B can run on the S100P BPU segmented path.
- The best candidate route reached `52.328%` average BPU loading on `384`
  processed requests with zero failed jobs.
- The 30-minute candidate soak reached `52.359%` average BPU loading over
  `6912` processed requests with zero failed jobs.
- The `2x192` route is now packaged into an isolated service candidate plan.
- OpenClaw has a safe NAS dry-run demo entry for `Personal/Movies`.

What is still pending:

- the 50% service candidate is planned but not installed;
- the default service remains unchanged;
- the large-batch candidate is throughput-oriented and still needs an explicit
  demo/interactive latency policy before being promoted for general use.
