#!/usr/bin/env bash
set -euo pipefail

queue_dir="${DREAM7B_BPU_TEXT_QUEUE_DIR:-/mnt/nas/openclaw/queues/dream7b-bpu}"
output_dir="${DREAM7B_BPU_TEXT_QUEUE_OUTPUT_DIR:-/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd}"
report_root="${DREAM7B_BPU_TEXT_QUEUE_RUN_REPORT_ROOT:-/mnt/nas/openclaw/reports/models}"
run_dir_override="${DREAM7B_BPU_TEXT_QUEUE_RUN_DIR:-}"
submit_cmd="${DREAM7B_BPU_TEXT_QUEUE_SUBMIT_CMD:-dream7b-bpu-text-queue-submit}"
seq_len="${DREAM7B_BPU_TEXT_QUEUE_SEQ_LEN:-16}"
fit_mode="${DREAM7B_BPU_TEXT_QUEUE_FIT:-pad-right}"
timeout_sec="${DREAM7B_BPU_TEXT_QUEUE_TIMEOUT_SEC:-180}"
poll_interval_sec="${DREAM7B_BPU_TEXT_QUEUE_POLL_INTERVAL_SEC:-2}"
request_id=""
job_stem=""
prompt_file=""
prompt_text=""

usage() {
  cat >&2 <<'USAGE'
usage: dream7b-bpu-text-queue-run [--queue-dir DIR] [--output-dir DIR] [--report-root DIR] [--run-dir DIR] [--job-stem NAME] [--request-id ID] [--fit exact|truncate-left|pad-right] [--seq-len 16] [--timeout-sec N] [--poll-interval-sec N] [--prompt TEXT|--prompt-file FILE] [--] prompt text

Encodes a Dream 7B prompt through dream7b-bpu-text-queue-submit, waits for the
NAS-backed BPU queue service to finish the submitted job, and writes a compact
text_queue_run JSON/Markdown result.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --queue-dir)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      queue_dir="$2"
      shift 2
      ;;
    --queue-dir=*)
      queue_dir="${1#--queue-dir=}"
      shift
      ;;
    --output-dir)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      output_dir="$2"
      shift 2
      ;;
    --output-dir=*)
      output_dir="${1#--output-dir=}"
      shift
      ;;
    --report-root)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      report_root="$2"
      shift 2
      ;;
    --report-root=*)
      report_root="${1#--report-root=}"
      shift
      ;;
    --run-dir)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      run_dir_override="$2"
      shift 2
      ;;
    --run-dir=*)
      run_dir_override="${1#--run-dir=}"
      shift
      ;;
    --job-stem)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      job_stem="$2"
      shift 2
      ;;
    --job-stem=*)
      job_stem="${1#--job-stem=}"
      shift
      ;;
    --request-id)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      request_id="$2"
      shift 2
      ;;
    --request-id=*)
      request_id="${1#--request-id=}"
      shift
      ;;
    --fit)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      fit_mode="$2"
      shift 2
      ;;
    --fit=*)
      fit_mode="${1#--fit=}"
      shift
      ;;
    --seq-len)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      seq_len="$2"
      shift 2
      ;;
    --seq-len=*)
      seq_len="${1#--seq-len=}"
      shift
      ;;
    --timeout-sec)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      timeout_sec="$2"
      shift 2
      ;;
    --timeout-sec=*)
      timeout_sec="${1#--timeout-sec=}"
      shift
      ;;
    --poll-interval-sec)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      poll_interval_sec="$2"
      shift 2
      ;;
    --poll-interval-sec=*)
      poll_interval_sec="${1#--poll-interval-sec=}"
      shift
      ;;
    --prompt)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      prompt_text="$2"
      shift 2
      ;;
    --prompt=*)
      prompt_text="${1#--prompt=}"
      shift
      ;;
    --prompt-file)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      prompt_file="$2"
      shift 2
      ;;
    --prompt-file=*)
      prompt_file="${1#--prompt-file=}"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    *)
      break
      ;;
  esac
