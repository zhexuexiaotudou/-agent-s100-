# Dream 7B S100P Default Service Ops Runbook

## Current Target

Document path:

```text
docs/dream7b_s100p_default_service_ops_runbook_2026-06-12.md
```

The default Dream service should run the segment-major/load-once 24-job,
batch-256 route through `dream7b-bpu-batch-queue.service`:

- service: `dream7b-bpu-batch-queue.service`
- queue: `/mnt/nas/openclaw/queues/dream7b-bpu`
- output: `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd`
- runtime: `/mnt/nas/openclaw/runtimes/dream7b-bpu-segment-major-default`
- runner: `dream7b_bpu_segment_major_load_once_queue_runner.py`
- expected promotion probe: `ok_dream7b_bpu_segment_major_default_promotion_probe`

This is the route that turns the 90 percent utilization candidate into the
default queue path. The older default unit is kept in the promotion report and
can be restored without touching model artifacts.

## Operator Commands

Install the long-running tools from the repo on S100P:

```bash
cd /mnt/nas/openclaw/tmp/cross_job_queue_repo
sudo DREAM7B_DEFAULT_OPS_REPO_DIR=/mnt/nas/openclaw/tmp/cross_job_queue_repo \
  bash scripts/install_dream7b_default_ops_tools.sh
```

Check the live default service:

```bash
dream7b-default-status
dream7b-default-status --json
```

Roll back to the unit captured before the latest segment-major default
promotion:

```bash
dream7b-default-rollback
```

The health timer writes:

- `dream7b-default-health.timer`
- `/mnt/nas/openclaw/reports/models/dream7b_default_health/latest_status.json`
- `/mnt/nas/openclaw/reports/models/dream7b_default_health/health.log`

Log rotation is installed at `/etc/logrotate.d/dream7b-default-health`.

## Acceptance Rule

Do not claim the default route is complete only because the service is active.
The default route is accepted only when all of the following are true:

- the promotion probe reports `default_service_replaced: true`
- the promotion probe reports `rollback_verified: true`
- post-promotion soak on `/mnt/nas/openclaw/queues/dream7b-bpu` reports
  `avg_bpu_loading >= 90`
- post-promotion soak reports `failed_job_count: 0`
- OpenClaw still resolves to `dream7b-local/Dream7B-S100P-local`
- NAS demo sorting is confirmed on the Personal/Movies demo folder

If any of these fail, run `dream7b-default-rollback` and keep the 24x256 route
as a candidate until the failing gate is corrected.
