#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
service_name="${2:-dream7b-bpu-batch-queue.service}"
queue_dir="${3:-/mnt/nas/openclaw/queues/dream7b-bpu}"
output_dir="${4:-/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd}"
tokenizer_venv="${DREAM7B_TOKENIZER_VENV:-/mnt/nas/openclaw/runtimes/dream7b-tokenizer-venv}"
tokenizer_dir="${DREAM7B_TOKENIZER:-/mnt/nas/openclaw/models/dream7b/tokenizer}"
prompt="${DREAM7B_BPU_TEXT_QUEUE_PROMPT:-hello}"
fit_mode="${DREAM7B_BPU_TEXT_QUEUE_FIT:-pad-right}"
seq_len="${DREAM7B_BPU_TEXT_QUEUE_SEQ_LEN:-16}"
timeout_sec="${DREAM7B_BPU_TEXT_QUEUE_TIMEOUT_SEC:-180}"
poll_interval_sec="${DREAM7B_BPU_TEXT_QUEUE_POLL_INTERVAL_SEC:-2}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

case "$queue_dir" in
  /tmp/*|/mnt/nas/openclaw/queues|/mnt/nas/openclaw/queues/*|/root/.openclaw/workspace/queues|/root/.openclaw/workspace/queues/*) ;;
  *)
    echo "Refusing queue path outside approved queue directories: $queue_dir" >&2
    exit 2
    ;;
esac

case "$output_dir" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing service output path outside approved report directories: $output_dir" >&2
    exit 2
    ;;
esac

if [[ ! -x "$tokenizer_venv/bin/python" ]]; then
  echo "Missing Dream 7B tokenizer venv: $tokenizer_venv" >&2
  exit 4
fi
if [[ ! -d "$tokenizer_dir" ]]; then
  echo "Missing Dream 7B tokenizer directory: $tokenizer_dir" >&2
  exit 4
fi
case "$fit_mode" in
  exact|truncate-left|pad-right) ;;
  *)
    echo "DREAM7B_BPU_TEXT_QUEUE_FIT must be exact, truncate-left, or pad-right." >&2
    exit 2
    ;;
esac
if ! [[ "$seq_len" =~ ^[1-9][0-9]*$ ]] || (( seq_len != 16 )); then
  echo "DREAM7B_BPU_TEXT_QUEUE_SEQ_LEN must be 16 for the current Dream 7B seq16 HBM artifacts." >&2
  exit 2
fi
if ! [[ "$timeout_sec" =~ ^[0-9]+$ ]] || (( timeout_sec < 1 )); then
  echo "DREAM7B_BPU_TEXT_QUEUE_TIMEOUT_SEC must be a positive integer." >&2
  exit 2
fi
if ! [[ "$poll_interval_sec" =~ ^[0-9]+$ ]] || (( poll_interval_sec < 1 )); then
  echo "DREAM7B_BPU_TEXT_QUEUE_POLL_INTERVAL_SEC must be a positive integer." >&2
  exit 2
fi
if [[ -z "$prompt" ]]; then
  echo "DREAM7B_BPU_TEXT_QUEUE_PROMPT must not be empty." >&2
  exit 2
fi

if (( EUID == 0 )); then
  sudo_cmd=()
else
  sudo_cmd=(sudo -n)
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_text_queue_systemd_$stamp"
mkdir -p "$run_dir"
job_name="text_queue_systemd_${stamp}.jsonl"
job_path="$run_dir/$job_name"
tokenizer_json="$run_dir/tokenizer_input.json"
request_id="text-queue-${stamp}-001"

service_status_before="$(systemctl is-active "$service_name" 2>/dev/null || true)"
service_enabled_before="$(systemctl is-enabled "$service_name" 2>/dev/null || true)"
unit_path="$(systemctl show "$service_name" -p FragmentPath --value 2>/dev/null || true)"
exec_start="$(systemctl show "$service_name" -p ExecStart --value 2>/dev/null || true)"
systemctl --no-pager --full status "$service_name" > "$run_dir/systemctl_status_before.txt" 2>&1 || true

if [[ "$service_status_before" != "active" ]]; then
  echo "Service is not active before text queue probe: $service_status_before" >&2
  exit 3
fi

"$tokenizer_venv/bin/python" - \
  "$tokenizer_dir" \
  "$seq_len" \
  "$fit_mode" \
  "$prompt" \
  "$request_id" \
  "$job_path" \
  "$tokenizer_json" <<'PY'
import json
import sys
from pathlib import Path

from transformers import AutoTokenizer

tokenizer_dir, seq_len_text, fit_mode, prompt, request_id, job_path, tokenizer_json = sys.argv[1:8]
seq_len = int(seq_len_text)
tok = AutoTokenizer.from_pretrained(tokenizer_dir, trust_remote_code=True, local_files_only=True)

if prompt.startswith("<|im_start|>"):
    prepared = prompt
else:
    prepared = f"<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"

ids = tok.encode(prepared)
original_token_count = len(ids)
if fit_mode == "exact":
    if original_token_count != seq_len:
        raise SystemExit(f"prompt encoded to {original_token_count} tokens, expected exactly {seq_len}")
elif fit_mode == "truncate-left":
    ids = ids[-seq_len:]
elif fit_mode == "pad-right":
    ids = ids[:seq_len] + [0] * max(0, seq_len - len(ids))
    ids = ids[:seq_len]
else:
    raise SystemExit(f"unsupported fit mode: {fit_mode}")

if len(ids) != seq_len:
    raise SystemExit(f"fit mode {fit_mode} produced {len(ids)} tokens, expected {seq_len}")

Path(job_path).write_text(
    json.dumps({"request_id": request_id, "tokens": [int(item) for item in ids]}, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
Path(tokenizer_json).write_text(
    json.dumps(
        {
            "tokenizer_dir": tokenizer_dir,
            "prompt": prompt,
            "prepared_prompt": prepared,
            "fit_mode": fit_mode,
            "seq_len": seq_len,
            "original_token_count": original_token_count,
            "token_count": len(ids),
            "tokens": [int(item) for item in ids],
        },
        ensure_ascii=False,
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
PY

"${sudo_cmd[@]}" mkdir -p "$queue_dir/pending" "$queue_dir/processing" "$queue_dir/done" "$queue_dir/failed"
"${sudo_cmd[@]}" test ! -e "$queue_dir/pending/$job_name"
"${sudo_cmd[@]}" test ! -e "$queue_dir/processing/$job_name"
"${sudo_cmd[@]}" test ! -e "$queue_dir/done/$job_name"
"${sudo_cmd[@]}" test ! -e "$queue_dir/failed/$job_name"
"${sudo_cmd[@]}" install -m 0644 "$job_path" "$queue_dir/pending/$job_name.upload"
"${sudo_cmd[@]}" mv "$queue_dir/pending/$job_name.upload" "$queue_dir/pending/$job_name"

deadline=$((SECONDS + timeout_sec))
while (( SECONDS < deadline )); do
  if "${sudo_cmd[@]}" test -f "$queue_dir/done/$job_name"; then
    break
  fi
  if "${sudo_cmd[@]}" test -f "$queue_dir/failed/$job_name"; then
    break
  fi
  sleep "$poll_interval_sec"
done

service_status_after="$(systemctl is-active "$service_name" 2>/dev/null || true)"
service_enabled_after="$(systemctl is-enabled "$service_name" 2>/dev/null || true)"
systemctl --no-pager --full status "$service_name" > "$run_dir/systemctl_status_after.txt" 2>&1 || true

summary_path="$output_dir/jobs/${job_name%.jsonl}/queue_summary.json"
job_status="missing"
for candidate in done failed processing pending; do
  if "${sudo_cmd[@]}" test -f "$queue_dir/$candidate/$job_name"; then
    job_status="$candidate"
    break
  fi
done

python3 - \
  "$run_dir" \
  "$service_name" \
  "$queue_dir" \
  "$output_dir" \
  "$job_name" \
  "$job_status" \
  "$summary_path" \
  "$tokenizer_venv" \
  "$tokenizer_dir" \
  "$tokenizer_json" \
  "$request_id" \
  "$timeout_sec" \
  "$poll_interval_sec" \
  "$service_status_before" \
  "$service_enabled_before" \
  "$service_status_after" \
  "$service_enabled_after" \
  "$unit_path" \
  "$exec_start" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
service_name = sys.argv[2]
queue_dir = sys.argv[3]
output_dir = sys.argv[4]
job_name = sys.argv[5]
job_status = sys.argv[6]
summary_path = Path(sys.argv[7])
tokenizer_venv = sys.argv[8]
tokenizer_dir = sys.argv[9]
tokenizer_json = Path(sys.argv[10])
request_id = sys.argv[11]
timeout_sec = int(sys.argv[12])
poll_interval_sec = int(sys.argv[13])
service_status_before = sys.argv[14]
service_enabled_before = sys.argv[15]
service_status_after = sys.argv[16]
service_enabled_after = sys.argv[17]
unit_path = sys.argv[18]
exec_start = sys.argv[19]

errors = []
tokenizer_payload = None
summary = None
if tokenizer_json.is_file():
    tokenizer_payload = json.loads(tokenizer_json.read_text(encoding="utf-8"))
else:
    errors.append(f"missing tokenizer JSON: {tokenizer_json}")
if summary_path.is_file():
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
else:
    errors.append(f"missing queue_summary.json: {summary_path}")

if service_status_before != "active":
    errors.append(f"unexpected service_status_before: {service_status_before}")
if service_enabled_before != "enabled":
    errors.append(f"unexpected service_enabled_before: {service_enabled_before}")
if service_status_after != "active":
    errors.append(f"unexpected service_status_after: {service_status_after}")
if service_enabled_after != "enabled":
    errors.append(f"unexpected service_enabled_after: {service_enabled_after}")
if not unit_path.endswith("/dream7b-bpu-batch-queue.service"):
    errors.append(f"unexpected unit_path: {unit_path}")
for text in (
    "dream7b-bpu-batch-queue-service",
    "/mnt/nas/openclaw/queues/dream7b-bpu",
    "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd",
    "/run/lock/dream7b_bpu_batch_queue_runner.lock",
    "--max-batch-size 16",
    "--top-k 3",
    "--drain-all",
):
    if text not in exec_start:
        errors.append(f"ExecStart missing {text}: {exec_start}")
if job_status != "done":
    errors.append(f"unexpected job_status: {job_status}")

if isinstance(tokenizer_payload, dict):
    if tokenizer_payload.get("token_count") != 16:
        errors.append(f"unexpected token_count: {tokenizer_payload.get('token_count')}")
    if tokenizer_payload.get("seq_len") != 16:
        errors.append(f"unexpected seq_len: {tokenizer_payload.get('seq_len')}")
    if tokenizer_payload.get("fit_mode") not in ("exact", "truncate-left", "pad-right"):
        errors.append(f"unexpected fit_mode: {tokenizer_payload.get('fit_mode')}")

processed_count = None
accepted_count = None
deferred_count = None
skipped_count = None
max_batch_size = None
drain_all = None
batch_run_count = None
batch_count = None
result_count = 0
execution_mode = None
window_execution_mode = None
child_process_count = None
total_wall_ms = 0.0
amortized_wall_ms = 0.0
bpu_lock_path = None
final_shape = None
topk_last_position = []
durable_results_jsonl = None

if isinstance(summary, dict):
    if summary.get("verdict") != "ok_dream7b_bpu_batch_queue_runner":
        errors.append(f"unexpected runner verdict: {summary.get('verdict')}")
    drain_all = summary.get("drain_all")
    max_batch_size = summary.get("max_batch_size")
    processed_count = summary.get("processed_count")
    accepted_count = summary.get("accepted_count")
    deferred_count = summary.get("deferred_count")
    skipped_count = summary.get("skipped_count")
    batch_run_count = summary.get("batch_run_count")
    if drain_all is not True:
        errors.append(f"unexpected drain_all: {drain_all}")
    if max_batch_size != 16:
        errors.append(f"unexpected max_batch_size: {max_batch_size}")
    if processed_count != 1:
        errors.append(f"unexpected processed_count: {processed_count}")
    if accepted_count != 1:
        errors.append(f"unexpected accepted_count: {accepted_count}")
    if deferred_count != 0:
        errors.append(f"unexpected deferred_count: {deferred_count}")
    if skipped_count != 0:
        errors.append(f"unexpected skipped_count: {skipped_count}")
    if batch_run_count != 1:
        errors.append(f"unexpected batch_run_count: {batch_run_count}")
    lock = summary.get("bpu_lock") or {}
    bpu_lock_path = lock.get("path")
    if bpu_lock_path != "/run/lock/dream7b_bpu_batch_queue_runner.lock":
        errors.append(f"unexpected bpu_lock.path: {bpu_lock_path}")
    batch_runs = summary.get("batch_runs") or []
    metrics = batch_runs[0].get("metrics", {}) if batch_runs else {}
    batch_count = metrics.get("batch_count")
    execution_mode = metrics.get("execution_mode")
    window_execution_mode = metrics.get("window_execution_mode")
    child_process_count = metrics.get("child_process_count")
    if batch_count != 1:
        errors.append(f"unexpected batch_count: {batch_count}")
    if execution_mode != "pair_window_batch":
        errors.append(f"unexpected execution_mode: {execution_mode}")
    if window_execution_mode != "window-batch":
        errors.append(f"unexpected window_execution_mode: {window_execution_mode}")
    if child_process_count != 0:
        errors.append(f"unexpected child_process_count: {child_process_count}")
    results = summary.get("results") or []
    result_count = len(results)
    if result_count != 1:
        errors.append(f"unexpected result_count: {result_count}")
    if results:
        result = results[0]
        if result.get("request_id") != request_id:
            errors.append(f"unexpected result request_id: {result.get('request_id')}")
        final_shape = result.get("final_shape")
        topk_last_position = result.get("topk_last_position") or []
        if final_shape != [1, 16, 152064]:
            errors.append(f"unexpected final_shape: {final_shape}")
        if not topk_last_position:
            errors.append("topk_last_position is empty")
    forward_metrics = summary.get("forward_metrics") or {}
    total_wall_ms = float(forward_metrics.get("total_wall_ms") or 0.0)
    amortized_wall_ms = float(forward_metrics.get("amortized_wall_ms_per_processed_request") or 0.0)
    if total_wall_ms <= 0:
        errors.append(f"unexpected total_wall_ms: {total_wall_ms}")
    if amortized_wall_ms <= 0:
        errors.append(f"unexpected amortized_wall_ms_per_processed_request: {amortized_wall_ms}")
    durable_results_jsonl = (summary.get("durable_state") or {}).get("results_jsonl")
    if not durable_results_jsonl:
        errors.append("missing durable_state.results_jsonl")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_text_queue_systemd_probe" if not errors else "failed_dream7b_bpu_text_queue_systemd_probe",
    "service_name": service_name,
    "queue_dir": queue_dir,
    "output_dir": output_dir,
    "job_name": job_name,
    "job_status": job_status,
    "summary_path": str(summary_path),
    "tokenizer_venv": tokenizer_venv,
    "tokenizer_dir": tokenizer_dir,
    "tokenizer_json": str(tokenizer_json),
    "tokenizer": tokenizer_payload,
    "request_id": request_id,
    "timeout_sec": timeout_sec,
    "poll_interval_sec": poll_interval_sec,
    "service_status_before": service_status_before,
    "service_enabled_before": service_enabled_before,
    "service_status_after": service_status_after,
    "service_enabled_after": service_enabled_after,
    "unit_path": unit_path,
    "exec_start": exec_start,
    "drain_all": drain_all,
    "max_batch_size": max_batch_size,
    "processed_count": processed_count,
    "accepted_count": accepted_count,
    "deferred_count": deferred_count,
    "skipped_count": skipped_count,
    "batch_run_count": batch_run_count,
    "batch_count": batch_count,
    "result_count": result_count,
    "execution_mode": execution_mode,
    "window_execution_mode": window_execution_mode,
    "child_process_count": child_process_count,
    "bpu_lock_path": bpu_lock_path,
    "final_shape": final_shape,
    "topk_last_position": topk_last_position,
    "durable_results_jsonl": durable_results_jsonl,
    "total_wall_ms": round(total_wall_ms, 3),
    "amortized_wall_ms_per_processed_request": round(amortized_wall_ms, 3),
    "errors": errors,
}
(run_dir / "text_queue_systemd_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
error_lines = [f"- {item}" for item in errors] if errors else ["- none"]
(run_dir / "text_queue_systemd_probe.md").write_text(
    "\n".join([
        "# Dream 7B BPU Text Queue Systemd Probe",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- service_name: {payload['service_name']}",
        f"- queue_dir: {payload['queue_dir']}",
        f"- output_dir: {payload['output_dir']}",
        f"- job_name: {payload['job_name']}",
        f"- job_status: {payload['job_status']}",
        f"- summary_path: {payload['summary_path']}",
        f"- tokenizer_venv: {payload['tokenizer_venv']}",
        f"- tokenizer_dir: {payload['tokenizer_dir']}",
        f"- tokenizer_json: {payload['tokenizer_json']}",
        f"- request_id: {payload['request_id']}",
        f"- processed_count: {payload['processed_count']}",
        f"- accepted_count: {payload['accepted_count']}",
        f"- batch_count: {payload['batch_count']}",
        f"- execution_mode: {payload['execution_mode']}",
        f"- window_execution_mode: {payload['window_execution_mode']}",
        f"- child_process_count: {payload['child_process_count']}",
        f"- final_shape: {payload['final_shape']}",
        f"- topk_last_position: {payload['topk_last_position']}",
        f"- durable_results_jsonl: {payload['durable_results_jsonl']}",
        f"- total_wall_ms: {payload['total_wall_ms']}",
        f"- amortized_wall_ms_per_processed_request: {payload['amortized_wall_ms_per_processed_request']}",
        "",
        "## Errors",
        "",
        *error_lines,
        "",
    ]) + "\n",
    encoding="utf-8",
)
print(run_dir / "text_queue_systemd_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
