# Project Reference

Last updated: 2026-06-05

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

### `dream7b-bpu-fine-batch-size-sweep-probe`

Source file: `scripts/probes/dream7b_bpu_fine_batch_size_sweep_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-fine-batch-size-sweep-probe
```

Environment variables copied from the script:

```text
DREAM7B_BPU_FINE_BATCH_SWEEP_COUNTS
DREAM7B_BPU_FINE_BATCH_SWEEP_TIMEOUT_SEC
DREAM7B_BPU_FINE_BATCH_SWEEP_TOP_K
```

Default values copied from the script:

```text
counts_text = 1 2 4 8
timeout_sec = 720
top_k = 3
```

Checked fields copied from the script:

```text
verdict
segment_plan
residency_window_size
execution_mode
window_execution_mode
child_process_count
batch_count
final_shapes
wall_ms
load_ms
run_ms
amortized_wall_ms_per_forward
amortized_load_ms_per_forward
amortized_run_ms_per_forward
load_share
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_size_sweep_20260604-181429/batch_size_sweep_probe.md
```

Latest recorded summaries:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_size_sweep_20260604-181429/batch_1/forward/summary.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_size_sweep_20260604-181429/batch_2/forward/summary.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_size_sweep_20260604-181429/batch_4/forward/summary.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_size_sweep_20260604-181429/batch_8/forward/summary.json
```

### `dream7b-bpu-batch-capacity-probe`

Source file: `scripts/probes/dream7b_bpu_batch_capacity_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-batch-capacity-probe
```

Environment variables copied from the script:

```text
DREAM7B_BPU_BATCH_CAPACITY_COUNTS
DREAM7B_BPU_BATCH_CAPACITY_TIMEOUT_SEC
DREAM7B_BPU_BATCH_CAPACITY_TOP_K
```

Default values copied from the script:

```text
counts_text = 8 12 16
timeout_sec = 900
top_k = 3
```

Checked fields copied from the script:

```text
max_passing_count
batch_count
status
wall_ms
load_ms
run_ms
amortized_wall_ms_per_forward
amortized_load_ms_per_forward
amortized_run_ms_per_forward
final_shape_count
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_capacity_20260605-123835/batch_capacity_probe.md
```

Latest recorded summaries:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_capacity_20260605-123835/batch_8/forward/summary.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_capacity_20260605-123835/batch_12/forward/summary.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_capacity_20260605-123835/batch_16/forward/summary.json
```

### `dream7b-bpu-runtime-telemetry-probe`

Source file: `scripts/probes/dream7b_bpu_runtime_telemetry_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-runtime-telemetry-probe
```

Environment variables copied from the script:

```text
DREAM7B_BPU_TELEMETRY_BATCH_COUNT
DREAM7B_BPU_TELEMETRY_MONITOR_DELAY_MS
DREAM7B_BPU_TELEMETRY_MONITOR_SAMPLE_COUNT
DREAM7B_BPU_TELEMETRY_TOP_K
DREAM7B_BPU_TELEMETRY_TIMEOUT_SEC
```

Default values copied from the script:

```text
batch_count = 16
monitor_delay_ms = 100
monitor_sample_count = 320
top_k = 3
timeout_sec = 480
```

Telemetry commands copied from the script and S100P discovery:

```text
hrt_ucp_monitor
hrut_somstatus
```

Checked fields copied from the script:

```text
bpu_loading_sample_count
nonzero_bpu_loading_sample_count
max_bpu_loading
avg_bpu_loading
forward_summary
wall_ms
load_ms
run_ms
amortized_wall_ms_per_forward
amortized_load_ms_per_forward
amortized_run_ms_per_forward
final_shapes
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_runtime_telemetry_20260605-132014/runtime_telemetry_probe.md
```

Latest recorded forward summary:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_runtime_telemetry_20260605-132014/forward/summary.json
```

### `dream7b-bpu-hbm-artifact-inventory-probe`

Source file: `scripts/probes/dream7b_bpu_hbm_artifact_inventory_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-hbm-artifact-inventory-probe
```

Default argument copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
```

Environment variables copied from the script:

```text
DREAM7B_BPU_ARTIFACT_INVENTORY_FORWARD_SCRIPT
DREAM7B_BPU_ARTIFACT_INVENTORY_NAS_HBM_DIR
DREAM7B_BPU_ARTIFACT_INVENTORY_NAS_FINE_HBM_DIR
DREAM7B_BPU_ARTIFACT_INVENTORY_LOCAL_HBM_DIR
DREAM7B_BPU_ARTIFACT_INVENTORY_LOCAL_FINE_HBM_DIR
DREAM7B_BPU_ARTIFACT_INVENTORY_VERIFY_MANIFEST
```

Default values copied from the script:

```text
forward_script = /mnt/nas/openclaw/runtimes/dream7b-bpu-forward/dream7b_segmented_hbm_python_forward.py
nas_hbm_dir = /mnt/nas/openclaw/models/dream7b-hbm/segments6
nas_fine_hbm_dir = /mnt/nas/openclaw/models/dream7b-hbm/fine-seq16
local_hbm_dir = /home/sunrise/.cache/openclaw/dream7b-hbm/segments6
local_fine_hbm_dir = /home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16
verify_manifest = 1
```

Segment constants parsed by the script:

```text
SEGMENTS6
FINE_ADJACENT_SEGMENTS
```

Checked fields copied from the script:

```text
expected_artifact_count
expected_base_count
expected_fine_count
nas_existing_count
local_existing_count
size_match_count
manifest_expected_count
manifest_verified_count
required_manifest_expected_count
inventory
warnings
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_hbm_artifact_inventory_20260605-160050/hbm_artifact_inventory_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_hbm_artifact_inventory_20260605-160050/hbm_artifact_inventory_probe.json
```

Verified artifact inventory fields copied from `hbm_artifact_inventory_probe.json`:

```text
verdict: ok_dream7b_bpu_hbm_artifact_inventory_probe
expected_artifact_count: 14
expected_base_count: 6
expected_fine_count: 8
nas_existing_count: 14
local_existing_count: 14
size_match_count: 14
manifest_expected_count: 12
manifest_verified_count: 12
required_manifest_expected_count: 12
warnings: []
errors: []
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

### `dream7b-bpu-text-queue-submit`

Source file: `scripts/dream7b-bpu-text-queue-submit.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-text-queue-submit
```

Environment variables copied from the script:

```text
DREAM7B_TOKENIZER_VENV
DREAM7B_TOKENIZER
DREAM7B_BPU_TEXT_QUEUE_DIR
DREAM7B_BPU_TEXT_QUEUE_SUBMIT_REPORT_ROOT
DREAM7B_BPU_TEXT_QUEUE_SUBMIT_RUN_DIR
DREAM7B_BPU_TEXT_QUEUE_SEQ_LEN
DREAM7B_BPU_TEXT_QUEUE_FIT
```

Default values copied from the script:

```text
tokenizer_venv = /mnt/nas/openclaw/runtimes/dream7b-tokenizer-venv
tokenizer_dir = /mnt/nas/openclaw/models/dream7b/tokenizer
queue_dir = /mnt/nas/openclaw/queues/dream7b-bpu
report_root = /mnt/nas/openclaw/reports/models
run_dir_override =
seq_len = 16
fit_mode = pad-right
```

Usage copied from the script:

```text
dream7b-bpu-text-queue-submit [--queue-dir DIR] [--report-root DIR] [--run-dir DIR] [--job-stem NAME] [--request-id ID] [--fit exact|truncate-left|pad-right] [--seq-len 16] [--prompt TEXT|--prompt-file FILE] [--] prompt text
```

Output files copied from the script:

```text
tokenizer_input.json
text_queue_submit.json
text_queue_submit.md
<job_stem>.jsonl
```

Submit summary fields copied from the script:

```text
verdict
queue_dir
report_root
run_dir
job_name
job_path
queue_pending_path
tokenizer_venv
tokenizer_dir
tokenizer_json
tokenizer
request_id
seq_len
fit_mode
prompt_file
errors
```

### `dream7b-bpu-text-queue-run`

Source file: `scripts/dream7b-bpu-text-queue-run.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-text-queue-run
```

Environment variables copied from the script:

```text
DREAM7B_BPU_TEXT_QUEUE_DIR
DREAM7B_BPU_TEXT_QUEUE_OUTPUT_DIR
DREAM7B_BPU_TEXT_QUEUE_RUN_REPORT_ROOT
DREAM7B_BPU_TEXT_QUEUE_RUN_DIR
DREAM7B_BPU_TEXT_QUEUE_SUBMIT_CMD
DREAM7B_BPU_TEXT_QUEUE_SEQ_LEN
DREAM7B_BPU_TEXT_QUEUE_FIT
DREAM7B_BPU_TEXT_QUEUE_TIMEOUT_SEC
DREAM7B_BPU_TEXT_QUEUE_POLL_INTERVAL_SEC
```

Default values copied from the script:

```text
queue_dir = /mnt/nas/openclaw/queues/dream7b-bpu
output_dir = /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd
report_root = /mnt/nas/openclaw/reports/models
run_dir_override =
submit_cmd = dream7b-bpu-text-queue-submit
seq_len = 16
fit_mode = pad-right
timeout_sec = 180
poll_interval_sec = 2
```

Usage copied from the script:

```text
dream7b-bpu-text-queue-run [--queue-dir DIR] [--output-dir DIR] [--report-root DIR] [--run-dir DIR] [--job-stem NAME] [--request-id ID] [--fit exact|truncate-left|pad-right] [--seq-len 16] [--timeout-sec N] [--poll-interval-sec N] [--prompt TEXT|--prompt-file FILE] [--] prompt text
```

Output files copied from the script:

```text
text_queue_run.json
text_queue_run.md
text_queue_submit.json
text_queue_submit.md
tokenizer_input.json
```

Run result fields copied from the script:

```text
verdict
queue_dir
output_dir
report_root
run_dir
job_name
job_status
summary_path
submit_cmd
submit_json
submit_md
submit_stdout
submit_stderr
submit
submit_verdict
tokenizer_json
tokenizer
request_id
seq_len
fit_mode
timeout_sec
poll_interval_sec
processed_count
accepted_count
deferred_count
skipped_count
batch_run_count
batch_count
result_count
execution_mode
window_execution_mode
child_process_count
bpu_lock_path
final_shape
topk_last_position
topk_last_position_decoded
durable_results_jsonl
total_wall_ms
amortized_wall_ms_per_processed_request
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_run_20260606-155102/text_queue_run.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_run_20260606-155102/text_queue_run.json
```

Verified text queue run fields copied from `text_queue_run.json`:

```text
verdict: ok_dream7b_bpu_text_queue_run
submit_cmd: dream7b-bpu-text-queue-submit
submit_verdict: ok_dream7b_bpu_text_queue_submit
job_status: done
request_id: text_queue_run_20260606-155102-001
summary_path: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/text_queue_run_20260606-155102/queue_summary.json
processed_count: 1
accepted_count: 1
deferred_count: 0
skipped_count: 0
batch_run_count: 1
batch_count: 1
result_count: 1
execution_mode: pair_window_batch
window_execution_mode: window-batch
child_process_count: 0
bpu_lock_path: /run/lock/dream7b_bpu_batch_queue_runner.lock
final_shape: [1, 16, 152064]
topk_last_position: [{'token_id': 323, 'score': 1.7742547988891602}, {'token_id': 476, 'score': 1.0451929569244385}, {'token_id': 11, 'score': 0.8926413059234619}]
topk_last_position_decoded: [{'token_id': 323, 'score': 1.7742547988891602, 'token_text': ' and'}, {'token_id': 476, 'score': 1.0451929569244385, 'token_text': ' or'}, {'token_id': 11, 'score': 0.8926413059234619, 'token_text': ','}]
durable_results_jsonl: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/text_queue_run_20260606-155102/durable_state/results.jsonl
total_wall_ms: 24132.416
amortized_wall_ms_per_processed_request: 24132.416
tokenizer.tokenizer_dir: /mnt/nas/openclaw/models/dream7b/tokenizer
tokenizer.fit_mode: pad-right
tokenizer.seq_len: 16
tokenizer.original_token_count: 9
tokenizer.token_count: 16
errors: []
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