done

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
case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac
if [[ -n "$run_dir_override" ]]; then
  case "$run_dir_override" in
    /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing run path outside approved report directories: $run_dir_override" >&2
      exit 2
      ;;
  esac
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
if [[ -n "$job_stem" && ! "$job_stem" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "--job-stem may only contain A-Z, a-z, 0-9, dot, underscore, or hyphen." >&2
  exit 2
fi
if [[ -n "$request_id" && ! "$request_id" =~ ^[A-Za-z0-9._:-]+$ ]]; then
  echo "--request-id may only contain A-Z, a-z, 0-9, dot, underscore, hyphen, or colon." >&2
  exit 2
fi
if ! command -v "$submit_cmd" >/dev/null 2>&1; then
  echo "Missing deployed command: $submit_cmd" >&2
  exit 3
fi

if [[ -n "$prompt_file" && -n "$prompt_text" ]]; then
  echo "Use either --prompt or --prompt-file, not both." >&2
  exit 2
fi
if [[ -n "$prompt_file" ]]; then
  if [[ ! -f "$prompt_file" ]]; then
    echo "Missing prompt file: $prompt_file" >&2
    exit 2
  fi
  prompt_text="$(cat "$prompt_file")"
fi
if [[ -z "$prompt_text" ]]; then
  prompt_text="$*"
fi
if [[ -z "$prompt_text" ]]; then
  if [[ ! -t 0 ]]; then
    prompt_text="$(cat)"
  fi
fi
if [[ -z "$prompt_text" ]]; then
  usage
  exit 2
fi

if (( EUID == 0 )); then
  sudo_cmd=()
else
  sudo_cmd=(sudo -n)
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
if [[ -z "$job_stem" ]]; then
  job_stem="text_queue_run_${stamp}"
fi
if [[ -z "$request_id" ]]; then
  request_id="${job_stem}-001"
fi
if [[ -n "$run_dir_override" ]]; then
  run_dir="$run_dir_override"
else
  run_dir="$report_root/dream7b_bpu_text_queue_run_$stamp"
fi
mkdir -p "$run_dir"
job_name="${job_stem}.jsonl"
summary_path="$output_dir/jobs/$job_stem/queue_summary.json"
submit_json="$run_dir/text_queue_submit.json"
submit_md="$run_dir/text_queue_submit.md"
tokenizer_json="$run_dir/tokenizer_input.json"
run_json="$run_dir/text_queue_run.json"
run_md="$run_dir/text_queue_run.md"
submit_stdout="$run_dir/text_queue_submit.stdout"
submit_stderr="$run_dir/text_queue_submit.stderr"

"$submit_cmd" \
  --queue-dir "$queue_dir" \
  --report-root "$report_root" \
  --run-dir "$run_dir" \
  --job-stem "$job_stem" \
  --request-id "$request_id" \
  --fit "$fit_mode" \
  --seq-len "$seq_len" \
  --prompt "$prompt_text" \
  >"$submit_stdout" 2>"$submit_stderr"

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

job_status="missing"
for candidate in done failed processing pending; do
  if "${sudo_cmd[@]}" test -f "$queue_dir/$candidate/$job_name"; then
    job_status="$candidate"
    break
  fi
done

python3 - \
  "$run_dir" \
  "$run_json" \
  "$run_md" \
  "$queue_dir" \
  "$output_dir" \
  "$report_root" \
  "$job_name" \
  "$job_status" \
  "$summary_path" \
  "$submit_cmd" \
  "$submit_json" \
  "$submit_md" \
  "$submit_stdout" \
  "$submit_stderr" \
  "$tokenizer_json" \
  "$request_id" \
  "$seq_len" \
  "$fit_mode" \
  "$timeout_sec" \
  "$poll_interval_sec" <<'PY'
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
run_json = Path(sys.argv[2])
run_md = Path(sys.argv[3])
queue_dir = sys.argv[4]
output_dir = sys.argv[5]
report_root = sys.argv[6]
job_name = sys.argv[7]
job_status = sys.argv[8]
summary_path = Path(sys.argv[9])
submit_cmd = sys.argv[10]
submit_json = Path(sys.argv[11])
submit_md = Path(sys.argv[12])
submit_stdout = Path(sys.argv[13])
submit_stderr = Path(sys.argv[14])
tokenizer_json = Path(sys.argv[15])
request_id = sys.argv[16]
seq_len = int(sys.argv[17])
fit_mode = sys.argv[18]
timeout_sec = int(sys.argv[19])
poll_interval_sec = int(sys.argv[20])

errors = []
submit_payload = None
tokenizer_payload = None
summary = None
if submit_json.is_file():
    submit_payload = json.loads(submit_json.read_text(encoding="utf-8"))
else:
    errors.append(f"missing text_queue_submit.json: {submit_json}")
if tokenizer_json.is_file():
    tokenizer_payload = json.loads(tokenizer_json.read_text(encoding="utf-8"))
else:
    errors.append(f"missing tokenizer JSON: {tokenizer_json}")
if summary_path.is_file():
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
else:
    errors.append(f"missing queue_summary.json: {summary_path}")

if job_status != "done":
    errors.append(f"unexpected job_status: {job_status}")
if isinstance(submit_payload, dict):
    if submit_payload.get("verdict") != "ok_dream7b_bpu_text_queue_submit":
        errors.append(f"unexpected submit verdict: {submit_payload.get('verdict')}")
    if submit_payload.get("job_name") != job_name:
        errors.append(f"unexpected submit job_name: {submit_payload.get('job_name')}")
    if submit_payload.get("request_id") != request_id:
        errors.append(f"unexpected submit request_id: {submit_payload.get('request_id')}")
    if submit_payload.get("queue_dir") != queue_dir:
        errors.append(f"unexpected submit queue_dir: {submit_payload.get('queue_dir')}")
    if submit_payload.get("seq_len") != seq_len:
        errors.append(f"unexpected submit seq_len: {submit_payload.get('seq_len')}")
    if submit_payload.get("fit_mode") != fit_mode:
        errors.append(f"unexpected submit fit_mode: {submit_payload.get('fit_mode')}")
    if submit_payload.get("errors"):
        errors.append(f"submit errors are not empty: {submit_payload.get('errors')}")
if isinstance(tokenizer_payload, dict):
    if tokenizer_payload.get("token_count") != seq_len:
        errors.append(f"unexpected token_count: {tokenizer_payload.get('token_count')}")
    if tokenizer_payload.get("seq_len") != seq_len:
        errors.append(f"unexpected tokenizer seq_len: {tokenizer_payload.get('seq_len')}")
    if tokenizer_payload.get("fit_mode") != fit_mode:
        errors.append(f"unexpected tokenizer fit_mode: {tokenizer_payload.get('fit_mode')}")

processed_count = None
accepted_count = None
deferred_count = None
skipped_count = None
batch_run_count = None
batch_count = None
result_count = 0
execution_mode = None
window_execution_mode = None
child_process_count = None
bpu_lock_path = None
final_shape = None
topk_last_position = []
topk_last_position_decoded = []
durable_results_jsonl = None
total_wall_ms = 0.0
amortized_wall_ms = 0.0

if isinstance(summary, dict):
    if summary.get("verdict") != "ok_dream7b_bpu_batch_queue_runner":
        errors.append(f"unexpected runner verdict: {summary.get('verdict')}")
    processed_count = summary.get("processed_count")
    accepted_count = summary.get("accepted_count")
    deferred_count = summary.get("deferred_count")
    skipped_count = summary.get("skipped_count")
    batch_run_count = summary.get("batch_run_count")
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
    bpu_lock_path = (summary.get("bpu_lock") or {}).get("path")
    if bpu_lock_path != "/run/lock/dream7b_bpu_batch_queue_runner.lock":
        errors.append(f"unexpected bpu_lock.path: {bpu_lock_path}")
    batch_runs = summary.get("batch_runs") or []
    metrics = batch_runs[0].get("metrics", {}) if batch_runs else {}
    batch_count = metrics.get("batch_count")
    execution_mode = metrics.get("execution_mode")
    window_execution_mode = metrics.get("window_execution_mode")
    child_process_count = metrics.get("child_process_count")
    results = summary.get("results") or []
    result_count = len(results)
    if batch_count != 1:
        errors.append(f"unexpected batch_count: {batch_count}")
    if execution_mode != "pair_window_batch":
        errors.append(f"unexpected execution_mode: {execution_mode}")
    if window_execution_mode != "window-batch":
        errors.append(f"unexpected window_execution_mode: {window_execution_mode}")
    if child_process_count != 0:
        errors.append(f"unexpected child_process_count: {child_process_count}")
    if result_count != 1:
        errors.append(f"unexpected result_count: {result_count}")
    if results:
        result = results[0]
        if result.get("request_id") != request_id:
            errors.append(f"unexpected result request_id: {result.get('request_id')}")
        final_shape = result.get("final_shape")
        topk_last_position = result.get("topk_last_position") or []
        if final_shape != [1, seq_len, 152064]:
            errors.append(f"unexpected final_shape: {final_shape}")
        if not topk_last_position:
            errors.append("topk_last_position is empty")
    forward_metrics = summary.get("forward_metrics") or {}
    total_wall_ms = float(forward_metrics.get("total_wall_ms") or 0.0)
    amortized_wall_ms = float(forward_metrics.get("amortized_wall_ms_per_processed_request") or 0.0)
    if total_wall_ms <= 0.0:
        errors.append(f"unexpected total_wall_ms: {total_wall_ms}")
    if amortized_wall_ms <= 0.0:
        errors.append(f"unexpected amortized_wall_ms_per_processed_request: {amortized_wall_ms}")
    durable_results_jsonl = (summary.get("durable_state") or {}).get("results_jsonl")
    if not durable_results_jsonl:
        errors.append("missing durable_state.results_jsonl")

if topk_last_position:
    tokenizer_venv = submit_payload.get("tokenizer_venv") if isinstance(submit_payload, dict) else None
    decode_tokenizer_dir = tokenizer_payload.get("tokenizer_dir") if isinstance(tokenizer_payload, dict) else None
    if not tokenizer_venv:
        errors.append("missing submit tokenizer_venv for topk decode")
    if not decode_tokenizer_dir:
        errors.append("missing tokenizer.tokenizer_dir for topk decode")
    if tokenizer_venv and decode_tokenizer_dir:
        decode_python = Path(tokenizer_venv) / "bin" / "python"
        if not decode_python.is_file():
            errors.append(f"missing tokenizer decode python: {decode_python}")
        else:
            token_ids = [int(item.get("token_id")) for item in topk_last_position]
            decoder = r'''
import json
import sys
from transformers import AutoTokenizer

tokenizer_dir = sys.argv[1]
token_ids = json.loads(sys.stdin.read())
tok = AutoTokenizer.from_pretrained(tokenizer_dir, trust_remote_code=True, local_files_only=True)
decoded = [
    {"token_id": int(token_id), "token_text": tok.decode([int(token_id)], skip_special_tokens=False)}
    for token_id in token_ids
]
print(json.dumps(decoded, ensure_ascii=False))
'''
            proc = subprocess.run(
                [str(decode_python), "-c", decoder, decode_tokenizer_dir],
                input=json.dumps(token_ids),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if proc.returncode != 0:
                errors.append(f"topk decode failed: {proc.stderr.strip()}")
            else:
                decoded_rows = None
                for line in reversed(proc.stdout.splitlines()):
                    candidate = line.strip()
                    if not candidate:
                        continue
                    try:
                        decoded_rows = json.loads(candidate)
                        break
                    except json.JSONDecodeError:
                        continue
                if decoded_rows is None:
                    errors.append(f"topk decode did not return JSON: {proc.stdout.strip()}")
                    decoded_rows = []
                decoded_by_id = {int(item["token_id"]): item.get("token_text", "") for item in decoded_rows}
                for item in topk_last_position:
                    enriched = dict(item)
                    token_id = int(enriched["token_id"])
                    enriched["token_text"] = decoded_by_id.get(token_id, "")
                    topk_last_position_decoded.append(enriched)
                if len(topk_last_position_decoded) != len(topk_last_position):
                    errors.append(
                        "topk_last_position_decoded length does not match topk_last_position"
                    )

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_text_queue_run" if not errors else "failed_dream7b_bpu_text_queue_run",
    "queue_dir": queue_dir,
    "output_dir": output_dir,
    "report_root": report_root,
    "run_dir": str(run_dir),
    "job_name": job_name,
    "job_status": job_status,
    "summary_path": str(summary_path),
    "submit_cmd": submit_cmd,
    "submit_json": str(submit_json),
    "submit_md": str(submit_md),
    "submit_stdout": str(submit_stdout),
    "submit_stderr": str(submit_stderr),
    "submit": submit_payload,
    "submit_verdict": submit_payload.get("verdict") if isinstance(submit_payload, dict) else None,
    "tokenizer_json": str(tokenizer_json),
    "tokenizer": tokenizer_payload,
    "request_id": request_id,
    "seq_len": seq_len,
    "fit_mode": fit_mode,
    "timeout_sec": timeout_sec,
    "poll_interval_sec": poll_interval_sec,
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
    "topk_last_position_decoded": topk_last_position_decoded,
    "durable_results_jsonl": durable_results_jsonl,
    "total_wall_ms": round(total_wall_ms, 3),
    "amortized_wall_ms_per_processed_request": round(amortized_wall_ms, 3),
    "errors": errors,
}
run_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
error_lines = [f"- {item}" for item in errors] if errors else ["- none"]
run_md.write_text(
    "\n".join([
        "# Dream 7B BPU Text Queue Run",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- queue_dir: {payload['queue_dir']}",
        f"- output_dir: {payload['output_dir']}",
        f"- run_dir: {payload['run_dir']}",
        f"- job_name: {payload['job_name']}",
        f"- job_status: {payload['job_status']}",
        f"- summary_path: {payload['summary_path']}",
        f"- submit_cmd: {payload['submit_cmd']}",
        f"- submit_verdict: {payload['submit_verdict']}",
        f"- tokenizer_json: {payload['tokenizer_json']}",
        f"- request_id: {payload['request_id']}",
        f"- processed_count: {payload['processed_count']}",
        f"- accepted_count: {payload['accepted_count']}",
        f"- batch_count: {payload['batch_count']}",
        f"- final_shape: {payload['final_shape']}",
        f"- topk_last_position: {payload['topk_last_position']}",
        f"- topk_last_position_decoded: {payload['topk_last_position_decoded']}",
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
print(run_md)
if errors:
    raise SystemExit("; ".join(errors))
PY
