# Project Reference

Last updated: 2026-06-08

This document is the project-level reference for API-like command interfaces, configuration keys, architecture, decisions, development log, requirements, and TODOs. All identifiers in this file are copied from repository files or recorded evidence. When a name, key, path, or field is uncertain, read the source file first and do not infer spelling, case, format, or structure.

## Documentation Rule

- Do not guess identifiers. This includes command names, script names, variable names, JSON keys, paths, report fields, service names, model names, and environment variable names.
- Before writing or changing an identifier, read the related file, report, config, or log and copy the exact spelling.
- After each task, run the documentation check described in `docs/documentation_audit_runbook.md`.
- If the check is not run, record why in the final task note.

## Project Requirements

- Follow the 2026-06-09 teacher demo priority: first finish the S100P OpenClaw entry demo, then the AI NAS movie-sort demo, then return to Dream 7B.
- Keep robot capability, ROS2, and rosbag work out of the current teacher demo path.
- Demonstrate that S100P can run the OpenClaw entry while the PC side does not need high-privilege operations and NAS provides persistence.
- Demonstrate an AI NAS workflow where OpenClaw on S100P organizes movie-like files by type on NAS.
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
  -> local resplit HBM cache: /home/sunrise/.cache/openclaw/dream7b-hbm/resplit-seq16

NAS
  -> mountPoint: /mnt/nas/openclaw
  -> Dream 7B HBM root: /mnt/nas/openclaw/models/dream7b-hbm
  -> Dream 7B resplit HBM root: /mnt/nas/openclaw/models/dream7b-hbm/resplit-seq16
  -> reports root: /mnt/nas/openclaw/reports/models
  -> teacher demo report roots: /mnt/nas/openclaw/reports/teacher-demos/openclaw-entry and /mnt/nas/openclaw/reports/teacher-demos/ai-nas-movie-sort
  -> AI NAS movie-sort demo root: /mnt/nas/openclaw/demo/ai-nas-movie-sort

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

### `scripts/run_allowlisted_tool.sh openclaw_entry_demo_probe`

Source files:

```text
scripts/run_allowlisted_tool.sh
scripts/probes/openclaw_entry_demo_probe.sh
```

Default argument copied from `scripts/probes/openclaw_entry_demo_probe.sh`:

```text
report_root = /mnt/nas/openclaw/reports/teacher-demos/openclaw-entry
```

Output files copied from `scripts/probes/openclaw_entry_demo_probe.sh`:

```text
openclaw_entry_demo.md
openclaw_entry_demo.json
captures/
```

JSON fields copied from `scripts/probes/openclaw_entry_demo_probe.sh`:

```text
generated_at
verdict
demo_id
host
report_root
run_dir
claims
safety_boundary
recording_script
captures
nas
openclaw_status_probe
```

Acceptance fields:

```text
verdict: ok_openclaw_entry_demo_probe
claims.openclaw_runs_on_s100p: validated_by_openclaw_gateway_status_and_port_capture
claims.pc_high_privilege_required: not_required_by_demo_procedure
claims.pc_unsafe_writes: not_required_by_demo_procedure
claims.persistence: nas_report_root_when_/mnt/nas/openclaw_is_mounted_and_writable
```

### `scripts/run_allowlisted_tool.sh ai_nas_movie_sort_demo_probe`

Source files:

```text
scripts/run_allowlisted_tool.sh
scripts/probes/ai_nas_movie_sort_demo_probe.sh
```

Default arguments copied from `scripts/probes/ai_nas_movie_sort_demo_probe.sh`:

```text
demo_root = /mnt/nas/openclaw/demo/ai-nas-movie-sort
report_root = /mnt/nas/openclaw/reports/teacher-demos/ai-nas-movie-sort
```

Output files copied from `scripts/probes/ai_nas_movie_sort_demo_probe.sh`:

```text
movie_sort_demo.md
movie_sort_demo.json
/mnt/nas/openclaw/demo/ai-nas-movie-sort/library/<type>/MANIFEST.md
/mnt/nas/openclaw/demo/ai-nas-movie-sort/library/<type>/<file>.movie.json
```

JSON fields copied from `scripts/probes/ai_nas_movie_sort_demo_probe.sh`:

```text
generated_at
verdict
demo_id
demo_root
inbox_dir
library_dir
report_dir
classification_engine
seeded_sample_files
processed_file_count
classified_file_count
types
originals_preserved
copy_mode
scope
records
```

Acceptance fields:

```text
verdict: ok_ai_nas_movie_sort_demo_probe
classification_engine: deterministic_filename_metadata_rules
originals_preserved: True
scope.real_media_library_touched: False
scope.ros2_or_robot_scope: out_of_scope
```

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

Selected-pair candidate arguments copied from the script:

```text
service_name = dream7b-bpu-selected-pair-candidate.service
queue_dir = /mnt/nas/openclaw/queues/dream7b-bpu-selected-pair-candidate
output_dir = /mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_candidate_service_systemd
run_prefix = dream7b_bpu_selected_pair_candidate_service_telemetry
expected_forward_command = dream7b-bpu-selected-pair-batch-forward
expected_window_execution_mode = selected-pair-resident
expected_child_process_count = 2
comparison_to_default_systemd_telemetry
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
forward_command
processed_count
batch_count
expected_forward_command
expected_window_execution_mode
expected_child_process_count
final_shape
bpu_lock.path
execution_mode
window_execution_mode
child_process_count
comparison_to_default_systemd_telemetry
candidate_wall_time_improved_vs_default_systemd
candidate_avg_bpu_loading_not_worse_than_default_systemd
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

Latest selected-pair candidate service telemetry report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_candidate_service_telemetry_20260606-043944/systemd_telemetry_probe.md
```

Latest selected-pair candidate service telemetry JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_candidate_service_telemetry_20260606-043944/systemd_telemetry_probe.json
```

Verified selected-pair candidate service telemetry fields copied from `systemd_telemetry_probe.json`:

```text
verdict: ok_dream7b_bpu_batch_queue_systemd_telemetry_probe
service_name: dream7b-bpu-selected-pair-candidate.service
job_count: 3
request_count: 16
processed_request_count: 48
accepted_request_count: 48
deferred_request_count: 0
result_count: 48
batch_counts: [16, 16, 16]
expected_forward_command: dream7b-bpu-selected-pair-batch-forward
expected_window_execution_mode: selected-pair-resident
expected_child_process_count: 2
amortized_wall_ms_per_processed_request: 1432.54
amortized_load_ms_per_processed_request: 1441.366
amortized_run_ms_per_processed_request: 147.708
avg_bpu_loading: 8.788
max_bpu_loading: 98.0
comparison_to_default_systemd_telemetry.default_systemd_telemetry_path: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_telemetry_20260605-133919/systemd_telemetry_probe.json
comparison_to_default_systemd_telemetry.default_amortized_wall_ms_per_processed_request: 1662.737
comparison_to_default_systemd_telemetry.candidate_amortized_wall_ms_per_processed_request: 1432.54
comparison_to_default_systemd_telemetry.wall_ms_delta_ratio_vs_default_systemd: 0.138445
comparison_to_default_systemd_telemetry.default_avg_bpu_loading: 9.616
comparison_to_default_systemd_telemetry.candidate_avg_bpu_loading: 8.788
comparison_to_default_systemd_telemetry.avg_bpu_loading_delta_vs_default_systemd: -0.828
comparison_to_default_systemd_telemetry.candidate_wall_time_improved_vs_default_systemd: True
comparison_to_default_systemd_telemetry.candidate_avg_bpu_loading_not_worse_than_default_systemd: False
errors: []
```

### `dream7b-bpu-selected-pair-cross-job-reuse-probe`

Source file: `scripts/probes/dream7b_bpu_selected_pair_cross_job_reuse_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-selected-pair-cross-job-reuse-probe
```

Environment variables copied from the script:

```text
DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_MODEL_REPORT_ROOT
DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_FORWARD_PROBE_CMD
DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_COUNT
DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_BATCH_COUNT
DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_TOP_K
DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_TIMEOUT_SEC
```

Default values copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_MODEL_REPORT_ROOT = /mnt/nas/openclaw/reports/models
DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_FORWARD_PROBE_CMD = dream7b-bpu-selected-pair-forward-path-probe
DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_COUNT = 3
DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_BATCH_COUNT = 16
DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_TOP_K = 3
DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_TIMEOUT_SEC = 1800
```

Latest selected-pair cross-job reuse report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_reuse_20260606-051721/selected_pair_cross_job_reuse_probe.md
```

Latest selected-pair cross-job reuse JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_reuse_20260606-051721/selected_pair_cross_job_reuse_probe.json
```

Verified selected-pair cross-job reuse fields copied from `selected_pair_cross_job_reuse_probe.json`:

```text
verdict: ok_dream7b_bpu_selected_pair_cross_job_reuse_probe
job_count: 3
batch_count: 16
processed_forward_count: 48
selected_pair: [1, 8]
selected_segments: ['seg02_04', 'seg24_26']
selected_pair_covers_all_segments: True
selected_worker_count: 2
selected_resident_load_ms: 3635.817
resident_load_once_amortized_ms_per_forward: 75.746
cross_job_metrics.amortized_wall_ms_per_forward: 1435.554
cross_job_metrics.amortized_total_load_ms_per_forward: 1344.68
candidate_service_metrics.amortized_wall_ms_per_processed_request: 1432.54
candidate_service_metrics.amortized_load_ms_per_processed_request: 1441.366
comparison_to_selected_pair_candidate_service.wall_ms_delta_ratio: -0.002104
comparison_to_selected_pair_candidate_service.load_ms_delta_ratio: 0.067079
comparison_to_selected_pair_candidate_service.cross_job_wall_time_improved: False
comparison_to_selected_pair_candidate_service.cross_job_load_time_improved: True
next_optimization_target: do not promote cross-job selected-pair reuse until telemetry shows amortized wall/load improvement
errors: []
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

### `dream7b-bpu-utilization-gap-probe`

Source file: `scripts/probes/dream7b_bpu_utilization_gap_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-utilization-gap-probe
```

Default argument copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
```

Environment variables copied from the script:

```text
DREAM7B_BPU_UTILIZATION_GAP_MIN_BATCH_COUNT
DREAM7B_BPU_UTILIZATION_GAP_MIN_SUSTAINED_ROUND_COUNT
DREAM7B_BPU_UTILIZATION_GAP_MIN_SUSTAINED_TOTAL_ITEMS
```

Default values copied from the script:

```text
min_batch_count = 16
min_sustained_round_count = 3
min_sustained_total_items = 48
```

Report globs copied from the script:

```text
dream7b_bpu_fine_batch_size_sweep_*/batch_size_sweep_probe.json
dream7b_bpu_runtime_telemetry_*/runtime_telemetry_probe.json
dream7b_bpu_batch_queue_systemd_telemetry_*/systemd_telemetry_probe.json
dream7b_bpu_diffusion_batch_generate_sustained_*/batch_generation_sustained_probe.json
dream7b_bpu_diffusion_batch_generate_telemetry_*/batch_generation_telemetry_probe.json
```

Output files copied from the script:

```text
utilization_gap_probe.json
utilization_gap_probe.md
```

Output fields copied from the script:

```text
generated_at
verdict
run_dir
report_root
min_batch_count
min_sustained_round_count
min_sustained_total_items
diagnosis
next_optimization_target
max_observed_bpu_loading
avg_observed_bpu_loading_across_reports
telemetry_avg_bpu_loading_values
telemetry_max_bpu_loading_values
batch_scaling_reference
max_available_batch_count
amortized_load_ms_per_forward
amortized_run_ms_per_forward
load_to_run_ratio
runtime_telemetry
selected_pair_telemetry
systemd_telemetry
sustained_generation
batch_generate_telemetry
warnings
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_utilization_gap_20260606-045527/utilization_gap_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_utilization_gap_20260606-045527/utilization_gap_probe.json
```

Verified utilization gap fields copied from `utilization_gap_probe.json`:

```text
verdict: ok_dream7b_bpu_utilization_gap_probe
diagnosis: hbm_reload_dominated
next_optimization_target: reduce per-window HBM reload overhead before expecting sustained 128TOPS-level average utilization
max_observed_bpu_loading: 100.0
avg_observed_bpu_loading_across_reports: 8.763
min_batch_count: 16
min_sustained_round_count: 3
min_sustained_total_items: 48
batch_scaling_reference.path: /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_size_sweep_20260604-181429/batch_size_sweep_probe.json
batch_scaling_reference.max_available_batch_count: 8
batch_scaling_reference.amortized_load_ms_per_forward: 2974.35
batch_scaling_reference.amortized_run_ms_per_forward: 173.565
batch_scaling_reference.load_to_run_ratio: 17.137
runtime_telemetry.path: /mnt/nas/openclaw/reports/models/dream7b_bpu_runtime_telemetry_20260606-031226/runtime_telemetry_probe.json
runtime_telemetry.batch_count: 16
runtime_telemetry.max_bpu_loading: 96.0
runtime_telemetry.avg_bpu_loading: 7.188
runtime_telemetry.forward_load_ms: 23285.631
runtime_telemetry.forward_run_ms: 2372.609
runtime_telemetry.amortized_load_ms_per_forward: 1455.352
runtime_telemetry.amortized_run_ms_per_forward: 148.288
runtime_telemetry.load_to_run_ratio: 9.814
selected_pair_telemetry.path: /mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_telemetry_20260606-031259/selected_pair_telemetry_probe.json
selected_pair_telemetry.batch_count: 16
selected_pair_telemetry.max_bpu_loading: 98.0
selected_pair_telemetry.avg_bpu_loading: 9.14
selected_pair_telemetry.selected_pair: [1, 8]
selected_pair_telemetry.selected_segments: ['seg02_04', 'seg24_26']
selected_pair_telemetry.selected_pair_covers_all_segments: True
selected_pair_telemetry.selected_wall_ms: 22955.54
selected_pair_telemetry.selected_forward_load_ms: 20290.033
selected_pair_telemetry.selected_run_ms: 2360.901
selected_pair_telemetry.wall_ms_delta_vs_default_runtime: 2960.232
selected_pair_telemetry.wall_ms_delta_ratio_vs_default_runtime: 0.114225
selected_pair_telemetry.avg_bpu_loading_delta_vs_default_runtime: 1.952
selected_pair_telemetry.selected_wall_time_improved_vs_default_runtime: True
selected_pair_telemetry.selected_avg_bpu_loading_improved_vs_default_runtime: True
systemd_telemetry.path: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_telemetry_20260605-133919/systemd_telemetry_probe.json
systemd_telemetry.processed_request_count: 48
systemd_telemetry.max_bpu_loading: 100.0
systemd_telemetry.avg_bpu_loading: 9.616
systemd_telemetry.total_load_ms: 70702.172
systemd_telemetry.total_run_ms: 8337.877
systemd_telemetry.load_to_run_ratio: 8.48
selected_pair_candidate_service_telemetry.path: /mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_candidate_service_telemetry_20260606-043944/systemd_telemetry_probe.json
selected_pair_candidate_service_telemetry.service_name: dream7b-bpu-selected-pair-candidate.service
selected_pair_candidate_service_telemetry.processed_request_count: 48
selected_pair_candidate_service_telemetry.batch_counts: [16, 16, 16]
selected_pair_candidate_service_telemetry.expected_forward_command: dream7b-bpu-selected-pair-batch-forward
selected_pair_candidate_service_telemetry.expected_window_execution_mode: selected-pair-resident
selected_pair_candidate_service_telemetry.expected_child_process_count: 2
selected_pair_candidate_service_telemetry.max_bpu_loading: 98.0
selected_pair_candidate_service_telemetry.avg_bpu_loading: 8.788
selected_pair_candidate_service_telemetry.total_load_ms: 69185.546
selected_pair_candidate_service_telemetry.total_run_ms: 7090.007
selected_pair_candidate_service_telemetry.load_to_run_ratio: 9.758
selected_pair_candidate_service_telemetry.comparison_to_default_systemd_telemetry.wall_ms_delta_ratio_vs_default_systemd: 0.138445
selected_pair_candidate_service_telemetry.comparison_to_default_systemd_telemetry.avg_bpu_loading_delta_vs_default_systemd: -0.828
selected_pair_candidate_service_telemetry.comparison_to_default_systemd_telemetry.candidate_wall_time_improved_vs_default_systemd: True
selected_pair_candidate_service_telemetry.comparison_to_default_systemd_telemetry.candidate_avg_bpu_loading_not_worse_than_default_systemd: False
sustained_generation.path: /mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_batch_generate_sustained_20260606-190058/batch_generation_sustained_probe.json
sustained_generation.round_count: 3
sustained_generation.batch_count: 16
sustained_generation.actual_total_batch_items: 48
sustained_generation.max_bpu_loading: 100.0
sustained_generation.avg_bpu_loading: 9.022
batch_generate_telemetry.path: /mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_batch_generate_telemetry_20260606-184316/batch_generation_telemetry_probe.json
batch_generate_telemetry.batch_count: 16
batch_generate_telemetry.max_bpu_loading: 100.0
batch_generate_telemetry.avg_bpu_loading: 8.825
warnings: ['batch_size_sweep max batch_count is below 16; using runtime/systemd/sustained telemetry as the authoritative batch-16 evidence']
errors: []
```

### `dream7b-bpu-persistent-pair-cache-probe`

Source file: `scripts/probes/dream7b_bpu_persistent_pair_cache_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-persistent-pair-cache-probe
```

Default argument copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
```

Environment variables copied from the script:

```text
DREAM7B_BPU_PERSISTENT_PAIR_CACHE_WORKER_HOLD_SECONDS
DREAM7B_BPU_PERSISTENT_PAIR_CACHE_READY_TIMEOUT_SECONDS
DREAM7B_BPU_PERSISTENT_PAIR_CACHE_START_DELAY_SECONDS
```

Default values copied from the script:

```text
worker_hold_seconds = 20
worker_ready_timeout_seconds = 180
worker_start_delay_seconds = 2
```

Output files copied from the script:

```text
persistent_pair_cache_probe.json
persistent_pair_cache_probe.md
```

Pair workers copied from the script:

```text
pair_00: seg00_02, seg02_04
pair_01: seg04_07, seg07_10
pair_02: seg10_14, seg14_17
pair_03: seg17_21, seg21_24
pair_04: seg24_26, seg26_28
```

Output fields copied from the script:

```text
generated_at
verdict
run_dir
base_hbm_dir
fine_hbm_dir
worker_hold_seconds
worker_ready_timeout_seconds
worker_start_delay_seconds
pair_worker_count
launched_pair_worker_count
ready_pair_worker_count
failed_pair_worker_count
ready_pair_indexes
failed_pair_indexes
launch_stopped_reason
all_pair_workers_ready
next_optimization_target
ready_records
worker_outputs
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_persistent_pair_cache_20260605-234349/persistent_pair_cache_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_persistent_pair_cache_20260605-234349/persistent_pair_cache_probe.json
```

Verified persistent pair cache fields copied from `persistent_pair_cache_probe.json`:

```text
verdict: ok_dream7b_bpu_persistent_pair_cache_probe
pair_worker_count: 5
launched_pair_worker_count: 2
ready_pair_worker_count: 1
failed_pair_worker_count: 1
ready_pair_indexes: [0]
failed_pair_indexes: [1]
launch_stopped_reason: pair_01_seg04_07__seg07_10 did not reach ready status
all_pair_workers_ready: False
next_optimization_target: do not implement all-pair persistent cache yet; use this failure boundary to guide a different split or runtime-residency strategy
ready_records[0].segments: ['seg00_02', 'seg02_04']
ready_records[0].status: ready
ready_records[0].load_ms: 5218.181
ready_records[1].segments: ['seg04_07', 'seg07_10']
ready_records[1].status: failed
ready_records[1].exception_type: RuntimeError
ready_records[1].exception: DNN Error (code: -400001, desc: Memory alloc failed, please check error log) hbDNN initialize from multiple .hbm files failed.
errors: []
```

### `dream7b-bpu-held-pair-residency-matrix-probe`

Source file: `scripts/probes/dream7b_bpu_held_pair_residency_matrix_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-held-pair-residency-matrix-probe
```

Default argument copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
```

Environment variables copied from the script:

```text
DREAM7B_BPU_HELD_PAIR_MATRIX_HOLDER_READY_TIMEOUT_SECONDS
DREAM7B_BPU_HELD_PAIR_MATRIX_CANDIDATE_TIMEOUT_SECONDS
```

Default values copied from the script:

```text
holder_ready_timeout_seconds = 180
candidate_timeout_seconds = 180
```

Output files copied from the script:

```text
held_pair_residency_matrix_probe.json
held_pair_residency_matrix_probe.md
```

Pair workers copied from the script:

```text
pair_00: seg00_02, seg02_04
pair_01: seg04_07, seg07_10
pair_02: seg10_14, seg14_17
pair_03: seg17_21, seg21_24
pair_04: seg24_26, seg26_28
```

Output fields copied from the script:

```text
generated_at
verdict
run_dir
base_hbm_dir
fine_hbm_dir
holder_ready_timeout_seconds
candidate_timeout_seconds
pair_worker_count
ready_holder_pair_count
ready_holder_pair_indexes
matrix_entry_count
successful_pair_edge_count
failed_pair_edge_count
successful_pair_edges
failed_pair_edges
max_resident_pair_count_observed
next_optimization_target
holder_records
matrix_entries
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_held_pair_residency_matrix_20260605-235813/held_pair_residency_matrix_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_held_pair_residency_matrix_20260605-235813/held_pair_residency_matrix_probe.json
```

Verified held-pair matrix fields copied from `held_pair_residency_matrix_probe.json`:

```text
verdict: ok_dream7b_bpu_held_pair_residency_matrix_probe
pair_worker_count: 5
ready_holder_pair_count: 5
ready_holder_pair_indexes: [0, 1, 2, 3, 4]
matrix_entry_count: 20
successful_pair_edge_count: 0
failed_pair_edge_count: 20
successful_pair_edges: []
failed_pair_edges: [[0, 1], [0, 2], [0, 3], [0, 4], [1, 0], [1, 2], [1, 3], [1, 4], [2, 0], [2, 1], [2, 3], [2, 4], [3, 0], [3, 1], [3, 2], [3, 4], [4, 0], [4, 1], [4, 2], [4, 3]]
max_resident_pair_count_observed: 1
next_optimization_target: persistent multi-pair residency is not supported by this fine split; reduce individual pair HBM size or pursue a different split
holder_records[0].status: ready
holder_records[1].status: ready
holder_records[2].status: ready
holder_records[3].status: ready
holder_records[4].status: ready
matrix_entries[0].exception_type: RuntimeError
matrix_entries[0].exception: DNN Error (code: -400001, desc: Memory alloc failed, please check error log) hbDNN initialize from multiple .hbm files failed.
errors: []
```

### `dream7b-bpu-single-segment-residency-matrix-probe`

Source file: `scripts/probes/dream7b_bpu_single_segment_residency_matrix_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-single-segment-residency-matrix-probe
```

Default argument copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
```

Environment variables copied from the script:

```text
DREAM7B_BPU_SINGLE_SEGMENT_MATRIX_HOLDER_READY_TIMEOUT_SECONDS
DREAM7B_BPU_SINGLE_SEGMENT_MATRIX_CANDIDATE_TIMEOUT_SECONDS
```

Default values copied from the script:

```text
holder_ready_timeout_seconds = 180
candidate_timeout_seconds = 180
```

Output files copied from the script:

```text
single_segment_residency_matrix_probe.json
single_segment_residency_matrix_probe.md
```

Segments copied from the script:

```text
segment_00: seg00_02
segment_01: seg02_04
segment_02: seg04_07
segment_03: seg07_10
segment_04: seg10_14
segment_05: seg14_17
segment_06: seg17_21
segment_07: seg21_24
segment_08: seg24_26
segment_09: seg26_28
```

Output fields copied from the script:

```text
generated_at
verdict
run_dir
base_hbm_dir
fine_hbm_dir
holder_ready_timeout_seconds
candidate_timeout_seconds
segment_count
ready_holder_segment_count
ready_holder_segment_indexes
matrix_entry_count
successful_segment_edge_count
failed_segment_edge_count
successful_segment_edges
failed_segment_edges
max_resident_segment_count_observed
next_optimization_target
holder_records
matrix_entries
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_single_segment_residency_matrix_20260606-002628/single_segment_residency_matrix_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_single_segment_residency_matrix_20260606-002628/single_segment_residency_matrix_probe.json
```

Verified single-segment matrix fields copied from `single_segment_residency_matrix_probe.json`:

```text
verdict: ok_dream7b_bpu_single_segment_residency_matrix_probe
segment_count: 10
ready_holder_segment_count: 10
matrix_entry_count: 90
successful_segment_edge_count: 90
failed_segment_edge_count: 0
max_resident_segment_count_observed: 2
next_optimization_target: inspect successful single-segment coexistence edges and then probe multi-segment cliques before changing the production runner
errors: []
```

### `dream7b-bpu-persistent-segment-cache-probe`

Source file: `scripts/probes/dream7b_bpu_persistent_segment_cache_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-persistent-segment-cache-probe
```

Default argument copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
```

Environment variables copied from the script:

```text
DREAM7B_BPU_PERSISTENT_SEGMENT_CACHE_WORKER_HOLD_SECONDS
DREAM7B_BPU_PERSISTENT_SEGMENT_CACHE_READY_TIMEOUT_SECONDS
DREAM7B_BPU_PERSISTENT_SEGMENT_CACHE_START_DELAY_SECONDS
```

Default values copied from the script:

```text
hold_seconds = 5
ready_timeout_seconds = 180
start_delay_seconds = 1
```

Output files copied from the script:

```text
persistent_segment_cache_probe.json
persistent_segment_cache_probe.md
```

Segments copied from the script:

```text
segment_00: seg00_02
segment_01: seg02_04
segment_02: seg04_07
segment_03: seg07_10
segment_04: seg10_14
segment_05: seg14_17
segment_06: seg17_21
segment_07: seg21_24
segment_08: seg24_26
segment_09: seg26_28
```

Output fields copied from the script:

```text
generated_at
verdict
run_dir
base_hbm_dir
fine_hbm_dir
hold_seconds
ready_timeout_seconds
start_delay_seconds
segment_worker_count
launched_segment_worker_count
ready_segment_worker_count
failed_segment_worker_count
ready_segment_indexes
failed_segment_indexes
all_segment_workers_ready
launch_stopped_reason
max_resident_segment_count_observed
next_optimization_target
ready_records
failed_records
records
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_persistent_segment_cache_20260606-005633/persistent_segment_cache_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_persistent_segment_cache_20260606-005633/persistent_segment_cache_probe.json
```

Verified persistent segment cache fields copied from `persistent_segment_cache_probe.json`:

```text
verdict: ok_dream7b_bpu_persistent_segment_cache_probe
segment_worker_count: 10
launched_segment_worker_count: 3
ready_segment_worker_count: 2
failed_segment_worker_count: 1
ready_segment_indexes: [0, 1]
failed_segment_indexes: [2]
all_segment_workers_ready: False
launch_stopped_reason: segment_02_seg04_07 did not reach ready status
max_resident_segment_count_observed: 2
next_optimization_target: use the ready prefix and failure record to choose a smaller segment split or different runtime-residency strategy
failed_records[0].exception_type: RuntimeError
failed_records[0].exception: DNN Error (code: -400001, desc: Memory alloc failed, please check error log) hbDNN initialize from multiple .hbm files failed.
errors: []
```

### `dream7b-bpu-single-segment-triplet-residency-probe`

Source file: `scripts/probes/dream7b_bpu_single_segment_triplet_residency_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-single-segment-triplet-residency-probe
```

Default argument copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
```

Environment variables copied from the script:

```text
DREAM7B_BPU_SINGLE_SEGMENT_TRIPLET_READY_TIMEOUT_SECONDS
DREAM7B_BPU_SINGLE_SEGMENT_TRIPLET_START_DELAY_SECONDS
DREAM7B_BPU_SINGLE_SEGMENT_TRIPLET_MAX_COMBINATIONS
```

Default values copied from the script:

```text
ready_timeout_seconds = 180
start_delay_seconds = 0
max_combinations = 120
```

Output files copied from the script:

```text
single_segment_triplet_residency_probe.json
single_segment_triplet_residency_probe.md
```

Segments copied from the script:

```text
segment_00: seg00_02
segment_01: seg02_04
segment_02: seg04_07
segment_03: seg07_10
segment_04: seg10_14
segment_05: seg14_17
segment_06: seg17_21
segment_07: seg21_24
segment_08: seg24_26
segment_09: seg26_28
```

Output fields copied from the script:

```text
generated_at
verdict
run_dir
base_hbm_dir
fine_hbm_dir
ready_timeout_seconds
start_delay_seconds
max_combinations
segment_count
total_triplet_combination_count
tested_triplet_combination_count
successful_triplet_count
failed_triplet_count
successful_triplets
failed_triplets
max_resident_segment_count_observed
next_optimization_target
combination_records
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_single_segment_triplet_residency_20260606-121243/single_segment_triplet_residency_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_single_segment_triplet_residency_20260606-121243/single_segment_triplet_residency_probe.json
```

Verified single-segment triplet residency fields copied from `single_segment_triplet_residency_probe.json`:

```text
verdict: ok_dream7b_bpu_single_segment_triplet_residency_probe
tested_triplet_combination_count: 120
successful_triplet_count: 20
failed_triplet_count: 100
max_resident_segment_count_observed: 3
successful_triplets: [[0, 1, 8], [1, 2, 3], [1, 2, 5], [1, 2, 7], [1, 2, 8], [1, 3, 5], [1, 3, 7], [1, 3, 8], [1, 4, 8], [1, 5, 7], [1, 5, 8], [1, 6, 8], [1, 7, 8], [1, 8, 9], [2, 3, 8], [2, 5, 8], [2, 7, 8], [3, 5, 8], [3, 7, 8], [5, 7, 8]]
next_optimization_target: inspect successful triplets and then test a persistent topology seeded by those segment groups
errors: []
```

### `dream7b-bpu-seeded-quad-residency-probe`

Source file: `scripts/probes/dream7b_bpu_seeded_quad_residency_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-seeded-quad-residency-probe
```

Default argument copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
```

Environment variables copied from the script:

```text
DREAM7B_BPU_SEEDED_QUAD_TRIPLET_JSON
DREAM7B_BPU_SEEDED_QUAD_READY_TIMEOUT_SECONDS
DREAM7B_BPU_SEEDED_QUAD_START_DELAY_SECONDS
DREAM7B_BPU_SEEDED_QUAD_MAX_COMBINATIONS
```

Default values copied from the script:

```text
triplet_json = latest dream7b_bpu_single_segment_triplet_residency_*/single_segment_triplet_residency_probe.json under report_root
ready_timeout_seconds = 180
start_delay_seconds = 0
max_combinations = 140
```

Output files copied from the script:

```text
seeded_quad_residency_probe.json
seeded_quad_residency_probe.md
```

Output fields copied from the script:

```text
generated_at
verdict
run_dir
base_hbm_dir
fine_hbm_dir
triplet_json
source_successful_triplet_count
ready_timeout_seconds
start_delay_seconds
max_combinations
segment_count
seeded_quad_candidate_count
tested_seeded_quad_count
successful_seeded_quad_count
failed_seeded_quad_count
successful_seeded_quads
failed_seeded_quads
max_resident_segment_count_observed
next_optimization_target
combination_records
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_seeded_quad_residency_20260606-124305/seeded_quad_residency_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_seeded_quad_residency_20260606-124305/seeded_quad_residency_probe.json
```

Verified seeded quad residency fields copied from `seeded_quad_residency_probe.json`:

```text
verdict: ok_dream7b_bpu_seeded_quad_residency_probe
source_successful_triplet_count: 20
seeded_quad_candidate_count: 84
tested_seeded_quad_count: 84
successful_seeded_quad_count: 0
failed_seeded_quad_count: 84
successful_seeded_quads: []
max_resident_segment_count_observed: 3
next_optimization_target: no tested seeded quad is resident; use successful triplets as the current persistent topology seed
errors: []
```

### `dream7b-bpu-segment-capacity-planner-probe`

Source file: `scripts/probes/dream7b_bpu_segment_capacity_planner_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-segment-capacity-planner-probe
```

Default argument copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
```

Environment variables copied from the script:

```text
DREAM7B_BPU_SEGMENT_CAPACITY_MODEL_REPORT_ROOT
DREAM7B_BPU_SEGMENT_CAPACITY_BASE_HBM_DIR
DREAM7B_BPU_SEGMENT_CAPACITY_FINE_HBM_DIR
```

Default values copied from the script:

```text
model_report_root = /mnt/nas/openclaw/reports/models
base_hbm_dir = /home/sunrise/.cache/openclaw/dream7b-hbm/segments6
fine_hbm_dir = /home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16
```

Output files copied from the script:

```text
segment_capacity_planner_probe.json
segment_capacity_planner_probe.md
```

Output fields copied from the script:

```text
generated_at
verdict
run_dir
model_report_root
base_hbm_dir
fine_hbm_dir
segment_count
hbm_segment_inventory
total_segment_hbm_size_bytes
largest_segment_indexes_by_size
smallest_segment_indexes_by_size
residency_reports
current_split_capacity
triplet_success_appearance_by_segment_index
triplet_failed_appearance_by_segment_index
triplet_failed_worker_count_by_segment_index
triplet_ready_worker_count_by_segment_index
recommended_anchor_segment_indexes
recommended_anchor_segments
recommended_resplit_segment_indexes
recommended_resplit_segments
next_optimization_target
warnings
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_capacity_planner_20260606-054148/segment_capacity_planner_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_capacity_planner_20260606-054148/segment_capacity_planner_probe.json
```

Verified segment capacity planner fields copied from `segment_capacity_planner_probe.json`:

```text
verdict: ok_dream7b_bpu_segment_capacity_planner_probe
segment_count: 10
current_split_capacity.max_resident_segment_count_observed: 3
current_split_capacity.successful_triplet_count: 20
current_split_capacity.successful_seeded_quad_count: 0
current_split_capacity.current_split_quad_residency_supported: False
current_split_capacity.selected_pair: [1, 8]
current_split_capacity.selected_pair_matches_anchor_pair: True
recommended_anchor_segment_indexes: [1, 8]
recommended_resplit_segment_indexes: [0, 9, 4, 6]
largest_segment_indexes_by_size: [0, 9, 4, 6, 7, 3, 2, 5, 8, 1]
next_optimization_target: recompile or split weak residency segments [0, 9, 4, 6] into smaller HBM shards before attempting four-resident forward path or default-service promotion
errors: []
```

### `compile_dream_segments_seq16_resplit_probe.sh`

Source file: `scripts/probes/compile_dream_segments_seq16_resplit_probe.sh`

Build host:

```text
WSL1 AVX build host
```

Environment variables copied from the script:

```text
DREAM_RESPLIT_VENV
DREAM_RESPLIT_MODEL_DIR
DREAM_RESPLIT_OUTPUT_ROOT
DREAM_RESPLIT_SEQ_LEN
DREAM_RESPLIT_SPECS
DREAM_RESPLIT_EXPECTED_SPECS
DREAM_RESPLIT_ALLOW_PARTIAL
DREAM_RESPLIT_SKIP_EXISTING
```

Default values copied from the script:

```text
venv = /opt/digua/dream-s100-oellm-venv
model_dir = /opt/digua/dream_hf
output_root = /opt/digua/dream7b-segments-seq16-resplit
seq_len = 16
specs = 0:1 1:2 10:12 12:14 17:19 19:21 26:27 27:28
expected_specs = 0:1 1:2 10:12 12:14 17:19 19:21 26:27 27:28
allow_partial = 0
skip_existing = 1
```

Compile command copied from the script:

```text
python -X faulthandler scripts/probes/compile_dream_segmented_full_forward.py --model-dir "$model_dir" --output-dir "$dir" --seq-len "$seq_len" --segment-start "$s" --segment-end "$e" --dtype float32 --march nash-e --w-bits 8
```

Verified compile report:

```text
/tmp/dream7b_resplit_compile_reports/dream7b_resplit_compile_20260608-112349/resplit_compile_probe.json
```

Verified recovery report:

```text
/tmp/dream7b_resplit_compile_reports_resume/dream7b_resplit_compile_20260608-120008/resplit_compile_probe.json
```

Verified fields copied from `resplit_compile_probe.json`:

```text
verdict: ok_dream7b_resplit_compile_probe
output_root: /opt/digua/dream7b-segments-seq16-resplit
seq_len: 16
specs: ['0:1', '1:2', '10:12', '12:14', '17:19', '19:21', '26:27', '27:28']
compiled_spec_count: 8
expected_spec_count: 8
hbm_success_count: 8
skipped_existing_count: 8
failed_spec_count: 0
manifest_path: /opt/digua/dream7b-segments-seq16-resplit/manifest.sha256
errors: []
```

### `dream7b-bpu-resplit-hbm-artifact-inventory-probe`

Source file: `scripts/probes/dream7b_bpu_resplit_hbm_artifact_inventory_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-resplit-hbm-artifact-inventory-probe
```

Environment variables copied from the script:

```text
DREAM7B_BPU_RESPLIT_HBM_DIR
DREAM7B_BPU_RESPLIT_EXPECTED_SPECS
DREAM7B_BPU_RESPLIT_VERIFY_MANIFEST
```

Default values copied from the script:

```text
hbm_dir = /mnt/nas/openclaw/models/dream7b-hbm/resplit-seq16
expected_specs = 0:1 1:2 10:12 12:14 17:19 19:21 26:27 27:28
verify_manifest = 1
```

Verified NAS report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_hbm_artifact_inventory_20260606-071645/resplit_hbm_artifact_inventory_probe.json
```

Verified S100P local-cache report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_hbm_artifact_inventory_20260606-071820/resplit_hbm_artifact_inventory_probe.json
```

Verified fields copied from `resplit_hbm_artifact_inventory_probe.json`:

```text
verdict: ok_dream7b_bpu_resplit_hbm_artifact_inventory_probe
expected_hbm_count: 8
existing_hbm_count: 8
manifest_entry_count: 8
manifest_verified_count: 8
total_hbm_size_bytes: 3851983368
total_hbm_size_gib: 3.587439
errors: []
```

Verified top-window NAS report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_hbm_artifact_inventory_20260606-110342/resplit_hbm_artifact_inventory_probe.json
```

Verified top-window S100P local-cache report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_hbm_artifact_inventory_20260606-110343/resplit_hbm_artifact_inventory_probe.json
```

Verified top-window fields copied from `resplit_hbm_artifact_inventory_probe.json`:

```text
verdict: ok_dream7b_bpu_resplit_hbm_artifact_inventory_probe
hbm_dir: /mnt/nas/openclaw/models/dream7b-hbm/resplit-topwindow-seq16
hbm_dir: /home/sunrise/.cache/openclaw/dream7b-hbm/resplit-topwindow-seq16
expected_specs: ['7:8', '8:10', '21:22', '22:24']
expected_hbm_count: 4
existing_hbm_count: 4
manifest_entry_count: 4
manifest_verified_count: 4
total_hbm_size_bytes: 1373714912
errors: []
```

### `dream7b-bpu-resplit-forward`

Source file: `scripts/dream7b-bpu-resplit-forward.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-resplit-forward
```

Environment variables copied from the script:

```text
DREAM7B_BPU_HBM_DIR
DREAM7B_BPU_FINE_HBM_DIR
DREAM7B_BPU_RESPLIT_HBM_DIR
DREAM7B_BPU_TOPWINDOW_HBM_DIR
DREAM7B_BPU_RESPLIT_SEGMENT_PLAN
DREAM7B_BPU_RESPLIT_WINDOW_SIZE
DREAM7B_BPU_RESPLIT_CHILD_WINDOW_MODE
DREAM7B_BPU_RESPLIT_CHILD_RUNTIME_MODE
DREAM7B_BPU_RESPLIT_WINDOW_EXECUTION_MODE
```

Default values copied from the script:

```text
base_hbm_dir = /home/sunrise/.cache/openclaw/dream7b-hbm/segments6
fine_hbm_dir = /home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16
resplit_hbm_dir = /home/sunrise/.cache/openclaw/dream7b-hbm/resplit-seq16
topwindow_hbm_dir = /home/sunrise/.cache/openclaw/dream7b-hbm/resplit-topwindow-seq16
segment_plan = resplit-adjacent
window_size = 2
child_window_mode = pair
child_runtime_mode = packed
window_execution_mode = in-process
```

Injected arguments copied from the script:

```text
--hbm-dir
--fine-hbm-dir
--resplit-hbm-dir
--topwindow-hbm-dir
--segment-plan
--residency-window-size
--child-window-mode
--child-runtime-mode
--window-execution-mode
```

Runtime support copied from `scripts/probes/dream7b_segmented_hbm_python_forward.py`:

```text
RESPLIT_ADJACENT_SEGMENTS
RESPLIT_TOPWINDOW_ADJACENT_SEGMENTS
--resplit-hbm-dir
--topwindow-hbm-dir
resplit-adjacent
resplit-topwindow-adjacent
resplit_hbm_dir
topwindow_hbm_dir
```

### `dream7b-bpu-resplit-segment-residency-probe`

Source file: `scripts/probes/dream7b_bpu_resplit_segment_residency_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-resplit-segment-residency-probe
```

Default values copied from the script:

```text
base_hbm_dir = /home/sunrise/.cache/openclaw/dream7b-hbm/segments6
fine_hbm_dir = /home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16
resplit_hbm_dir = /home/sunrise/.cache/openclaw/dream7b-hbm/resplit-seq16
venv = /mnt/nas/openclaw/runtimes/hbm-runtime-venv
single_timeout_seconds = 180
holder_ready_timeout_seconds = 180
candidate_timeout_seconds = 180
prefix_start_delay_seconds = 1
```

Verified report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_segment_residency_20260606-072919/resplit_segment_residency_probe.json
```

Verified fields copied from `resplit_segment_residency_probe.json`:

```text
verdict: ok_dream7b_bpu_resplit_segment_residency_probe
segment_count: 14
single_success_count: 14
adjacent_pair_count: 13
adjacent_pair_success_count: 13
resplit_adjacent_pair_supported: True
ready_prefix_count: 3
first_prefix_failure.segment: seg04_07
next_optimization_target: adapt the Dream forward runtime to a resplit-layout segment plan and benchmark load/run telemetry
errors: []
```

### `dream7b-bpu-resplit-forward-probe`

Source file: `scripts/probes/dream7b_bpu_resplit_forward_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-resplit-forward-probe
```

Default values copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
tokens = 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16
DREAM7B_BPU_RESPLIT_FORWARD_EXPECTED_BASE_HBM_DIR
DREAM7B_BPU_RESPLIT_FORWARD_EXPECTED_FINE_HBM_DIR
DREAM7B_BPU_RESPLIT_FORWARD_EXPECTED_RESPLIT_HBM_DIR
expected_base_hbm_dir = /home/sunrise/.cache/openclaw/dream7b-hbm/segments6
expected_fine_hbm_dir = /home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16
expected_resplit_hbm_dir = /home/sunrise/.cache/openclaw/dream7b-hbm/resplit-seq16
```

Verified report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_forward_20260606-074419/resplit_forward_probe.json
```