Runtime behavior copied from `scripts/dream7b_bpu_batch_queue_service.py`:

```text
service_summary.json is refreshed during each service loop iteration
service_summary.md is refreshed during each service loop iteration
```

### `install-dream7b-bpu-queue-service`

Source file: `scripts/install_dream7b_bpu_queue_service.sh`

Installed command on S100P:

```text
/usr/local/bin/install-dream7b-bpu-queue-service
```

Actions copied from the script:

```text
plan
install
status
uninstall
```

Environment variables copied from the script:

```text
DREAM7B_BPU_QUEUE_POLL_INTERVAL_SEC
DREAM7B_BPU_QUEUE_MAX_BATCH_SIZE
DREAM7B_BPU_QUEUE_TOP_K
DREAM7B_BPU_QUEUE_LOCK_PATH
DREAM7B_BPU_QUEUE_REPO_DIR
DREAM7B_BPU_QUEUE_DRAIN_ALL
```

Default values copied from the script and verified by `install-dream7b-bpu-queue-service plan` on S100P:

```text
service: dream7b-bpu-batch-queue.service
service_path: /etc/systemd/system/dream7b-bpu-batch-queue.service
queue_dir: /mnt/nas/openclaw/queues/dream7b-bpu
output_dir: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd
poll_interval_sec: 1
max_batch_size: 16
top_k: 3
bpu_lock_path: /run/lock/dream7b_bpu_batch_queue_runner.lock
drain_all: true
working_directory: /mnt/nas/openclaw
```

Unit fields copied from `/etc/systemd/system/dream7b-bpu-batch-queue.service`:

```text
Description=Dream 7B BPU batch queue service
Documentation=file:///usr/local/bin/install-dream7b-bpu-queue-service
RequiresMountsFor=/mnt/nas/openclaw
WorkingDirectory=/mnt/nas/openclaw
Restart=always
RestartSec=5
ExecStart includes --max-batch-size 16
ExecStart includes --drain-all
```

### `dream7b-bpu-batch-queue-systemd-probe`

Source file: `scripts/probes/dream7b_bpu_batch_queue_systemd_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-batch-queue-systemd-probe
```

Default arguments copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
service_name = dream7b-bpu-batch-queue.service
```

Checked fields copied from the script:

```text
service_status
service_enabled
unit_path
exec_start
max_batch_size_required
drain_all_required
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_20260605-131550/systemd_probe.md
```

Latest live service summary after a real systemd-queued BPU job:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/service_summary.md
```

Latest real systemd-queued BPU job summary:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_job_20260603_220710/queue_summary.json
```

### `dream7b-bpu-batch-queue-systemd-soak-probe`

Source file: `scripts/probes/dream7b_bpu_batch_queue_systemd_soak_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-batch-queue-systemd-soak-probe
```

Default arguments copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
service_name = dream7b-bpu-batch-queue.service
queue_dir = /mnt/nas/openclaw/queues/dream7b-bpu
output_dir = /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd
```

Environment variables copied from the script:

```text
DREAM7B_BPU_SYSTEMD_SOAK_JOB_COUNT
DREAM7B_BPU_SYSTEMD_SOAK_TIMEOUT_SEC
DREAM7B_BPU_SYSTEMD_SOAK_POLL_INTERVAL_SEC
```

Default values copied from the script:

```text
job_count = 2
timeout_sec = 420
poll_interval_sec = 2
```

Checked fields copied from the script:

```text
service_status_before
service_enabled_before
service_status_after
service_enabled_after
completed_job_count
failed_job_count
processed_request_count
verdict
processed_count
final_shape
bpu_lock.path
execution_mode
window_execution_mode
child_process_count
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_soak_20260604-131223/systemd_soak_probe.md
```

Latest recorded job summaries:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_soak_20260604-131223_001/queue_summary.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_soak_20260604-131223_002/queue_summary.json
```

### `dream7b-bpu-batch-queue-systemd-batch-probe`

Source file: `scripts/probes/dream7b_bpu_batch_queue_systemd_batch_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-batch-queue-systemd-batch-probe
```

Default arguments copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
service_name = dream7b-bpu-batch-queue.service
queue_dir = /mnt/nas/openclaw/queues/dream7b-bpu
output_dir = /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd
```

Environment variables copied from the script:

```text
DREAM7B_BPU_SYSTEMD_BATCH_REQUEST_COUNT
DREAM7B_BPU_SYSTEMD_BATCH_TIMEOUT_SEC
DREAM7B_BPU_SYSTEMD_BATCH_POLL_INTERVAL_SEC
```

Default values copied from the script:

```text
request_count = 16
timeout_sec = 420
poll_interval_sec = 2
```

Checked fields copied from the script:

```text
service_status_before
service_enabled_before
service_status_after
service_enabled_after
job_status
request_count
processed_count
accepted_count
deferred_count
max_batch_size
batch_run_count
batch_count
result_count
final_shape
bpu_lock.path
execution_mode
window_execution_mode
child_process_count
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_batch_20260605-131550/systemd_batch_probe.md
```

Latest recorded batch job summary:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_batch_20260605-131550/queue_summary.json
```

### `dream7b-bpu-batch-queue-systemd-drain-probe`

Source file: `scripts/probes/dream7b_bpu_batch_queue_systemd_drain_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-batch-queue-systemd-drain-probe
```

Default arguments copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
service_name = dream7b-bpu-batch-queue.service
queue_dir = /mnt/nas/openclaw/queues/dream7b-bpu
output_dir = /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd
```

Environment variables copied from the script:

```text
DREAM7B_BPU_SYSTEMD_DRAIN_REQUEST_COUNT
DREAM7B_BPU_SYSTEMD_DRAIN_TIMEOUT_SEC
DREAM7B_BPU_SYSTEMD_DRAIN_POLL_INTERVAL_SEC
```

Default values copied from the script:

```text
request_count = 16
timeout_sec = 600
poll_interval_sec = 2
expected_max_batch_size = 16
```

Checked fields copied from the script:

```text
service_status_before
service_enabled_before
service_status_after
service_enabled_after
job_status
request_count
expected_batch_counts
drain_all
max_batch_size
processed_count
accepted_count
deferred_count
batch_run_count
batch_counts
result_count
final_shape
bpu_lock.path
execution_modes
window_execution_modes
child_process_counts
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_drain_20260605-131621/systemd_drain_probe.md
```

Latest recorded drain job summary:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_drain_20260605-131621/queue_summary.json
```

Latest recorded full-batch drain report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_drain_20260605-131621/systemd_drain_probe.md
```

Latest recorded full-batch drain job summary:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_drain_20260605-131621/queue_summary.json
```

### `dream7b-bpu-batch-queue-systemd-canary-probe`

Source file: `scripts/probes/dream7b_bpu_batch_queue_systemd_canary_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-batch-queue-systemd-canary-probe
```

Default arguments copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
service_name = dream7b-bpu-batch-queue.service
queue_dir = /mnt/nas/openclaw/queues/dream7b-bpu
output_dir = /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd
```

Environment variables copied from the script:

```text
DREAM7B_BPU_SYSTEMD_CANARY_REQUEST_COUNT
DREAM7B_BPU_SYSTEMD_CANARY_TIMEOUT_SEC
DREAM7B_BPU_SYSTEMD_CANARY_POLL_INTERVAL_SEC
```

Default values copied from the script:

```text
request_count = 1
timeout_sec = 180
poll_interval_sec = 2
```

Checked fields copied from the script:

```text
service_status_before
service_enabled_before
service_status_after
service_enabled_after
unit_path
exec_start
job_status
drain_all
max_batch_size
processed_count
accepted_count
deferred_count
skipped_count
batch_run_count
batch_count
result_count
execution_mode
window_execution_mode
child_process_count
bpu_lock_path
final_shapes
total_wall_ms
amortized_wall_ms_per_processed_request
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_canary_20260605-151715/systemd_canary_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_canary_20260605-151715/systemd_canary_probe.json
```

Latest recorded canary job summary:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_canary_20260605-151715/queue_summary.json
```

### `dream7b-bpu-batch-queue-systemd-telemetry-probe`

Source file: `scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-batch-queue-systemd-telemetry-probe
```

Default arguments copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
service_name = dream7b-bpu-batch-queue.service
queue_dir = /mnt/nas/openclaw/queues/dream7b-bpu
output_dir = /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd
```

Environment variables copied from the script:

```text
DREAM7B_BPU_SYSTEMD_TELEMETRY_JOB_COUNT
DREAM7B_BPU_SYSTEMD_TELEMETRY_REQUEST_COUNT
DREAM7B_BPU_SYSTEMD_TELEMETRY_TIMEOUT_SEC
DREAM7B_BPU_SYSTEMD_TELEMETRY_POLL_INTERVAL_SEC
DREAM7B_BPU_SYSTEMD_TELEMETRY_MONITOR_DELAY_MS
DREAM7B_BPU_SYSTEMD_TELEMETRY_MONITOR_SAMPLE_COUNT
```

Default values copied from the script:

```text
job_count = 3
request_count = 16
timeout_sec = 900
poll_interval_sec = 2
monitor_delay_ms = 100
monitor_sample_count = 1200
```

Telemetry commands copied from the script:

```text
hrt_ucp_monitor
hrut_somstatus
```

Checked fields copied from the script:

```text
service_status_before
service_enabled_before
service_status_after
service_enabled_after
job_count
request_count
expected_request_total
completed_job_count
failed_job_count
processed_request_count
accepted_request_count
deferred_request_count
result_count
batch_counts
total_wall_ms
total_load_ms
total_run_ms
amortized_wall_ms_per_processed_request
amortized_load_ms_per_processed_request
amortized_run_ms_per_processed_request
bpu_loading_sample_count
nonzero_bpu_loading_sample_count
max_bpu_loading
avg_bpu_loading
job_name
status
summary_path
runner_verdict
processed_count
batch_count
final_shape
bpu_lock.path
execution_mode
window_execution_mode
child_process_count
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_telemetry_20260605-133919/systemd_telemetry_probe.md
```

