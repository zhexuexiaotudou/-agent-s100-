# Project Reference

Last updated: 2026-06-03

This document is the project-level reference for API-like command interfaces, configuration keys, architecture, decisions, development log, requirements, and TODOs. All identifiers in this file are copied from repository files or recorded evidence. When a name, key, path, or field is uncertain, read the source file first and do not infer spelling, case, format, or structure.

## Documentation Rule

- Do not guess identifiers. This includes command names, script names, variable names, JSON keys, paths, report fields, service names, model names, and environment variable names.
- Before writing or changing an identifier, read the related file, report, config, or log and copy the exact spelling.
- After each task, run the documentation check described in `docs/documentation_audit_runbook.md`.
- If the check is not run, record why in the final task note.

## Project Requirements

- Keep Dream 7B as the model; do not replace it with another model for the BPU route.
- Make real Dream 7B weights execute on the S100P BPU path through segmented S100 `.hbm` artifacts.
- Keep S100P + NAS + OpenClaw link checks reproducible through scripts and report files.
- Store project evidence in Markdown documents under `docs/` and runtime reports under `/mnt/nas/openclaw/reports/` when running on S100P.
- Keep post-task documentation verification explicit and repeatable.

## Architecture

```text
Windows host
  -> workspace root: F:\Project\Digua
  -> repository root: read the current working directory with Get-Location or pwd before copying the full non-ASCII path
  -> startup link check: scripts/startup_link_check/
  -> SSH key: C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519

S100P
  -> host: 192.168.127.10
  -> user: sunrise
  -> BPU runtime venv: /mnt/nas/openclaw/runtimes/hbm-runtime-venv
  -> tokenizer venv: /mnt/nas/openclaw/runtimes/dream7b-tokenizer-venv
  -> deployed command path: /usr/local/bin
  -> local HBM cache: /home/sunrise/.cache/openclaw/dream7b-hbm/

NAS
  -> mountPoint: /mnt/nas/openclaw
  -> Dream 7B HBM root: /mnt/nas/openclaw/models/dream7b-hbm
  -> reports root: /mnt/nas/openclaw/reports/models

Dream 7B BPU path
  -> Dream HF weights
  -> WSL1 AVX build host
  -> segmented S100 HBM
  -> NAS storage
  -> S100P tokenizer/runtime
  -> deployed S100P commands
```

The current Dream 7B BPU route is documented in `docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md`.

## Command Interfaces

### `dream7b-bpu-forward`

Source file: `scripts/dream7b-bpu-forward.sh`

Environment variables copied from the script:

```text
DREAM7B_BPU_VENV
DREAM7B_BPU_FORWARD_SCRIPT
DREAM7B_BPU_HBM_DIR
DREAM7B_BPU_REPORT_ROOT
```

Default values copied from the script:

```text
/mnt/nas/openclaw/runtimes/hbm-runtime-venv
/mnt/nas/openclaw/runtimes/dream7b-bpu-forward/dream7b_segmented_hbm_python_forward.py
/mnt/nas/openclaw/models/dream7b-hbm/segments6
/mnt/nas/openclaw/reports/models
```

Forwarded options recognized by `scripts/probes/dream7b_segmented_hbm_python_forward.py`:

```text
--hbm-dir
--fine-hbm-dir
--segment-plan
--residency-window-size
--child-window-mode
--child-runtime-mode
--window-execution-mode
--output-dir
--tokens-bin
--tokens
--tokens-batch-json
--seq-len
--hidden-size
--vocab-size
--save-logits
--top-k
```

### `dream7b-bpu-fine-forward`

Source file: `scripts/dream7b-bpu-fine-forward.sh`

Environment variables copied from the script:

```text
DREAM7B_BPU_HBM_DIR
DREAM7B_BPU_FINE_HBM_DIR
DREAM7B_BPU_FINE_WINDOW_SIZE
DREAM7B_BPU_FINE_CHILD_WINDOW_MODE
DREAM7B_BPU_FINE_CHILD_RUNTIME_MODE
DREAM7B_BPU_FINE_WINDOW_EXECUTION_MODE
```

Default values copied from the script:

```text
/home/sunrise/.cache/openclaw/dream7b-hbm/segments6
/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16
2
pair
packed
in-process
```

Default arguments injected by the wrapper when they are absent:

