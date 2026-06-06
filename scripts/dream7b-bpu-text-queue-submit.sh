#!/usr/bin/env bash
set -euo pipefail

tokenizer_venv="${DREAM7B_TOKENIZER_VENV:-/mnt/nas/openclaw/runtimes/dream7b-tokenizer-venv}"
tokenizer_dir="${DREAM7B_TOKENIZER:-/mnt/nas/openclaw/models/dream7b/tokenizer}"
queue_dir="${DREAM7B_BPU_TEXT_QUEUE_DIR:-/mnt/nas/openclaw/queues/dream7b-bpu}"
report_root="${DREAM7B_BPU_TEXT_QUEUE_SUBMIT_REPORT_ROOT:-/mnt/nas/openclaw/reports/models}"
run_dir_override="${DREAM7B_BPU_TEXT_QUEUE_SUBMIT_RUN_DIR:-}"
seq_len="${DREAM7B_BPU_TEXT_QUEUE_SEQ_LEN:-16}"
fit_mode="${DREAM7B_BPU_TEXT_QUEUE_FIT:-pad-right}"
request_id=""
job_stem=""
prompt_file=""
prompt_text=""

usage() {
  cat >&2 <<'USAGE'
usage: dream7b-bpu-text-queue-submit [--queue-dir DIR] [--report-root DIR] [--run-dir DIR] [--job-stem NAME] [--request-id ID] [--fit exact|truncate-left|pad-right] [--seq-len 16] [--prompt TEXT|--prompt-file FILE] [--] prompt text

Encodes a Dream 7B prompt on S100P and atomically submits one JSONL job into
the NAS-backed Dream 7B BPU queue. The command does not wait for the systemd
queue service; use dream7b-bpu-text-queue-systemd-probe for end-to-end service
acceptance.
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

case "$queue_dir" in
  /tmp/*|/mnt/nas/openclaw/queues|/mnt/nas/openclaw/queues/*|/root/.openclaw/workspace/queues|/root/.openclaw/workspace/queues/*) ;;
  *)
    echo "Refusing queue path outside approved queue directories: $queue_dir" >&2
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
if [[ -n "$job_stem" && ! "$job_stem" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "--job-stem may only contain A-Z, a-z, 0-9, dot, underscore, or hyphen." >&2
  exit 2
fi
if [[ -n "$request_id" && ! "$request_id" =~ ^[A-Za-z0-9._:-]+$ ]]; then
  echo "--request-id may only contain A-Z, a-z, 0-9, dot, underscore, hyphen, or colon." >&2
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
  job_stem="text_queue_submit_${stamp}"
fi
if [[ -z "$request_id" ]]; then
  request_id="${job_stem}-001"
fi
if [[ -n "$run_dir_override" ]]; then
  run_dir="$run_dir_override"
else
  run_dir="$report_root/dream7b_bpu_text_queue_submit_$stamp"
fi
mkdir -p "$run_dir"
job_name="${job_stem}.jsonl"
job_path="$run_dir/$job_name"
tokenizer_json="$run_dir/tokenizer_input.json"
summary_json="$run_dir/text_queue_submit.json"
summary_md="$run_dir/text_queue_submit.md"

"$tokenizer_venv/bin/python" - \
  "$tokenizer_dir" \
  "$seq_len" \
  "$fit_mode" \
  "$prompt_text" \
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

token_ids = [int(item) for item in ids]
Path(job_path).write_text(
    json.dumps({"request_id": request_id, "tokens": token_ids}, ensure_ascii=False) + "\n",
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
            "token_count": len(token_ids),
            "tokens": token_ids,
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

python3 - \
  "$run_dir" \
  "$summary_json" \
  "$summary_md" \
  "$queue_dir" \
  "$report_root" \
  "$job_name" \
  "$job_path" \
  "$queue_dir/pending/$job_name" \
  "$tokenizer_venv" \
  "$tokenizer_dir" \
  "$tokenizer_json" \
  "$request_id" \
  "$seq_len" \
  "$fit_mode" \
  "$prompt_file" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
summary_json = Path(sys.argv[2])
summary_md = Path(sys.argv[3])
queue_dir = sys.argv[4]
report_root = sys.argv[5]
job_name = sys.argv[6]
job_path = sys.argv[7]
queue_pending_path = sys.argv[8]
tokenizer_venv = sys.argv[9]
tokenizer_dir = sys.argv[10]
tokenizer_json = Path(sys.argv[11])
request_id = sys.argv[12]
seq_len = int(sys.argv[13])
fit_mode = sys.argv[14]
prompt_file = sys.argv[15]

errors = []
tokenizer_payload = None
if tokenizer_json.is_file():
    tokenizer_payload = json.loads(tokenizer_json.read_text(encoding="utf-8"))
else:
    errors.append(f"missing tokenizer JSON: {tokenizer_json}")

if isinstance(tokenizer_payload, dict):
    if tokenizer_payload.get("tokenizer_dir") != tokenizer_dir:
        errors.append(f"unexpected tokenizer_dir: {tokenizer_payload.get('tokenizer_dir')}")
    if tokenizer_payload.get("fit_mode") != fit_mode:
        errors.append(f"unexpected fit_mode: {tokenizer_payload.get('fit_mode')}")
    if tokenizer_payload.get("seq_len") != seq_len:
        errors.append(f"unexpected seq_len: {tokenizer_payload.get('seq_len')}")
    if tokenizer_payload.get("token_count") != seq_len:
        errors.append(f"unexpected token_count: {tokenizer_payload.get('token_count')}")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_text_queue_submit" if not errors else "failed_dream7b_bpu_text_queue_submit",
    "queue_dir": queue_dir,
    "report_root": report_root,
    "run_dir": str(run_dir),
    "job_name": job_name,
    "job_path": job_path,
    "queue_pending_path": queue_pending_path,
    "tokenizer_venv": tokenizer_venv,
    "tokenizer_dir": tokenizer_dir,
    "tokenizer_json": str(tokenizer_json),
    "tokenizer": tokenizer_payload,
    "request_id": request_id,
    "seq_len": seq_len,
    "fit_mode": fit_mode,
    "prompt_file": prompt_file or None,
    "errors": errors,
}
summary_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
error_lines = [f"- {item}" for item in errors] if errors else ["- none"]
summary_md.write_text(
    "\n".join([
        "# Dream 7B BPU Text Queue Submit",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- queue_dir: {payload['queue_dir']}",
        f"- report_root: {payload['report_root']}",
        f"- run_dir: {payload['run_dir']}",
        f"- job_name: {payload['job_name']}",
        f"- job_path: {payload['job_path']}",
        f"- queue_pending_path: {payload['queue_pending_path']}",
        f"- tokenizer_venv: {payload['tokenizer_venv']}",
        f"- tokenizer_dir: {payload['tokenizer_dir']}",
        f"- tokenizer_json: {payload['tokenizer_json']}",
        f"- request_id: {payload['request_id']}",
        f"- seq_len: {payload['seq_len']}",
        f"- fit_mode: {payload['fit_mode']}",
        "",
        "## Errors",
        "",
        *error_lines,
        "",
    ]) + "\n",
    encoding="utf-8",
)
print(summary_md)
if errors:
    raise SystemExit("; ".join(errors))
PY