Latest recorded telemetry JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_telemetry_20260605-133919/systemd_telemetry_probe.json
```

Latest recorded queue job summaries:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_telemetry_20260605-133919_001/queue_summary.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_telemetry_20260605-133919_002/queue_summary.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_telemetry_20260605-133919_003/queue_summary.json
```

### `dream7b-bpu-batch-queue-retention-probe`

Source file: `scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-batch-queue-retention-probe
```

Default arguments copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
queue_dir = /mnt/nas/openclaw/queues/dream7b-bpu
```

Environment variables copied from the script:

```text
DREAM7B_BPU_QUEUE_RETENTION_DONE_DAYS
DREAM7B_BPU_QUEUE_RETENTION_FAILED_DAYS
DREAM7B_BPU_QUEUE_RETENTION_PENDING_STALE_MINUTES
DREAM7B_BPU_QUEUE_RETENTION_PROCESSING_STALE_MINUTES
DREAM7B_BPU_QUEUE_RETENTION_MAX_LIST
```

Default values copied from the script:

```text
done_retention_days = 14
failed_retention_days = 30
pending_stale_minutes = 60
processing_stale_minutes = 60
max_list = 50
policy_mode = report_only
apply_supported = False
```

Checked fields copied from the script:

```text
queue_counts
queue_size_bytes
pending_stale_count
processing_stale_count
done_archive_candidate_count
failed_archive_candidate_count
pending_stale
processing_stale
done_archive_candidates
failed_archive_candidates
archive_plan
warnings
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_retention_20260605-135448/queue_retention_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_retention_20260605-135448/queue_retention_probe.json
```

### `dream7b-bpu-text-queue-systemd-probe`

Source file: `scripts/probes/dream7b_bpu_text_queue_systemd_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-text-queue-systemd-probe
```

Environment variables copied from the script:

```text
DREAM7B_TOKENIZER_VENV
DREAM7B_TOKENIZER
DREAM7B_BPU_TEXT_QUEUE_PROMPT
DREAM7B_BPU_TEXT_QUEUE_FIT
DREAM7B_BPU_TEXT_QUEUE_SEQ_LEN
DREAM7B_BPU_TEXT_QUEUE_TIMEOUT_SEC
DREAM7B_BPU_TEXT_QUEUE_POLL_INTERVAL_SEC
DREAM7B_BPU_TEXT_QUEUE_SUBMIT_CMD
DREAM7B_BPU_TEXT_QUEUE_RUN_CMD
```

Default values copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
service_name = dream7b-bpu-batch-queue.service
queue_dir = /mnt/nas/openclaw/queues/dream7b-bpu
output_dir = /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd
tokenizer_venv = /mnt/nas/openclaw/runtimes/dream7b-tokenizer-venv
tokenizer_dir = /mnt/nas/openclaw/models/dream7b/tokenizer
prompt = hello
fit_mode = pad-right
seq_len = 16
timeout_sec = 180
poll_interval_sec = 2
submit_cmd = dream7b-bpu-text-queue-submit
run_cmd = dream7b-bpu-text-queue-run
```

Checked fields copied from the script:

```text
verdict
job_status
summary_path
run_cmd
run_json
run_md
run_stdout
run_stderr
run
run_verdict
submit_cmd
submit_json
submit_md
submit_stdout
submit_stderr
submit
tokenizer_venv
tokenizer_dir
tokenizer_json
request_id
processed_count
accepted_count
deferred_count
skipped_count
batch_run_count
batch_count
result_count
execution_mode
window_execution_mode
child_process_count
bpu_lock_path
final_shape
topk_last_position
durable_results_jsonl
total_wall_ms
amortized_wall_ms_per_processed_request
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260606-144634/text_queue_systemd_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260606-155148/text_queue_systemd_probe.json
```

Latest recorded run report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260606-155148/text_queue_run.md
```

Latest recorded run JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260606-155148/text_queue_run.json
```

Latest recorded submit report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260606-155148/text_queue_submit.md
```

Latest recorded submit JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260606-155148/text_queue_submit.json
```

Latest recorded tokenizer JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260606-155148/tokenizer_input.json
```

Latest recorded queue summary:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/text_queue_systemd_20260606-155148/queue_summary.json
```

Verified text queue systemd fields copied from `text_queue_systemd_probe.json`:

```text
verdict: ok_dream7b_bpu_text_queue_systemd_probe
run_cmd: dream7b-bpu-text-queue-run
run_verdict: ok_dream7b_bpu_text_queue_run
submit_cmd: dream7b-bpu-text-queue-submit
submit.verdict: ok_dream7b_bpu_text_queue_submit
job_status: done
request_id: text-queue-20260606-155148-001
processed_count: 1
accepted_count: 1
deferred_count: 0
skipped_count: 0
batch_run_count: 1
batch_count: 1
result_count: 1
execution_mode: pair_window_batch
window_execution_mode: window-batch
child_process_count: 0
bpu_lock_path: /run/lock/dream7b_bpu_batch_queue_runner.lock
final_shape: [1, 16, 152064]
topk_last_position: [{'token_id': 323, 'score': 1.7742547988891602}, {'token_id': 476, 'score': 1.0451929569244385}, {'token_id': 11, 'score': 0.8926413059234619}]
topk_last_position_decoded: [{'token_id': 323, 'score': 1.7742547988891602, 'token_text': ' and'}, {'token_id': 476, 'score': 1.0451929569244385, 'token_text': ' or'}, {'token_id': 11, 'score': 0.8926413059234619, 'token_text': ','}]
durable_results_jsonl: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/text_queue_systemd_20260606-155148/durable_state/results.jsonl
total_wall_ms: 24279.5
amortized_wall_ms_per_processed_request: 24279.5
tokenizer.tokenizer_dir: /mnt/nas/openclaw/models/dream7b/tokenizer
tokenizer.fit_mode: pad-right
tokenizer.seq_len: 16
tokenizer.original_token_count: 9
tokenizer.token_count: 16
errors: []
```

### `dream7b-bpu-deployment-acceptance-probe`

Source file: `scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-deployment-acceptance-probe
```