```text
--hbm-dir
--fine-hbm-dir
--segment-plan fine-adjacent
--residency-window-size 2
--child-window-mode pair
--child-runtime-mode packed
--window-execution-mode in-process
```

### `dream7b-bpu-fine-batch-forward`

Source file: `scripts/dream7b-bpu-fine-batch-forward.sh`

Environment variables copied from the script:

```text
DREAM7B_BPU_HBM_DIR
DREAM7B_BPU_FINE_HBM_DIR
DREAM7B_BPU_FINE_BATCH_WINDOW_SIZE
DREAM7B_BPU_FINE_BATCH_CHILD_WINDOW_MODE
DREAM7B_BPU_FINE_BATCH_CHILD_RUNTIME_MODE
DREAM7B_BPU_FINE_BATCH_WINDOW_EXECUTION_MODE
DREAM7B_BPU_TOKENS_BATCH_JSON
```

Default values copied from the script:

```text
/home/sunrise/.cache/openclaw/dream7b-hbm/segments6
/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16
2
pair
packed
window-batch
```

Default arguments injected by the wrapper when they are absent:

```text
--hbm-dir
--fine-hbm-dir
--segment-plan fine-adjacent
--residency-window-size 2
--child-window-mode pair
--child-runtime-mode packed
--window-execution-mode window-batch
```

Conditional argument injected by the wrapper when `DREAM7B_BPU_TOKENS_BATCH_JSON` is set and `--tokens-batch-json` is absent:

```text
--tokens-batch-json
```

Input schema for `--tokens-batch-json` copied from `scripts/probes/dream7b_segmented_hbm_python_forward.py`:

```text
JSON list containing one or more token-id lists, each with seq_len entries.
```

Latest recorded probe:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_forward_20260603-183625/fine_batch_forward_probe.md
```

### `dream7b-bpu-batch-queue-runner`

Source file: `scripts/dream7b-bpu-batch-queue-runner.sh`

Python implementation: `scripts/dream7b_bpu_batch_queue_runner.py`

Environment variable copied from the wrapper:

```text
DREAM7B_BPU_BATCH_QUEUE_RUNNER_SCRIPT
```

Default value copied from the wrapper:

```text
/mnt/nas/openclaw/runtimes/dream7b-bpu-forward/dream7b_bpu_batch_queue_runner.py
```

Positional arguments copied from `scripts/dream7b_bpu_batch_queue_runner.py`:

```text
request_jsonl
output_dir
```

Optional arguments copied from `scripts/dream7b_bpu_batch_queue_runner.py`:

```text
--max-batch-size
--seq-len
--top-k
--forward-cmd
--drain-all
--bpu-lock-path
--bpu-lock-timeout-sec
```

Default values copied from `scripts/dream7b_bpu_batch_queue_runner.py`:

```text
max_batch_size = 4
seq_len = 16
top_k = 3
forward_cmd = dream7b-bpu-fine-batch-forward
bpu_lock_path = /tmp/dream7b_bpu_batch_queue_runner.lock
bpu_lock_timeout_sec = 600.0
```

Request JSONL keys copied from `scripts/dream7b_bpu_batch_queue_runner.py`:

```text
request_id
tokens
cancelled
not_after_epoch_ms
```

Output summary keys copied from `scripts/dream7b_bpu_batch_queue_runner.py`:

```text
verdict
request_jsonl
output_dir
forward_command
drain_all
max_batch_size
bpu_lock
request_count
runnable_count
processed_count
accepted_count
deferred_count
deferred_request_ids
skipped_count
skipped_requests
batch_run_count
batch_runs
durable_state
results
forward_metrics
errors
```

Durable state files copied from `scripts/dream7b_bpu_batch_queue_runner.py`:

```text
accepted_requests.jsonl
deferred_requests.jsonl
skipped_requests.jsonl
results.jsonl
```

Latest recorded probe:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_runner_20260603-193243/batch_queue_runner_probe.md
```

### `dream7b-bpu-text-forward`

Source file: `scripts/dream7b-bpu-text-forward.sh`

Environment variables copied from the script:

```text
DREAM7B_TOKENIZER_VENV
DREAM7B_TOKENIZER
DREAM7B_BPU_SEQ_LEN
DREAM7B_BPU_PROMPT_FIT
```

Usage copied from the script:

```text
dream7b-bpu-text-forward [--fit exact|truncate-left|pad-right] [--save-logits] [--top-k N] [--output-dir DIR] [--] prompt text
```