Verified fields copied from `resplit_forward_probe.json`:

```text
verdict: ok_dream7b_bpu_resplit_forward_probe
segment_plan: resplit-adjacent
residency_window_size: 2
execution_mode: pair_in_process
window_execution_mode: in-process
child_window_mode: pair
child_runtime_mode: packed
child_process_count: 0
hbm_dir: /home/sunrise/.cache/openclaw/dream7b-hbm/segments6
fine_hbm_dir: /home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16
resplit_hbm_dir: /home/sunrise/.cache/openclaw/dream7b-hbm/resplit-seq16
batch_count: 1
top_k: 5
topk_last_position: [{'token_id': 11, 'score': 2.890040397644043}, {'token_id': 279, 'score': 2.2086405754089355}, {'token_id': 220, 'score': 2.064786672592163}, {'token_id': 419, 'score': 2.022850275039673}, {'token_id': 481, 'score': 1.9011082649230957}]
final_shape: [1, 16, 152064]
final_dtype: float32
segment_event_count: 14
segment_sources: ['base', 'fine', 'resplit']
wall_ms: 24260.349
load_ms: 23906.713
run_ms: 152.863
amortized_wall_ms_per_forward: 24260.349
amortized_load_ms_per_forward: 23906.713
amortized_run_ms_per_forward: 152.863
errors: []
```

### `dream7b-bpu-resplit-batch-forward`

Source file: `scripts/dream7b-bpu-resplit-batch-forward.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-resplit-batch-forward
```

Environment variables copied from the script:

```text
DREAM7B_BPU_HBM_DIR
DREAM7B_BPU_FINE_HBM_DIR
DREAM7B_BPU_RESPLIT_HBM_DIR
DREAM7B_BPU_RESPLIT_BATCH_WINDOW_SIZE
DREAM7B_BPU_RESPLIT_BATCH_CHILD_WINDOW_MODE
DREAM7B_BPU_RESPLIT_BATCH_CHILD_RUNTIME_MODE
DREAM7B_BPU_RESPLIT_BATCH_WINDOW_EXECUTION_MODE
DREAM7B_BPU_RESPLIT_TOKENS_BATCH_JSON
```

Default values copied from the script:

```text
base_hbm_dir = /home/sunrise/.cache/openclaw/dream7b-hbm/segments6
fine_hbm_dir = /home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16
resplit_hbm_dir = /home/sunrise/.cache/openclaw/dream7b-hbm/resplit-seq16
topwindow_hbm_dir = /home/sunrise/.cache/openclaw/dream7b-hbm/resplit-topwindow-seq16
segment_plan = resplit-adjacent
window_size = 2
child_window_mode = pair
child_runtime_mode = packed
window_execution_mode = window-batch
```

Injected arguments copied from the script:

```text
--hbm-dir
--fine-hbm-dir
--resplit-hbm-dir
--topwindow-hbm-dir
--segment-plan
--residency-window-size
--child-window-mode
--child-runtime-mode
--window-execution-mode
--tokens-batch-json
```

### `dream7b-bpu-resplit-batch-forward-probe`

Source file: `scripts/probes/dream7b_bpu_resplit_batch_forward_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-resplit-batch-forward-probe
```

Environment variables copied from the script:

```text
DREAM7B_BPU_RESPLIT_BATCH_FORWARD_COUNT
DREAM7B_BPU_RESPLIT_BATCH_FORWARD_TOP_K
DREAM7B_BPU_RESPLIT_BATCH_FORWARD_TIMEOUT_SEC
```

Default values copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
batch_count = 16
top_k = 3
timeout_sec = 900
```

Verified report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_batch_forward_20260606-075837/resplit_batch_forward_probe.json
```

Verified fields copied from `resplit_batch_forward_probe.json`:

```text
verdict: ok_dream7b_bpu_resplit_batch_forward_probe
segment_plan: resplit-adjacent
residency_window_size: 2
execution_mode: pair_window_batch
window_execution_mode: window-batch
child_window_mode: pair
child_runtime_mode: packed
child_process_count: 0
batch_count: 16
top_k: 3
topk_last_position_by_batch_count: 16
final_shape_count: 16
segment_event_count: 224
expected_segment_event_count: 224
segment_sources: ['base', 'fine', 'resplit']
hbm_dir: /home/sunrise/.cache/openclaw/dream7b-hbm/segments6
fine_hbm_dir: /home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16
resplit_hbm_dir: /home/sunrise/.cache/openclaw/dream7b-hbm/resplit-seq16
wall_ms: 26679.548
load_ms: 24002.465
run_ms: 2396.71
amortized_wall_ms_per_forward: 1667.472
amortized_load_ms_per_forward: 1500.154
amortized_run_ms_per_forward: 149.794
load_to_run_ratio: 10.014756
errors: []
```

### `dream7b-bpu-resplit-batch-telemetry-probe`

Source file: `scripts/probes/dream7b_bpu_resplit_batch_telemetry_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-resplit-batch-telemetry-probe
```

Environment variables copied from the script:

```text
DREAM7B_BPU_RESPLIT_BATCH_TELEMETRY_COUNT
DREAM7B_BPU_RESPLIT_BATCH_TELEMETRY_MONITOR_DELAY_MS
DREAM7B_BPU_RESPLIT_BATCH_TELEMETRY_MONITOR_SAMPLE_COUNT
DREAM7B_BPU_RESPLIT_BATCH_TELEMETRY_TOP_K
DREAM7B_BPU_RESPLIT_BATCH_TELEMETRY_TIMEOUT_SEC
DREAM7B_BPU_RESPLIT_BATCH_TELEMETRY_FORWARD_CMD
DREAM7B_BPU_RESPLIT_BATCH_TELEMETRY_EXPECTED_SEGMENT_PLAN
DREAM7B_BPU_RESPLIT_BATCH_TELEMETRY_EXPECTED_SEGMENT_EVENT_COUNT
DREAM7B_BPU_RESPLIT_BATCH_TELEMETRY_EXPECTED_SEGMENT_SOURCES
```

Default values copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
batch_count = 16
monitor_delay_ms = 100
monitor_sample_count = 320
top_k = 3
timeout_sec = 900
forward_cmd = dream7b-bpu-resplit-batch-forward
expected_segment_plan = resplit-adjacent
expected_segment_event_count =
expected_segment_sources = base fine resplit
```

Verified report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_batch_telemetry_20260606-080917/resplit_batch_telemetry_probe.json
```

Verified fields copied from `resplit_batch_telemetry_probe.json`:

```text
verdict: ok_dream7b_bpu_resplit_batch_telemetry_probe
batch_count: 16
bpu_loading_sample_count: 261
nonzero_bpu_loading_sample_count: 30
max_bpu_loading: 100.0
avg_bpu_loading: 8.697
forward_cmd: dream7b-bpu-resplit-batch-forward
forward_metrics.segment_plan: resplit-adjacent
forward_metrics.execution_mode: pair_window_batch
forward_metrics.window_execution_mode: window-batch
forward_metrics.child_process_count: 0
forward_metrics.segment_event_count: 224
forward_metrics.expected_segment_event_count: 224
forward_metrics.final_shape_count: 16
forward_metrics.topk_last_position_by_batch_count: 16
forward_metrics.wall_ms: 26251.992
forward_metrics.load_ms: 23570.225
forward_metrics.run_ms: 2400.803
forward_metrics.load_to_run_ratio: 9.817642
forward_metrics.amortized_wall_ms_per_forward: 1640.749
forward_metrics.amortized_load_ms_per_forward: 1473.139
forward_metrics.amortized_run_ms_per_forward: 150.05
next_optimization_target: reduce resplit batch HBM load overhead before expecting sustained 128TOPS-level average utilization
errors: []
```

Verified top-window report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_batch_telemetry_20260606-112018/resplit_batch_telemetry_probe.json
```

Verified top-window fields copied from `resplit_batch_telemetry_probe.json`:

```text
verdict: ok_dream7b_bpu_resplit_batch_telemetry_probe
batch_count: 16
expected_segment_plan: resplit-topwindow-adjacent
expected_segment_event_count: 256
max_bpu_loading: 100.0
avg_bpu_loading: 8.946
forward_metrics.segment_plan: resplit-topwindow-adjacent
forward_metrics.segment_event_count: 256
forward_metrics.expected_segment_event_count: 256
forward_metrics.segment_sources: ['base', 'fine', 'resplit', 'topwindow']
forward_metrics.load_ms: 23476.584
forward_metrics.run_ms: 2421.61
forward_metrics.load_to_run_ratio: 9.694618
forward_metrics.amortized_load_ms_per_forward: 1467.286
forward_metrics.amortized_run_ms_per_forward: 151.351
forward_metrics.topwindow_hbm_dir: /home/sunrise/.cache/openclaw/dream7b-hbm/resplit-topwindow-seq16
errors: []
```

### `dream7b-bpu-resplit-window-cost-probe`

Source file: `scripts/probes/dream7b_bpu_resplit_window_cost_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-resplit-window-cost-probe
```

Environment variables copied from the script:

```text
DREAM7B_BPU_RESPLIT_WINDOW_COST_MODEL_REPORT_ROOT
DREAM7B_BPU_RESPLIT_WINDOW_COST_MIN_BATCH_COUNT
DREAM7B_BPU_RESPLIT_WINDOW_COST_EXPECTED_WINDOW_COUNT
DREAM7B_BPU_RESPLIT_WINDOW_COST_EXPECTED_SEGMENT_EVENT_COUNT
DREAM7B_BPU_RESPLIT_WINDOW_COST_EXPECTED_SEGMENT_PLAN
```

Default values copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
model_report_root = /mnt/nas/openclaw/reports/models
min_batch_count = 16
expected_window_count = 7
expected_segment_event_count = 224
expected_segment_plan = resplit-adjacent
```

Verified report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_window_cost_20260606-083152/resplit_window_cost_probe.json
```

Verified fields copied from `resplit_window_cost_probe.json`:

```text
verdict: ok_dream7b_bpu_resplit_window_cost_probe
resplit_batch_telemetry_path: /mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_batch_telemetry_20260606-080917/resplit_batch_telemetry_probe.json
forward_summary_path: /mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_batch_telemetry_20260606-080917/forward/summary.json
batch_count: 16
segment_plan: resplit-adjacent
execution_mode: pair_window_batch
window_execution_mode: window-batch
child_process_count: 0
segment_event_count: 224
window_count: 7
total_load_ms: 23570.225
total_run_ms: 2400.803
load_to_run_ratio: 9.817642
amortized_load_ms_per_forward: 1473.139062
amortized_run_ms_per_forward: 150.050187
top_load_window.resident_segments: ['seg07_10', 'seg10_12']
top_load_window.load_ms: 3842.891
top_load_window.load_share: 0.16304
top_load_to_run_ratio_window.resident_segments: ['seg00_01', 'seg01_02']
top_load_to_run_ratio_window.load_to_run_ratio: 18.428821
next_optimization_target: reduce packed HBM load cost for top ranked resplit windows before expecting sustained 128TOPS-level average utilization
errors: []
```

Verified top-window window-cost report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_window_cost_20260606-112223/resplit_window_cost_probe.json
```

Verified top-window fields copied from `resplit_window_cost_probe.json`:

```text
verdict: ok_dream7b_bpu_resplit_window_cost_probe
segment_plan: resplit-topwindow-adjacent
expected_segment_plan: resplit-topwindow-adjacent
batch_count: 16
segment_event_count: 256
window_count: 8
total_load_ms: 23476.584
total_run_ms: 2421.61
load_to_run_ratio: 9.694618
amortized_load_ms_per_forward: 1467.2865
amortized_run_ms_per_forward: 151.350625
top_load_window.resident_segments: ['seg14_17', 'seg17_19']
top_load_window.load_ms: 3505.334
top_load_to_run_ratio_window.resident_segments: ['seg00_01', 'seg01_02']
top_load_to_run_ratio_window.load_to_run_ratio: 18.920179
errors: []
```

### `dream7b-bpu-persistent-triplet-topology-probe`

Source file: `scripts/probes/dream7b_bpu_persistent_triplet_topology_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-persistent-triplet-topology-probe
```

Default argument copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
```

Environment variables copied from the script:

```text
DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_TRIPLET_JSON
DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_HOLD_SECONDS
DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_READY_TIMEOUT_SECONDS
DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_POLL_INTERVAL_SECONDS
DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_START_DELAY_SECONDS
DREAM7B_BPU_PERSISTENT_TRIPLET_TOPOLOGY_MAX_TRIPLETS
```

Default values copied from the script:

```text
triplet_json = latest dream7b_bpu_single_segment_triplet_residency_*/single_segment_triplet_residency_probe.json under report_root
hold_seconds = 10
ready_timeout_seconds = 180
poll_interval_seconds = 2
start_delay_seconds = 0
max_triplets = 20
```

Output files copied from the script:

```text
persistent_triplet_topology_probe.json
persistent_triplet_topology_probe.md
```

Output fields copied from the script:

```text
generated_at
verdict
run_dir
base_hbm_dir
fine_hbm_dir
triplet_json
source_successful_triplet_count
tested_triplet_topology_count
stable_triplet_topology_count
failed_triplet_topology_count
hold_seconds
ready_timeout_seconds
poll_interval_seconds
start_delay_seconds
max_triplets
segment_count
stable_triplets
failed_triplets
selected_topology
selection_rule
max_resident_segment_count_observed
next_optimization_target
topology_records
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_persistent_triplet_topology_20260606-131107/persistent_triplet_topology_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_persistent_triplet_topology_20260606-131107/persistent_triplet_topology_probe.json
```

Verified persistent triplet topology fields copied from `persistent_triplet_topology_probe.json`:

```text
verdict: ok_dream7b_bpu_persistent_triplet_topology_probe
source_successful_triplet_count: 20
tested_triplet_topology_count: 20
stable_triplet_topology_count: 20
failed_triplet_topology_count: 0
hold_seconds: 10.0
poll_interval_seconds: 2.0
stable_triplets: [[0, 1, 8], [1, 2, 3], [1, 2, 5], [1, 2, 7], [1, 2, 8], [1, 3, 5], [1, 3, 7], [1, 3, 8], [1, 4, 8], [1, 5, 7], [1, 5, 8], [1, 6, 8], [1, 7, 8], [1, 8, 9], [2, 3, 8], [2, 5, 8], [2, 7, 8], [3, 5, 8], [3, 7, 8], [5, 7, 8]]
selected_topology: [0, 1, 8]
selection_rule: first stable topology in source successful_triplets order
max_resident_segment_count_observed: 3
next_optimization_target: wire the selected stable triplet into a forward-path experiment and compare HBM load share against the current pair-window production path
errors: []
```

### `dream7b-bpu-window3-forward-feasibility-probe`

Source file: `scripts/probes/dream7b_bpu_window3_forward_feasibility_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-window3-forward-feasibility-probe
```

Default argument copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
```

Environment variables copied from the script:

```text
DREAM7B_BPU_WINDOW3_FORWARD_CMD
DREAM7B_BPU_WINDOW3_FORWARD_TIMEOUT_SEC
DREAM7B_BPU_WINDOW3_FORWARD_TOP_K
```

Default values copied from the script:

```text
forward_cmd = dream7b-bpu-fine-batch-forward
timeout_sec = 240
top_k = 3
```

Output files copied from the script:

```text
window3_forward_feasibility_probe.json
window3_forward_feasibility_probe.md
forward.stdout
forward.stderr
forward.returncode
```

Output fields copied from the script:

```text
generated_at
verdict
run_dir
forward_cmd
forward_dir
command
timeout_sec
top_k
returncode
timed_out
wall_ms
stdout
stderr
summary_json
direct_window3_forward_supported
expected_window3_failure_observed
stderr_contains_memory_alloc_failure
window_size
child_window_mode
child_runtime_mode
window_execution_mode
next_optimization_target
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_window3_forward_feasibility_20260606-133931/window3_forward_feasibility_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_window3_forward_feasibility_20260606-133931/window3_forward_feasibility_probe.json
```

Verified window3 forward feasibility fields copied from `window3_forward_feasibility_probe.json`:

```text
verdict: ok_dream7b_bpu_window3_forward_feasibility_probe
returncode: 1
direct_window3_forward_supported: False
expected_window3_failure_observed: True
stderr_contains_memory_alloc_failure: True
window_size: 3
child_window_mode: pair
child_runtime_mode: packed
window_execution_mode: window-batch
next_optimization_target: do not switch production defaults to window3; use selected stable triplet worker or a new HBM split for the next forward-path experiment
errors: []
```

### `dream7b-bpu-selected-triplet-forward-path-probe`

Source file: `scripts/probes/dream7b_bpu_selected_triplet_forward_path_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-selected-triplet-forward-path-probe
```

Default argument copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
```

Environment variables copied from the script:

```text
DREAM7B_BPU_HBM_DIR
DREAM7B_BPU_FINE_HBM_DIR
DREAM7B_BPU_SELECTED_TRIPLET_TOPOLOGY_JSON
DREAM7B_BPU_SELECTED_TRIPLET_BASELINE_FORWARD_CMD
DREAM7B_BPU_SELECTED_TRIPLET_BATCH_COUNT
DREAM7B_BPU_SELECTED_TRIPLET_TOP_K
DREAM7B_BPU_SELECTED_TRIPLET_TIMEOUT_SEC
DREAM7B_BPU_SELECTED_TRIPLET_ALLOW_CRASH_RETRY
```

Default values copied from the script:

```text
base_hbm_dir = /home/sunrise/.cache/openclaw/dream7b-hbm/segments6
fine_hbm_dir = /home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16
forward_cmd = dream7b-bpu-fine-batch-forward
batch_count = 4
top_k = 3
timeout_sec = 900
```

Output files copied from the script:

```text
tokens_batch.json
selected_triplet_forward_summary.json
selected_triplet_forward_path_probe.json
selected_triplet_forward_path_probe.md
baseline.forward.stdout
baseline.forward.stderr
baseline_pair_window_forward/summary.json
```

Crash/reboot guard copied from the script:

```text
If the latest dream7b_bpu_selected_triplet_forward_path_* directory contains tokens_batch.json but not selected_triplet_forward_path_probe.json, the probe writes a structured guard report and exits without retrying BPU forward unless DREAM7B_BPU_SELECTED_TRIPLET_ALLOW_CRASH_RETRY=1.
```

Output fields copied from the script:

```text
generated_at
verdict
run_dir
topology_json
forward_cmd
base_hbm_dir
fine_hbm_dir
batch_count
top_k
timeout_sec
tokens_batch_json
selected_triplet_forward_supported
reboot_or_disconnect_observed
expected_reboot_guard_observed
source_incomplete_run_dir
source_incomplete_files
selected.selected_topology
selected.selected_segments
selected.selected_worker_count
selected.selected_resident_load_ms
selected.forward_load_ms
selected.selected_total_load_ms
selected.run_ms
selected.wall_ms
baseline.returncode
baseline.verdict
comparison.warm_path_load_improved
comparison.total_path_load_improved
comparison.reason
next_optimization_target
warnings
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_triplet_forward_path_20260606-135729/selected_triplet_forward_path_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_triplet_forward_path_20260606-135729/selected_triplet_forward_path_probe.json
```

Verified selected triplet forward path fields copied from `selected_triplet_forward_path_probe.json`:

```text
verdict: ok_dream7b_bpu_selected_triplet_forward_path_probe
selected_triplet_forward_supported: False
reboot_or_disconnect_observed: True
expected_reboot_guard_observed: True
source_incomplete_run_dir: /mnt/nas/openclaw/reports/models/dream7b_bpu_selected_triplet_forward_path_20260606-135729
source_incomplete_files: ['tokens_batch.json']
selected.selected_topology: [0, 1, 8]
selected.selected_worker_count: 3
comparison.warm_path_load_improved: False
comparison.total_path_load_improved: False
next_optimization_target: do not promote selected triplet forward path; test smaller resident sets or vendor-supported multi-segment HBM residency instead
errors: []
```

### `dream7b-bpu-selected-pair-forward-path-probe`

Source file: `scripts/probes/dream7b_bpu_selected_pair_forward_path_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-selected-pair-forward-path-probe
```

Default argument copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
```

Environment variables copied from the script:

```text
DREAM7B_BPU_HBM_DIR
DREAM7B_BPU_FINE_HBM_DIR
DREAM7B_BPU_SELECTED_PAIR_TRIPLET_JSON
DREAM7B_BPU_SELECTED_PAIR_INDEXES
DREAM7B_BPU_SELECTED_PAIR_BASELINE_FORWARD_CMD
DREAM7B_BPU_SELECTED_PAIR_BATCH_COUNT
DREAM7B_BPU_SELECTED_PAIR_TOP_K
DREAM7B_BPU_SELECTED_PAIR_TIMEOUT_SEC
```

Default values copied from the script:

```text
base_hbm_dir = /home/sunrise/.cache/openclaw/dream7b-hbm/segments6
fine_hbm_dir = /home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16
forward_cmd = dream7b-bpu-fine-batch-forward
batch_count = 4
top_k = 3
timeout_sec = 900
```

The selected pair is derived from `successful_triplets` in `single_segment_triplet_residency_probe.json` unless `DREAM7B_BPU_SELECTED_PAIR_INDEXES` is explicitly set. The selected pair must satisfy `selected_pair_covers_all_segments: True`; otherwise the probe exits instead of running a forward path.

Output files copied from the script:

```text
tokens_batch.json
selected_pair_forward_summary.json
selected_pair_forward_path_probe.json
selected_pair_forward_path_probe.md
baseline.forward.stdout
baseline.forward.stderr
baseline_pair_window_forward/summary.json
```

Output fields copied from the script:

```text
generated_at
verdict
run_dir
triplet_json
forward_cmd
base_hbm_dir
fine_hbm_dir
batch_count
top_k
timeout_sec
tokens_batch_json
selected_summary_json
selected.selected_pair
selected.selected_segments
selected.selected_third_segments
selected.selected_pair_covers_all_segments
selected.selected_worker_count
selected.selected_resident_load_ms
selected.forward_load_ms
selected.selected_total_load_ms
selected.run_ms
selected.wall_ms
baseline.load_ms
baseline.run_ms
baseline.wall_ms
comparison.warm_load_ms_delta_vs_baseline
comparison.warm_load_ms_delta_ratio_vs_baseline
comparison.total_load_ms_delta_vs_baseline
comparison.total_load_ms_delta_ratio_vs_baseline
comparison.warm_path_load_improved
comparison.total_path_load_improved
next_optimization_target
warnings
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_forward_path_20260606-022052/selected_pair_forward_path_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_forward_path_20260606-022052/selected_pair_forward_path_probe.json
```

Verified selected pair forward path fields copied from `selected_pair_forward_path_probe.json`:

```text
verdict: ok_dream7b_bpu_selected_pair_forward_path_probe
batch_count: 16
selected.selected_pair: [1, 8]
selected.selected_segments: ['seg02_04', 'seg24_26']
selected.selected_third_segments: ['seg00_02', 'seg04_07', 'seg07_10', 'seg10_14', 'seg14_17', 'seg17_21', 'seg21_24', 'seg26_28']
selected.selected_pair_covers_all_segments: True
selected.selected_worker_count: 2
selected.selected_resident_load_ms: 3505.384
selected.forward_load_ms: 20428.46
selected.selected_total_load_ms: 23933.844
selected.run_ms: 2357.697
selected.wall_ms: 23090.689
baseline.load_ms: 23181.414
baseline.run_ms: 2351.057
baseline.wall_ms: 25785.378
comparison.warm_load_ms_delta_vs_baseline: 2752.954
comparison.warm_load_ms_delta_ratio_vs_baseline: 0.118757
comparison.total_load_ms_delta_vs_baseline: -752.43
comparison.total_load_ms_delta_ratio_vs_baseline: -0.032458
comparison.warm_path_load_improved: True
comparison.total_path_load_improved: False
warnings: ['selected total load including resident startup did not improve baseline load_ms: baseline=23181.414, selected_total=23933.844']
errors: []
next_optimization_target: promote selected-pair worker path only after batch16 and telemetry probes confirm the warm-load reduction improves sustained BPU utilization
```

### `dream7b-bpu-selected-pair-telemetry-probe`

Source file: `scripts/probes/dream7b_bpu_selected_pair_telemetry_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-selected-pair-telemetry-probe
```

Default argument copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
```

Environment variables copied from the script:

```text
DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_BATCH_COUNT
DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_MONITOR_DELAY_MS
DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_MONITOR_SAMPLE_COUNT
DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_TOP_K
DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_TIMEOUT_SEC
DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_FORWARD_CMD
```

Default values copied from the script:

```text
batch_count = 16
monitor_delay_ms = 100
monitor_sample_count = 320
top_k = 3
timeout_sec = 480
selected_pair_cmd = dream7b-bpu-selected-pair-forward-path-probe
```

The probe runs:

```text
DREAM7B_BPU_SELECTED_PAIR_ONLY=1
DREAM7B_BPU_SELECTED_PAIR_BATCH_COUNT=$batch_count
DREAM7B_BPU_SELECTED_PAIR_TOP_K=$top_k
dream7b-bpu-selected-pair-forward-path-probe
```

Output files copied from the script:

```text
selected_pair_telemetry_probe.json
selected_pair_telemetry_probe.md
hrt_ucp_monitor.stdout
hrt_ucp_monitor.stderr
selected_pair.forward.stdout
selected_pair.forward.stderr
hrut_somstatus_before.txt
hrut_somstatus_after.txt
```

Output fields copied from the script:

```text
generated_at
verdict
run_dir
batch_count
selected_pair_cmd
forward_status
selected_pair_report_json
selected.selected_pair
selected.selected_segments
selected.selected_pair_covers_all_segments
selected.selected_worker_count
selected.forward_load_ms
selected.selected_total_load_ms
selected.run_ms
selected.wall_ms
bpu_loading_sample_count
nonzero_bpu_loading_sample_count
max_bpu_loading
avg_bpu_loading
default_runtime_telemetry.path
default_runtime_telemetry.avg_bpu_loading
default_runtime_telemetry.forward_wall_ms
comparison_to_default_runtime_telemetry.wall_ms_delta_vs_default_runtime
comparison_to_default_runtime_telemetry.wall_ms_delta_ratio_vs_default_runtime
comparison_to_default_runtime_telemetry.avg_bpu_loading_delta_vs_default_runtime
comparison_to_default_runtime_telemetry.selected_wall_time_improved_vs_default_runtime
comparison_to_default_runtime_telemetry.selected_avg_bpu_loading_improved_vs_default_runtime
next_optimization_target
warnings
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_telemetry_20260606-031259/selected_pair_telemetry_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_telemetry_20260606-031259/selected_pair_telemetry_probe.json
```

Verified selected pair telemetry fields copied from `selected_pair_telemetry_probe.json`:

```text
verdict: ok_dream7b_bpu_selected_pair_telemetry_probe
batch_count: 16
selected.selected_pair: [1, 8]
selected.selected_segments: ['seg02_04', 'seg24_26']
selected.selected_pair_covers_all_segments: True
selected.selected_worker_count: 2
selected.selected_resident_load_ms: 2983.357
selected.forward_load_ms: 20290.033
selected.selected_total_load_ms: 23273.39
selected.run_ms: 2360.901
selected.wall_ms: 22955.54
bpu_loading_sample_count: 258
nonzero_bpu_loading_sample_count: 36
max_bpu_loading: 98.0
avg_bpu_loading: 9.14
default_runtime_telemetry.path: /mnt/nas/openclaw/reports/models/dream7b_bpu_runtime_telemetry_20260606-031226/runtime_telemetry_probe.json
default_runtime_telemetry.forward_wall_ms: 25915.772
comparison_to_default_runtime_telemetry.wall_ms_delta_vs_default_runtime: 2960.232
comparison_to_default_runtime_telemetry.wall_ms_delta_ratio_vs_default_runtime: 0.114225
comparison_to_default_runtime_telemetry.avg_bpu_loading_delta_vs_default_runtime: 1.952
comparison_to_default_runtime_telemetry.selected_wall_time_improved_vs_default_runtime: True
comparison_to_default_runtime_telemetry.selected_avg_bpu_loading_improved_vs_default_runtime: True
next_optimization_target: rerun default runtime telemetry and selected-pair telemetry back-to-back before promoting selected-pair worker path into the default Dream 7B service
warnings: []
errors: []
```

### `dream7b-bpu-selected-pair-promotion-gate-probe`

Source file: `scripts/probes/dream7b_bpu_selected_pair_promotion_gate_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-selected-pair-promotion-gate-probe
```

Default argument copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
```

Environment variables copied from the script:

```text
DREAM7B_BPU_SELECTED_PAIR_PROMOTION_MIN_BATCH_COUNT
DREAM7B_BPU_SELECTED_PAIR_PROMOTION_MIN_WALL_DELTA_RATIO
DREAM7B_BPU_SELECTED_PAIR_PROMOTION_MIN_AVG_BPU_DELTA
```

Default values copied from the script:

```text
min_batch_count = 16
min_wall_delta_ratio = 0.05
min_avg_bpu_delta = 1.0
```

Input reports copied from the script:

```text
dream7b_bpu_selected_pair_telemetry_*/selected_pair_telemetry_probe.json
dream7b_bpu_utilization_gap_*/utilization_gap_probe.json
dream7b_bpu_deployment_acceptance_*/deployment_acceptance_probe.json
```

Output files copied from the script:

```text
selected_pair_promotion_gate_probe.json
selected_pair_promotion_gate_probe.md
```

Output fields copied from the script:

```text
generated_at
verdict
run_dir
report_root
min_batch_count
min_wall_delta_ratio
min_avg_bpu_delta
selected_pair_telemetry_path
utilization_gap_path
deployment_acceptance_path
promotion_ready_for_guarded_default_service_candidate
default_service_already_promoted
checks
next_optimization_target
warnings
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_promotion_gate_20260606-034228/selected_pair_promotion_gate_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_promotion_gate_20260606-034228/selected_pair_promotion_gate_probe.json
```

Verified selected pair promotion gate fields copied from `selected_pair_promotion_gate_probe.json`:

```text
verdict: ok_dream7b_bpu_selected_pair_promotion_gate_probe
min_batch_count: 16
min_wall_delta_ratio: 0.05
min_avg_bpu_delta: 1.0
selected_pair_telemetry_path: /mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_telemetry_20260606-031259/selected_pair_telemetry_probe.json
utilization_gap_path: /mnt/nas/openclaw/reports/models/dream7b_bpu_utilization_gap_20260606-031454/utilization_gap_probe.json
deployment_acceptance_path: /mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-031455/deployment_acceptance_probe.json
promotion_ready_for_guarded_default_service_candidate: True
default_service_already_promoted: False
next_optimization_target: implement a guarded selected-pair default-service candidate and re-run deployment acceptance before replacing the current default Dream 7B service path
warnings: []
errors: []
```

### `dream7b-bpu-selected-pair-batch-forward`

Source file: `scripts/dream7b-bpu-selected-pair-batch-forward.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-selected-pair-batch-forward
```

CLI copied from the script:

```text
dream7b-bpu-selected-pair-batch-forward --tokens-batch-json FILE --top-k N --output-dir DIR
```

Environment variables copied from the script:

```text
DREAM7B_BPU_SELECTED_PAIR_BATCH_FORWARD_TOKENS_BATCH_JSON
DREAM7B_BPU_SELECTED_PAIR_BATCH_FORWARD_OUTPUT_DIR
DREAM7B_BPU_SELECTED_PAIR_BATCH_FORWARD_TOP_K
DREAM7B_BPU_SELECTED_PAIR_BATCH_FORWARD_REPORT_ROOT
DREAM7B_BPU_SELECTED_PAIR_BATCH_FORWARD_PROBE_CMD
DREAM7B_BPU_SELECTED_PAIR_BATCH_FORWARD_TIMEOUT_SEC
DREAM7B_BPU_SELECTED_PAIR_BATCH_FORWARD_TRIPLET_JSON
DREAM7B_BPU_SELECTED_PAIR_TRIPLET_JSON
DREAM7B_BPU_SELECTED_PAIR_TOKENS_BATCH_JSON
```

Default values copied from the script:

```text
top_k = 3
probe_cmd = dream7b-bpu-selected-pair-forward-path-probe
timeout_sec = 900
```

Output files copied from the script:

```text
summary.json
summary.md
selected_pair_reports
```

Runner-compatible output fields copied from the script:

```text
verdict
selected_pair_candidate
source_probe_json
source_selected_summary_json
source_tokens_batch_json
execution_mode
window_execution_mode
child_process_count
segment_plan
batch_count
seq_len
top_k
selected_pair
selected_segments
selected_pair_covers_all_segments
selected_resident_load_ms
load_ms
warm_load_ms
run_ms
wall_ms
load_share
warm_load_share
amortized_load_ms_per_forward
amortized_warm_load_ms_per_forward
amortized_run_ms_per_forward
amortized_wall_ms_per_forward
final_shape
final_shapes
topk_last_position_by_batch
warnings
errors
```

Latest recorded wrapper summary:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_candidate_forward_20260606-035716/forward/summary.json
```

Verified selected-pair batch forward fields copied from `summary.json`:

```text
verdict: ok_dream7b_segmented_hbm_python_forward
selected_pair_candidate: True
execution_mode: pair_window_batch
window_execution_mode: selected-pair-resident
child_process_count: 2
batch_count: 16
selected_pair: [1, 8]
selected_segments: ['seg02_04', 'seg24_26']
selected_pair_covers_all_segments: True
load_ms: 24018.25
warm_load_ms: 20522.582
run_ms: 2362.387
wall_ms: 23190.463
amortized_wall_ms_per_forward: 1449.404
source_tokens_batch_json: /mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_candidate_forward_20260606-035716/tokens_batch.json
source_probe_json: /mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_candidate_forward_20260606-035716/forward/selected_pair_reports/dream7b_bpu_selected_pair_forward_path_20260606-035716/selected_pair_forward_path_probe.json
```

### `dream7b-bpu-selected-pair-candidate-forward-probe`

Source file: `scripts/probes/dream7b_bpu_selected_pair_candidate_forward_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-selected-pair-candidate-forward-probe
```

Default argument copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
```

Environment variables copied from the script:

```text
DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_FORWARD_CMD
DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_BATCH_COUNT
DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_TOP_K
DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_TIMEOUT_SEC
```

Default values copied from the script:

```text
forward_cmd = dream7b-bpu-selected-pair-batch-forward
batch_count = 16
top_k = 3
timeout_sec = 900
```

Output files copied from the script:

```text
selected_pair_candidate_forward_probe.json
selected_pair_candidate_forward_probe.md
tokens_batch.json
forward/summary.json
forward/summary.md
```

Output fields copied from the script:

```text
generated_at
verdict
run_dir
forward_cmd
batch_count
top_k
timeout_sec
tokens_batch_json
forward_dir
forward_status
stdout_path
stderr_path
summary_json
summary_verdict
selected_pair_candidate
execution_mode
window_execution_mode
child_process_count
selected_pair
selected_segments
selected_pair_covers_all_segments
load_ms
warm_load_ms
run_ms
wall_ms
amortized_wall_ms_per_forward
source_probe_json
next_optimization_target
warnings
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_candidate_forward_20260606-035716/selected_pair_candidate_forward_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_candidate_forward_20260606-035716/selected_pair_candidate_forward_probe.json
```

Verified selected-pair candidate forward fields copied from `selected_pair_candidate_forward_probe.json`:

```text
verdict: ok_dream7b_bpu_selected_pair_candidate_forward_probe
forward_cmd: dream7b-bpu-selected-pair-batch-forward
batch_count: 16
top_k: 3
forward_status: 0
summary_json: /mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_candidate_forward_20260606-035716/forward/summary.json
summary_verdict: ok_dream7b_segmented_hbm_python_forward
selected_pair_candidate: True
execution_mode: pair_window_batch
window_execution_mode: selected-pair-resident
child_process_count: 2
selected_pair: [1, 8]
selected_segments: ['seg02_04', 'seg24_26']
selected_pair_covers_all_segments: True
load_ms: 24018.25
warm_load_ms: 20522.582
run_ms: 2362.387
wall_ms: 23190.463
amortized_wall_ms_per_forward: 1449.404
source_probe_json: /mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_candidate_forward_20260606-035716/forward/selected_pair_reports/dream7b_bpu_selected_pair_forward_path_20260606-035716/selected_pair_forward_path_probe.json
next_optimization_target: wire this selected-pair candidate forward command into a guarded service candidate and re-run deployment acceptance before replacing the current default service path
warnings: []
errors: []
```

### `install-dream7b-bpu-selected-pair-candidate-service`

Source file: `scripts/install_dream7b_bpu_selected_pair_candidate_service.sh`

Installed command on S100P:

```text
/usr/local/bin/install-dream7b-bpu-selected-pair-candidate-service
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
DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_SERVICE_NAME
DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_POLL_INTERVAL_SEC
DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_MAX_BATCH_SIZE
DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_TOP_K
DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_LOCK_PATH
DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_REPO_DIR
DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_FORWARD_CMD
DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_DRAIN_ALL
```

Default values copied from the script:

```text
service_name = dream7b-bpu-selected-pair-candidate.service
queue_dir = /mnt/nas/openclaw/queues/dream7b-bpu-selected-pair-candidate
output_dir = /mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_candidate_service_systemd
poll_interval_sec = 1
max_batch_size = 16
top_k = 3
forward_cmd = dream7b-bpu-selected-pair-batch-forward
bpu_lock_path = /run/lock/dream7b_bpu_batch_queue_runner.lock
drain_all = true
working_directory = /mnt/nas/openclaw
default_service_replaced = false
default_service_name = dream7b-bpu-batch-queue.service
```

Installed systemd unit copied from the script:

```text
dream7b-bpu-selected-pair-candidate.service
ExecStart=/usr/local/bin/dream7b-bpu-batch-queue-service /mnt/nas/openclaw/queues/dream7b-bpu-selected-pair-candidate /mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_candidate_service_systemd --poll-interval-sec 1 --max-batch-size 16 --top-k 3 --forward-cmd dream7b-bpu-selected-pair-batch-forward --bpu-lock-path /run/lock/dream7b_bpu_batch_queue_runner.lock --drain-all
```

### `dream7b-bpu-selected-pair-candidate-service-probe`

Source file: `scripts/probes/dream7b_bpu_selected_pair_candidate_service_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-selected-pair-candidate-service-probe
```

Default arguments copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
service_name = dream7b-bpu-selected-pair-candidate.service
queue_dir = /mnt/nas/openclaw/queues/dream7b-bpu-selected-pair-candidate
output_dir = /mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_candidate_service_systemd
```

Environment variables copied from the script:

```text
DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_SERVICE_REQUEST_COUNT
DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_SERVICE_TIMEOUT_SEC
DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_SERVICE_POLL_INTERVAL_SEC
```

Default values copied from the script:

```text
request_count = 16
timeout_sec = 480
poll_interval_sec = 2
```

Output files copied from the script:

```text
selected_pair_candidate_service_probe.json
selected_pair_candidate_service_probe.md
```

Output fields copied from the script:

```text
generated_at
verdict
service_name
queue_dir
output_dir
job_name
job_status
summary_path
request_count
timeout_sec
poll_interval_sec
service_status_before
service_enabled_before
service_status_after
service_enabled_after
default_service_status
default_service_enabled
unit_path
exec_start
forward_command
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
forward_summary_path
selected_pair_candidate
selected_pair
selected_segments
selected_pair_covers_all_segments
default_service_replaced
next_optimization_target
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_candidate_service_20260606-041550/selected_pair_candidate_service_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_candidate_service_20260606-041550/selected_pair_candidate_service_probe.json
```

Verified selected-pair candidate service fields copied from `selected_pair_candidate_service_probe.json`:

```text
verdict: ok_dream7b_bpu_selected_pair_candidate_service_probe
service_name: dream7b-bpu-selected-pair-candidate.service
job_status: done
forward_command: dream7b-bpu-selected-pair-batch-forward
request_count: 16
processed_count: 16
accepted_count: 16
deferred_count: 0
skipped_count: 0
batch_run_count: 1
batch_count: 16
execution_mode: pair_window_batch
window_execution_mode: selected-pair-resident
child_process_count: 2
selected_pair_candidate: True
selected_pair: [1, 8]
selected_segments: ['seg02_04', 'seg24_26']
selected_pair_covers_all_segments: True
default_service_replaced: False
total_wall_ms: 22953.06
amortized_wall_ms_per_processed_request: 1434.566
errors: []
```

### `s100-official-llm-baseline-probe`

Source file: `scripts/probes/s100_official_llm_baseline_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/s100-official-llm-baseline-probe
```

Default argument copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
```

Environment variables copied from the script:

```text
S100_OFFICIAL_LLM_SDK_ROOT
S100_OFFICIAL_LLM_DREAM_REPORT_ROOT
S100_OFFICIAL_LLM_DOC_URL
```

Default values copied from the script:

```text
sdk_root = /mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK
dream_report_root = /mnt/nas/openclaw/reports/models
official_doc_url = https://developer.d-robotics.cc/rdk_doc/rdk_s/Advanced_development/toolchain_development/LLM_Toolchain/
```

Official SDK paths copied from the script:

```text
oellm_runtime
oellm_build
oellm_runtime/config
oellm_runtime/example
oellm_runtime/model/resolve_model_nash-m.txt
oellm_runtime/example/oellm_multichat/qwen_multichat_config.json
```

Output files copied from the script:

```text
official_llm_baseline_probe.json
official_llm_baseline_probe.md
```

Output fields copied from the script:

```text
generated_at
verdict
run_dir
official_doc_url
sdk_root
runtime_root
build_root
resolve_model_path
qwen_multichat_config_path
sdk_exists
runtime_exists
build_exists
config_dir_count
config_dirs
supported_model_names_from_resolve_model
official_hbm_download_entry_count
official_hbm_download_entries
qwen_hbm_download_entries
qwen_existing_hbm_count
qwen_multichat_config
qwen_hbm_expected_from_multichat
qwen_hbm_exists_from_multichat
official_qwen_local_runtime_report_present
official_qwen_latest_runtime_report_path
official_qwen_runtime_completed
official_qwen_runtime_returncode
official_qwen_memory_alloc_failure_observed
official_qwen_hbm_load_success_observed
official_qwen_init_model_success_observed
similar_issue_evidence_available_for_official_qwen
comparison_to_dream.official_qwen_route
comparison_to_dream.dream_route
comparison_to_dream.same_failure_class_as_dream_proven
comparison_to_dream.reason
comparison_to_dream.dream_failure_summary.diagnosis
comparison_to_dream.dream_failure_summary.runtime_telemetry.load_to_run_ratio
comparison_to_dream.dream_failure_summary.systemd_telemetry.load_to_run_ratio
comparison_to_dream.dream_failure_summary.selected_triplet_forward_supported
comparison_to_dream.dream_failure_summary.reboot_or_disconnect_observed
next_probe_target
warnings
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/s100_official_llm_baseline_20260606-004107/official_llm_baseline_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/s100_official_llm_baseline_20260606-004107/official_llm_baseline_probe.json
```

Verified official LLM/Qwen baseline fields copied from `official_llm_baseline_probe.json`:

```text
verdict: ok_s100_official_llm_baseline_probe
sdk_exists: True
runtime_exists: True
build_exists: True
config_dir_count: 8
config_dirs: ['DeepSeek_R1_Distill_Qwen_1.5B_config', 'DeepSeek_R1_Distill_Qwen_7B_config', 'InternLM2_1.8B_config', 'Qwen2.5_1.5B_Instruct_config', 'Qwen2.5_1.5B_config', 'Qwen2.5_7B_Instruct_config', 'Qwen2.5_7B_config', 'Qwen2.5_Omni_3B_config']
supported_model_names_from_resolve_model: ['DeepSeek-R1-Distill-Qwen-1.5B', 'DeepSeek-R1-Distill-Qwen-7B', 'Qwen-2.5-1.5B', 'Qwen-2.5-7B', 'Qwen-2.5-1.5B-Instruct', 'Qwen-2.5-7B-Instruct', 'InternLM2-1.8B', 'Qwen2.5-Omni-3B']
official_hbm_download_entry_count: 14
qwen_existing_hbm_count: 1
qwen_multichat_config.hbm_path: ../../model/Qwen2.5_1.5B_Instruct_1024.hbm
qwen_multichat_config.tokenizer_dir: ../../config/Qwen2.5_1.5B_Instruct_config/
qwen_multichat_config.template_path: ../../config/Qwen2.5_1.5B_Instruct_config/Qwen2.5_1.5B_Instruct.jinja
qwen_multichat_config.model_type: 7
qwen_hbm_exists_from_multichat: True
official_qwen_local_runtime_report_present: True
official_qwen_latest_runtime_report_path: /mnt/nas/openclaw/reports/models/s100_official_qwen_runtime_20260606-003908/official_qwen_runtime_probe.json
official_qwen_runtime_completed: False
official_qwen_runtime_returncode: -11
official_qwen_memory_alloc_failure_observed: True
similar_issue_evidence_available_for_official_qwen: True
comparison_to_dream.same_failure_class_as_dream_proven: True
comparison_to_dream.dream_failure_summary.diagnosis: hbm_reload_dominated
comparison_to_dream.dream_failure_summary.runtime_telemetry.load_to_run_ratio: 8.399
comparison_to_dream.dream_failure_summary.systemd_telemetry.load_to_run_ratio: 8.48
comparison_to_dream.dream_failure_summary.selected_triplet_forward_supported: False
comparison_to_dream.dream_failure_summary.reboot_or_disconnect_observed: True
next_probe_target: inspect S100P BPU/common-buffer memory pool and official runtime performance-mode prerequisites before using Qwen as a clean 128TOPS utilization baseline
errors: []
```

### `s100-official-qwen-runtime-probe`

Source file: `scripts/probes/s100_official_qwen_runtime_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/s100-official-qwen-runtime-probe
```

Default argument copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
```

Environment variables copied from the script:

```text
S100_OFFICIAL_QWEN_RUNTIME_SDK_ROOT
S100_OFFICIAL_QWEN_RUNTIME_DREAM_REPORT_ROOT
S100_OFFICIAL_QWEN_RUNTIME_TIMEOUT_SECONDS
```

Default values copied from the script:

```text
sdk_root = /mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK
dream_report_root = /mnt/nas/openclaw/reports/models
runtime_timeout_seconds = 60
```

Exact runtime config source copied from the script:

```text
oellm_runtime/example/oellm_multichat/qwen_multichat_config.json
```

Output files copied from the script:

```text
official_qwen_runtime_probe.json
official_qwen_runtime_probe.md
oellm_multichat.stdout.txt
oellm_multichat.stderr.txt
oellm_multichat.ldd.txt
```

Output fields copied from the script:

```text
generated_at
verdict
run_dir
sdk_root
runtime_root
multichat_dir
runtime_bin
runtime_config
runtime_lib_dir
performance_mode_script
performance_mode_script_exists
performance_mode_script_action
runtime_timeout_seconds
qwen_multichat_config
qwen_hbm_path
qwen_hbm_exists
qwen_hbm_size_bytes
tokenizer_dir
tokenizer_dir_exists
template_path
template_path_exists
ldd_returncode
ldd_missing_dependency_observed
runtime_returncode
runtime_timed_out
runtime_completed
hbm_load_success_observed
prefill_model_load_success_observed
decode_model_load_success_observed
init_model_success_observed
memory_alloc_failure_observed
ion_alloc_failure_observed
bpu_mem_pool_alloc_error_observed
segmentation_fault_observed
official_qwen_runtime_supported_on_current_s100p_state
same_failure_class_as_dream
comparison_to_dream.reason
comparison_to_dream.dream_failure_summary.diagnosis
comparison_to_dream.dream_failure_summary.runtime_load_to_run_ratio
comparison_to_dream.dream_failure_summary.systemd_load_to_run_ratio
next_probe_target
captured_stdout_path
captured_stderr_path
captured_ldd_path
warnings
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/s100_official_qwen_runtime_20260606-003908/official_qwen_runtime_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/s100_official_qwen_runtime_20260606-003908/official_qwen_runtime_probe.json
```

Verified official Qwen runtime fields copied from `official_qwen_runtime_probe.json`:

```text
verdict: ok_s100_official_qwen_runtime_probe
qwen_hbm_exists: True
qwen_hbm_size_bytes: 1917038584
ldd_missing_dependency_observed: False
runtime_returncode: -11
runtime_timed_out: False
runtime_completed: False
hbm_load_success_observed: True
prefill_model_load_success_observed: True
decode_model_load_success_observed: True
init_model_success_observed: True
memory_alloc_failure_observed: True
ion_alloc_failure_observed: True
bpu_mem_pool_alloc_error_observed: True
segmentation_fault_observed: True
official_qwen_runtime_supported_on_current_s100p_state: False
same_failure_class_as_dream: True
next_probe_target: inspect S100P BPU/common-buffer memory pool and official runtime performance-mode prerequisites before using Qwen as a clean 128TOPS utilization baseline
errors: []
```

### `s100-official-qwen-performance-mode-retest-probe`

Source file: `scripts/probes/s100_official_qwen_performance_mode_retest_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/s100-official-qwen-performance-mode-retest-probe
```

Default argument copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
```

Environment variables copied from the script:

```text
S100_OFFICIAL_QWEN_PERF_RETEST_RUNTIME_PROBE
S100_OFFICIAL_QWEN_PERF_RETEST_DEVMEM_BIN
S100_OFFICIAL_QWEN_PERF_RETEST_TARGET_VALUE
```

Safety constraints copied from the script:

```text
qwen_runtime_probe = /usr/local/bin/s100-official-qwen-runtime-probe
devmem_bin = /usr/bin/devmem
target_value = 0x99
registers = ['0x2b047000', '0x2b047004']
target_register_value = 0x00000099
```

Output files copied from the script:

```text
performance_mode_retest_probe.json
performance_mode_retest_probe.md
boardid.txt
before_0x2b047000.txt
before_0x2b047004.txt
write_0x2b047000.txt
write_0x2b047004.txt
after_0x2b047000.txt
after_0x2b047004.txt
qwen_runtime_probe.txt
```

Output fields copied from the script:

```text
generated_at
verdict
run_dir
report_root
qwen_runtime_probe
devmem_bin
target_value
boardid
registers
before_values
after_values
target_applied
runtime_probe_returncode
runtime_probe_timed_out
runtime_report_path
runtime_completed_after_performance_mode
memory_alloc_failure_observed_after_performance_mode
runtime_returncode_after_performance_mode
hbm_load_success_observed_after_performance_mode
init_model_success_observed_after_performance_mode
next_probe_target
captures
warnings
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/s100_official_qwen_performance_mode_retest_20260606-003908/performance_mode_retest_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/s100_official_qwen_performance_mode_retest_20260606-003908/performance_mode_retest_probe.json
```

Verified official Qwen performance-mode retest fields copied from `performance_mode_retest_probe.json`:

```text
verdict: ok_s100_official_qwen_performance_mode_retest_probe
boardid: 0x6486
devmem_bin: /usr/bin/devmem
target_value: 0x99
before_values: {'0x2b047000': '0x0000007E', '0x2b047004': '0x00EC4EC4'}
after_values: {'0x2b047000': '0x00000099', '0x2b047004': '0x00000099'}
target_applied: True
runtime_report_path: /mnt/nas/openclaw/reports/models/s100_official_qwen_runtime_20260606-003908/official_qwen_runtime_probe.json
runtime_completed_after_performance_mode: False
runtime_returncode_after_performance_mode: -11
memory_alloc_failure_observed_after_performance_mode: True
hbm_load_success_observed_after_performance_mode: True
init_model_success_observed_after_performance_mode: True
next_probe_target: inspect ION/common-buffer reserved memory and HBMEM/UCP allocation prerequisites; performance-mode register apply alone did not clear official Qwen allocation failure
errors: []
```

### `s100-bpu-memory-pool-probe`

Source file: `scripts/probes/s100_bpu_memory_pool_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/s100-bpu-memory-pool-probe
```

Default argument copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
```

Environment variables copied from the script:

```text
S100_BPU_MEMORY_POOL_SDK_ROOT
S100_BPU_MEMORY_POOL_RELATED_REPORT_ROOT
```

Output files copied from the script:

```text
bpu_memory_pool_probe.json
bpu_memory_pool_probe.md
boardid.txt
which_devmem.txt
sudo_which_devmem.txt
devmem_default_test.txt
devmem_busybox_test.txt
ion_meminfo.txt
ion_meminfo_fallback_bash.txt
memstat.txt
memstat_fallback_busybox_ash.txt
debug_probe.txt
ion_heap_all_heap_info.txt
ion_heap_cma_reserved.txt
ion_heap_ion_cma.txt
ion_heap_carveout.txt
ion_heap_chunk.txt
ion_heap_system.txt
ion_heap_system_contig.txt
ion_client_bpu_0.txt
iovmm_bpu.txt
iovmm_bpu_hp.txt
reserved_memory_nodes.json
proc_cmdline.txt
proc_meminfo.txt
proc_modules.txt
proc_mounts.txt
```

Output fields copied from the script:

```text
generated_at
verdict
run_dir
sdk_root
performance_mode_script
performance_mode_script_exists
performance_mode_script_action
boardid
official_script_would_match_s100p
cmdline_contains_cma
cmdline_contains_ion
debug_mount_present
ion_debug_present
ion_all_heap_info_exists
ion_heap_names
ion_heap_total_sizes
ion_heap_allocated_totals
ion_heap_available_estimates
ion_heap_bpu_allocation_counts
ion_heap_bpu_allocation_sizes
system_heap_total_size
system_contig_heap_total_size
carveout_heap_total_size
carveout_heap_allocated_total
cma_reserved_heap_total_size
cma_reserved_heap_allocated_total
ion_cma_heap_total_size
ion_cma_heap_allocated_total
ion_client_bpu_0_exists
ion_client_bpu_0_total_line
iovmm_bpu
iovmm_bpu_hp
reserved_memory_node_count
reserved_memory_summary
default_devmem_path
sudo_devmem_path
usr_hobot_devmem_exists
usr_bin_devmem_exists
busybox_has_devmem
default_devmem_returncode
busybox_devmem_returncode
perf_register_0x2b047000
perf_register_0x2b047004
performance_mode_target_applied_from_latest_retest
latest_performance_mode_retest_path
latest_performance_mode_retest_memory_alloc_failure_observed
ion_meminfo_shebang
ion_meminfo_shebang_interpreter_exists
ion_meminfo_fallback_returncode
memstat_shebang
memstat_shebang_interpreter_exists
memstat_fallback_returncode
latest_official_qwen_memory_alloc_failure_observed
latest_dream_diagnosis
allocation_failure_interpretation
next_probe_target
captures
warnings
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/s100_bpu_memory_pool_20260606-010941/bpu_memory_pool_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/s100_bpu_memory_pool_20260606-010941/bpu_memory_pool_probe.json
```

Verified S100 BPU memory-pool fields copied from `bpu_memory_pool_probe.json`:

```text
verdict: ok_s100_bpu_memory_pool_probe
boardid: 0x6486
default_devmem_path: /usr/bin/devmem
sudo_devmem_path: /usr/hobot/bin/devmem
default_devmem_returncode: 127
busybox_devmem_returncode: 0
perf_register_0x2b047000: 0x00000099
perf_register_0x2b047004: 0x00000099
performance_mode_target_applied_from_latest_retest: True
latest_performance_mode_retest_memory_alloc_failure_observed: True
ion_debug_present: True
ion_all_heap_info_exists: True
ion_heap_total_sizes: {'all_heap_info': 0, 'cma_reserved': 1073741824, 'ion_cma': 536870912, 'carveout': 536870912, 'chunk': 4194304, 'system': 0, 'system_contig': 0}
ion_heap_allocated_totals: {'all_heap_info': 0, 'cma_reserved': 56492032, 'ion_cma': 0, 'carveout': 3145728, 'chunk': 0, 'system': 0, 'system_contig': 0}
ion_heap_bpu_allocation_sizes: {'all_heap_info': 3145728, 'cma_reserved': 0, 'ion_cma': 0, 'carveout': 3145728, 'chunk': 0, 'system': 0, 'system_contig': 0}
system_heap_total_size: 0
system_contig_heap_total_size: 0
cma_reserved_heap_total_size: 1073741824
ion_cma_heap_total_size: 536870912
carveout_heap_total_size: 536870912
ion_client_bpu_0_total_line: total            300000
iovmm_bpu.total_mappings: 0
iovmm_bpu_hp.total_mappings: 99
reserved_memory_summary.bpu_region@9A000000.reg.size_mib: 96.0
reserved_memory_summary.ion_reserved@C80000000.reg.size_mib: 1024.0
reserved_memory_summary.ion_cma@400000000.reg.size_mib: 512.0
reserved_memory_summary.ion_carveout@800000000.reg.size_mib: 512.0
ion_meminfo_shebang: #!/bin/zsh
ion_meminfo_shebang_interpreter_exists: False
ion_meminfo_fallback_returncode: 1
memstat_shebang: #!/var/busybox/ash
memstat_shebang_interpreter_exists: False
memstat_fallback_returncode: 0
latest_official_qwen_memory_alloc_failure_observed: True
latest_dream_diagnosis: hbm_reload_dominated
allocation_failure_interpretation: reserved ION heaps are visible through debugfs, so the official Qwen failure is not explained by an absent ION debugfs heap; system/system_contig heap capacity and the exact HBMEM/UCP backend selection need a minimal allocation probe
next_probe_target: run a minimal HBMEM/UCP common-buffer allocation matrix against the exact backend/heap flags used by official Qwen; performance-mode register apply alone did not clear official Qwen allocation failure
errors: []
```

### `s100-hbmem-common-buffer-matrix-probe`

Source file: `scripts/probes/s100_hbmem_common_buffer_matrix_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/s100-hbmem-common-buffer-matrix-probe
```

Default argument copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
```

Environment variables copied from the script:

```text
S100_HBMEM_MATRIX_SDK_ROOT
```

Output files copied from the script:

```text
hbmem_common_buffer_matrix.c
hbmem_common_buffer_matrix
hbmem_common_buffer_matrix.jsonl
hbmem_common_buffer_matrix.stdout.txt
hbmem_common_buffer_matrix.stderr.txt
hbmem_common_buffer_matrix_probe.json
hbmem_common_buffer_matrix_probe.md
compile.stdout.txt
compile.stderr.txt
```

Output fields copied from the script:

```text
generated_at
verdict
run_dir
source_path
binary_path
jsonl_path
stdout_path
stderr_path
run_status
ucp_enabled
row_count
hbmem_alloc_case_count
hbmem_alloc_success_count
hbmem_alloc_failure_count
qwen_log_size_case_count
qwen_log_size_success_count
qwen_log_size_failure_count
qwen_log_sizes
successful_qwen_size_cases
failed_qwen_size_cases
ucp_case_count
ucp_success_count
next_probe_target
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/s100_hbmem_common_buffer_matrix_20260606-012033/hbmem_common_buffer_matrix_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/s100_hbmem_common_buffer_matrix_20260606-012033/hbmem_common_buffer_matrix_probe.json
```

Verified S100 HBMEM/UCP common-buffer allocation matrix fields copied from `hbmem_common_buffer_matrix_probe.json`:

```text
verdict: ok_s100_hbmem_common_buffer_matrix_probe
run_status: 0
ucp_enabled: True
hbmem_alloc_case_count: 28
hbmem_alloc_success_count: 28
hbmem_alloc_failure_count: 0
qwen_log_sizes: [786432, 2359296]
qwen_log_size_case_count: 14
qwen_log_size_success_count: 14
qwen_log_size_failure_count: 0
ucp_case_count: 8
ucp_success_count: 8
next_probe_target: compare these direct HBMEM/UCP allocation results with official Qwen's backend: 9 failure path and inspect libhbucp backend-to-hbmem flag selection if direct allocations pass
errors: []
```

### `s100-qwen-backend9-baseline-probe`

Source file: `scripts/probes/s100_qwen_backend9_baseline_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/s100-qwen-backend9-baseline-probe
```

Default argument copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
```

Environment variables copied from the script:

```text
S100_QWEN_BACKEND9_SDK_ROOT
```

Input files copied from the script:

```text
/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/oellm_runtime/example/oellm_multichat/qwen_multichat_config.json
/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/oellm_runtime/example/oellm_multichat/oellm_multichat_demo.cc
/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/oellm_runtime/lib/libhbucp.so
/usr/include/hobot/hb_ucp.h
```

Output files copied from the script:

```text
qwen_multichat_config.json
oellm_multichat_demo_bpu_core_lines.txt
hb_ucp_backend_constants.txt
qwen_backend_failure_lines.txt
libhbucp_nm_relevant.txt
libhbucp_strings_relevant.txt
qwen_backend9_baseline_probe.json
qwen_backend9_baseline_probe.md
```

Output fields copied from the script:

```text
generated_at
verdict
run_dir
sdk_root
qwen_multichat_config_path
qwen_multichat_config
config_has_bpu_core
config_bpu_core_value
demo_source_path
demo_default_bpu_core_value
demo_default_infer_backend
demo_bpu_core_lines
hb_ucp_header_path
hb_ucp_backend_constants
observed_backend_values
observed_backend_bit_matches_from_hb_ucp_header
backend_9_equals_hb_ucp_bpu_core_any
observed_ucp_alloc_failure_sizes
stderr_alloc_error_lens
ion_failure_line_count
qwen_runtime_report_path
qwen_runtime_returncode
qwen_runtime_completed
qwen_hbm_load_success_observed
qwen_init_model_success_observed
qwen_memory_alloc_failure_observed
qwen_ion_alloc_failure_observed
qwen_bpu_mem_pool_alloc_error_observed
qwen_segmentation_fault_observed
qwen_same_failure_class_as_dream
hbmem_matrix_report_path
hbmem_matrix_qwen_log_size_success_count
hbmem_matrix_qwen_log_size_failure_count
hbmem_matrix_ucp_success_count
direct_hbmem_matrix_qwen_sizes_pass
official_qwen_has_similar_bpu_memory_issue
official_qwen_issue_not_raw_size_only
dream_utilization_report_path
dream_diagnosis
dream_max_observed_bpu_loading
dream_avg_observed_bpu_loading_across_reports
dream_window3_report_path
dream_window3_stderr_contains_memory_alloc_failure
comparison
next_probe_target
captures
warnings
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/s100_qwen_backend9_baseline_20260606-013902/qwen_backend9_baseline_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/s100_qwen_backend9_baseline_20260606-013902/qwen_backend9_baseline_probe.json
```

Verified S100 Qwen backend 9 baseline fields copied from `qwen_backend9_baseline_probe.json`:

```text
verdict: ok_s100_qwen_backend9_baseline_probe
config_has_bpu_core: False
config_bpu_core_value: None
demo_default_bpu_core_value: -1
demo_default_infer_backend: XLM_INFER_BACKEND_BPU_ANY
observed_backend_values: [9]
observed_backend_bit_matches_from_hb_ucp_header: {'9': ['HB_UCP_BPU_CORE_0', 'HB_UCP_BPU_CORE_3']}
backend_9_equals_hb_ucp_bpu_core_any: False
observed_ucp_alloc_failure_sizes: [786432, 1572864]
stderr_alloc_error_lens: [2359296]
hbmem_matrix_qwen_log_size_success_count: 14
hbmem_matrix_qwen_log_size_failure_count: 0
direct_hbmem_matrix_qwen_sizes_pass: True
official_qwen_has_similar_bpu_memory_issue: True
official_qwen_issue_not_raw_size_only: True
dream_diagnosis: hbm_reload_dominated
dream_window3_stderr_contains_memory_alloc_failure: True
next_probe_target: run a controlled official Qwen bpu_core sweep by copying qwen_multichat_config.json and adding exact bpu_core values -1, 0, 1, 2, and 3; compare backend values and memory failures before transferring any backend/core-pinning idea to Dream 7B
warnings: ['observed Qwen backend: 9 does not equal HB_UCP_BPU_CORE_ANY from /usr/include/hobot/hb_ucp.h', 'official Qwen has a BPU/common-buffer allocation failure even though direct HBMEM/UCP allocation of logged Qwen sizes passed']
errors: []
```

### `s100-qwen-bpu-core-sweep-probe`

Source file: `scripts/probes/s100_qwen_bpu_core_sweep_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/s100-qwen-bpu-core-sweep-probe
```

Default argument copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
```

Environment variables copied from the script:

```text
S100_QWEN_BPU_CORE_SWEEP_SDK_ROOT
S100_QWEN_BPU_CORE_SWEEP_TIMEOUT_SECONDS
S100_QWEN_BPU_CORE_SWEEP_CORES
```

Default values copied from the script:

```text
timeout_seconds = 45
cores_text = -1 0 1 2 3
```

Input files copied from the script:

```text
/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/oellm_runtime/example/oellm_multichat/qwen_multichat_config.json
/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/oellm_runtime/example/oellm_multichat/oellm_multichat
/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/oellm_runtime/example/oellm_multichat/oellm_multichat_demo.cc
/usr/include/hobot/hb_ucp.h
```

Output files copied from the script:

```text
qwen_bpu_core_sweep_probe.json
qwen_bpu_core_sweep_probe.md
bpu_core_minus_1/qwen_multichat_config.json
bpu_core_minus_1/oellm_multichat.stdout.txt
bpu_core_minus_1/oellm_multichat.stderr.txt
bpu_core_minus_1/case_result.json
bpu_core_minus_1/case_result.md
bpu_core_0/qwen_multichat_config.json
bpu_core_0/oellm_multichat.stdout.txt
bpu_core_0/oellm_multichat.stderr.txt
bpu_core_0/case_result.json
bpu_core_0/case_result.md
bpu_core_1/qwen_multichat_config.json
bpu_core_1/oellm_multichat.stdout.txt
bpu_core_1/oellm_multichat.stderr.txt
bpu_core_1/case_result.json
bpu_core_1/case_result.md
bpu_core_2/qwen_multichat_config.json
bpu_core_2/oellm_multichat.stdout.txt
bpu_core_2/oellm_multichat.stderr.txt
bpu_core_2/case_result.json
bpu_core_2/case_result.md
bpu_core_3/qwen_multichat_config.json
bpu_core_3/oellm_multichat.stdout.txt
bpu_core_3/oellm_multichat.stderr.txt
bpu_core_3/case_result.json
bpu_core_3/case_result.md
```

Output fields copied from the script:

```text
generated_at
verdict
run_dir
sdk_root
runtime_bin
source_config_path
runtime_lib_dir
timeout_seconds
tested_bpu_core_values
source_config_had_bpu_core
demo_source_path
demo_supports_config_bpu_core
demo_default_bpu_core_value
demo_default_infer_backend
demo_bpu_core_lines
hb_ucp_header_path
hb_ucp_backend_constants
qwen_hbm_path
tokenizer_dir
template_path
case_count
case_report_paths
case_results
backend_values_by_core
memory_alloc_failure_by_core
runtime_completed_by_core
returncode_by_core
segmentation_fault_by_core
functional_failure_by_core
functional_success_by_core
prefill_failure_by_core
all_cases_failed_memory
all_cases_failed_functionally
any_case_completed
any_case_functional_success
backend_changed_by_core
explicit_core_changed_backend_or_failure
latest_backend9_baseline_report_path
latest_backend9_baseline_observed_backend_values
latest_backend9_baseline_direct_hbmem_matrix_qwen_sizes_pass
dream_utilization_report_path
dream_diagnosis
interpretation
next_probe_target
warnings
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/s100_qwen_bpu_core_sweep_20260606-015133/qwen_bpu_core_sweep_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/s100_qwen_bpu_core_sweep_20260606-015133/qwen_bpu_core_sweep_probe.json
```

Verified S100 Qwen `bpu_core` sweep fields copied from `qwen_bpu_core_sweep_probe.json`:

```text
verdict: ok_s100_qwen_bpu_core_sweep_probe
tested_bpu_core_values: [-1, 0, 1, 2, 3]
backend_values_by_core: {'-1': [9], '0': [9], '1': [9], '2': [9], '3': [9]}
memory_alloc_failure_by_core: {'-1': True, '0': True, '1': True, '2': True, '3': True}
runtime_completed_by_core: {'-1': False, '0': False, '1': True, '2': True, '3': True}
returncode_by_core: {'-1': -11, '0': -11, '1': 0, '2': 0, '3': 0}
segmentation_fault_by_core: {'-1': True, '0': True, '1': False, '2': False, '3': False}
functional_failure_by_core: {'-1': True, '0': True, '1': True, '2': True, '3': True}
functional_success_by_core: {'-1': False, '0': False, '1': False, '2': False, '3': False}
prefill_failure_by_core: {'-1': False, '0': False, '1': True, '2': True, '3': True}
all_cases_failed_memory: True
all_cases_failed_functionally: True
any_case_completed: True
any_case_functional_success: False
backend_changed_by_core: False
explicit_core_changed_backend_or_failure: True
interpretation: explicit bpu_core values changed the official Qwen crash behavior, but no tested core produced functional inference; core pinning alone is not sufficient
next_probe_target: treat explicit bpu_core as an optional crash-mitigation variable, but continue Dream 7B HBM reload/residency work before expecting sustained 128TOPS utilization
warnings: ['all tested official Qwen bpu_core values still reported memory allocation failure', 'all tested official Qwen bpu_core values produced the same observed backend value set', 'all tested official Qwen bpu_core values still failed functionally']
errors: []
```

### `dream7b-bpu-scheduling-params-probe`

Source file: `scripts/probes/dream7b_bpu_scheduling_params_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-scheduling-params-probe
```

Environment variables copied from the script:

```text
DREAM7B_BPU_SCHEDULING_PARAMS_PYTHON
DREAM7B_BPU_SCHEDULING_PARAMS_HBM
DREAM7B_BPU_SCHEDULING_PARAMS_CORES
DREAM7B_BPU_SCHEDULING_PARAMS_TIMEOUT_SECONDS
```

Default values copied from the script:

```text
python_bin = /mnt/nas/openclaw/runtimes/hbm-runtime-venv/bin/python
hbm_path = /home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16/seg00_02/dream7b_segment_0_2_seq16_q8.hbm
cores_text = default 0 1 2 3
timeout_seconds = 30
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_scheduling_params_20260606-020548/scheduling_params_probe.json
```

Verified Dream 7B BPU scheduling params fields copied from `scheduling_params_probe.json`:

```text
verdict: ok_dream7b_bpu_scheduling_params_probe
tested_cores: ['default', '0', '1', '2', '3']
run_ok_by_core: {'default': True, '0': True, '1': False, '2': False, '3': False}
returncode_by_core: {'default': 0, '0': 0, '1': -6, '2': -6, '3': -6}
schedule_backend_unsupported_by_core: {'default': False, '0': False, '1': True, '2': True, '3': True}
abort_by_core: {'default': False, '0': False, '1': True, '2': True, '3': True}
core0_explicit_supported: True
nonzero_cores_supported: False
interpretation: Dream HB_HBMRuntime exposes set_scheduling_params with bpu_cores mapping; the tested single segment supports default and core 0, while cores 1/2/3 are unsupported for this HBM and abort in isolated child processes.
next_probe_target: treat Dream bpu_cores as a model-specific scheduling constraint; do not port Qwen bpu_core values directly, and continue HBM reload/residency optimization with optional core0-only scheduling checks.
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
DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_GENERATE_SUSTAINED_ROUND_COUNT
DREAM7B_BPU_ACCEPTANCE_MIN_LONG_REPEAT_COUNT
DREAM7B_BPU_ACCEPTANCE_MAX_LONG_REPEAT_WALL_SPREAD_RATIO
```

Default values copied from the script:

```text
min_batch_capacity = 16
min_systemd_batch_requests = 16
min_systemd_telemetry_requests = 48
min_batch_generate_count = 16
min_batch_generate_sustained_round_count = 3
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
dream7b_bpu_diffusion_batch_generate_sustained_*/batch_generation_sustained_probe.json
dream7b_bpu_utilization_gap_*/utilization_gap_probe.json
dream7b_bpu_persistent_pair_cache_*/persistent_pair_cache_probe.json
dream7b_bpu_held_pair_residency_matrix_*/held_pair_residency_matrix_probe.json
dream7b_bpu_single_segment_residency_matrix_*/single_segment_residency_matrix_probe.json
dream7b_bpu_persistent_segment_cache_*/persistent_segment_cache_probe.json
dream7b_bpu_single_segment_triplet_residency_*/single_segment_triplet_residency_probe.json
dream7b_bpu_seeded_quad_residency_*/seeded_quad_residency_probe.json
dream7b_bpu_segment_capacity_planner_*/segment_capacity_planner_probe.json
dream7b_bpu_persistent_triplet_topology_*/persistent_triplet_topology_probe.json
dream7b_bpu_window3_forward_feasibility_*/window3_forward_feasibility_probe.json
dream7b_bpu_selected_triplet_forward_path_*/selected_triplet_forward_path_probe.json
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
diffusion_batch_generate_sustained
utilization_gap
persistent_pair_cache
held_pair_residency_matrix
single_segment_residency_matrix
persistent_segment_cache
single_segment_triplet_residency
seeded_quad_residency
segment_capacity_planner
persistent_triplet_topology
window3_forward_feasibility
selected_triplet_forward_path
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
min_batch_generate_sustained_round_count
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
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-184511/deployment_acceptance_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-205153/deployment_acceptance_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-212134/deployment_acceptance_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-234654/deployment_acceptance_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-000234/deployment_acceptance_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-120028/deployment_acceptance_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-123257/deployment_acceptance_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-125750/deployment_acceptance_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-131933/deployment_acceptance_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-133119/deployment_acceptance_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-134115/deployment_acceptance_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-234652/deployment_acceptance_probe.md
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-054148/deployment_acceptance_probe.md
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
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-184511/deployment_acceptance_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-205153/deployment_acceptance_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-212134/deployment_acceptance_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-234654/deployment_acceptance_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-000234/deployment_acceptance_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-120028/deployment_acceptance_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-123257/deployment_acceptance_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-125750/deployment_acceptance_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-131933/deployment_acceptance_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-133119/deployment_acceptance_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-134115/deployment_acceptance_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-234652/deployment_acceptance_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-054148/deployment_acceptance_probe.json
```

Verified deployment acceptance fields copied from `deployment_acceptance_probe.json`:

```text
verdict: ok_dream7b_bpu_deployment_acceptance_probe
check_count: 30
passed_check_count: 30
min_batch_capacity: 16
min_systemd_batch_requests: 16
min_systemd_telemetry_requests: 48
min_batch_generate_count: 16
min_batch_generate_sustained_round_count: 3
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
diffusion_batch_generate_sustained.ok: True
utilization_gap.ok: True
selected_pair_telemetry.ok: True
selected_pair_candidate_service.ok: True
selected_pair_candidate_service_telemetry.ok: True
selected_pair_cross_job_reuse.ok: True
persistent_pair_cache.ok: True
held_pair_residency_matrix.ok: True
single_segment_residency_matrix.ok: True
persistent_segment_cache.ok: True
single_segment_triplet_residency.ok: True
seeded_quad_residency.ok: True
segment_capacity_planner.ok: True
persistent_triplet_topology.ok: True
window3_forward_feasibility.ok: True
selected_triplet_forward_path.ok: True
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
diffusion_batch_generate_telemetry.path: /mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_batch_generate_telemetry_20260606-184316/batch_generation_telemetry_probe.json
diffusion_batch_generate_telemetry.details.verdict: ok_dream7b_bpu_diffusion_batch_generate_telemetry_probe
diffusion_batch_generate_telemetry.details.generate_cmd: dream7b-bpu-diffusion-batch-generate
diffusion_batch_generate_telemetry.details.generation_status: 0
diffusion_batch_generate_telemetry.details.batch_count: 16
diffusion_batch_generate_telemetry.details.max_bpu_loading: 100.0
diffusion_batch_generate_telemetry.details.avg_bpu_loading: 8.825
diffusion_batch_generate_telemetry.details.nonzero_bpu_loading_sample_count: 68
diffusion_batch_generate_telemetry.details.generation_verdict: ok_dream7b_bpu_diffusion_batch_generate
diffusion_batch_generate_telemetry.details.forward_cmd: dream7b-bpu-fine-batch-forward
diffusion_batch_generate_telemetry.details.seq_len: 16
diffusion_batch_generate_telemetry.details.executed_step_count: 2
diffusion_batch_generate_telemetry.details.forward_batch_counts: [16, 16]
diffusion_batch_generate_telemetry.details.boundary: bounded_seq16_batch_generation_entrypoint_not_complete_production_text_service
diffusion_batch_generate_sustained.path: /mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_batch_generate_sustained_20260606-190058/batch_generation_sustained_probe.json
diffusion_batch_generate_sustained.details.verdict: ok_dream7b_bpu_diffusion_batch_generate_sustained_probe
diffusion_batch_generate_sustained.details.generate_cmd: dream7b-bpu-diffusion-batch-generate
diffusion_batch_generate_sustained.details.round_count: 3
diffusion_batch_generate_sustained.details.batch_count: 16
diffusion_batch_generate_sustained.details.successful_generation_count: 3
diffusion_batch_generate_sustained.details.expected_total_batch_items: 48
diffusion_batch_generate_sustained.details.actual_total_batch_items: 48
diffusion_batch_generate_sustained.details.generation_statuses: [0, 0, 0]
diffusion_batch_generate_sustained.details.generation_batch_counts: [16, 16, 16]
diffusion_batch_generate_sustained.details.generation_executed_step_counts: [2, 2, 2]
diffusion_batch_generate_sustained.details.generation_forward_batch_counts_by_round: [[16, 16], [16, 16], [16, 16]]
diffusion_batch_generate_sustained.details.total_forward_call_count: 6
diffusion_batch_generate_sustained.details.max_bpu_loading: 100.0
diffusion_batch_generate_sustained.details.avg_bpu_loading: 9.022
diffusion_batch_generate_sustained.details.nonzero_bpu_loading_sample_count: 199
utilization_gap.path: /mnt/nas/openclaw/reports/models/dream7b_bpu_utilization_gap_20260606-031454/utilization_gap_probe.json
utilization_gap.details.verdict: ok_dream7b_bpu_utilization_gap_probe
utilization_gap.details.diagnosis: hbm_reload_dominated
utilization_gap.details.next_optimization_target: reduce per-window HBM reload overhead before expecting sustained 128TOPS-level average utilization
utilization_gap.details.max_observed_bpu_loading: 100.0
utilization_gap.details.avg_observed_bpu_loading_across_reports: 8.758
utilization_gap.details.runtime_batch_count: 16
utilization_gap.details.runtime_load_to_run_ratio: 9.814
utilization_gap.details.systemd_processed_request_count: 48
utilization_gap.details.systemd_load_to_run_ratio: 8.48
utilization_gap.details.sustained_round_count: 3
utilization_gap.details.sustained_actual_total_batch_items: 48
utilization_gap.details.batch_generate_batch_count: 16
utilization_gap.details.warnings: ['batch_size_sweep max batch_count is below 16; using runtime/systemd/sustained telemetry as the authoritative batch-16 evidence']
selected_pair_telemetry.path: /mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_telemetry_20260606-031259/selected_pair_telemetry_probe.json
selected_pair_telemetry.details.verdict: ok_dream7b_bpu_selected_pair_telemetry_probe
selected_pair_telemetry.details.batch_count: 16
selected_pair_telemetry.details.selected_pair: [1, 8]
selected_pair_telemetry.details.selected_segments: ['seg02_04', 'seg24_26']
selected_pair_telemetry.details.selected_pair_covers_all_segments: True
selected_pair_telemetry.details.selected_wall_ms: 22955.54
selected_pair_telemetry.details.selected_forward_load_ms: 20290.033
selected_pair_telemetry.details.selected_run_ms: 2360.901
selected_pair_telemetry.details.max_bpu_loading: 98.0
selected_pair_telemetry.details.avg_bpu_loading: 9.14
selected_pair_telemetry.details.wall_ms_delta_vs_default_runtime: 2960.232
selected_pair_telemetry.details.wall_ms_delta_ratio_vs_default_runtime: 0.114225
selected_pair_telemetry.details.avg_bpu_loading_delta_vs_default_runtime: 1.952
selected_pair_telemetry.details.selected_wall_time_improved_vs_default_runtime: True
selected_pair_telemetry.details.selected_avg_bpu_loading_improved_vs_default_runtime: True
persistent_pair_cache.path: /mnt/nas/openclaw/reports/models/dream7b_bpu_persistent_pair_cache_20260605-234349/persistent_pair_cache_probe.json
persistent_pair_cache.details.verdict: ok_dream7b_bpu_persistent_pair_cache_probe
persistent_pair_cache.details.pair_worker_count: 5
persistent_pair_cache.details.launched_pair_worker_count: 2
persistent_pair_cache.details.ready_pair_worker_count: 1
persistent_pair_cache.details.failed_pair_worker_count: 1
persistent_pair_cache.details.ready_pair_indexes: [0]
persistent_pair_cache.details.failed_pair_indexes: [1]
persistent_pair_cache.details.launch_stopped_reason: pair_01_seg04_07__seg07_10 did not reach ready status
persistent_pair_cache.details.all_pair_workers_ready: False
persistent_pair_cache.details.next_optimization_target: do not implement all-pair persistent cache yet; use this failure boundary to guide a different split or runtime-residency strategy
held_pair_residency_matrix.path: /mnt/nas/openclaw/reports/models/dream7b_bpu_held_pair_residency_matrix_20260605-235813/held_pair_residency_matrix_probe.json
held_pair_residency_matrix.details.verdict: ok_dream7b_bpu_held_pair_residency_matrix_probe
held_pair_residency_matrix.details.pair_worker_count: 5
held_pair_residency_matrix.details.ready_holder_pair_count: 5
held_pair_residency_matrix.details.ready_holder_pair_indexes: [0, 1, 2, 3, 4]
held_pair_residency_matrix.details.matrix_entry_count: 20
held_pair_residency_matrix.details.successful_pair_edge_count: 0
held_pair_residency_matrix.details.failed_pair_edge_count: 20
held_pair_residency_matrix.details.max_resident_pair_count_observed: 1
held_pair_residency_matrix.details.next_optimization_target: persistent multi-pair residency is not supported by this fine split; reduce individual pair HBM size or pursue a different split
single_segment_residency_matrix.path: /mnt/nas/openclaw/reports/models/dream7b_bpu_single_segment_residency_matrix_20260606-002628/single_segment_residency_matrix_probe.json
single_segment_residency_matrix.details.verdict: ok_dream7b_bpu_single_segment_residency_matrix_probe
single_segment_residency_matrix.details.segment_count: 10
single_segment_residency_matrix.details.ready_holder_segment_count: 10
single_segment_residency_matrix.details.matrix_entry_count: 90
single_segment_residency_matrix.details.successful_segment_edge_count: 90
single_segment_residency_matrix.details.failed_segment_edge_count: 0
single_segment_residency_matrix.details.max_resident_segment_count_observed: 2
single_segment_residency_matrix.details.next_optimization_target: inspect successful single-segment coexistence edges and then probe multi-segment cliques before changing the production runner
persistent_segment_cache.path: /mnt/nas/openclaw/reports/models/dream7b_bpu_persistent_segment_cache_20260606-005633/persistent_segment_cache_probe.json
persistent_segment_cache.details.verdict: ok_dream7b_bpu_persistent_segment_cache_probe
persistent_segment_cache.details.segment_worker_count: 10
persistent_segment_cache.details.launched_segment_worker_count: 3
persistent_segment_cache.details.ready_segment_worker_count: 2
persistent_segment_cache.details.failed_segment_worker_count: 1
persistent_segment_cache.details.ready_segment_indexes: [0, 1]
persistent_segment_cache.details.failed_segment_indexes: [2]
persistent_segment_cache.details.all_segment_workers_ready: False
persistent_segment_cache.details.launch_stopped_reason: segment_02_seg04_07 did not reach ready status
persistent_segment_cache.details.max_resident_segment_count_observed: 2
persistent_segment_cache.details.next_optimization_target: use the ready prefix and failure record to choose a smaller segment split or different runtime-residency strategy
single_segment_triplet_residency.path: /mnt/nas/openclaw/reports/models/dream7b_bpu_single_segment_triplet_residency_20260606-121243/single_segment_triplet_residency_probe.json
single_segment_triplet_residency.details.verdict: ok_dream7b_bpu_single_segment_triplet_residency_probe
single_segment_triplet_residency.details.segment_count: 10
single_segment_triplet_residency.details.total_triplet_combination_count: 120
single_segment_triplet_residency.details.tested_triplet_combination_count: 120
single_segment_triplet_residency.details.successful_triplet_count: 20
single_segment_triplet_residency.details.failed_triplet_count: 100
single_segment_triplet_residency.details.max_resident_segment_count_observed: 3
single_segment_triplet_residency.details.next_optimization_target: inspect successful triplets and then test a persistent topology seeded by those segment groups
seeded_quad_residency.path: /mnt/nas/openclaw/reports/models/dream7b_bpu_seeded_quad_residency_20260606-124305/seeded_quad_residency_probe.json
seeded_quad_residency.details.verdict: ok_dream7b_bpu_seeded_quad_residency_probe
seeded_quad_residency.details.segment_count: 10
seeded_quad_residency.details.source_successful_triplet_count: 20
seeded_quad_residency.details.seeded_quad_candidate_count: 84
seeded_quad_residency.details.tested_seeded_quad_count: 84
seeded_quad_residency.details.successful_seeded_quad_count: 0
seeded_quad_residency.details.failed_seeded_quad_count: 84
seeded_quad_residency.details.successful_seeded_quads: []
seeded_quad_residency.details.max_resident_segment_count_observed: 3
seeded_quad_residency.details.next_optimization_target: no tested seeded quad is resident; use successful triplets as the current persistent topology seed
persistent_triplet_topology.path: /mnt/nas/openclaw/reports/models/dream7b_bpu_persistent_triplet_topology_20260606-131107/persistent_triplet_topology_probe.json
persistent_triplet_topology.details.verdict: ok_dream7b_bpu_persistent_triplet_topology_probe
persistent_triplet_topology.details.segment_count: 10
persistent_triplet_topology.details.source_successful_triplet_count: 20
persistent_triplet_topology.details.tested_triplet_topology_count: 20
persistent_triplet_topology.details.stable_triplet_topology_count: 20
persistent_triplet_topology.details.failed_triplet_topology_count: 0
persistent_triplet_topology.details.hold_seconds: 10.0
persistent_triplet_topology.details.selected_topology: [0, 1, 8]
persistent_triplet_topology.details.selection_rule: first stable topology in source successful_triplets order
persistent_triplet_topology.details.max_resident_segment_count_observed: 3
persistent_triplet_topology.details.next_optimization_target: wire the selected stable triplet into a forward-path experiment and compare HBM load share against the current pair-window production path
window3_forward_feasibility.path: /mnt/nas/openclaw/reports/models/dream7b_bpu_window3_forward_feasibility_20260606-133931/window3_forward_feasibility_probe.json
window3_forward_feasibility.details.verdict: ok_dream7b_bpu_window3_forward_feasibility_probe
window3_forward_feasibility.details.returncode: 1
window3_forward_feasibility.details.direct_window3_forward_supported: False
window3_forward_feasibility.details.expected_window3_failure_observed: True
window3_forward_feasibility.details.stderr_contains_memory_alloc_failure: True
window3_forward_feasibility.details.window_size: 3
window3_forward_feasibility.details.child_window_mode: pair
window3_forward_feasibility.details.child_runtime_mode: packed
window3_forward_feasibility.details.window_execution_mode: window-batch
window3_forward_feasibility.details.next_optimization_target: do not switch production defaults to window3; use selected stable triplet worker or a new HBM split for the next forward-path experiment
selected_triplet_forward_path.path: /mnt/nas/openclaw/reports/models/dream7b_bpu_selected_triplet_forward_path_20260606-135729/selected_triplet_forward_path_probe.json
selected_triplet_forward_path.details.verdict: ok_dream7b_bpu_selected_triplet_forward_path_probe
selected_triplet_forward_path.details.selected_triplet_forward_supported: False
selected_triplet_forward_path.details.reboot_or_disconnect_observed: True
selected_triplet_forward_path.details.expected_reboot_guard_observed: True
selected_triplet_forward_path.details.source_incomplete_run_dir: /mnt/nas/openclaw/reports/models/dream7b_bpu_selected_triplet_forward_path_20260606-135729
selected_triplet_forward_path.details.selected_topology: [0, 1, 8]
selected_triplet_forward_path.details.selected_worker_count: 3
selected_triplet_forward_path.details.warm_path_load_improved: False
selected_triplet_forward_path.details.total_path_load_improved: False
selected_triplet_forward_path.details.next_optimization_target: do not promote selected triplet forward path; test smaller resident sets or vendor-supported multi-segment HBM residency instead
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
batch_count = 16
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
/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_batch_generate_telemetry_20260606-184316/generation/batch_generation.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_batch_generate_telemetry_20260606-184316/generation/batch_generation.json
```