Default argument copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
```

Environment variables copied from the script:

```text
DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_CAPACITY
DREAM7B_BPU_ACCEPTANCE_MIN_SYSTEMD_BATCH_REQUESTS
DREAM7B_BPU_ACCEPTANCE_MIN_SYSTEMD_TELEMETRY_REQUESTS
DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_GENERATE_COUNT
DREAM7B_BPU_ACCEPTANCE_MIN_LONG_REPEAT_COUNT
DREAM7B_BPU_ACCEPTANCE_MAX_LONG_REPEAT_WALL_SPREAD_RATIO
```

Default values copied from the script:

```text
min_batch_capacity = 16
min_systemd_batch_requests = 16
min_systemd_telemetry_requests = 48
min_batch_generate_count = 8
min_long_repeat_count = 6
max_long_repeat_wall_spread_ratio = 0.10
```

Report globs copied from the script:

```text
dream7b_bpu_batch_queue_systemd_*/systemd_probe.json
dream7b_bpu_batch_capacity_*/batch_capacity_probe.json
dream7b_bpu_hbm_artifact_inventory_*/hbm_artifact_inventory_probe.json
dream7b_bpu_batch_queue_systemd_batch_*/systemd_batch_probe.json
dream7b_bpu_batch_queue_systemd_drain_*/systemd_drain_probe.json
dream7b_bpu_batch_queue_systemd_canary_*/systemd_canary_probe.json
dream7b_bpu_text_queue_run_*/text_queue_run.json
dream7b_bpu_text_queue_systemd_*/text_queue_systemd_probe.json
dream7b_bpu_diffusion_generate_*/generation.json
dream7b_bpu_diffusion_generate_telemetry_*/generation_telemetry_probe.json
dream7b_bpu_diffusion_batch_generate_telemetry_*/batch_generation_telemetry_probe.json
dream7b_bpu_batch_queue_systemd_telemetry_*/systemd_telemetry_probe.json
dream7b_bpu_fine_forward_long_repeat_*/long_repeat_probe.json
dream7b_bpu_batch_queue_retention_*/queue_retention_probe.json
```

Check names copied from the script:

```text
systemd_service
batch_capacity
hbm_artifact_inventory
systemd_batch
systemd_drain
systemd_canary
text_queue_run
text_queue_systemd
diffusion_generate
diffusion_generate_telemetry
diffusion_batch_generate_telemetry
systemd_telemetry
long_repeat
queue_retention
```

Output fields copied from the script:

```text
generated_at
verdict
report_root
run_dir
min_batch_capacity
min_systemd_batch_requests
min_systemd_telemetry_requests
min_batch_generate_count
min_long_repeat_count
max_long_repeat_wall_spread_ratio
check_count
passed_check_count
checks
warnings
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-143759/deployment_acceptance_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-153747/deployment_acceptance_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-161000/deployment_acceptance_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-172156/deployment_acceptance_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-134314/deployment_acceptance_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-142559/deployment_acceptance_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-144721/deployment_acceptance_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-155233/deployment_acceptance_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-161252/deployment_acceptance_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-165607/deployment_acceptance_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-182851/deployment_acceptance_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-143759/deployment_acceptance_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-153747/deployment_acceptance_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-161000/deployment_acceptance_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-172156/deployment_acceptance_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-134314/deployment_acceptance_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-142559/deployment_acceptance_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-144721/deployment_acceptance_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-155233/deployment_acceptance_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-161252/deployment_acceptance_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-165607/deployment_acceptance_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-182851/deployment_acceptance_probe.json
```

Verified deployment acceptance fields copied from `deployment_acceptance_probe.json`:

```text
verdict: ok_dream7b_bpu_deployment_acceptance_probe
check_count: 14
passed_check_count: 14
min_batch_capacity: 16
min_systemd_batch_requests: 16
min_systemd_telemetry_requests: 48
min_batch_generate_count: 8
min_long_repeat_count: 6
max_long_repeat_wall_spread_ratio: 0.1
warnings: []
errors: []
systemd_service.ok: True
batch_capacity.ok: True
hbm_artifact_inventory.ok: True
systemd_batch.ok: True
systemd_drain.ok: True
systemd_canary.ok: True
text_queue_run.ok: True
text_queue_systemd.ok: True
diffusion_generate.ok: True
diffusion_generate_telemetry.ok: True
diffusion_batch_generate_telemetry.ok: True
systemd_telemetry.ok: True
long_repeat.ok: True
queue_retention.ok: True
systemd_canary.details.job_status: done
systemd_canary.details.request_count: 1
systemd_canary.details.processed_count: 1
systemd_canary.details.final_shapes: [[1, 16, 152064]]
text_queue_run.details.submit_cmd: dream7b-bpu-text-queue-submit
text_queue_run.details.submit_verdict: ok_dream7b_bpu_text_queue_submit
text_queue_run.details.request_id: text_queue_run_20260606-155102-001
text_queue_run.details.tokenizer_dir: /mnt/nas/openclaw/models/dream7b/tokenizer
text_queue_run.details.fit_mode: pad-right
text_queue_run.details.original_token_count: 9
text_queue_run.details.token_count: 16
text_queue_run.details.final_shape: [1, 16, 152064]
text_queue_run.details.topk_last_position: [{'token_id': 323, 'score': 1.7742547988891602}, {'token_id': 476, 'score': 1.0451929569244385}, {'token_id': 11, 'score': 0.8926413059234619}]
text_queue_run.details.topk_last_position_decoded: [{'token_id': 323, 'score': 1.7742547988891602, 'token_text': ' and'}, {'token_id': 476, 'score': 1.0451929569244385, 'token_text': ' or'}, {'token_id': 11, 'score': 0.8926413059234619, 'token_text': ','}]
text_queue_systemd.details.run_cmd: dream7b-bpu-text-queue-run
text_queue_systemd.details.run_verdict: ok_dream7b_bpu_text_queue_run
text_queue_systemd.details.submit_cmd: dream7b-bpu-text-queue-submit
text_queue_systemd.details.submit_verdict: ok_dream7b_bpu_text_queue_submit
text_queue_systemd.details.request_id: text-queue-20260606-155148-001
text_queue_systemd.details.tokenizer_dir: /mnt/nas/openclaw/models/dream7b/tokenizer
text_queue_systemd.details.fit_mode: pad-right
text_queue_systemd.details.original_token_count: 9
text_queue_systemd.details.token_count: 16
text_queue_systemd.details.final_shape: [1, 16, 152064]
text_queue_systemd.details.topk_last_position: [{'token_id': 323, 'score': 1.7742547988891602}, {'token_id': 476, 'score': 1.0451929569244385}, {'token_id': 11, 'score': 0.8926413059234619}]
text_queue_systemd.details.topk_last_position_decoded: [{'token_id': 323, 'score': 1.7742547988891602, 'token_text': ' and'}, {'token_id': 476, 'score': 1.0451929569244385, 'token_text': ' or'}, {'token_id': 11, 'score': 0.8926413059234619, 'token_text': ','}]
diffusion_generate.details.verdict: ok_dream7b_bpu_diffusion_generate
diffusion_generate.details.forward_cmd: dream7b-bpu-fine-forward
diffusion_generate.details.seq_len: 16
diffusion_generate.details.steps: 2
diffusion_generate.details.executed_step_count: 2
diffusion_generate.details.remaining_mask_positions: []
diffusion_generate.details.decoded_final: <|im_start|>user
hello<|im_end|>
<|im_start|>assistant
osaosa and and and and and
diffusion_generate.details.boundary: bounded_seq16_generation_entrypoint_not_complete_production_text_service
diffusion_generate_telemetry.path: /mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_generate_telemetry_20260606-163625/generation_telemetry_probe.json
diffusion_generate_telemetry.details.verdict: ok_dream7b_bpu_diffusion_generate_telemetry_probe
diffusion_generate_telemetry.details.generate_cmd: dream7b-bpu-diffusion-generate
diffusion_generate_telemetry.details.generation_status: 0
diffusion_generate_telemetry.details.max_bpu_loading: 38.0
diffusion_generate_telemetry.details.avg_bpu_loading: 0.637
diffusion_generate_telemetry.details.nonzero_bpu_loading_sample_count: 14
diffusion_generate_telemetry.details.generation_verdict: ok_dream7b_bpu_diffusion_generate
diffusion_generate_telemetry.details.forward_cmd: dream7b-bpu-fine-forward
diffusion_generate_telemetry.details.seq_len: 16
diffusion_generate_telemetry.details.executed_step_count: 2
diffusion_generate_telemetry.details.remaining_mask_positions: []
diffusion_generate_telemetry.details.decoded_final: <|im_start|>user
hello<|im_end|>
<|im_start|>assistant
osaosa and and and and and
diffusion_generate_telemetry.details.boundary: bounded_seq16_generation_entrypoint_not_complete_production_text_service
diffusion_batch_generate_telemetry.path: /mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_batch_generate_telemetry_20260606-181845/batch_generation_telemetry_probe.json
diffusion_batch_generate_telemetry.details.verdict: ok_dream7b_bpu_diffusion_batch_generate_telemetry_probe
diffusion_batch_generate_telemetry.details.generate_cmd: dream7b-bpu-diffusion-batch-generate
diffusion_batch_generate_telemetry.details.generation_status: 0
diffusion_batch_generate_telemetry.details.batch_count: 8
diffusion_batch_generate_telemetry.details.max_bpu_loading: 100.0
diffusion_batch_generate_telemetry.details.avg_bpu_loading: 4.998
diffusion_batch_generate_telemetry.details.nonzero_bpu_loading_sample_count: 39
diffusion_batch_generate_telemetry.details.generation_verdict: ok_dream7b_bpu_diffusion_batch_generate
diffusion_batch_generate_telemetry.details.forward_cmd: dream7b-bpu-fine-batch-forward
diffusion_batch_generate_telemetry.details.seq_len: 16
diffusion_batch_generate_telemetry.details.executed_step_count: 2
diffusion_batch_generate_telemetry.details.forward_batch_counts: [8, 8]
diffusion_batch_generate_telemetry.details.boundary: bounded_seq16_batch_generation_entrypoint_not_complete_production_text_service
hbm_artifact_inventory.details.expected_artifact_count: 14
hbm_artifact_inventory.details.nas_existing_count: 14
hbm_artifact_inventory.details.local_existing_count: 14
hbm_artifact_inventory.details.size_match_count: 14
hbm_artifact_inventory.details.manifest_verified_count: 12
systemd_telemetry.details.max_bpu_loading: 100.0
systemd_telemetry.details.avg_bpu_loading: 9.616
queue_retention.details.queue_counts: {'pending': 0, 'processing': 0, 'done': 13, 'failed': 1}
```

### `dream7b-bpu-diffusion-generate`

Source file: `scripts/dream7b-bpu-diffusion-generate.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-diffusion-generate
```

Environment variables copied from the script:

```text
DREAM7B_TOKENIZER_VENV
DREAM7B_TOKENIZER
DREAM7B_BPU_DIFFUSION_GENERATE_REPORT_ROOT
DREAM7B_BPU_DIFFUSION_GENERATE_RUN_DIR
DREAM7B_BPU_DIFFUSION_GENERATE_SEQ_LEN
DREAM7B_BPU_DIFFUSION_GENERATE_MIN_MASK_COUNT
DREAM7B_BPU_DIFFUSION_GENERATE_STEPS
DREAM7B_BPU_DIFFUSION_GENERATE_TOP_K
DREAM7B_BPU_DIFFUSION_GENERATE_EPS
DREAM7B_BPU_DIFFUSION_GENERATE_REMASKING
DREAM7B_BPU_DIFFUSION_GENERATE_TEMP
DREAM7B_BPU_DIFFUSION_GENERATE_SEED
DREAM7B_BPU_DIFFUSION_GENERATE_ENTROPY_THRESHOLD
DREAM7B_BPU_DIFFUSION_GENERATE_FORWARD_CMD
```

Default values copied from the script:

```text
tokenizer_venv = /mnt/nas/openclaw/runtimes/dream7b-tokenizer-venv
tokenizer_dir = /mnt/nas/openclaw/models/dream7b/tokenizer
report_root = /mnt/nas/openclaw/reports/models
run_dir_override =
seq_len = 16
min_mask_count = 4
steps = 2
top_k = 5
eps = 0.001
remasking = entropy_exit
temperature = 0
seed = 42
entropy_threshold = 1.5
forward_cmd = dream7b-bpu-fine-forward
```

Usage copied from the script:

```text
dream7b-bpu-diffusion-generate [--report-root DIR] [--run-dir DIR] [--seq-len 16] [--min-mask-count N] [--steps N] [--top-k N] [--eps FLOAT] [--remasking low_confidence|entropy_exit|maskgit_plus|topk_margin|entropy] [--temperature FLOAT] [--seed N] [--entropy-threshold FLOAT] [--forward-cmd CMD] [--prompt TEXT|--prompt-file FILE] [--] prompt text
```

Supported `DREAM7B_BPU_DIFFUSION_GENERATE_REMASKING` values copied from the script:

```text
low_confidence
entropy_exit
maskgit_plus
topk_margin
entropy
```

Output files copied from the script:

```text
generation.json
generation.md
step_00/forward/summary.json
step_00/forward/logits.npy
step_01/forward/summary.json
step_01/forward/logits.npy
```

Generation fields copied from the script:

```text
verdict
run_dir
tokenizer_dir
prompt
prepared_prompt
seq_len
steps
executed_step_count
eps
top_k
remasking
temperature
seed
entropy_threshold
forward_cmd
fit_mode
prompt_token_count
prefix_token_count
mask_token_id
initial_tokens
final_tokens
remaining_mask_positions
decoded_final
history
forward_summary_count
logits_shift
boundary
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_generate_20260606-161120/generation.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_generate_20260606-161120/generation.json
```

Verified bounded generation fields copied from `generation.json`:

```text
verdict: ok_dream7b_bpu_diffusion_generate
forward_cmd: dream7b-bpu-fine-forward
prompt: hello
seq_len: 16
steps: 2
executed_step_count: 2
top_k: 5
remasking: entropy_exit
temperature: 0.0
seed: 42
entropy_threshold: 1.5
fit_mode: natural_prompt_then_masks
prompt_token_count: 9
prefix_token_count: 9
mask_token_id: 151666
remaining_mask_positions: []
decoded_final: <|im_start|>user
hello<|im_end|>
<|im_start|>assistant
osaosa and and and and and
history[0].forward_verdict: ok_dream7b_segmented_hbm_python_forward
history[0].forward_summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_generate_20260606-161120/step_00/forward/summary.json
history[0].forward_execution_mode: pair_in_process
history[0].forward_window_execution_mode: in-process
history[0].forward_child_process_count: 0
history[0].forward_final_shape: [1, 16, 152064]
history[1].forward_verdict: ok_dream7b_segmented_hbm_python_forward
history[1].forward_summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_generate_20260606-161120/step_01/forward/summary.json
history[1].forward_execution_mode: pair_in_process
history[1].forward_window_execution_mode: in-process
history[1].forward_child_process_count: 0
history[1].forward_final_shape: [1, 16, 152064]
forward_summary_count: 2
boundary: bounded_seq16_generation_entrypoint_not_complete_production_text_service
errors: []
```

### `dream7b-bpu-diffusion-batch-generate`

Source file: `scripts/dream7b-bpu-diffusion-batch-generate.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-diffusion-batch-generate
```

Environment variables copied from the script:

```text
DREAM7B_TOKENIZER_VENV
DREAM7B_TOKENIZER
DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_REPORT_ROOT
DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_RUN_DIR
DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_BATCH_COUNT
DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SEQ_LEN
DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_MIN_MASK_COUNT
DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_STEPS
DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_TOP_K
DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_EPS
DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_REMASKING
DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_TEMP
DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SEED
DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_ENTROPY_THRESHOLD
DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_FORWARD_CMD
```

Default values copied from the script:

```text
tokenizer_venv = /mnt/nas/openclaw/runtimes/dream7b-tokenizer-venv
tokenizer_dir = /mnt/nas/openclaw/models/dream7b/tokenizer
report_root = /mnt/nas/openclaw/reports/models
run_dir_override =
batch_count = 8
seq_len = 16
min_mask_count = 4
steps = 2
top_k = 5
eps = 0.001
remasking = entropy_exit
temperature = 0
seed = 42
entropy_threshold = 1.5
forward_cmd = dream7b-bpu-fine-batch-forward
```

Usage copied from the script:

```text
dream7b-bpu-diffusion-batch-generate [--report-root DIR] [--run-dir DIR] [--batch-count N] [--seq-len 16] [--min-mask-count N] [--steps N] [--top-k N] [--eps FLOAT] [--remasking low_confidence|entropy_exit|maskgit_plus|topk_margin|entropy] [--temperature FLOAT] [--seed N] [--entropy-threshold FLOAT] [--forward-cmd CMD] [--prompts-json FILE|--prompts-jsonl FILE|--prompt TEXT ...]
```

Prompt input formats copied from the script:

```text
--prompts-json
--prompts-jsonl
--prompt
built_in_defaults
```

Output files copied from the script:

```text
batch_generation.json
batch_generation.md
step_00/tokens_batch.json
step_00/forward/summary.json
step_00/forward/logits_batch_000.npy
step_01/tokens_batch.json
step_01/forward/summary.json
step_01/forward/logits_batch_000.npy
```

Batch generation fields copied from the script:

```text
verdict
run_dir
tokenizer_dir
prompt_source
batch_count
seq_len
steps
executed_step_count
eps
top_k
remasking
temperature
seed
entropy_threshold
forward_cmd
mask_token_id
remaining_mask_positions_by_batch
decoded_final_by_batch
samples
history
forward_summary_count
forward_batch_counts
logits_shift
boundary
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_batch_generate_telemetry_20260606-181845/generation/batch_generation.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_batch_generate_telemetry_20260606-181845/generation/batch_generation.json
```

Verified bounded batch generation fields copied from `batch_generation.json` through `batch_generation_telemetry_probe.json`:

```text
verdict: ok_dream7b_bpu_diffusion_batch_generate
forward_cmd: dream7b-bpu-fine-batch-forward
batch_count: 8
seq_len: 16
steps: 2
executed_step_count: 2
forward_batch_counts: [8, 8]
remaining_mask_positions_by_batch: [{'batch_index': 0, 'remaining_mask_positions': []}, {'batch_index': 1, 'remaining_mask_positions': []}, {'batch_index': 2, 'remaining_mask_positions': []}, {'batch_index': 3, 'remaining_mask_positions': []}, {'batch_index': 4, 'remaining_mask_positions': []}, {'batch_index': 5, 'remaining_mask_positions': []}, {'batch_index': 6, 'remaining_mask_positions': []}, {'batch_index': 7, 'remaining_mask_positions': []}]
history[0].forward_verdict: ok_dream7b_segmented_hbm_python_forward
history[0].forward_execution_mode: pair_window_batch
history[0].forward_window_execution_mode: window-batch
history[0].forward_child_process_count: 0
history[0].forward_batch_count: 8
history[1].forward_verdict: ok_dream7b_segmented_hbm_python_forward
history[1].forward_execution_mode: pair_window_batch
history[1].forward_window_execution_mode: window-batch
history[1].forward_child_process_count: 0
history[1].forward_batch_count: 8
boundary: bounded_seq16_batch_generation_entrypoint_not_complete_production_text_service
errors: []
```

### `dream7b-bpu-diffusion-generate-telemetry-probe`

Source file: `scripts/probes/dream7b_bpu_diffusion_generate_telemetry_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-diffusion-generate-telemetry-probe
```

Default argument copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
```

