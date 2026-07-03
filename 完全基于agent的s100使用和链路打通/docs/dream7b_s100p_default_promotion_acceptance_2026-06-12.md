# Dream 7B S100P Default Promotion Acceptance

## Conclusion

Document path:

```text
docs/dream7b_s100p_default_promotion_acceptance_2026-06-12.md
```

Dream 7B is now accepted as the default S100P local route through the
segment-major/load-once 24-job, batch-256 service path. This conclusion is based
on default-service promotion, rollback verification, post-promotion sustained
telemetry, OpenClaw local Dream routing, and a non-destructive NAS copy-sort
demo.

## Final Acceptance Report

```text
scripts/probes/dream7b_default_promotion_acceptance_probe.py
/mnt/nas/openclaw/reports/models/dream7b_default_promotion_acceptance_20260612-213745/default_promotion_acceptance_probe.json
verdict: ok_dream7b_default_promotion_acceptance_probe
decision: dream7b_24x256_segment_major_default_accepted
active: active
enabled: enabled
avg_bpu_loading: 90.097
failed_job_count: 0
elapsed_sec: 1932
iteration_count: 2
load_to_run_ratio: 0.025975
copy_count: 20
errors: []
```

All final checks passed:

```text
promotion_ok: true
default_service_replaced: true
rollback_verified: true
default_service_active: true
default_service_enabled: true
execstart_segment_major_24x256: true
post_promotion_soak_ok: true
post_promotion_soak_30min: true
post_promotion_soak_two_iterations: true
post_promotion_avg_bpu_ge_90: true
post_promotion_failed_jobs_zero: true
openclaw_copy_sort_ok: true
openclaw_copy_sort_20_files: true
openclaw_copy_sort_non_destructive: true
health_snapshot_present: true
health_segment_major_default: true
```

## Default Service

```text
service_name: dream7b-bpu-batch-queue.service
queue_dir: /mnt/nas/openclaw/queues/dream7b-bpu
output_dir: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd
runtime_dir: /mnt/nas/openclaw/runtimes/dream7b-bpu-segment-major-default
runner: dream7b_bpu_segment_major_load_once_queue_runner.py
max_job_count: 24
max_batch_size: 256
```

Promotion report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_default_promotion_20260612-210011/segment_major_default_promotion_probe.json
verdict: ok_dream7b_bpu_segment_major_default_promotion_probe
default_service_replaced: True
rollback_verified: True
smoke_request_id: segment-major-default-smoke-20260612-210011
errors: []
```

## OpenClaw Demo

OpenClaw local routing uses:

```text
model: Dream7B-S100P-local
provider_base_url: http://127.0.0.1:18888/v1
tool_id: personal_data_sort_probe
```

NAS copy-sort report:

```text
/mnt/nas/openclaw/reports/personal-data-sort/personal_data_sort_20260612-211115/personal_data_sort.md
verdict: ok_personal_data_sort_probe
file_count: 20
copy_count: 20
dry_run: False
upload_performed: True
delete_or_move_performed: False
target_root: Personal/Sorted/Movies
```

The demo remains non-destructive: originals stay in `Personal/Movies`, while
organized copies are written under `Personal/Sorted/Movies`.

## Operations

Installed commands:

```bash
dream7b-default-status
dream7b-default-rollback
```

Installed service health:

```text
dream7b-default-health.timer
/mnt/nas/openclaw/reports/models/dream7b_default_health/latest_status.json
/etc/logrotate.d/dream7b-default-health
```
