# Dream 7B S100P 90 Percent Vendor Question

## Short Summary

We have a non-official segmented Dream 7B BPU route running on S100P and an
isolated long-running candidate service. The current service-level job-major
runner is stable around `53.459%` average BPU loading with zero failed jobs.
Increasing queue backlog from `2x192` to `12x192` only improves average BPU by
about `2.096` percentage points, and continuous prefetch only reaches
`53.583%`.

We then tested a repo-level segment-major/load-once scheduler. It changes the
execution order from `job -> segment` to `segment -> all jobs`, so each segment
is loaded once for a 12x192 run. This offline probe reaches `87.021%` average
BPU loading and `load_to_run_ratio: 0.069417`.

We need official toolchain guidance on how to turn this scheduling pattern into
a production Dream adapter / HBM layout / runtime memory-pool route.

## Current Hardware / Runtime

```text
Board: S100P
Model: Dream 7B
Route: non-official segmented S100 HBM route
Service: dream7b-bpu-selected-pair-cross-job-candidate-50pct.service
Default service replaced: false
Candidate max_batch_size: 192
Candidate max_batch_size_limit: 256
Selected resident pair: [1, 8]
Selected segments: seg02_04, seg24_26
New offline scheduler: segment-major/load-once, not serviceized yet
```

## Evidence

30-minute candidate soak:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_50pct_candidate_soak_20260611-224510/50pct_candidate_soak_probe.json
elapsed_sec: 1904
iteration_count: 18
processed_request_count: 6912
failed_job_count: 0
avg_bpu_loading: 52.359
max_iteration_load_to_run_ratio: 0.784137
```

Service backlog sweep:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_50pct_service_backlog_sweep_summary_20260612-112113/50pct_service_backlog_sweep_summary_probe.json
```

Results:

```text
job_count=2:  processed=384,  failed=0, avg_bpu=51.363, load_to_run=0.781743
job_count=4:  processed=768,  failed=0, avg_bpu=53.086, load_to_run=0.751983
job_count=8:  processed=1536, failed=0, avg_bpu=53.416, load_to_run=0.737577
job_count=12: processed=2304, failed=0, avg_bpu=53.459, load_to_run=0.734513
```

Conclusion:

```text
decision: backlog_plateau_below_70_percent
```

Continuous prefetch:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_50pct_candidate_service_continuous_prefetch_20260612-121446/50pct_candidate_service_continuous_prefetch_probe.json
processed_request_count: 4608
failed_job_count: 0
avg_bpu_loading: 53.583
aggregate_load_to_run_ratio: 0.732649
decision: continuous_prefetch_plateau_below_70_percent
```

Segment-major/load-once offline probe:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_load_once_forward_20260612-124719/segment_major_load_once_forward_probe.json
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
avg_bpu_loading: 87.021
max_bpu_loading: 100.0
peak_live_mib: 504.0
errors: []
warnings: []
```

## What We Need Help With

### 1. Dream Adapter / Official Build Path

Dream is not registered in the current official `oellm_build` model registry.
Is there an internal or recommended adapter route for a custom HuggingFace
DreamModel-like architecture?

If yes, what is the minimum adapter contract?

- config parser fields;
- supported attention / RoPE / MLP patterns;
- quantization calibration requirements;
- HBM layout constraints;
- runtime config fields.

### 2. HBM Layout / Segment Residency

The repo-level selected-pair resident route reduces early segmented reload
overhead, but service-level job-major load/run still plateaus around `0.73`.
The segment-major/load-once probe reduces that ratio to `0.069417` by loading
10 segments once instead of 98 job-major load events.

Which level should be optimized next?

- official HBM layout for segment-major/load-once execution;
- runtime support for keeping model handles or common buffers reusable while
  streaming all jobs through one segment;
- whether intermediate hidden states should stay in host memory, common buffer,
  or a runtime-managed pool;
- whether the final logits/top-k can be streamed without holding all final
  tensors in memory;