Environment variables copied from the script:

```text
DREAM7B_BPU_DIFFUSION_GENERATE_TELEMETRY_PROMPT
DREAM7B_BPU_DIFFUSION_GENERATE_TELEMETRY_CMD
DREAM7B_BPU_DIFFUSION_GENERATE_TELEMETRY_MONITOR_DELAY_MS
DREAM7B_BPU_DIFFUSION_GENERATE_TELEMETRY_MONITOR_SAMPLE_COUNT
DREAM7B_BPU_DIFFUSION_GENERATE_TELEMETRY_TIMEOUT_SEC
```

Default values copied from the script:

```text
prompt = hello
generate_cmd = dream7b-bpu-diffusion-generate
monitor_delay_ms = 100
monitor_sample_count = 900
timeout_sec = 900
```

Output files copied from the script:

```text
generation_telemetry_probe.json
generation_telemetry_probe.md
hrt_ucp_monitor.stdout
hrt_ucp_monitor.stderr
generation.stdout
generation.stderr
hrut_somstatus_before.txt
hrut_somstatus_after.txt
generation/generation.json
generation/generation.md
```

Output fields copied from the script:

```text
generated_at
verdict
run_dir
generation_dir
prompt
generate_cmd
monitor_delay_ms
monitor_sample_count
timeout_sec
generation_status
generation_json
generation_md
bpu_loading_sample_count
nonzero_bpu_loading_sample_count
max_bpu_loading
avg_bpu_loading
generation_metrics
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_generate_telemetry_20260606-163625/generation_telemetry_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_generate_telemetry_20260606-163625/generation_telemetry_probe.json
```

Verified generation telemetry fields copied from `generation_telemetry_probe.json`:

```text
verdict: ok_dream7b_bpu_diffusion_generate_telemetry_probe
run_dir: /mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_generate_telemetry_20260606-163625
generation_dir: /mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_generate_telemetry_20260606-163625/generation
prompt: hello
generate_cmd: dream7b-bpu-diffusion-generate
monitor_delay_ms: 100
monitor_sample_count: 900
generation_status: 0
generation_json: /mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_generate_telemetry_20260606-163625/generation/generation.json
bpu_loading_sample_count: 509
nonzero_bpu_loading_sample_count: 14
max_bpu_loading: 38.0
avg_bpu_loading: 0.637
generation_metrics.verdict: ok_dream7b_bpu_diffusion_generate
generation_metrics.forward_cmd: dream7b-bpu-fine-forward
generation_metrics.seq_len: 16
generation_metrics.steps: 2
generation_metrics.executed_step_count: 2
generation_metrics.remaining_mask_positions: []
generation_metrics.decoded_final: <|im_start|>user
hello<|im_end|>
<|im_start|>assistant
osaosa and and and and and
generation_metrics.boundary: bounded_seq16_generation_entrypoint_not_complete_production_text_service
generation_metrics.history_forward_verdicts: ['ok_dream7b_segmented_hbm_python_forward', 'ok_dream7b_segmented_hbm_python_forward']
generation_metrics.history_forward_execution_modes: ['pair_in_process', 'pair_in_process']
generation_metrics.history_forward_window_execution_modes: ['in-process', 'in-process']
generation_metrics.history_forward_child_process_counts: [0, 0]
generation_metrics.history_forward_final_shapes: [[1, 16, 152064], [1, 16, 152064]]
errors: []
```

### `dream7b-bpu-diffusion-batch-generate-telemetry-probe`

Source file: `scripts/probes/dream7b_bpu_diffusion_batch_generate_telemetry_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-diffusion-batch-generate-telemetry-probe
```

Default argument copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
```

Environment variables copied from the script:

```text
DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_TELEMETRY_BATCH_COUNT
DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_TELEMETRY_CMD
DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_TELEMETRY_MONITOR_DELAY_MS
DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_TELEMETRY_MONITOR_SAMPLE_COUNT
DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_TELEMETRY_TIMEOUT_SEC
```

Default values copied from the script:

```text
batch_count = 8
generate_cmd = dream7b-bpu-diffusion-batch-generate
monitor_delay_ms = 100
monitor_sample_count = 900
timeout_sec = 900
```

Output files copied from the script:

```text
batch_generation_telemetry_probe.json
batch_generation_telemetry_probe.md
hrt_ucp_monitor.stdout
hrt_ucp_monitor.stderr
generation.stdout
generation.stderr
hrut_somstatus_before.txt
hrut_somstatus_after.txt
generation/batch_generation.json
generation/batch_generation.md
```

Output fields copied from the script:

```text
generated_at
verdict
run_dir
generation_dir
batch_count
generate_cmd
monitor_delay_ms
monitor_sample_count
timeout_sec
generation_status
generation_json
generation_md
bpu_loading_sample_count
nonzero_bpu_loading_sample_count
max_bpu_loading
avg_bpu_loading
generation_metrics
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_batch_generate_telemetry_20260606-181845/batch_generation_telemetry_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_batch_generate_telemetry_20260606-181845/batch_generation_telemetry_probe.json
```

Verified batch generation telemetry fields copied from `batch_generation_telemetry_probe.json`:

```text
verdict: ok_dream7b_bpu_diffusion_batch_generate_telemetry_probe
run_dir: /mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_batch_generate_telemetry_20260606-181845
generation_dir: /mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_batch_generate_telemetry_20260606-181845/generation
batch_count: 8
generate_cmd: dream7b-bpu-diffusion-batch-generate
monitor_delay_ms: 100
monitor_sample_count: 900
generation_status: 0
generation_json: /mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_batch_generate_telemetry_20260606-181845/generation/batch_generation.json
bpu_loading_sample_count: 553
nonzero_bpu_loading_sample_count: 39
max_bpu_loading: 100.0
avg_bpu_loading: 4.998
generation_metrics.verdict: ok_dream7b_bpu_diffusion_batch_generate
generation_metrics.forward_cmd: dream7b-bpu-fine-batch-forward
generation_metrics.batch_count: 8
generation_metrics.seq_len: 16
generation_metrics.steps: 2
generation_metrics.executed_step_count: 2
generation_metrics.forward_batch_counts: [8, 8]
generation_metrics.remaining_mask_positions_by_batch: [{'batch_index': 0, 'remaining_mask_positions': []}, {'batch_index': 1, 'remaining_mask_positions': []}, {'batch_index': 2, 'remaining_mask_positions': []}, {'batch_index': 3, 'remaining_mask_positions': []}, {'batch_index': 4, 'remaining_mask_positions': []}, {'batch_index': 5, 'remaining_mask_positions': []}, {'batch_index': 6, 'remaining_mask_positions': []}, {'batch_index': 7, 'remaining_mask_positions': []}]
generation_metrics.boundary: bounded_seq16_batch_generation_entrypoint_not_complete_production_text_service
generation_metrics.history_forward_verdicts: ['ok_dream7b_segmented_hbm_python_forward', 'ok_dream7b_segmented_hbm_python_forward']
generation_metrics.history_forward_execution_modes: ['pair_window_batch', 'pair_window_batch']
generation_metrics.history_forward_window_execution_modes: ['window-batch', 'window-batch']
generation_metrics.history_forward_child_process_counts: [0, 0]
generation_metrics.history_forward_batch_counts: [8, 8]
errors: []
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

### `dream7b-bpu-fine-forward-long-repeat-probe`

Source file: `scripts/probes/dream7b_bpu_fine_forward_long_repeat_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-fine-forward-long-repeat-probe
```

Environment variables copied from the script:

```text
DREAM7B_BPU_FINE_FORWARD_LONG_REPEAT_COUNT
DREAM7B_BPU_FINE_FORWARD_LONG_REPEAT_MAX_WALL_SPREAD_RATIO
```