Forwarded options copied from the script:

```text
--save-logits
--output-dir
--hbm-dir
--top-k
```

### `dream7b-bpu-batch-queue-service`

Source file: `scripts/dream7b-bpu-batch-queue-service.sh`

Python implementation: `scripts/dream7b_bpu_batch_queue_service.py`

Environment variable copied from the wrapper:

```text
DREAM7B_BPU_BATCH_QUEUE_SERVICE_SCRIPT
```

Default value copied from the wrapper:

```text
/mnt/nas/openclaw/runtimes/dream7b-bpu-forward/dream7b_bpu_batch_queue_service.py
```

Positional arguments copied from `scripts/dream7b_bpu_batch_queue_service.py`:

```text
queue_dir
output_dir
```

Optional arguments copied from `scripts/dream7b_bpu_batch_queue_service.py`:

```text
--runner-cmd
--max-batch-size
--seq-len
--top-k
--forward-cmd
--bpu-lock-path
--bpu-lock-timeout-sec
--poll-interval-sec
--max-iterations
--once
--drain-all
```

Default values copied from `scripts/dream7b_bpu_batch_queue_service.py`:

```text
runner_cmd = dream7b-bpu-batch-queue-runner
max_batch_size = 4
seq_len = 16
top_k = 3
forward_cmd = dream7b-bpu-fine-batch-forward
bpu_lock_path = /tmp/dream7b_bpu_batch_queue_runner.lock
bpu_lock_timeout_sec = 600.0
poll_interval_sec = 1.0
max_iterations = 0
```

Queue subdirectories copied from `scripts/dream7b_bpu_batch_queue_service.py`:

```text
pending
processing
done
failed
```

Output summary keys copied from `scripts/dream7b_bpu_batch_queue_service.py`:

```text
verdict
queue_dir
output_dir
runner_command
processed_job_count
failed_job_count
iteration_count
queue_paths
jobs
errors
```

Latest recorded service probe:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_20260603-194437/batch_queue_service_probe.md
```

Latest recorded real BPU service one-shot:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_real_scp_20260603-194827/output/service_summary.md
```

### `dream7b-bpu-diffusion-loop-probe`

Source file: `scripts/probes/dream7b_bpu_diffusion_loop_probe.sh`

Environment variables copied from the script:

```text
DREAM7B_TOKENIZER_VENV
DREAM7B_TOKENIZER
DREAM7B_BPU_SEQ_LEN
DREAM7B_BPU_MIN_MASK_COUNT
DREAM7B_BPU_DIFFUSION_STEPS
DREAM7B_BPU_TOP_K
DREAM7B_BPU_EPS
DREAM7B_BPU_REMASKING
DREAM7B_BPU_TEMP
DREAM7B_BPU_SEED
DREAM7B_BPU_ENTROPY_THRESHOLD
DREAM7B_BPU_FORWARD_CMD
```

Supported `DREAM7B_BPU_REMASKING` values copied from the script:

```text
low_confidence
entropy_exit
maskgit_plus
topk_margin
entropy
```

Current verified fine-forward invocation:

```bash
DREAM7B_BPU_FORWARD_CMD=dream7b-bpu-fine-forward \
  dream7b-bpu-diffusion-loop-probe \
  /mnt/nas/openclaw/reports/models \
  'Explain why S100P BPU matters for Dream 7B in OpenClaw.'
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_loop_20260603-175030/summary.md
```

### Documentation Consistency Probe

Source file: `scripts/probes/project_docs_consistency_probe.sh`

The probe checks that the project reference documents exist and include required exact strings for current Dream 7B and startup-link documentation.

Run:

```bash
bash scripts/probes/project_docs_consistency_probe.sh /tmp/project_docs_consistency
```

Approved output roots:

```text
/tmp/
/mnt/nas/openclaw/reports/
/root/.openclaw/workspace/reports/
```

### `dream7b-bpu-fine-forward-repeat-probe`

Source file: `scripts/probes/dream7b_bpu_fine_forward_repeat_probe.sh`

Run:

```bash
dream7b-bpu-fine-forward-repeat-probe /mnt/nas/openclaw/reports/models
```

Default `repeat_count` copied from the script:

```text
3
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_repeat_20260603-180108/summary.md
```

### `dream7b-bpu-fine-forward-window-batch-probe`

