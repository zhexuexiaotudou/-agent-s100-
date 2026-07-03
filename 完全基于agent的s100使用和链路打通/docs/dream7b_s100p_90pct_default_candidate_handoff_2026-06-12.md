# Dream 7B S100P 90 Percent Default Candidate Handoff

## Purpose

This handoff defines the current Dream 7B S100P default-candidate boundary.
The candidate has passed the 30-minute and 2-hour soak gates, but it is still
kept isolated from the existing default service until the operator explicitly
promotes it.

Document path:

```text
docs/dream7b_s100p_90pct_default_candidate_handoff_2026-06-12.md
```

## Candidate

Primary candidate:

```text
dream7b-bpu-segment-major-load-once-candidate-24job-b256.service
queue_dir: /mnt/nas/openclaw/queues/dream7b-bpu-segment-major-load-once-candidate-24job-b256
output_dir: /mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_load_once_candidate_24job_b256_service
max_job_count: 24
max_batch_size: 256
default_service_replaced: false
```

Low-memory fallback:

```text
dream7b-bpu-segment-major-load-once-candidate-24job.service
queue_dir: /mnt/nas/openclaw/queues/dream7b-bpu-segment-major-load-once-candidate-24job
output_dir: /mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_load_once_candidate_24job_service
max_job_count: 24
max_batch_size: 192
default_service_replaced: false
```

Current default service remains separate:

```text
dream7b-bpu-batch-queue.service
```

## Verified Evidence

30-minute 24x256 soak:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_candidate_soak_20260612-162823/segment_major_candidate_soak_probe.json
verdict: ok_dream7b_bpu_segment_major_candidate_soak_probe
decision: segment_major_service_soak_meets_90pct_goal
elapsed_sec: 1930
iteration_count: 2
processed_request_count: 12288
failed_job_count: 0
avg_bpu_loading: 90.327
min_iteration_avg_bpu_loading: 90.311
avg_load_to_run_ratio: 0.025995
```

OpenClaw local Dream route validation:

```text
scripts/probes/dream7b_openclaw_candidate_validation_probe.py
/mnt/nas/openclaw/reports/models/dream7b_openclaw_candidate_validation_20260612-172108/openclaw_candidate_validation_probe.json
verdict: ok_dream7b_openclaw_candidate_validation_probe
primary_model: dream7b-local/Dream7B-S100P-local
dream_provider_base_url: http://127.0.0.1:18888/v1
minimax_fallback_present: true
recent_trace_has_openclaw_heartbeat: true
recent_trace_has_sort_trigger: true
default_service_replaced: false
errors: []
```

The OpenClaw validation ran the fixed allowlisted Personal/Movies dry-run sorter
through the local Dream gateway and wrote:

```text
/mnt/nas/openclaw/reports/personal-data-sort-dry-run/personal_data_sort_20260612-172108/personal_data_sort.md
```

Final evidence package probe:

```text
scripts/probes/dream7b_90pct_candidate_evidence_package_probe.py
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

Two-hour 24x256 soak:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_candidate_soak_20260612-171402/segment_major_candidate_soak_probe.json
verdict: ok_dream7b_bpu_segment_major_candidate_soak_probe
decision: segment_major_service_soak_meets_90pct_goal
target_duration_sec: 7200
service_name: dream7b-bpu-segment-major-load-once-candidate-24job-b256.service
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

## Promotion Boundary

The promotion gate has been executed. The current default service is now the
segment-major/load-once 24x256 route on the default Dream queue, with the
previous unit captured in the promotion report for rollback.

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
avg_bpu_loading: 90.264
min_iteration_avg_bpu_loading: 90.155
failed_job_count: 0
avg_load_to_run_ratio: 0.026177
services_active: True
project_docs_consistency_probe errors: []
```

## Rollback

One-command rollback after installing ops tools:

```bash
dream7b-default-rollback
```

Disable the primary 24x256 candidate:

```bash
sudo systemctl disable --now dream7b-bpu-segment-major-load-once-candidate-24job-b256.service
```

Fall back to the lower-memory 24x192 candidate:

```bash
sudo systemctl enable --now dream7b-bpu-segment-major-load-once-candidate-24job.service
```

Return to the existing default Dream queue service:

```bash
sudo systemctl restart dream7b-bpu-batch-queue.service
```

The operator status command is:

```bash
dream7b-default-status
```

## Final Default Acceptance

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

## Teacher Or Vendor Question

The self-managed repo path has proven that segment-major/load-once scheduling
can reach the 90% average BPU band. The remaining vendor-facing question is not
whether Dream can run, but whether the official SDK can make this scheduling
native in the Dream adapter, HBM layout, or runtime memory pool so that the same
utilization does not depend on a repo-managed service wrapper.