Default values copied from the script:

```text
repeat_count = 6
max_wall_spread_ratio = 0.10
```

Checked fields copied from the script:

```text
repeat_status
repeat_summary_md
repeat_summary_json
failure_count
median_wall_ms
median_load_ms
median_run_ms
min_wall_ms
max_wall_ms
wall_spread_ratio
max_wall_spread_ratio
execution_mode
window_execution_mode
child_process_count
segment_count
final_shape
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_long_repeat_20260605-140733/long_repeat_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_long_repeat_20260605-163343/long_repeat_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_long_repeat_20260605-140733/long_repeat_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_long_repeat_20260605-163343/long_repeat_probe.json
```

Latest recorded child repeat summary:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_long_repeat_20260605-140733/repeat/dream7b_bpu_fine_forward_repeat_20260605-140733/summary.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_long_repeat_20260605-163343/repeat/dream7b_bpu_fine_forward_repeat_20260605-163343/summary.json
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
/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_size_sweep_20260604-181429/batch_size_sweep_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_runtime_telemetry_20260604-225030/runtime_telemetry_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_runtime_telemetry_20260604-225030/forward/summary.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_capacity_20260605-123835/batch_capacity_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_runtime_telemetry_20260605-132014/runtime_telemetry_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_runner_20260603-193243/batch_queue_runner_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_drain_20260603-193309/batch_queue_drain_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_control_20260603-193400/batch_queue_control_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_lock_20260603-193209/batch_queue_lock_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_20260603-194437/batch_queue_service_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_real_scp_20260603-194827/output/service_summary.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_20260603-183906/fine_forward_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_loop_20260603-175030/summary.md
```

Verified batch-size sweep fields copied from `batch_size_sweep_probe.json`:

```text
verdict: ok_dream7b_bpu_fine_batch_size_sweep_probe
counts: [1, 2, 4, 8]
batch_count 1 amortized_wall_ms_per_forward: 24562.798
batch_count 1 amortized_load_ms_per_forward: 24198.434
batch_count 1 amortized_run_ms_per_forward: 175.949
batch_count 2 amortized_wall_ms_per_forward: 12293.305
batch_count 2 amortized_load_ms_per_forward: 12022.294
batch_count 2 amortized_run_ms_per_forward: 175.037
batch_count 4 amortized_wall_ms_per_forward: 6336.077
batch_count 4 amortized_load_ms_per_forward: 6111.385
batch_count 4 amortized_run_ms_per_forward: 173.981
batch_count 8 amortized_wall_ms_per_forward: 3175.416
batch_count 8 amortized_load_ms_per_forward: 2974.35
batch_count 8 amortized_run_ms_per_forward: 173.565
```

Verified batch capacity fields copied from `batch_capacity_probe.json`:

```text
verdict: ok_dream7b_bpu_batch_capacity_probe
counts: [8, 12, 16]
max_passing_count: 16
batch_count 8 amortized_wall_ms_per_forward: 3197.161
batch_count 8 amortized_load_ms_per_forward: 2996.019
batch_count 8 amortized_run_ms_per_forward: 173.652
batch_count 12 amortized_wall_ms_per_forward: 2188.664
batch_count 12 amortized_load_ms_per_forward: 1995.449
batch_count 12 amortized_run_ms_per_forward: 173.423
batch_count 16 amortized_wall_ms_per_forward: 1714.647
batch_count 16 amortized_load_ms_per_forward: 1525.35
batch_count 16 amortized_run_ms_per_forward: 173.253
```

Verified runtime telemetry fields copied from `runtime_telemetry_probe.json`:

```text
verdict: ok_dream7b_bpu_runtime_telemetry_probe
batch_count: 16
monitor_delay_ms: 100
monitor_sample_count: 320
bpu_loading_sample_count: 320
nonzero_bpu_loading_sample_count: 35
max_bpu_loading: 100.0
avg_bpu_loading: 8.45
forward execution_mode: pair_window_batch
forward window_execution_mode: window-batch
forward child_process_count: 0
forward wall_ms: 26369.124
forward load_ms: 23336.624
forward run_ms: 2778.412
forward amortized_wall_ms_per_forward: 1648.07
forward amortized_load_ms_per_forward: 1458.539
forward amortized_run_ms_per_forward: 173.651
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

Decision: use `dream7b-bpu-batch-queue-service` as the reusable directory-backed service loop. It consumes `*.jsonl` jobs from `pending`, moves active jobs to `processing`, moves successful jobs to `done`, moves failed jobs to `failed`, refreshes `service_summary.json` and `service_summary.md` during each loop iteration, and calls `dream7b-bpu-batch-queue-runner` for each job so the existing `durable_state` and `bpu_lock` behavior remains authoritative.

Evidence reports:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_20260603-194437/batch_queue_service_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_real_scp_20260603-194827/output/service_summary.md
```

Boundary: this is a long-running-capable command loop. The systemd unit is recorded in the next decision section.

### Use systemd supervision for the NAS-backed Dream 7B queue

Decision: install `dream7b-bpu-batch-queue.service` on S100P with `RequiresMountsFor=/mnt/nas/openclaw`, `WorkingDirectory=/mnt/nas/openclaw`, queue directory `/mnt/nas/openclaw/queues/dream7b-bpu`, output directory `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd`, BPU lock path `/run/lock/dream7b_bpu_batch_queue_runner.lock`, default `--max-batch-size 16` through `DREAM7B_BPU_QUEUE_MAX_BATCH_SIZE`, and default `--drain-all` enabled through `DREAM7B_BPU_QUEUE_DRAIN_ALL`.

Reason: the NAS+S100P product path should not depend on the Windows PC. The first queued systemd job exposed a real `/tmp/dream7b_bpu_batch_queue_runner.lock` permission failure, so the systemd default lock path was moved to `/run/lock/dream7b_bpu_batch_queue_runner.lock`, which is allowed by `scripts/dream7b_bpu_batch_queue_runner.py`.

Evidence reports:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_20260603-221324/systemd_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/service_summary.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_job_20260603_220710/queue_summary.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_soak_20260604-131223/systemd_soak_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_soak_20260604-131223_001/queue_summary.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_soak_20260604-131223_002/queue_summary.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_batch_20260604-133034/systemd_batch_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_batch_20260604-133034/queue_summary.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_20260604-174953/systemd_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_drain_20260604-174953/systemd_drain_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_drain_20260604-174953/queue_summary.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_drain_20260604-180557/systemd_drain_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_drain_20260604-180557/queue_summary.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_20260604-233926/systemd_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_batch_20260604-235205/systemd_batch_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_batch_20260604-235205/queue_summary.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_drain_20260604-235302/systemd_drain_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_drain_20260604-235302/queue_summary.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_20260605-131550/systemd_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_batch_20260605-131550/systemd_batch_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_batch_20260605-131550/queue_summary.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_drain_20260605-131621/systemd_drain_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_drain_20260605-131621/queue_summary.json
```

Verified job fields copied from `queue_summary.json`:

```text
verdict: ok_dream7b_bpu_batch_queue_runner
request_id: systemd-req-001
processed_count: 1
final_shape: [1, 16, 152064]
bpu_lock.path: /run/lock/dream7b_bpu_batch_queue_runner.lock
execution_mode: pair_window_batch
window_execution_mode: window-batch
child_process_count: 0
```

Verified soak fields copied from `systemd_soak_probe.json`:

```text
verdict: ok_dream7b_bpu_batch_queue_systemd_soak_probe
job_count: 2
service_status_before: active
service_status_after: active
completed_job_count: 2
failed_job_count: 0
processed_request_count: 2
total_wall_ms: 49192.894
amortized_wall_ms_per_processed_request: 24596.447
```

Verified batch fields copied from `systemd_batch_probe.json`:

```text
verdict: ok_dream7b_bpu_batch_queue_systemd_batch_probe
job_name: systemd_batch_20260604-133034.jsonl
job_status: done
request_count: 4
processed_count: 4
accepted_count: 4
deferred_count: 0
batch_count: 4
result_count: 4
execution_mode: pair_window_batch
window_execution_mode: window-batch
child_process_count: 0
total_wall_ms: 24977.437
amortized_wall_ms_per_processed_request: 6244.359
```

Verified drain-all systemd fields copied from `systemd_drain_probe.json`:

```text
verdict: ok_dream7b_bpu_batch_queue_systemd_drain_probe
job_name: systemd_drain_20260604-174953.jsonl
job_status: done
request_count: 5
expected_batch_counts: [4, 1]
drain_all: True
max_batch_size: 4
processed_count: 5
accepted_count: 5
deferred_count: 0
batch_run_count: 2
batch_counts: [4, 1]
result_count: 5
execution_modes: ['pair_window_batch', 'pair_window_batch']
window_execution_modes: ['window-batch', 'window-batch']
child_process_counts: [0, 0]
total_wall_ms: 49773.849
amortized_wall_ms_per_processed_request: 9954.77
```

Verified full-batch drain-all systemd fields copied from `systemd_drain_probe.json`:

```text
verdict: ok_dream7b_bpu_batch_queue_systemd_drain_probe
job_name: systemd_drain_20260604-180557.jsonl
job_status: done
request_count: 8
expected_batch_counts: [4, 4]
drain_all: True
max_batch_size: 4
processed_count: 8
accepted_count: 8
deferred_count: 0
batch_run_count: 2
batch_counts: [4, 4]
result_count: 8
execution_modes: ['pair_window_batch', 'pair_window_batch']
window_execution_modes: ['window-batch', 'window-batch']
child_process_counts: [0, 0]
total_wall_ms: 49509.638
amortized_wall_ms_per_processed_request: 6188.705
```

Verified current max-batch-size-8 systemd fields copied from `systemd_probe.json`:

```text
verdict: ok_dream7b_bpu_batch_queue_systemd_probe
service_status: active
service_enabled: enabled
max_batch_size_required: 8
drain_all_required: True
exec_start includes: --max-batch-size 8
exec_start includes: --drain-all
```

Verified current eight-request systemd batch fields copied from `systemd_batch_probe.json`:

```text
verdict: ok_dream7b_bpu_batch_queue_systemd_batch_probe
job_name: systemd_batch_20260604-235205.jsonl
job_status: done
request_count: 8
processed_count: 8
accepted_count: 8
deferred_count: 0
max_batch_size: 8
batch_run_count: 1
batch_count: 8
result_count: 8
total_wall_ms: 25568.117
amortized_wall_ms_per_processed_request: 3196.015
```

Verified current eight-request drain-all fields copied from `systemd_drain_probe.json`:

```text
verdict: ok_dream7b_bpu_batch_queue_systemd_drain_probe
job_name: systemd_drain_20260604-235302.jsonl
job_status: done
request_count: 8
expected_batch_counts: [8]
drain_all: True
max_batch_size: 8
processed_count: 8
accepted_count: 8
deferred_count: 0
batch_run_count: 1
batch_counts: [8]
result_count: 8
total_wall_ms: 25621.258
amortized_wall_ms_per_processed_request: 3202.657
```