Source file: `scripts/probes/dream7b_bpu_fine_forward_window_batch_probe.sh`

Run:

```bash
dream7b-bpu-fine-forward-window-batch-probe /mnt/nas/openclaw/reports/models
```

Default `batch_count` copied from the script:

```text
3
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_window_batch_20260603-181131/summary.md
```

Boundary: this is a throughput probe for independent seq16 inputs. It does not reduce reload cost for a single dependent Dream diffusion request.

### `dream7b-bpu-fine-batch-forward-probe`

Source file: `scripts/probes/dream7b_bpu_fine_batch_forward_probe.sh`

Run:

```bash
dream7b-bpu-fine-batch-forward-probe /mnt/nas/openclaw/reports/models
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_forward_20260603-183625/fine_batch_forward_probe.md
```

### `dream7b-bpu-batch-queue-runner-probe`

Source file: `scripts/probes/dream7b_bpu_batch_queue_runner_probe.sh`

Run:

```bash
dream7b-bpu-batch-queue-runner-probe /mnt/nas/openclaw/reports/models
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_runner_20260603-193243/batch_queue_runner_probe.md
```

### `dream7b-bpu-batch-queue-drain-probe`

Source file: `scripts/probes/dream7b_bpu_batch_queue_drain_probe.sh`

Run:

```bash
dream7b-bpu-batch-queue-drain-probe /mnt/nas/openclaw/reports/models
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_drain_20260603-193309/batch_queue_drain_probe.md
```

### `dream7b-bpu-batch-queue-control-probe`

Source file: `scripts/probes/dream7b_bpu_batch_queue_control_probe.sh`

Run:

```bash
dream7b-bpu-batch-queue-control-probe /mnt/nas/openclaw/reports/models
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_control_20260603-193400/batch_queue_control_probe.md
```

### `dream7b-bpu-batch-queue-lock-probe`

Source file: `scripts/probes/dream7b_bpu_batch_queue_lock_probe.sh`

Run:

```bash
dream7b-bpu-batch-queue-lock-probe /mnt/nas/openclaw/reports/models
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_lock_20260603-193209/batch_queue_lock_probe.md
```

### `dream7b-bpu-batch-queue-service-probe`

Source file: `scripts/probes/dream7b_bpu_batch_queue_service_probe.sh`

Run:

```bash
dream7b-bpu-batch-queue-service-probe /mnt/nas/openclaw/reports/models
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_20260603-194437/batch_queue_service_probe.md
```

## Configuration Interfaces

### Startup Link Check

Source file: `scripts/startup_link_check/link-check.config.json`

Top-level keys copied from the file:

```text
windows
s100p
nas
openclaw
logging
```

Nested keys copied from the file:

```text
windows.interfaceAlias
windows.requiredIPv4
windows.startupDelaySeconds
windows.autoCloseSuccessSeconds
windows.autoCloseFixedSeconds
s100p.host
s100p.user
s100p.sshKey
s100p.sshConnectTimeoutSeconds
s100p.interface
s100p.nasInterface
s100p.nasInterfaceIPv4
s100p.requiredIPv4
s100p.defaultGateway
s100p.defaultRouteMetric
s100p.dns
s100p.netplanPath
s100p.netplanMacEth0
s100p.netplanMacEth1
nas.ip
nas.nfsExport
nas.mountPoint
nas.parentDir
nas.probeDir
openclaw.serviceName
openclaw.rootUserRuntimeDir
openclaw.logFile
openclaw.feishuHost
logging.localDir
```

Selected values copied from the file:

```text
s100p.host = 192.168.127.10
s100p.user = sunrise
s100p.interface = eth1
s100p.nasInterface = eth0
s100p.nasInterfaceIPv4 = 169.254.8.10/16
s100p.defaultGateway = 192.168.137.1
s100p.netplanPath = /etc/netplan/99-hobot-net.yaml
nas.ip = 169.254.143.37
nas.nfsExport = /OpenClawWorkspace
nas.mountPoint = /mnt/nas/openclaw
openclaw.serviceName = openclaw-gateway.service
openclaw.feishuHost = open.feishu.cn
logging.localDir = F:\Project\Digua\logs\link-check
```

Do not rewrite non-ASCII values from this JSON unless the file is read with an encoding-safe method and the exact value is verified.

### Tool Allowlist

Source file: `scripts/tool_allowlist.json`