Verified bounded batch generation fields copied from `batch_generation.json` through `batch_generation_telemetry_probe.json`:

```text
verdict: ok_dream7b_bpu_diffusion_batch_generate
forward_cmd: dream7b-bpu-fine-batch-forward
batch_count: 16
seq_len: 16
steps: 2
executed_step_count: 2
forward_batch_counts: [16, 16]
remaining_mask_positions_by_batch: [{'batch_index': 0, 'remaining_mask_positions': []}, {'batch_index': 1, 'remaining_mask_positions': []}, {'batch_index': 2, 'remaining_mask_positions': []}, {'batch_index': 3, 'remaining_mask_positions': []}, {'batch_index': 4, 'remaining_mask_positions': []}, {'batch_index': 5, 'remaining_mask_positions': []}, {'batch_index': 6, 'remaining_mask_positions': []}, {'batch_index': 7, 'remaining_mask_positions': []}, {'batch_index': 8, 'remaining_mask_positions': []}, {'batch_index': 9, 'remaining_mask_positions': []}, {'batch_index': 10, 'remaining_mask_positions': []}, {'batch_index': 11, 'remaining_mask_positions': []}, {'batch_index': 12, 'remaining_mask_positions': []}, {'batch_index': 13, 'remaining_mask_positions': []}, {'batch_index': 14, 'remaining_mask_positions': []}, {'batch_index': 15, 'remaining_mask_positions': []}]
history[0].forward_verdict: ok_dream7b_segmented_hbm_python_forward
history[0].forward_execution_mode: pair_window_batch
history[0].forward_window_execution_mode: window-batch
history[0].forward_child_process_count: 0
history[0].forward_batch_count: 16
history[1].forward_verdict: ok_dream7b_segmented_hbm_python_forward
history[1].forward_execution_mode: pair_window_batch
history[1].forward_window_execution_mode: window-batch
history[1].forward_child_process_count: 0
history[1].forward_batch_count: 16
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
batch_count = 16
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
/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_batch_generate_telemetry_20260606-184316/batch_generation_telemetry_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_batch_generate_telemetry_20260606-184316/batch_generation_telemetry_probe.json
```

Verified batch generation telemetry fields copied from `batch_generation_telemetry_probe.json`:

```text
verdict: ok_dream7b_bpu_diffusion_batch_generate_telemetry_probe
run_dir: /mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_batch_generate_telemetry_20260606-184316
generation_dir: /mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_batch_generate_telemetry_20260606-184316/generation
batch_count: 16
generate_cmd: dream7b-bpu-diffusion-batch-generate
monitor_delay_ms: 100
monitor_sample_count: 900
generation_status: 0
generation_json: /mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_batch_generate_telemetry_20260606-184316/generation/batch_generation.json
bpu_loading_sample_count: 604
nonzero_bpu_loading_sample_count: 68
max_bpu_loading: 100.0
avg_bpu_loading: 8.825
generation_metrics.verdict: ok_dream7b_bpu_diffusion_batch_generate
generation_metrics.forward_cmd: dream7b-bpu-fine-batch-forward
generation_metrics.batch_count: 16
generation_metrics.seq_len: 16
generation_metrics.steps: 2
generation_metrics.executed_step_count: 2
generation_metrics.forward_batch_counts: [16, 16]
generation_metrics.remaining_mask_positions_by_batch: [{'batch_index': 0, 'remaining_mask_positions': []}, {'batch_index': 1, 'remaining_mask_positions': []}, {'batch_index': 2, 'remaining_mask_positions': []}, {'batch_index': 3, 'remaining_mask_positions': []}, {'batch_index': 4, 'remaining_mask_positions': []}, {'batch_index': 5, 'remaining_mask_positions': []}, {'batch_index': 6, 'remaining_mask_positions': []}, {'batch_index': 7, 'remaining_mask_positions': []}, {'batch_index': 8, 'remaining_mask_positions': []}, {'batch_index': 9, 'remaining_mask_positions': []}, {'batch_index': 10, 'remaining_mask_positions': []}, {'batch_index': 11, 'remaining_mask_positions': []}, {'batch_index': 12, 'remaining_mask_positions': []}, {'batch_index': 13, 'remaining_mask_positions': []}, {'batch_index': 14, 'remaining_mask_positions': []}, {'batch_index': 15, 'remaining_mask_positions': []}]
generation_metrics.boundary: bounded_seq16_batch_generation_entrypoint_not_complete_production_text_service
generation_metrics.history_forward_verdicts: ['ok_dream7b_segmented_hbm_python_forward', 'ok_dream7b_segmented_hbm_python_forward']
generation_metrics.history_forward_execution_modes: ['pair_window_batch', 'pair_window_batch']
generation_metrics.history_forward_window_execution_modes: ['window-batch', 'window-batch']
generation_metrics.history_forward_child_process_counts: [0, 0]
generation_metrics.history_forward_batch_counts: [16, 16]
errors: []
```

### `dream7b-bpu-diffusion-batch-generate-sustained-probe`

Source file: `scripts/probes/dream7b_bpu_diffusion_batch_generate_sustained_probe.sh`

Installed command on S100P:

```text
/usr/local/bin/dream7b-bpu-diffusion-batch-generate-sustained-probe
```

Default argument copied from the script:

```text
report_root = /mnt/nas/openclaw/reports/models
```

Environment variables copied from the script:

```text
DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_ROUND_COUNT
DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_BATCH_COUNT
DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_CMD
DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_MONITOR_DELAY_MS
DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_MONITOR_SAMPLE_COUNT
DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_TIMEOUT_SEC
```

Default values copied from the script:

```text
round_count = 3
batch_count = 16
generate_cmd = dream7b-bpu-diffusion-batch-generate
monitor_delay_ms = 100
monitor_sample_count = 2400
timeout_sec = 900
```

Output files copied from the script:

```text
batch_generation_sustained_probe.json
batch_generation_sustained_probe.md
hrt_ucp_monitor.stdout
hrt_ucp_monitor.stderr
round_status.tsv
hrut_somstatus_before.txt
hrut_somstatus_after.txt
generation_round_01/batch_generation.json
generation_round_02/batch_generation.json
generation_round_03/batch_generation.json
```

Output fields copied from the script:

```text
generated_at
verdict
run_dir
round_count
batch_count
generate_cmd
monitor_delay_ms
monitor_sample_count
timeout_sec
successful_generation_count
expected_total_batch_items
actual_total_batch_items
generation_statuses
generation_wall_ms
generation_batch_counts
generation_executed_step_counts
generation_forward_batch_counts_by_round
total_forward_call_count
bpu_loading_sample_count
nonzero_bpu_loading_sample_count
max_bpu_loading
avg_bpu_loading
rounds
errors
```

Latest recorded report:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_batch_generate_sustained_20260606-190058/batch_generation_sustained_probe.md
```

Latest recorded JSON:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_batch_generate_sustained_20260606-190058/batch_generation_sustained_probe.json
```

Verified sustained batch generation fields copied from `batch_generation_sustained_probe.json`:

```text
verdict: ok_dream7b_bpu_diffusion_batch_generate_sustained_probe
run_dir: /mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_batch_generate_sustained_20260606-190058
round_count: 3
batch_count: 16
generate_cmd: dream7b-bpu-diffusion-batch-generate
successful_generation_count: 3
expected_total_batch_items: 48
actual_total_batch_items: 48
generation_statuses: [0, 0, 0]
generation_wall_ms: [60548, 59410, 59494]
generation_batch_counts: [16, 16, 16]
generation_executed_step_counts: [2, 2, 2]
generation_forward_batch_counts_by_round: [[16, 16], [16, 16], [16, 16]]
total_forward_call_count: 6
monitor_delay_ms: 100
monitor_sample_count: 2400
bpu_loading_sample_count: 1790
nonzero_bpu_loading_sample_count: 199
max_bpu_loading: 100.0
avg_bpu_loading: 9.022
rounds[0].verdict: ok_dream7b_bpu_diffusion_batch_generate
rounds[1].verdict: ok_dream7b_bpu_diffusion_batch_generate
rounds[2].verdict: ok_dream7b_bpu_diffusion_batch_generate
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

### Use official Qwen only as a baseline probe

Decision: use official Qwen and DeepSeek-Qwen SDK assets as an S100 LLM baseline comparison, but do not replace Dream 7B with Qwen.

Reason: the official SDK contains supported Qwen/DeepSeek-Qwen/InternLM/Omni configs and precompiled `.hbm` download entries, while the current Dream route is a custom segmented `.hbm` chain. A Qwen run can help identify whether official runtime layout avoids the current Dream `hbm_reload_dominated` failure class, but it is not the requested model.

2026-06-08 raw-log recheck decision: official Qwen is not a clean high-average 128TOPS utilization baseline on the current S100P state. The raw official runtime logs show `decode` and `prefill` model load success first, followed by `AllocError { len: 2359296 }`, repeated `UCP Allocate memory failed` entries with `backend: 9`, and `ION_ALLOCATOR`/`MEM_ALLOCATOR` common-buffer failures. This is similar to Dream only at the broad "BPU runtime problem exists" level; the currently verified Dream service bottleneck remains `hbm_reload_dominated`.

Evidence:

```text
/mnt/nas/openclaw/reports/models/s100_official_llm_baseline_20260606-004107/official_llm_baseline_probe.json
/mnt/nas/openclaw/reports/models/s100_official_qwen_runtime_20260606-003908/official_qwen_runtime_probe.json
/mnt/nas/openclaw/reports/models/s100_official_qwen_performance_mode_retest_20260606-003908/performance_mode_retest_probe.json
/mnt/nas/openclaw/reports/models/s100_bpu_memory_pool_20260606-004401/bpu_memory_pool_probe.json
/mnt/nas/openclaw/reports/models/s100_qwen_backend9_baseline_20260606-013902/qwen_backend9_baseline_probe.json
/mnt/nas/openclaw/reports/models/s100_qwen_bpu_core_sweep_20260606-015133/qwen_bpu_core_sweep_probe.json
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
acceptance_report: /mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-045552/deployment_acceptance_probe.md
acceptance_json: /mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-045552/deployment_acceptance_probe.json
verdict: ok_dream7b_bpu_deployment_acceptance_probe
check_count: 28
passed_check_count: 28
min_batch_capacity: 16
min_systemd_batch_requests: 16
min_systemd_telemetry_requests: 48
min_batch_generate_count: 16
min_batch_generate_sustained_round_count: 3
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
selected_pair_telemetry.ok: True
selected_pair_candidate_service.ok: True
selected_pair_candidate_service_telemetry.ok: True
utilization_gap.details.selected_pair_candidate_service_processed_request_count: 48
utilization_gap.details.selected_pair_candidate_service_load_to_run_ratio: 9.758
utilization_gap.details.selected_pair_candidate_service_wall_delta_ratio_vs_default_systemd: 0.138445
utilization_gap.details.selected_pair_candidate_service_avg_bpu_loading_delta_vs_default_systemd: -0.828
utilization_gap.details.selected_pair_candidate_service_wall_time_improved_vs_default_systemd: True
utilization_gap.details.selected_pair_candidate_service_avg_bpu_loading_not_worse_than_default_systemd: False
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
- Raised `dream7b-bpu-diffusion-batch-generate`, `dream7b-bpu-diffusion-batch-generate-telemetry-probe`, and `dream7b-bpu-deployment-acceptance-probe` defaults so bounded Dream diffusion batch generation now defaults to `batch_count: 16` and acceptance requires `min_batch_generate_count: 16`.
- Verified batch generation telemetry report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_batch_generate_telemetry_20260606-184316/batch_generation_telemetry_probe.md` with `batch_count: 16`, `forward_batch_counts: [16, 16]`, `nonzero_bpu_loading_sample_count: 68`, `avg_bpu_loading: 8.825`, and `max_bpu_loading: 100.0`.
- Verified 16-gate deployment acceptance report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-184511/deployment_acceptance_probe.md` with `check_count: 14`, `passed_check_count: 14`, `min_batch_generate_count: 16`, and `diffusion_batch_generate_telemetry.ok: True`.
- Added `dream7b-bpu-diffusion-batch-generate-sustained-probe` for repeated bounded seq16 batch Dream diffusion generation while sampling `hrt_ucp_monitor`.
- Verified sustained batch generation report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_batch_generate_sustained_20260606-190058/batch_generation_sustained_probe.md` with `round_count: 3`, `batch_count: 16`, `successful_generation_count: 3`, `actual_total_batch_items: 48`, `total_forward_call_count: 6`, `avg_bpu_loading: 9.022`, and `max_bpu_loading: 100.0`.
- Updated `dream7b-bpu-deployment-acceptance-probe` to include `diffusion_batch_generate_sustained` and `DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_GENERATE_SUSTAINED_ROUND_COUNT`.
- Verified sustained-aware deployment acceptance report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-205153/deployment_acceptance_probe.md` with `check_count: 15`, `passed_check_count: 15`, `min_batch_generate_sustained_round_count: 3`, and `diffusion_batch_generate_sustained.ok: True`.
- Added `dream7b-bpu-utilization-gap-probe` for report-only Dream 7B BPU utilization diagnosis across batch-size sweep, runtime telemetry, systemd telemetry, sustained generation, and batch-generation telemetry.
- Verified utilization gap report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_utilization_gap_20260606-211927/utilization_gap_probe.md` with `verdict: ok_dream7b_bpu_utilization_gap_probe`, `diagnosis: hbm_reload_dominated`, `max_observed_bpu_loading: 100.0`, `avg_observed_bpu_loading_across_reports: 8.978`, `runtime_load_to_run_ratio: 8.399`, and `systemd_load_to_run_ratio: 8.48`.
- Updated `dream7b-bpu-deployment-acceptance-probe` to include `utilization_gap`.
- Verified utilization-gap-aware deployment acceptance report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-212134/deployment_acceptance_probe.md` with `check_count: 16`, `passed_check_count: 16`, and `utilization_gap.ok: True`.
- Added `dream7b-bpu-persistent-pair-cache-probe` for testing whether all five fine pair runtimes can be held as long-lived workers before implementing any persistent pair-worker forward pipeline.
- Verified persistent pair cache report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_persistent_pair_cache_20260605-234349/persistent_pair_cache_probe.md` with `pair_worker_count: 5`, `launched_pair_worker_count: 2`, `ready_pair_worker_count: 1`, `all_pair_workers_ready: False`, and `launch_stopped_reason: pair_01_seg04_07__seg07_10 did not reach ready status`.
- Updated `dream7b-bpu-deployment-acceptance-probe` to include `persistent_pair_cache`.
- Verified persistent-pair-cache-aware deployment acceptance report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-234654/deployment_acceptance_probe.md` with `check_count: 17`, `passed_check_count: 17`, and `persistent_pair_cache.ok: True`.
- Added `dream7b-bpu-held-pair-residency-matrix-probe` for testing every held-pair/candidate-pair coexistence edge across the current five fine pair windows.
- Verified held-pair residency matrix report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_held_pair_residency_matrix_20260605-235813/held_pair_residency_matrix_probe.md` with `ready_holder_pair_count: 5`, `matrix_entry_count: 20`, `successful_pair_edge_count: 0`, `failed_pair_edge_count: 20`, and `max_resident_pair_count_observed: 1`.
- Updated `dream7b-bpu-deployment-acceptance-probe` to include `held_pair_residency_matrix`.
- Verified held-pair-matrix-aware deployment acceptance report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-000234/deployment_acceptance_probe.md` with `check_count: 18`, `passed_check_count: 18`, and `held_pair_residency_matrix.ok: True`.
- Added `dream7b-bpu-single-segment-residency-matrix-probe` for testing every held-single-segment/candidate-single-segment coexistence edge across the current ten fine segments.
- Verified single-segment residency matrix report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_single_segment_residency_matrix_20260606-002628/single_segment_residency_matrix_probe.md` with `segment_count: 10`, `ready_holder_segment_count: 10`, `matrix_entry_count: 90`, `successful_segment_edge_count: 90`, `failed_segment_edge_count: 0`, and `max_resident_segment_count_observed: 2`.
- Added `dream7b-bpu-persistent-segment-cache-probe` for launching single-segment runtimes sequentially and recording the current simultaneous residency boundary before implementing a persistent single-segment worker pipeline.
- Verified persistent segment cache report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_persistent_segment_cache_20260606-005633/persistent_segment_cache_probe.md` with `segment_worker_count: 10`, `launched_segment_worker_count: 3`, `ready_segment_worker_count: 2`, `failed_segment_worker_count: 1`, `all_segment_workers_ready: False`, `launch_stopped_reason: segment_02_seg04_07 did not reach ready status`, and `max_resident_segment_count_observed: 2`.
- Updated `dream7b-bpu-deployment-acceptance-probe` to include `single_segment_residency_matrix` and `persistent_segment_cache`.
- Verified segment-residency-aware deployment acceptance report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-120028/deployment_acceptance_probe.md` with `check_count: 20`, `passed_check_count: 20`, `single_segment_residency_matrix.ok: True`, and `persistent_segment_cache.ok: True`.
- Added `dream7b-bpu-single-segment-triplet-residency-probe` for testing all 120 three-single-segment residency combinations across the current ten fine segments.
- Verified single-segment triplet residency report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_single_segment_triplet_residency_20260606-121243/single_segment_triplet_residency_probe.md` with `tested_triplet_combination_count: 120`, `successful_triplet_count: 20`, `failed_triplet_count: 100`, and `max_resident_segment_count_observed: 3`.
- Updated `dream7b-bpu-deployment-acceptance-probe` to include `single_segment_triplet_residency`.
- Verified triplet-aware deployment acceptance report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-123257/deployment_acceptance_probe.md` with `check_count: 21`, `passed_check_count: 21`, and `single_segment_triplet_residency.ok: True`.
- Added `dream7b-bpu-seeded-quad-residency-probe` for expanding the 20 successful triplets into unique four-segment residency candidates.
- Verified seeded quad residency report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_seeded_quad_residency_20260606-124305/seeded_quad_residency_probe.md` with `source_successful_triplet_count: 20`, `seeded_quad_candidate_count: 84`, `tested_seeded_quad_count: 84`, `successful_seeded_quad_count: 0`, `failed_seeded_quad_count: 84`, and `max_resident_segment_count_observed: 3`.
- Updated `dream7b-bpu-deployment-acceptance-probe` to include `seeded_quad_residency`.
- Verified seeded-quad-aware deployment acceptance report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-125750/deployment_acceptance_probe.md` with `check_count: 22`, `passed_check_count: 22`, and `seeded_quad_residency.ok: True`.
- Added `dream7b-bpu-segment-capacity-planner-probe` for aggregating HBM segment sizes and residency reports into an explicit split-capacity boundary; verified `/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_capacity_planner_20260606-054148/segment_capacity_planner_probe.md` with `recommended_resplit_segment_indexes: [0, 9, 4, 6]`, `recommended_anchor_segment_indexes: [1, 8]`, and `current_split_quad_residency_supported: False`.
- Updated `dream7b-bpu-deployment-acceptance-probe` to include `segment_capacity_planner`; verified `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-054148/deployment_acceptance_probe.md` with `check_count: 30`, `passed_check_count: 30`, and `segment_capacity_planner.ok: True`.
- Added `compile_dream_segments_seq16_resplit_probe.sh` for the weak-segment resplit specs `0:1 1:2 10:12 12:14 17:19 19:21 26:27 27:28`; verified `/tmp/dream7b_resplit_compile_reports/dream7b_resplit_compile_20260608-112349/resplit_compile_probe.md` with `hbm_success_count: 8` and `failed_spec_count: 0`, then verified recovery mode at `/tmp/dream7b_resplit_compile_reports_resume/dream7b_resplit_compile_20260608-120008/resplit_compile_probe.md` with `skipped_existing_count: 8`.
- Copied the verified resplit `.hbm` artifacts and `manifest.sha256` to `/mnt/nas/openclaw/models/dream7b-hbm/resplit-seq16` and `/home/sunrise/.cache/openclaw/dream7b-hbm/resplit-seq16`; both locations passed `sha256sum -c manifest.sha256`.
- Added and installed `dream7b-bpu-resplit-hbm-artifact-inventory-probe`; verified NAS report `/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_hbm_artifact_inventory_20260606-071645/resplit_hbm_artifact_inventory_probe.md` and local-cache report `/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_hbm_artifact_inventory_20260606-071820/resplit_hbm_artifact_inventory_probe.md`, both with `expected_hbm_count: 8`, `existing_hbm_count: 8`, `manifest_verified_count: 8`, `total_hbm_size_bytes: 3851983368`, and `errors: []`.
- Added and installed `dream7b-bpu-resplit-segment-residency-probe`; verified `/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_segment_residency_20260606-072919/resplit_segment_residency_probe.md` with `segment_count: 14`, `single_success_count: 14`, `adjacent_pair_success_count: 13`, `adjacent_pair_count: 13`, `resplit_adjacent_pair_supported: True`, `ready_prefix_count: 3`, and `first_prefix_failure.segment: seg04_07`.
- Updated `scripts/probes/dream7b_segmented_hbm_python_forward.py` with `RESPLIT_ADJACENT_SEGMENTS`, `--resplit-hbm-dir`, `resplit-adjacent`, and `resplit_hbm_dir` summary coverage for the 14-segment mixed base/fine/resplit forward plan.
- Added and installed `dream7b-bpu-resplit-forward`; it wraps `dream7b-bpu-forward` with `--segment-plan resplit-adjacent`, `--residency-window-size 2`, `--child-window-mode pair`, `--child-runtime-mode packed`, and `--window-execution-mode in-process`.
- Added and installed `dream7b-bpu-resplit-forward-probe`; verified `/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_forward_20260606-074419/resplit_forward_probe.md` with `verdict: ok_dream7b_bpu_resplit_forward_probe`, `segment_plan: resplit-adjacent`, `execution_mode: pair_in_process`, `child_process_count: 0`, `segment_event_count: 14`, `final_shape: [1, 16, 152064]`, non-empty `topk_last_position`, `load_ms: 23906.713`, `run_ms: 152.863`, and `amortized_wall_ms_per_forward: 24260.349`.
- Added and installed `dream7b-bpu-resplit-batch-forward`; it wraps `dream7b-bpu-forward` with the same resplit layout and defaults `--window-execution-mode window-batch` for independent seq16 token batches.
- Added and installed `dream7b-bpu-resplit-batch-forward-probe`; verified `/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_batch_forward_20260606-075837/resplit_batch_forward_probe.md` with `verdict: ok_dream7b_bpu_resplit_batch_forward_probe`, `batch_count: 16`, `segment_plan: resplit-adjacent`, `execution_mode: pair_window_batch`, `child_process_count: 0`, `segment_event_count: 224`, `final_shape_count: 16`, `topk_last_position_by_batch_count: 16`, `amortized_wall_ms_per_forward: 1667.472`, `amortized_load_ms_per_forward: 1500.154`, `amortized_run_ms_per_forward: 149.794`, and `load_to_run_ratio: 10.014756`.
- Added and installed `dream7b-bpu-resplit-batch-telemetry-probe`; verified `/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_batch_telemetry_20260606-080917/resplit_batch_telemetry_probe.md` with `verdict: ok_dream7b_bpu_resplit_batch_telemetry_probe`, `batch_count: 16`, `max_bpu_loading: 100.0`, `avg_bpu_loading: 8.697`, `nonzero_bpu_loading_sample_count: 30`, `forward_metrics.segment_plan: resplit-adjacent`, `forward_metrics.execution_mode: pair_window_batch`, `forward_metrics.window_execution_mode: window-batch`, `forward_metrics.child_process_count: 0`, `forward_metrics.segment_event_count: 224`, `forward_metrics.amortized_wall_ms_per_forward: 1640.749`, and `forward_metrics.load_to_run_ratio: 9.817642`.
- Updated `dream7b-bpu-utilization-gap-probe` to include `resplit_batch_telemetry`; verified `/mnt/nas/openclaw/reports/models/dream7b_bpu_utilization_gap_20260606-081136/utilization_gap_probe.json` and `/mnt/nas/openclaw/reports/models/dream7b_bpu_utilization_gap_20260606-081136/utilization_gap_probe.md` with `diagnosis: hbm_reload_dominated`, `max_observed_bpu_loading: 100.0`, `avg_observed_bpu_loading_across_reports: 8.754`, `resplit_batch_telemetry.avg_bpu_loading: 8.697`, `resplit_batch_telemetry.load_to_run_ratio: 9.818`, and `resplit_batch_telemetry.amortized_wall_ms_per_forward: 1640.749`.
- Updated `dream7b-bpu-deployment-acceptance-probe` to require resplit batch telemetry evidence in the `utilization_gap` check; verified `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-081322/deployment_acceptance_probe.json` and `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-081322/deployment_acceptance_probe.md` with `check_count: 30`, `passed_check_count: 30`, `utilization_gap.ok: True`, `resplit_batch_telemetry_batch_count: 16`, `resplit_batch_telemetry_max_bpu_loading: 100.0`, and `resplit_batch_telemetry_segment_event_count: 224`.
- Added and installed `dream7b-bpu-resplit-window-cost-probe`; verified `/mnt/nas/openclaw/reports/models/dream7b_bpu_resplit_window_cost_20260606-083152/resplit_window_cost_probe.md` with `verdict: ok_dream7b_bpu_resplit_window_cost_probe`, `window_count: 7`, `segment_event_count: 224`, `load_to_run_ratio: 9.817642`, `top_load_window.resident_segments: ['seg07_10', 'seg10_12']`, `top_load_window.load_ms: 3842.891`, `top_load_to_run_ratio_window.resident_segments: ['seg00_01', 'seg01_02']`, and `top_load_to_run_ratio_window.load_to_run_ratio: 18.428821`.
- Updated `dream7b-bpu-utilization-gap-probe` to include `resplit_window_cost`; verified `/mnt/nas/openclaw/reports/models/dream7b_bpu_utilization_gap_20260606-083359/utilization_gap_probe.json` and `/mnt/nas/openclaw/reports/models/dream7b_bpu_utilization_gap_20260606-083359/utilization_gap_probe.md` with `diagnosis: hbm_reload_dominated`, `resplit_window_cost.window_count: 7`, `resplit_window_cost.load_to_run_ratio: 9.817642`, `resplit_window_cost.top_load_window.resident_segments: ['seg07_10', 'seg10_12']`, and `resplit_window_cost.top_load_to_run_ratio_window.resident_segments: ['seg00_01', 'seg01_02']`.
- Updated `dream7b-bpu-deployment-acceptance-probe` to require resplit window cost evidence through `utilization_gap`; verified `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-083359/deployment_acceptance_probe.json` and `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-083359/deployment_acceptance_probe.md` with `check_count: 30`, `passed_check_count: 30`, `utilization_gap.ok: True`, `resplit_window_cost_window_count: 7`, `resplit_window_cost_top_load_window: ['seg07_10', 'seg10_12']`, and `resplit_window_cost_top_load_to_run_ratio_window: ['seg00_01', 'seg01_02']`.
- Added `dream7b-bpu-persistent-triplet-topology-probe` for replaying successful triplets as long-lived workers before a forward-path experiment.
- Verified persistent triplet topology report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_persistent_triplet_topology_20260606-131107/persistent_triplet_topology_probe.md` with `source_successful_triplet_count: 20`, `tested_triplet_topology_count: 20`, `stable_triplet_topology_count: 20`, `failed_triplet_topology_count: 0`, `selected_topology: [0, 1, 8]`, and `max_resident_segment_count_observed: 3`.
- Updated `dream7b-bpu-deployment-acceptance-probe` to include `persistent_triplet_topology`.
- Verified persistent-triplet-aware deployment acceptance report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-133119/deployment_acceptance_probe.md` with `check_count: 23`, `passed_check_count: 23`, and `persistent_triplet_topology.ok: True`.
- Added `dream7b-bpu-window3-forward-feasibility-probe` for testing whether the existing packed adjacent three-segment forward path can replace the current pair-window path.
- Verified window3 forward feasibility report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_window3_forward_feasibility_20260606-133931/window3_forward_feasibility_probe.md` with `direct_window3_forward_supported: False`, `expected_window3_failure_observed: True`, `stderr_contains_memory_alloc_failure: True`, and `returncode: 1`.
- Updated `dream7b-bpu-deployment-acceptance-probe` to include `window3_forward_feasibility`.
- Verified window3-aware deployment acceptance report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-134115/deployment_acceptance_probe.md` with `check_count: 24`, `passed_check_count: 24`, and `window3_forward_feasibility.ok: True`.
- Added `dream7b-bpu-selected-triplet-forward-path-probe` for the selected `[0, 1, 8]` triplet forward-path experiment, plus a reboot/disconnect guard that records an incomplete run without retrying unless `DREAM7B_BPU_SELECTED_TRIPLET_ALLOW_CRASH_RETRY=1`.
- Verified selected triplet forward path report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_triplet_forward_path_20260606-135729/selected_triplet_forward_path_probe.md` with `selected_triplet_forward_supported: False`, `reboot_or_disconnect_observed: True`, `expected_reboot_guard_observed: True`, and `selected_topology: [0, 1, 8]`.
- Updated `dream7b-bpu-deployment-acceptance-probe` to include `selected_triplet_forward_path`.
- Verified selected-triplet-aware deployment acceptance report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-234652/deployment_acceptance_probe.md` with `check_count: 25`, `passed_check_count: 25`, and `selected_triplet_forward_path.ok: True`.
- Added `dream7b-bpu-selected-pair-forward-path-probe` to test the smaller resident-set route requested after the selected triplet forward path was rejected.
- Verified selected pair forward path report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_forward_path_20260606-022052/selected_pair_forward_path_probe.md` with `batch_count: 16`, `selected.selected_pair: [1, 8]`, `selected.selected_pair_covers_all_segments: True`, `comparison.warm_path_load_improved: True`, `comparison.warm_load_ms_delta_ratio_vs_baseline: 0.118757`, `selected.wall_ms: 23090.689`, `baseline.wall_ms: 25785.378`, and `comparison.total_path_load_improved: False`.
- Added `dream7b-bpu-selected-pair-telemetry-probe` to run selected-pair selected-only batch16 execution under `hrt_ucp_monitor`.
- Verified selected pair telemetry report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_telemetry_20260606-031259/selected_pair_telemetry_probe.md` with `batch_count: 16`, `selected.selected_pair: [1, 8]`, `max_bpu_loading: 98.0`, `avg_bpu_loading: 9.14`, `comparison_to_default_runtime_telemetry.wall_ms_delta_ratio_vs_default_runtime: 0.114225`, `comparison_to_default_runtime_telemetry.avg_bpu_loading_delta_vs_default_runtime: 1.952`, `comparison_to_default_runtime_telemetry.selected_wall_time_improved_vs_default_runtime: True`, and `comparison_to_default_runtime_telemetry.selected_avg_bpu_loading_improved_vs_default_runtime: True`.
- Updated `dream7b-bpu-utilization-gap-probe` to include `selected_pair_telemetry`.
- Verified selected-pair-aware utilization gap report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_utilization_gap_20260606-031454/utilization_gap_probe.md` with `diagnosis: hbm_reload_dominated`, `max_observed_bpu_loading: 100.0`, `avg_observed_bpu_loading_across_reports: 8.758`, and `selected_pair_telemetry.selected_wall_time_improved_vs_default_runtime: True`.
- Updated `dream7b-bpu-deployment-acceptance-probe` to include `selected_pair_telemetry`.
- Verified selected-pair-aware deployment acceptance report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-031455/deployment_acceptance_probe.md` with `check_count: 26`, `passed_check_count: 26`, and `selected_pair_telemetry.ok: True`.
- Added `dream7b-bpu-selected-pair-promotion-gate-probe` as a report-only gate for entering a guarded selected-pair default-service candidate without claiming the default service has already been promoted.
- Verified selected pair promotion gate report at `/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_promotion_gate_20260606-034228/selected_pair_promotion_gate_probe.md` with `promotion_ready_for_guarded_default_service_candidate: True`, `default_service_already_promoted: False`, `min_wall_delta_ratio: 0.05`, `min_avg_bpu_delta: 1.0`, and `next_optimization_target: implement a guarded selected-pair default-service candidate and re-run deployment acceptance before replacing the current default Dream 7B service path`.
- Added `s100-official-llm-baseline-probe` to compare the staged official S100 LLM SDK/Qwen route with the custom segmented Dream 7B route without replacing Dream 7B.
- Added `s100-official-qwen-runtime-probe` to run the official Qwen `oellm_multichat` example through the vendor runtime without replacing Dream 7B.
- Verified official Qwen runtime report at `/mnt/nas/openclaw/reports/models/s100_official_qwen_runtime_20260606-003908/official_qwen_runtime_probe.md` with `qwen_hbm_size_bytes: 1917038584`, `ldd_missing_dependency_observed: False`, `hbm_load_success_observed: True`, `prefill_model_load_success_observed: True`, `decode_model_load_success_observed: True`, `init_model_success_observed: True`, `runtime_returncode: -11`, `memory_alloc_failure_observed: True`, `ion_alloc_failure_observed: True`, `bpu_mem_pool_alloc_error_observed: True`, and `official_qwen_runtime_supported_on_current_s100p_state: False`.
- Added and verified `s100-official-qwen-performance-mode-retest-probe` at `/mnt/nas/openclaw/reports/models/s100_official_qwen_performance_mode_retest_20260606-003908/performance_mode_retest_probe.md`; it changed `0x2b047000` and `0x2b047004` to `0x00000099`, but official Qwen still reported `memory_alloc_failure_observed_after_performance_mode: True`.
- Updated and verified `s100-bpu-memory-pool-probe` at `/mnt/nas/openclaw/reports/models/s100_bpu_memory_pool_20260606-010941/bpu_memory_pool_probe.md`; it records direct debugfs ION heap data, BPU ION allocations, BPU iovmm counters, and device-tree reserved-memory nodes, correcting the earlier `ion_meminfo` wrapper error by showing `ion_all_heap_info_exists: True`, `system_heap_total_size: 0`, `system_contig_heap_total_size: 0`, `cma_reserved_heap_total_size: 1073741824`, `ion_cma_heap_total_size: 536870912`, `carveout_heap_total_size: 536870912`, and `reserved_memory_summary.bpu_region@9A000000.reg.size_mib: 96.0`.
- Added and verified `s100-hbmem-common-buffer-matrix-probe` at `/mnt/nas/openclaw/reports/models/s100_hbmem_common_buffer_matrix_20260606-012033/hbmem_common_buffer_matrix_probe.md`; it compiles a minimal C allocation matrix against `hb_mem_alloc_com_buf`, `hbUCPMalloc`, and `hbUCPMallocCached`, and shows the official Qwen failure sizes `786432` and `2359296` pass all tested HBMEM cases (`qwen_log_size_success_count: 14`, `qwen_log_size_failure_count: 0`) and all tested UCP cases pass (`ucp_success_count: 8`).
- Added and verified `s100-qwen-backend9-baseline-probe` at `/mnt/nas/openclaw/reports/models/s100_qwen_backend9_baseline_20260606-013902/qwen_backend9_baseline_probe.md`; it records official Qwen `qwen_multichat_config.json` lacks `bpu_core`, `oellm_multichat_demo.cc` defaults `bpu_core` to `-1` and `XLM_INFER_BACKEND_BPU_ANY`, the observed Qwen failure uses `backend: 9`, `/usr/include/hobot/hb_ucp.h` maps `backend: 9` to `HB_UCP_BPU_CORE_0` plus `HB_UCP_BPU_CORE_3` and not `HB_UCP_BPU_CORE_ANY`, and direct HBMEM/UCP allocation of the logged Qwen sizes still passes.
- Added and verified `s100-qwen-bpu-core-sweep-probe` at `/mnt/nas/openclaw/reports/models/s100_qwen_bpu_core_sweep_20260606-015133/qwen_bpu_core_sweep_probe.md`; it copies official Qwen config and tests exact `bpu_core` values `-1`, `0`, `1`, `2`, and `3`, showing every case still reports memory allocation failure and `functional_success_by_core` is `False` for every case. Explicit `bpu_core` values `1`, `2`, and `3` remove the process segfault but still fail prefill, so core pinning alone is not sufficient.
- Updated and verified official LLM/Qwen baseline report at `/mnt/nas/openclaw/reports/models/s100_official_llm_baseline_20260606-004107/official_llm_baseline_probe.md` with `sdk_exists: True`, `config_dir_count: 8`, `official_hbm_download_entry_count: 14`, `qwen_existing_hbm_count: 1`, `official_qwen_local_runtime_report_present: True`, `official_qwen_runtime_completed: False`, `official_qwen_memory_alloc_failure_observed: True`, and `similar_issue_evidence_available_for_official_qwen: True`.
- Rechecked the official Qwen route by SSH on 2026-06-08: `/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/oellm_runtime/example/oellm_multichat/qwen_multichat_config.json` contains exact keys `hbm_path`, `tokenizer_dir`, and `template_path` with values `../../model/Qwen2.5_1.5B_Instruct_1024.hbm`, `../../config/Qwen2.5_1.5B_Instruct_config/`, and `../../config/Qwen2.5_1.5B_Instruct_config/Qwen2.5_1.5B_Instruct.jinja`; `/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/oellm_runtime/example/oellm_multichat/oellm_multichat_demo.cc` defaults `bpu_core` to `-1` and maps that path to `XLM_INFER_BACKEND_BPU_ANY`, so the Qwen comparison remains a valid official-route memory/allocation comparison rather than a clean 128TOPS utilization baseline.
- Rechecked the official Qwen raw logs by SSH on 2026-06-08: `/mnt/nas/openclaw/reports/models/s100_official_qwen_runtime_20260606-003908/oellm_multichat.stderr.txt` records `Load dnn model success` for `decode` and `prefill`, then `AllocError { len: 2359296 }`; `/mnt/nas/openclaw/reports/models/s100_official_qwen_runtime_20260606-003908/oellm_multichat.stdout.txt` records repeated `UCP Allocate memory failed` with `backend: 9` plus `ION_ALLOCATOR` and `MEM_ALLOCATOR` common-buffer errors, so official Qwen did hit a BPU/common-buffer allocation problem on this board state, while Dream's current sustained-utilization blocker remains HBM reload/residency overhead.

## TODO

- Record the S100P OpenClaw entry demo after `openclaw_entry_demo_probe` writes NAS-backed evidence.
- Record the AI NAS movie-sort demo after `ai_nas_movie_sort_demo_probe` writes NAS-backed evidence.
- Keep Dream 7B work paused behind the two teacher demos until both demo runbooks are runnable.
- For the next Dream 7B phase, run an official S100 LLM quantization-to-deployment sample flow before replacing the official model with Dream 7B.
- Keep `--window-execution-mode child-process` as the fallback path until more long-run evidence extends beyond the current gated 6-run `--window-execution-mode in-process` probe.
- Do not implement a pair-worker persistent cache on the current five-pair split; the held-pair matrix has `successful_pair_edge_count: 0`.
- Use the single-segment results as the next residency route: two single-segment runtimes can coexist, but `segment_02_seg04_07` fails as the third resident runtime with S100 BPU `-400001` memory allocation failure.
- Do not promote `selected_topology: [0, 1, 8]` as a forward-path optimization; the selected triplet forward-path probe records `selected_triplet_forward_supported: False` and `reboot_or_disconnect_observed: True`.
- Treat selected pair `[1, 8]` as a positive telemetry-backed warm-path optimization; the promotion gate is ready for a guarded default-service candidate, but `default_service_already_promoted: False`, so the next implementation must add the guarded candidate and rerun deployment acceptance before replacing the current default Dream 7B service path.
- Do not switch `dream7b-bpu-fine-batch-forward` defaults to packed adjacent window size 3; the window3 feasibility probe records `expected_window3_failure_observed: True`.
- Do not attempt a four-segment resident topology on the current HBM artifacts without a new split or runtime change; the seeded quad probe has `successful_seeded_quad_count: 0`.
- Use the verified resplit window cost ranking as the next optimization baseline: `['seg07_10', 'seg10_12']` is the top absolute HBM load window and `['seg00_01', 'seg01_02']` is the top load/run ratio window, so the next split/runtime experiment should reduce packed HBM load cost for these windows before any default-service promotion.
- Treat explicit `bpu_core` as an optional crash-mitigation variable only; the controlled official Qwen sweep still has `functional_success_by_core` false for every tested value, so Dream 7B must continue focusing on HBM reload/residency reduction before expecting sustained 128TOPS utilization.
- Evaluate smaller HBM artifacts, different segment boundaries, or runtime residency support before expecting sustained 128TOPS-level average utilization from Dream 7B.
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