Verified current max-batch-size-16 systemd fields copied from `systemd_probe.json`:

```text
verdict: ok_dream7b_bpu_batch_queue_systemd_probe
service_status: active
service_enabled: enabled
max_batch_size_required: 16
drain_all_required: True
exec_start includes: --max-batch-size 16
exec_start includes: --drain-all
```

Verified current sixteen-request systemd batch fields copied from `systemd_batch_probe.json`:

```text
verdict: ok_dream7b_bpu_batch_queue_systemd_batch_probe
job_name: systemd_batch_20260605-131550.jsonl
job_status: done
request_count: 16
processed_count: 16
accepted_count: 16
deferred_count: 0
max_batch_size: 16
batch_run_count: 1
batch_count: 16
result_count: 16
total_wall_ms: 27416.621
amortized_wall_ms_per_processed_request: 1713.539
```

Verified current sixteen-request drain-all fields copied from `systemd_drain_probe.json`:

```text
verdict: ok_dream7b_bpu_batch_queue_systemd_drain_probe
job_name: systemd_drain_20260605-131621.jsonl
job_status: done
request_count: 16
expected_batch_counts: [16]
drain_all: True
max_batch_size: 16
processed_count: 16
accepted_count: 16
deferred_count: 0
batch_run_count: 1
batch_counts: [16]
result_count: 16
total_wall_ms: 27248.799
amortized_wall_ms_per_processed_request: 1703.05
```

Verified lightweight systemd canary fields copied from `systemd_canary_probe.json`:

```text
canary_report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_canary_20260605-151715/systemd_canary_probe.md
canary_json: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_canary_20260605-151715/systemd_canary_probe.json
verdict: ok_dream7b_bpu_batch_queue_systemd_canary_probe
service_name: dream7b-bpu-batch-queue.service
job_name: systemd_canary_20260605-151715.jsonl
job_status: done
request_count: 1
processed_count: 1
accepted_count: 1
deferred_count: 0
skipped_count: 0
drain_all: True
max_batch_size: 16
batch_run_count: 1
batch_count: 1
result_count: 1
execution_mode: pair_window_batch
window_execution_mode: window-batch
child_process_count: 0
bpu_lock_path: /run/lock/dream7b_bpu_batch_queue_runner.lock
final_shapes: [[1, 16, 152064]]
total_wall_ms: 24073.138
amortized_wall_ms_per_processed_request: 24073.138
errors: []
```

Verified HBM artifact inventory fields copied from `hbm_artifact_inventory_probe.json`:

```text
inventory_report: /mnt/nas/openclaw/reports/models/dream7b_bpu_hbm_artifact_inventory_20260605-160050/hbm_artifact_inventory_probe.md
inventory_json: /mnt/nas/openclaw/reports/models/dream7b_bpu_hbm_artifact_inventory_20260605-160050/hbm_artifact_inventory_probe.json
verdict: ok_dream7b_bpu_hbm_artifact_inventory_probe
expected_artifact_count: 14
expected_base_count: 6
expected_fine_count: 8
nas_existing_count: 14
local_existing_count: 14
size_match_count: 14
manifest_expected_count: 12
manifest_verified_count: 12
required_manifest_expected_count: 12
warnings: []
errors: []
```

Verified current sustained systemd telemetry fields copied from `systemd_telemetry_probe.json`:

```text
verdict: ok_dream7b_bpu_batch_queue_systemd_telemetry_probe
job_count: 3
request_count: 16
expected_request_total: 48
completed_job_count: 3
failed_job_count: 0
processed_request_count: 48
accepted_request_count: 48
deferred_request_count: 0
result_count: 48
batch_counts: [16, 16, 16]
total_wall_ms: 79811.376
total_load_ms: 70702.172
total_run_ms: 8337.877
amortized_wall_ms_per_processed_request: 1662.737
amortized_load_ms_per_processed_request: 1472.962
amortized_run_ms_per_processed_request: 173.706
bpu_loading_sample_count: 829
nonzero_bpu_loading_sample_count: 99
max_bpu_loading: 100.0
avg_bpu_loading: 9.616
service_status_before: active
service_status_after: active
errors: []
```

Verified current queue retention fields copied from `queue_retention_probe.json`:

```text
verdict: ok_dream7b_bpu_batch_queue_retention_probe
policy_mode: report_only
queue_counts: {'pending': 0, 'processing': 0, 'done': 13, 'failed': 1}
queue_size_bytes: {'pending': 0, 'processing': 0, 'done': 18685, 'failed': 83}
pending_stale_count: 0
processing_stale_count: 0
done_archive_candidate_count: 0
failed_archive_candidate_count: 0
archive_root: /mnt/nas/openclaw/queues/dream7b-bpu/archive
apply_supported: False
warnings: []
errors: []
```

Verified long repeat fields copied from `long_repeat_probe.json`:

```text
verdict: ok_dream7b_bpu_fine_forward_long_repeat_probe
repeat_count: 6
repeat_status: 0
failure_count: 0
median_wall_ms: 25253.389
median_load_ms: 24134.596
median_run_ms: 176.056
min_wall_ms: 24998.927
max_wall_ms: 26168.34
wall_spread_ratio: 0.046307
max_wall_spread_ratio: 0.1
execution_mode: pair_in_process
window_execution_mode: in-process
child_process_count: 0
segment_count: 10
final_shape: [1, 16, 152064]
errors: []
```

Verified deployment acceptance fields copied from `deployment_acceptance_probe.json`:

```text
acceptance_report: /mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-172156/deployment_acceptance_probe.md
acceptance_json: /mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-172156/deployment_acceptance_probe.json
verdict: ok_dream7b_bpu_deployment_acceptance_probe
check_count: 9
passed_check_count: 9
min_batch_capacity: 16
min_systemd_batch_requests: 16
min_systemd_telemetry_requests: 48
min_long_repeat_count: 6
max_long_repeat_wall_spread_ratio: 0.1
systemd_service.ok: True
batch_capacity.ok: True
hbm_artifact_inventory.ok: True
systemd_batch.ok: True
systemd_drain.ok: True
systemd_canary.ok: True
systemd_telemetry.ok: True
long_repeat.ok: True
queue_retention.ok: True
warnings: []
errors: []
```

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
- Added `install-dream7b-bpu-queue-service` and `dream7b-bpu-batch-queue-systemd-probe`.
- Installed and restarted `dream7b-bpu-batch-queue.service` at `/etc/systemd/system/dream7b-bpu-batch-queue.service`.
- Verified `dream7b-bpu-batch-queue-systemd-probe` report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_20260603-221324/systemd_probe.md`.
- Verified a real systemd-queued BPU job at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_job_20260603_220710/queue_summary.json`.
- Added `dream7b-bpu-batch-queue-systemd-soak-probe` for multi-job service verification.
- Verified `dream7b-bpu-batch-queue-systemd-soak-probe` report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_soak_20260604-131223/systemd_soak_probe.md`.
- Verified two real systemd-queued BPU job summaries at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_soak_20260604-131223_001/queue_summary.json` and `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_soak_20260604-131223_002/queue_summary.json`.
- Added `dream7b-bpu-batch-queue-systemd-batch-probe` for one JSONL job with four requests.
- Verified `dream7b-bpu-batch-queue-systemd-batch-probe` report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_batch_20260604-133034/systemd_batch_probe.md`.
- Verified the four-request batch job summary at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_batch_20260604-133034/queue_summary.json`.

### 2026-06-04

- Added `DREAM7B_BPU_QUEUE_DRAIN_ALL` to `install-dream7b-bpu-queue-service` with default `drain_all: true`.
- Updated `dream7b-bpu-batch-queue-systemd-probe` to require `--drain-all` in `ExecStart`.
- Added `dream7b-bpu-batch-queue-systemd-drain-probe` for one JSONL job with five requests through the NAS-backed systemd queue.
- Reinstalled and restarted `dream7b-bpu-batch-queue.service`; verified `ExecStart` includes `--drain-all` at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_20260604-174953/systemd_probe.md`.
- Verified `dream7b-bpu-batch-queue-systemd-drain-probe` report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_drain_20260604-174953/systemd_drain_probe.md`.
- Verified the five-request drain-all job summary at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_drain_20260604-174953/queue_summary.json`.
- Verified an eight-request full-batch drain-all report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_drain_20260604-180557/systemd_drain_probe.md`.
- Verified the eight-request full-batch drain-all job summary at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_drain_20260604-180557/queue_summary.json`.
- Added `dream7b-bpu-fine-batch-size-sweep-probe` for batch-count load amortization evidence.
- Verified `dream7b-bpu-fine-batch-size-sweep-probe` report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_size_sweep_20260604-181429/batch_size_sweep_probe.md`.
- Added `dream7b-bpu-runtime-telemetry-probe` for `hrt_ucp_monitor` BPU loading telemetry during Dream 7B BPU forward.
- Verified `dream7b-bpu-runtime-telemetry-probe` report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_runtime_telemetry_20260604-225030/runtime_telemetry_probe.md`.
- Changed `install-dream7b-bpu-queue-service` default `DREAM7B_BPU_QUEUE_MAX_BATCH_SIZE` from 4 to 8 after the batch-size sweep and runtime telemetry proved batch 8 viable.
- Updated `dream7b-bpu-batch-queue-systemd-probe`, `dream7b-bpu-batch-queue-systemd-batch-probe`, and `dream7b-bpu-batch-queue-systemd-drain-probe` to require `--max-batch-size 8`.
- Reinstalled and restarted `dream7b-bpu-batch-queue.service`; verified `ExecStart` includes `--max-batch-size 8 --drain-all` at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_20260604-233926/systemd_probe.md`.
- Verified an eight-request single-run systemd batch report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_batch_20260604-235205/systemd_batch_probe.md`.
- Verified the eight-request single-run batch job summary at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_batch_20260604-235205/queue_summary.json`.
- Verified the current eight-request drain-all report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_drain_20260604-235302/systemd_drain_probe.md`.
- Verified the current eight-request drain-all job summary at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_drain_20260604-235302/queue_summary.json`.

### 2026-06-05