Top-level keys copied from the file:

```text
version
tools
```

Tool object keys copied from the file:

```text
id
script
mode
approvedInputPrefixes
approvedOutputPrefixes
description
```

Dream-related tool IDs copied from `scripts/tool_allowlist.json`:

```text
dream7b_readiness_probe
dream7b_config_template_probe
dream7b_smoke_probe
```

## Decisions

### Keep Dream 7B

Decision: keep Dream 7B as the model and do not switch to another official sample LLM.

Evidence document:

```text
docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md
```

### Use segmented `.hbm`

Decision: compile Dream 7B seq16 full-forward into segmented S100 `.hbm` artifacts because larger single-file and four-segment attempts exceeded observed S100P load limits.

Current working six-segment root:

```text
/mnt/nas/openclaw/models/dream7b-hbm/segments6
```

Current fine-split root:

```text
/mnt/nas/openclaw/models/dream7b-hbm/fine-seq16
```

### Use fine adjacent pair residency

Decision: use `fine-adjacent` with `--residency-window-size 2` because every adjacent two-segment window passed the fine residency probe, while three-segment combinations still failed.

Evidence report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_residency_20260603-054031/summary.md
```

### Use `pair` plus `packed` plus `in-process`

Decision: default `dream7b-bpu-fine-forward` to `--child-window-mode pair`, `--child-runtime-mode packed`, and `--window-execution-mode in-process`.

Evidence reports:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_20260603-174608/fine_forward_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_perf_20260603-174745/summary.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_repeat_20260603-180108/summary.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_window_batch_20260603-181131/summary.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_forward_20260603-183625/fine_batch_forward_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_runner_20260603-193243/batch_queue_runner_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_drain_20260603-193309/batch_queue_drain_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_control_20260603-193400/batch_queue_control_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_lock_20260603-193209/batch_queue_lock_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_20260603-194437/batch_queue_service_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_real_scp_20260603-194827/output/service_summary.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_20260603-183906/fine_forward_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_loop_20260603-175030/summary.md
```

### Use JSONL queue batching for independent seq16 requests

Decision: use `dream7b-bpu-batch-queue-runner` as the service-level batching bridge for independent seq16 token requests. It reads required `request_id` and `tokens` keys from JSONL, accepts optional `cancelled` and `not_after_epoch_ms` keys, skips cancelled or expired requests, accepts up to `--max-batch-size`, records deferred request IDs by default, supports `--drain-all` for multiple batch runs, writes durable JSONL state under `durable_state`, acquires the default single-flight BPU lock at `/tmp/dream7b_bpu_batch_queue_runner.lock`, records lock status in `bpu_lock`, and calls `dream7b-bpu-fine-batch-forward`.

Evidence report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_runner_20260603-193243/batch_queue_runner_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_drain_20260603-193309/batch_queue_drain_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_control_20260603-193400/batch_queue_control_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_lock_20260603-193209/batch_queue_lock_probe.md
```

Boundary: this is a service-level throughput bridge for independent requests. It is not a single-request Dream diffusion acceleration path.

### Use directory-backed service queue for reusable operation

Decision: use `dream7b-bpu-batch-queue-service` as the reusable directory-backed service loop. It consumes `*.jsonl` jobs from `pending`, moves active jobs to `processing`, moves successful jobs to `done`, moves failed jobs to `failed`, writes `service_summary.json`, and calls `dream7b-bpu-batch-queue-runner` for each job so the existing `durable_state` and `bpu_lock` behavior remains authoritative.

Evidence reports:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_20260603-194437/batch_queue_service_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_real_scp_20260603-194827/output/service_summary.md
```

Boundary: this is a long-running-capable command loop. It is not yet installed as a systemd unit.

### Do not claim production text service yet

Decision: current Dream 7B BPU route is a verified seq16 BPU logits and bounded diffusion-loop path, not a complete production text-generation service.

Current boundary is recorded in:

```text
docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md
```

## Development Log

### 2026-06-01

- Recorded BPU HBM smoke progress in `docs/baseline_progress_2026-06-01_bpu_hbm_smoke.md`.

### 2026-06-02

- Recorded startup link repair in `docs/baseline_progress_2026-06-02_startup_link_repair.md`.
- Recorded Dream 7B diffuse.cpp deployment in `docs/baseline_progress_2026-06-02_dream7b_diffuse_cpp_deployment.md`.
- Recorded Dream 7B BPU compile attempt in `docs/baseline_progress_2026-06-02_dream7b_bpu_compile_attempt.md`.