- recommended split boundaries if segment-major execution is the intended
  production route.

### 3. Runtime Memory Pool / Long-Running Service

For a long-running LLM service on S100P, is there an official way to preallocate
or reuse runtime buffers across jobs so repeated `load` overhead is reduced?

We need to know whether the current ratio is caused by:

- HBM file load;
- model handle creation;
- common-buffer allocation;
- segment activation buffers;
- host-side scheduling;
- unavoidable runtime synchronization.

The offline segment-major probe used about `504 MiB` peak host-side live
intermediate state for 12x192. We need guidance on the safe production memory
placement for this buffer pattern.

### 4. 90 Percent Target Feasibility

Given the current service-level job-major numbers:

```text
avg_bpu_loading: 53.459
load_to_run_ratio: 0.734513
failed_job_count: 0
```

and the current offline segment-major/load-once numbers:

```text
avg_bpu_loading: 87.021
load_to_run_ratio: 0.069417
failed_forward_count: 0
```

Is this segment-major/load-once pattern the right production direction for a 7B
LLM on S100P?

If yes, what target configuration should we test first?

- serviceized segment-major queue runner;
- official Dream adapter with segment-major HBM layout;
- runtime memory pool / prealloc configuration;
- a smaller/larger segment split to reduce host intermediate memory.

## Minimal Reproduction Command

Install the isolated service candidate:

```bash
cd /mnt/nas/openclaw/tmp/cross_job_queue_repo
sudo env \
  DREAM7B_BPU_CROSS_JOB_CANDIDATE_REPO_DIR=/mnt/nas/openclaw/tmp/cross_job_queue_repo \
  DREAM7B_BPU_CROSS_JOB_CANDIDATE_SERVICE_NAME=dream7b-bpu-selected-pair-cross-job-candidate-50pct.service \
  DREAM7B_BPU_CROSS_JOB_CANDIDATE_MAX_BATCH_SIZE=192 \
  DREAM7B_BPU_CROSS_JOB_CANDIDATE_MAX_BATCH_SIZE_LIMIT=256 \
  DREAM7B_BPU_CROSS_JOB_CANDIDATE_SINGLE_JOB_FLUSH_TIMEOUT_SEC=30 \
  bash scripts/install_dream7b_bpu_selected_pair_cross_job_candidate_service.sh install \
    /mnt/nas/openclaw/queues/dream7b-bpu-selected-pair-cross-job-candidate-50pct \
    /mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_candidate_50pct_service
```

Run the maximum backlog canary:

```bash
cd /mnt/nas/openclaw/tmp/cross_job_queue_repo
DREAM7B_BPU_50PCT_SERVICE_JOB_COUNT=12 \
DREAM7B_BPU_50PCT_SERVICE_REQUEST_COUNT=192 \
bash scripts/probes/dream7b_bpu_50pct_candidate_service_telemetry_probe.sh \
  /mnt/nas/openclaw/reports/models \
  /mnt/nas/openclaw/queues/dream7b-bpu-selected-pair-cross-job-candidate-50pct \
  /mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_candidate_50pct_service
```

Run the segment-major/load-once offline probe:

```bash
cd /mnt/nas/openclaw/tmp/cross_job_queue_repo
sudo env \
  DREAM7B_BPU_SEGMENT_MAJOR_JOB_COUNT=12 \
  DREAM7B_BPU_SEGMENT_MAJOR_BATCH_COUNT=192 \
  DREAM7B_BPU_SEGMENT_MAJOR_TIMEOUT_SEC=1200 \
  DREAM7B_BPU_SEGMENT_MAJOR_MONITOR_SAMPLE_COUNT=15000 \
  bash scripts/probes/dream7b_bpu_segment_major_load_once_forward_probe.sh \
    /mnt/nas/openclaw/reports/models
```

Rollback:

```bash
sudo systemctl disable --now dream7b-bpu-selected-pair-cross-job-candidate-50pct.service
```