- Added `dream7b-bpu-batch-capacity-probe` for bounded 8/12/16 independent seq16 capacity testing through `dream7b-bpu-fine-batch-forward`.
- Verified `dream7b-bpu-batch-capacity-probe` report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_capacity_20260605-123835/batch_capacity_probe.md`.
- Verified `max_passing_count: 16` with batch 16 `amortized_wall_ms_per_forward: 1714.647`.
- Changed `install-dream7b-bpu-queue-service` default `DREAM7B_BPU_QUEUE_MAX_BATCH_SIZE` from 8 to 16 after the capacity probe passed.
- Updated `dream7b-bpu-batch-queue-systemd-probe`, `dream7b-bpu-batch-queue-systemd-batch-probe`, and `dream7b-bpu-batch-queue-systemd-drain-probe` to require `--max-batch-size 16`.
- Reinstalled and restarted `dream7b-bpu-batch-queue.service`; verified `ExecStart` includes `--max-batch-size 16 --drain-all` at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_20260605-131550/systemd_probe.md`.
- Verified a sixteen-request single-run systemd batch report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_batch_20260605-131550/systemd_batch_probe.md`.
- Verified the sixteen-request single-run batch job summary at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_batch_20260605-131550/queue_summary.json`.
- Verified the current sixteen-request drain-all report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_drain_20260605-131621/systemd_drain_probe.md`.
- Verified the current sixteen-request drain-all job summary at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_drain_20260605-131621/queue_summary.json`.
- Updated `dream7b-bpu-runtime-telemetry-probe` default `DREAM7B_BPU_TELEMETRY_BATCH_COUNT` from 8 to 16.
- Verified batch 16 runtime telemetry at `/mnt/nas/openclaw/reports/models/dream7b_bpu_runtime_telemetry_20260605-132014/runtime_telemetry_probe.md`.
- Added `dream7b-bpu-batch-queue-systemd-telemetry-probe` for sustained NAS-backed systemd queue telemetry while sampling `hrt_ucp_monitor`.
- Verified sustained systemd telemetry report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_telemetry_20260605-133919/systemd_telemetry_probe.md`.
- Verified three sixteen-request systemd telemetry queue summaries at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_telemetry_20260605-133919_001/queue_summary.json`, `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_telemetry_20260605-133919_002/queue_summary.json`, and `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_telemetry_20260605-133919_003/queue_summary.json`.
- Added `dream7b-bpu-batch-queue-retention-probe` for report-only Dream 7B BPU queue retention, stale-file, and archive-candidate checks.
- Verified current NAS queue retention report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_retention_20260605-135448/queue_retention_probe.md`.
- Added `dream7b-bpu-fine-forward-long-repeat-probe` for longer `pair_in_process` repeated-run evidence over the existing fine-forward repeat path.
- Verified six-run long repeat report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_long_repeat_20260605-140733/long_repeat_probe.md`.
- Added `dream7b-bpu-deployment-acceptance-probe` as a report-only deployment acceptance gate over the latest Dream 7B BPU service, batch capacity, systemd batch/drain/telemetry, long-repeat, and queue-retention reports.
- Verified deployment acceptance report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-143759/deployment_acceptance_probe.md` with `check_count: 7` and `passed_check_count: 7`.
- Added `dream7b-bpu-batch-queue-systemd-canary-probe` as a lightweight real BPU canary through the NAS-backed `dream7b-bpu-batch-queue.service`.
- Verified canary report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_canary_20260605-151715/systemd_canary_probe.md` with `request_count: 1`, `processed_count: 1`, `final_shapes: [[1, 16, 152064]]`, and `errors: []`.
- Updated `dream7b-bpu-deployment-acceptance-probe` to include `systemd_canary`.
- Verified updated deployment acceptance report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-153747/deployment_acceptance_probe.md` with `check_count: 8` and `passed_check_count: 8`.
- Added `dream7b-bpu-hbm-artifact-inventory-probe` for Dream 7B base/fine HBM artifact inventory, NAS/local-cache size matching, and base `manifest.sha256` verification.
- Verified HBM artifact inventory report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_hbm_artifact_inventory_20260605-160050/hbm_artifact_inventory_probe.md` with `expected_artifact_count: 14`, `size_match_count: 14`, and `manifest_verified_count: 12`.
- Updated `dream7b-bpu-deployment-acceptance-probe` to include `hbm_artifact_inventory`.
- Verified updated deployment acceptance report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-161000/deployment_acceptance_probe.md` with `check_count: 9` and `passed_check_count: 9`.
- Changed `dream7b-bpu-fine-forward-long-repeat-probe` default `DREAM7B_BPU_FINE_FORWARD_LONG_REPEAT_MAX_WALL_SPREAD_RATIO` from `0` to `0.10`.
- Verified gated six-run long repeat report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_long_repeat_20260605-163343/long_repeat_probe.md` with `wall_spread_ratio: 0.046307`, `max_wall_spread_ratio: 0.1`, and `errors: []`.
- Updated `dream7b-bpu-deployment-acceptance-probe` to require gated long-repeat spread evidence through `DREAM7B_BPU_ACCEPTANCE_MAX_LONG_REPEAT_WALL_SPREAD_RATIO`.
- Verified gated deployment acceptance report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-172156/deployment_acceptance_probe.md` with `check_count: 9`, `passed_check_count: 9`, and `max_long_repeat_wall_spread_ratio: 0.1`.
- Added `dream7b-bpu-text-queue-systemd-probe` for real Dream 7B prompt tokenization into the NAS-backed systemd BPU queue.
- Verified text queue systemd report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260605-234555/text_queue_systemd_probe.md` with `token_count: 16`, `final_shape: [1, 16, 152064]`, non-empty `topk_last_position`, and `errors: []`.
- Updated `dream7b-bpu-deployment-acceptance-probe` to include `text_queue_systemd`.
- Verified text-queue-aware deployment acceptance report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-134314/deployment_acceptance_probe.md` with `check_count: 10`, `passed_check_count: 10`, and `text_queue_systemd.ok: True`.
- Added reusable `dream7b-bpu-text-queue-submit` for Dream 7B prompt tokenizer encoding and atomic NAS-backed queue submission.
- Updated `dream7b-bpu-text-queue-systemd-probe` to call `dream7b-bpu-text-queue-submit` and preserve `text_queue_submit.json` in the same run directory.
- Verified submit-aware text queue systemd report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260606-142516/text_queue_systemd_probe.md` with `submit_verdict: ok_dream7b_bpu_text_queue_submit`, `token_count: 16`, `final_shape: [1, 16, 152064]`, non-empty `topk_last_position`, and `errors: []`.
- Updated `dream7b-bpu-deployment-acceptance-probe` to require `submit_cmd` and `submit_verdict` inside `text_queue_systemd`.
- Verified submit-aware deployment acceptance report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-142559/deployment_acceptance_probe.md` with `check_count: 10`, `passed_check_count: 10`, `text_queue_systemd.details.submit_cmd: dream7b-bpu-text-queue-submit`, and `text_queue_systemd.details.submit_verdict: ok_dream7b_bpu_text_queue_submit`.
- Added reusable `dream7b-bpu-text-queue-run` for Dream 7B prompt submission, systemd queue wait, and compact BPU result extraction.
- Verified standalone text queue run report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_run_20260606-144526/text_queue_run.md` with `verdict: ok_dream7b_bpu_text_queue_run`, `job_status: done`, `final_shape: [1, 16, 152064]`, and non-empty `topk_last_position`.
- Updated `dream7b-bpu-text-queue-systemd-probe` to call `dream7b-bpu-text-queue-run`.
- Verified run-aware text queue systemd report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260606-144634/text_queue_systemd_probe.md` with `run_verdict: ok_dream7b_bpu_text_queue_run`, `submit_verdict: ok_dream7b_bpu_text_queue_submit`, `final_shape: [1, 16, 152064]`, and `errors: []`.
- Updated `dream7b-bpu-deployment-acceptance-probe` to include independent `text_queue_run` evidence.
- Verified run-aware deployment acceptance report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-144721/deployment_acceptance_probe.md` with `check_count: 11`, `passed_check_count: 11`, `text_queue_run.ok: True`, and `text_queue_systemd.ok: True`.
- Updated `dream7b-bpu-text-queue-run` to decode BPU `topk_last_position` through the Dream 7B tokenizer venv and write `topk_last_position_decoded`.
- Verified decoded standalone text queue run report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_run_20260606-155102/text_queue_run.md` with `topk_last_position_decoded` token texts ` and`, ` or`, and `,`.
- Verified decoded text queue systemd report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260606-155148/text_queue_systemd_probe.md` with `run_verdict: ok_dream7b_bpu_text_queue_run`, `topk_last_position_decoded`, `final_shape: [1, 16, 152064]`, and `errors: []`.
- Updated `dream7b-bpu-deployment-acceptance-probe` to require decoded top-k evidence in both `text_queue_run` and `text_queue_systemd`.
- Verified decoded deployment acceptance report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-155233/deployment_acceptance_probe.md` with `check_count: 11`, `passed_check_count: 11`, `text_queue_run.details.topk_last_position_decoded`, and `text_queue_systemd.details.topk_last_position_decoded`.
- Added reusable `dream7b-bpu-diffusion-generate` for bounded seq16 Dream diffusion generation through `dream7b-bpu-fine-forward`.
- Verified bounded generation report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_generate_20260606-161120/generation.md` with `verdict: ok_dream7b_bpu_diffusion_generate`, `executed_step_count: 2`, `remaining_mask_positions: []`, and `decoded_final`.
- Updated `dream7b-bpu-deployment-acceptance-probe` to include `diffusion_generate`.
- Verified generation-aware deployment acceptance report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-161252/deployment_acceptance_probe.md` with `check_count: 12`, `passed_check_count: 12`, and `diffusion_generate.ok: True`.
- Added `dream7b-bpu-diffusion-generate-telemetry-probe` for direct `hrt_ucp_monitor` telemetry around bounded single-prompt Dream diffusion generation.
- Verified generation telemetry report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_generate_telemetry_20260606-163625/generation_telemetry_probe.md` with `verdict: ok_dream7b_bpu_diffusion_generate_telemetry_probe`, `generation_status: 0`, `nonzero_bpu_loading_sample_count: 14`, and `max_bpu_loading: 38.0`.
- Updated `dream7b-bpu-deployment-acceptance-probe` to include `diffusion_generate_telemetry`.
- Verified generation-telemetry-aware deployment acceptance report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-165607/deployment_acceptance_probe.md` with `check_count: 13`, `passed_check_count: 13`, and `diffusion_generate_telemetry.ok: True`.
- Added reusable `dream7b-bpu-diffusion-batch-generate` for bounded seq16 batch Dream diffusion generation through `dream7b-bpu-fine-batch-forward`.
- Added `dream7b-bpu-diffusion-batch-generate-telemetry-probe` for direct `hrt_ucp_monitor` telemetry around bounded batch Dream diffusion generation.
- Verified batch generation telemetry report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_batch_generate_telemetry_20260606-181845/batch_generation_telemetry_probe.md` with `batch_count: 8`, `forward_batch_counts: [8, 8]`, `nonzero_bpu_loading_sample_count: 39`, and `max_bpu_loading: 100.0`.
- Updated `dream7b-bpu-deployment-acceptance-probe` to include `diffusion_batch_generate_telemetry` and `DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_GENERATE_COUNT`.
- Verified batch-generation-aware deployment acceptance report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-182851/deployment_acceptance_probe.md` with `check_count: 14`, `passed_check_count: 14`, `min_batch_generate_count: 8`, and `diffusion_batch_generate_telemetry.ok: True`.

## TODO

- Keep `--window-execution-mode child-process` as the fallback path until more long-run evidence extends beyond the current gated 6-run `--window-execution-mode in-process` probe.
- Continue collecting long-repeat reports before tightening the current `DREAM7B_BPU_FINE_FORWARD_LONG_REPEAT_MAX_WALL_SPREAD_RATIO` default of `0.10`.
- Keep queue cleanup report-only until an explicit apply mode and archive directory migration rule are approved.
- Re-run `dream7b-bpu-deployment-acceptance-probe` after every Dream 7B BPU service, batching, telemetry, or retention change.
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
