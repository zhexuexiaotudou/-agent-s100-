# Dream7B Deployment File Map

Date: 2026-06-19

This map is read-only inventory. No files were moved, services changed, or
default model paths replaced.

## Production Service Audit

- Service: `dream7b-bpu-batch-queue.service`
- Remote status: exists, loaded, enabled, active/running
- Active since: 2026-06-18 11:06:05 CST
- Current production port: `127.0.0.1:18888`
- Current OpenAI-compatible API: `http://127.0.0.1:18888/v1`
- Current model id returned by `/v1/models`: `Dream7B-S100P-local`
- OpenClaw model alias reported by `dream7b-default-status`: `dream7b-local/Dream7B-S100P-local`
- Current route: `raw-final segment-major load-once 24x256 queue batch top_k=1`
- Current service runtime dir: `/mnt/nas/openclaw/runtimes/dream7b-bpu-segment-major-default`
- Current queue dir: `/mnt/nas/openclaw/queues/dream7b-bpu`
- Current report dir: `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd`

Remote systemd unit excerpt:

```text
Description=Dream 7B BPU batch queue service (segment-major load-once 24x256 default)
WorkingDirectory=/mnt/nas/openclaw/runtimes/dream7b-bpu-segment-major-default
Environment=DREAM7B_BPU_SEGMENT_MAJOR_RAW_FINAL=1
Environment=DREAM7B_BPU_SEGMENT_MAJOR_SKIP_EXPLICIT_GC=0
ExecStart=/usr/bin/python3 ... dream7b_bpu_selected_pair_cross_job_queue_service.py ... --min-job-count 24 --max-job-count 24 --max-batch-size 256 --top-k 1 --poll-interval-sec 0.05 --single-job-flush-timeout-sec 5
```

Local service templates:

- `configs/systemd/dream7b-bpu-batch-queue.service`
- `configs/systemd/dream7b-local-openai-gateway.service`

## True-Batch Compile Environment Audit

- Local WSL root path exists: `F:\Project\Digua\tmp\wsl\DiguaTrueBatchBuilder`
- WSL distro exists: `DiguaTrueBatchBuilder`
- WSL distro state: `Stopped`
- WSL version: `2`
- Compile-like local processes observed:
  - `F:\Program\Anaconda\envs\tf2\python.exe`, about 18.26 GiB private memory, unrelated long-running Python process
  - `wslservice`
  - no active `make`, `cmake`, `ninja`, `gcc`, or WSL compile workload was observed
- Existing true-batch B=4 artifact root: `/mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b4`
- Artifact root exists: yes
- Artifact size: about `56G`
- Segment count: `28`
- Segment range: `seg00_01` through `seg27_28`
- Missing required per-segment files: `0`
- Required per-segment files checked: `.bc`, `_convert.bc`, `_convert_removed.bc`, `.hbo`, `.hbm`, `manifest.sha256`

Key true-batch reports:

- `/mnt/nas/openclaw/reports/models/dream7b_true_batch_runtime_chain_20260619-063711_b4/true_batch_runtime_chain.json`
  - verdict: `ok_dream7b_true_batch_runtime_chain`
  - final shape: `[4, 16, 152064]`
- `/mnt/nas/openclaw/reports/models/dream7b_true_batch_group_major_telemetry_20260619-105833_segment_major_mb1536_b4/true_batch_group_major_telemetry.json`
  - verdict: `ok_dream7b_true_batch_group_major_telemetry`
  - processed requests: `6144`
  - failed jobs: `0`
  - avg BPU: `76.789`
  - avg nonzero BPU: `89.776`
  - max BPU: `100.0`
- `/mnt/nas/openclaw/reports/models/dream7b_true_batch_telemetry_compare_20260619-064106/true_batch_telemetry_compare.json`
  - verdict: `true_batch_runtime_ok_but_telemetry_not_better`

## Primary Local Docs

- `docs/dream7b_bpu_93_95_optimization_status.md`
- `docs/dream7b_true_batch_hbm_feasibility_2026-06-18.md`
- `docs/dream7b_true_batch_b4_segment_analysis_2026-06-19.md`
- `docs/dream7b_s100p_evidence_2026-06-18.md`
- `docs/dream7b_s100p_next_work_runbook.md`
- `docs/community/dream7b_s100_bpu_developer_post.md`

## Primary Local Scripts

Production and OpenAI-compatible route:

- `scripts/probes/dream7b_perf_identity_probe.py`
- `scripts/probes/dream7b_fast_path_regression_probe.py`
- `scripts/probes/dream7b_first_response_packet.py`
- `scripts/probes/dream7b_first_response_fast_status_packet.py`
- `scripts/probes/dream7b_first_response_routing_packet.py`
- `scripts/probes/dream7b_product_guardrail_snapshot.py`
- `scripts/probes/dream7b_product_decision_packet.py`

Queue baseline and segment-major telemetry:

- `scripts/probes/dream7b_bpu_segment_major_phase_timing_probe.sh`
- `scripts/probes/dream7b_bpu_segment_major_extreme_benchmark_probe.sh`

True-batch compile and runtime:

- `tmp/wsl_compile_dream_full_forward.py`
- `scripts/probes/Compile-DreamTrueBatchSegments.ps1`
- `scripts/probes/compile_dream_true_batch_segments.sh`
- `scripts/probes/dream7b_true_batch_compile_segments_wsl.sh`
- `scripts/probes/dream7b_true_batch_single_segment_runtime_probe.py`
- `scripts/probes/dream7b_true_batch_runtime_chain_probe.py`
- `scripts/probes/dream7b_true_batch_runtime_telemetry_probe.sh`
- `scripts/probes/dream7b_true_batch_load_once_telemetry_probe.py`
- `scripts/probes/dream7b_true_batch_group_major_telemetry_probe.py`
- `scripts/probes/dream7b_true_batch_compare_telemetry.py`
- `scripts/probes/dream7b_true_batch_schedule_analysis.py`
- `scripts/probes/analyze_dream_true_batch_b4.py`
- `scripts/probes/dream7b_b4_segment_drag_breakdown.py`
- `scripts/probes/dream7b_b4_final_logits_breakdown.py`

Unified telemetry wrappers added for this route:

- `scripts/telemetry/run_queue_baseline_telemetry.ps1`
- `scripts/telemetry/run_true_batch_telemetry.ps1`
- `scripts/telemetry/parse_bpu_telemetry.py`
- `scripts/telemetry/compare_backends.py`

## Mirrored Deployment Tree

The directory `完全基于agent的s100使用和链路打通/` contains deployment-era
copies of service scripts, probes, installers, and OpenClaw plugin assets. It is
treated as a source/reference tree for deployed scripts and should not be moved
as part of baseline or true-batch planning.
