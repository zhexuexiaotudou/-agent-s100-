# Dream7B Deployment Baseline

Date: 2026-06-19

This document records the current production baseline and the current
true-batch research boundary. It is not a promotion plan and does not replace
the default service.

## Current Default Service

- Service: `dream7b-bpu-batch-queue.service`
- Status from read-only audit: loaded, enabled, active/running
- Production API: `http://127.0.0.1:18888/v1`
- Listening port: `127.0.0.1:18888`
- Model id returned by `/v1/models`: `Dream7B-S100P-local`
- OpenClaw model alias: `dream7b-local/Dream7B-S100P-local`
- Runtime dir: `/mnt/nas/openclaw/runtimes/dream7b-bpu-segment-major-default`
- Queue dir: `/mnt/nas/openclaw/queues/dream7b-bpu`
- Report dir: `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd`

## Queue Baseline Route

The current production route is:

```text
raw-final segment-major load-once 24x256 queue batch top_k=1
```

The running systemd command uses:

- `--min-job-count 24`
- `--max-job-count 24`
- `--max-batch-size 256`
- `--top-k 1`
- `--poll-interval-sec 0.05`
- `--single-job-flush-timeout-sec 5`
- `DREAM7B_BPU_SEGMENT_MAJOR_RAW_FINAL=1`
- `DREAM7B_BPU_SEGMENT_MAJOR_SKIP_EXPLICIT_GC=0`

This route is the current production default. It must remain the fallback and
must not be replaced by true-batch artifacts until a separate promotion gate is
met.

## Baseline Telemetry

Known promoted-default telemetry:

- `93.024` full-window avg BPU, `failed_jobs=0`
- `93.014` full-window avg BPU, `failed_jobs=0`

`dream7b-default-status` currently reports:

- latest telemetry avg BPU: `93.014`
- failed jobs: `0`
- latest soak avg BPU: `93.037`
- default replaced with rollback verified in the promotion probe
- 2026-06-20 read-only recovery contract: `dream7b-default-status json` was parseable and reported active/enabled segment-major default; `dream7b-default-rollback` dry-run returned `dry_run=1; no changes applied`
- status script sha256: `67a957abd62581547c248fd22a1c4d13ae33d0653de35e67898b7e0e440dcadb`
- rollback script sha256: `911d5bb43fe5844c17eaed3d18eecd3cee1257f834e855505327dd2db376bf80`

## True-Batch Research Route

Current B=4 true-batch route:

- Artifact root: `/mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b4`
- Batch size: `4`
- Sequence length: `16`
- Segment count: `28`
- Segment range: `seg00_01` through `seg27_28`
- Final runtime shape: `[4, 16, 152064]`
- Per-segment manifest files: present for all 28 segments
- Required artifact files: present for all 28 segments

Current long telemetry result:

- report: `/mnt/nas/openclaw/reports/models/dream7b_true_batch_group_major_telemetry_20260619-105833_segment_major_mb1536_b4/true_batch_group_major_telemetry.json`
- verdict: `ok_dream7b_true_batch_group_major_telemetry`
- processed requests: `6144`
- failed jobs: `0`
- avg BPU: `76.789`
- avg nonzero BPU: `89.776`
- max BPU: `100.0`
- amortized wall time: `72.249 ms/request`

## Why True-Batch Is Not Default

True-batch B=4 is a valid research artifact, but it is not a production
replacement candidate yet.

Reasons:

- It does not beat the queue baseline full-window avg BPU (`76.789` vs about `93%`).
- Its active/nonzero BPU is still below the queue baseline nonzero BPU.
- A shape-correct HBM chain is not sufficient for promotion.
- Throughput improvement alone is not sufficient if full-window BPU, latency,
  and failure metrics do not clear the gate.
- The route still needs independent experimental service isolation, fallback
  behavior, and unified telemetry before any promotion discussion.

## Promotion Gate Summary

Minimum gate for a future true-batch backend:

- `failed_jobs = 0`
- full-window `avg_bpu_loading >= queue_baseline - 1%`
- `tokens/s >= queue_baseline + 15%`
- P95 TTFT does not degrade by more than `10%`
- P95 TPOT does not degrade by more than `10%`
- final logits time does not obviously grow
- multiple consecutive full-window telemetry runs are stable

Preferred gate:

- `avg_bpu_loading >= 93.5%`
- `tokens/s >= queue_baseline + 20%`
- `failed_jobs = 0`
- P95 latency does not materially degrade

Do not promote based only on `avg_nonzero_bpu_loading`.