### 2026-06-03

- Recorded segmented S100 BPU HBM route in `docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md`.
- Pushed commit `a8089c5 Add Dream 7B fine forward perf probe`.
- Pushed commit `eb6558f Pack Dream 7B fine pair runtimes`.
- Verified `dream7b-bpu-fine-forward-probe` report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_20260603-171052/fine_forward_probe.md`.
- Verified `dream7b-bpu-fine-forward-perf-probe` report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_perf_20260603-171203/summary.md`.
- Verified `dream7b-bpu-diffusion-loop-probe` report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_loop_20260603-171725/summary.md`.
- Verified `dream7b-bpu-fine-forward-probe` report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_20260603-174608/fine_forward_probe.md`.
- Verified `dream7b-bpu-fine-forward-perf-probe` report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_perf_20260603-174745/summary.md`.
- Verified `dream7b-bpu-diffusion-loop-probe` report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_loop_20260603-175030/summary.md`.
- Promoted the manual in-process pair release experiment into repository code through `--window-execution-mode in-process`.
- Verified `dream7b-bpu-fine-forward-repeat-probe` report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_repeat_20260603-180108/summary.md`.
- Verified `dream7b-bpu-fine-forward-window-batch-probe` report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_window_batch_20260603-181131/summary.md`.
- Promoted the window-batch throughput path into `dream7b-bpu-fine-batch-forward`.
- Verified `dream7b-bpu-fine-batch-forward-probe` report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_forward_20260603-183625/fine_batch_forward_probe.md`.
- Re-verified `dream7b-bpu-fine-forward-probe` report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_20260603-183906/fine_forward_probe.md` after adding `--tokens-batch-json`, `--window-execution-mode window-batch`, and timing fields.
- Added `dream7b-bpu-batch-queue-runner` for service-level JSONL request batching.
- Verified `dream7b-bpu-batch-queue-runner-probe` report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_runner_20260603-193243/batch_queue_runner_probe.md`.
- Added `--drain-all` multi-batch scheduling to `dream7b-bpu-batch-queue-runner`.
- Verified `dream7b-bpu-batch-queue-drain-probe` report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_drain_20260603-193309/batch_queue_drain_probe.md`.
- Added `cancelled`, `not_after_epoch_ms`, skipped request, and `durable_state` JSONL handling to `dream7b-bpu-batch-queue-runner`.
- Verified `dream7b-bpu-batch-queue-control-probe` report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_control_20260603-193400/batch_queue_control_probe.md`.
- Added default single-flight `bpu_lock` handling to `dream7b-bpu-batch-queue-runner`.
- Verified `dream7b-bpu-batch-queue-lock-probe` report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_lock_20260603-193209/batch_queue_lock_probe.md`.
- Added `dream7b-bpu-batch-queue-service` for directory-backed `pending` / `processing` / `done` / `failed` queue operation.
- Verified `dream7b-bpu-batch-queue-service-probe` report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_20260603-194437/batch_queue_service_probe.md`.
- Verified real BPU one-shot service report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_real_scp_20260603-194827/output/service_summary.md`.

## TODO

- Keep `--window-execution-mode child-process` as the fallback path until longer-run evidence proves `--window-execution-mode in-process` is stable beyond the current 3-run probe.
- Add longer repeated-run performance evidence for `fine_pair_in_process_packed`.
- Add daemon supervision for `dream7b-bpu-batch-queue-service` after the desired queue root and restart policy are selected.
- Run documentation consistency checking through `scripts/probes/project_docs_consistency_probe.sh` after each task.
- Continue quality gates against the CPU Dream path before describing the BPU route as production text generation.

## Post-Task Documentation Check

Run this after each task that changes code, scripts, config, reports, or project decisions:

```bash
bash scripts/probes/project_docs_consistency_probe.sh /tmp/project_docs_consistency
```

Minimum manual review:

```text
README.md
docs/project_reference.md
docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md
docs/documentation_audit_runbook.md
```

The check must confirm:

- README points to `docs/project_reference.md`.
- `docs/project_reference.md` contains the current command names and config keys.
- `docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md` contains the latest Dream 7B BPU evidence.
- Any newly introduced identifier is copied from a source file, config file, runtime report, or command output.
