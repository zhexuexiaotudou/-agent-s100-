#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/tmp/dream7b_bpu_batch_queue_lock_probe}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

runner_script="${DREAM7B_BPU_BATCH_QUEUE_RUNNER_SCRIPT:-/mnt/nas/openclaw/runtimes/dream7b-bpu-forward/dream7b_bpu_batch_queue_runner.py}"
if [[ ! -f "$runner_script" && -f scripts/dream7b_bpu_batch_queue_runner.py ]]; then
  runner_script="scripts/dream7b_bpu_batch_queue_runner.py"
fi
if [[ ! -f "$runner_script" ]]; then
  echo "Missing runner script: $runner_script" >&2
  exit 4
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_batch_queue_lock_$stamp"
mkdir -p "$run_dir"
fake_forward="$run_dir/fake_forward.py"
lock_path="$run_dir/dream7b_bpu_batch_queue_runner.lock"

cat > "$fake_forward" <<'PY'
#!/usr/bin/env python3
import argparse
import json
import os
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--tokens-batch-json", required=True)
parser.add_argument("--top-k", required=True)
parser.add_argument("--output-dir", required=True)
args = parser.parse_args()

sleep_sec = float(os.environ.get("DREAM7B_FAKE_FORWARD_SLEEP_SEC", "2.0"))
tokens = json.loads(Path(args.tokens_batch_json).read_text(encoding="utf-8"))
time.sleep(sleep_sec)
output_dir = Path(args.output_dir)
output_dir.mkdir(parents=True, exist_ok=True)
batch_count = len(tokens)
payload = {
    "verdict": "ok_dream7b_segmented_hbm_python_forward",
    "execution_mode": "pair_window_batch",
    "window_execution_mode": "window-batch",
    "child_process_count": 0,
    "batch_count": batch_count,
    "wall_ms": round(sleep_sec * 1000, 3),
    "load_ms": 0.0,
    "run_ms": round(sleep_sec * 1000, 3),
    "amortized_wall_ms_per_forward": round(sleep_sec * 1000 / batch_count, 3) if batch_count else 0.0,
    "amortized_load_ms_per_forward": 0.0,
    "final_shapes": [[1, 16, 152064] for _ in tokens],
    "topk_last_position_by_batch": [
        {"batch_index": index, "topk_last_position": []}
        for index in range(batch_count)
    ],
}
(output_dir / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
chmod +x "$fake_forward"

cat > "$run_dir/requests_a.jsonl" <<'JSONL'
{"request_id":"lock-a","tokens":[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16]}
JSONL

cat > "$run_dir/requests_b.jsonl" <<'JSONL'
{"request_id":"lock-b","tokens":[16,15,14,13,12,11,10,9,8,7,6,5,4,3,2,1]}
JSONL

DREAM7B_FAKE_FORWARD_SLEEP_SEC=2.0 python3 "$runner_script" \
  "$run_dir/requests_a.jsonl" \
  "$run_dir/run_a" \
  --max-batch-size 1 \
  --top-k 1 \
  --forward-cmd "$fake_forward" \
  --bpu-lock-path "$lock_path" \
  --bpu-lock-timeout-sec 30 > "$run_dir/run_a.stdout" 2> "$run_dir/run_a.stderr" &
pid_a=$!

sleep 0.2

DREAM7B_FAKE_FORWARD_SLEEP_SEC=2.0 python3 "$runner_script" \
  "$run_dir/requests_b.jsonl" \
  "$run_dir/run_b" \
  --max-batch-size 1 \
  --top-k 1 \
  --forward-cmd "$fake_forward" \
  --bpu-lock-path "$lock_path" \
  --bpu-lock-timeout-sec 30 > "$run_dir/run_b.stdout" 2> "$run_dir/run_b.stderr" &
pid_b=$!

wait "$pid_a"
wait "$pid_b"

python3 - "$run_dir" <<'PY'
import json
import sys
from pathlib import Path

run_dir = Path(sys.argv[1])
summary_a = json.loads((run_dir / "run_a" / "queue_summary.json").read_text(encoding="utf-8"))
summary_b = json.loads((run_dir / "run_b" / "queue_summary.json").read_text(encoding="utf-8"))
errors = []

for label, summary in (("run_a", summary_a), ("run_b", summary_b)):
    if summary.get("verdict") != "ok_dream7b_bpu_batch_queue_runner":
        errors.append(f"{label} unexpected verdict: {summary.get('verdict')}")
    lock = summary.get("bpu_lock", {})
    if lock.get("acquired") is not True:
        errors.append(f"{label} did not acquire bpu_lock: {lock}")
    if summary.get("processed_count") != 1:
        errors.append(f"{label} unexpected processed_count: {summary.get('processed_count')}")
    results = summary.get("results", [])
    if len(results) != 1 or results[0].get("final_shape") != [1, 16, 152064]:
        errors.append(f"{label} unexpected results: {results}")

wait_a = summary_a.get("bpu_lock", {}).get("wait_ms")
wait_b = summary_b.get("bpu_lock", {}).get("wait_ms")
if wait_b is None or wait_b < 1000:
    errors.append(f"run_b did not wait for single-flight lock long enough: wait_ms={wait_b}")

payload = {
    "verdict": "ok_dream7b_bpu_batch_queue_lock_probe" if not errors else "failed_dream7b_bpu_batch_queue_lock_probe",
    "run_dir": str(run_dir),
    "errors": errors,
    "checked": {
        "run_a_summary": str(run_dir / "run_a" / "queue_summary.json"),
        "run_b_summary": str(run_dir / "run_b" / "queue_summary.json"),
        "run_a_bpu_lock_wait_ms": wait_a,
        "run_b_bpu_lock_wait_ms": wait_b,
        "lock_path": summary_a.get("bpu_lock", {}).get("path"),
    },
}
(run_dir / "batch_queue_lock_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(run_dir / "batch_queue_lock_probe.md").write_text(
    "\n".join([
        "# Dream 7B BPU Batch Queue Lock Probe",
        "",
        f"- verdict: {payload['verdict']}",
        f"- run_a_summary: {payload['checked']['run_a_summary']}",
        f"- run_b_summary: {payload['checked']['run_b_summary']}",
        f"- run_a_bpu_lock_wait_ms: {payload['checked']['run_a_bpu_lock_wait_ms']}",
        f"- run_b_bpu_lock_wait_ms: {payload['checked']['run_b_bpu_lock_wait_ms']}",
        f"- lock_path: {payload['checked']['lock_path']}",
        "",
    ]) + "\n",
    encoding="utf-8",
)
print(run_dir / "batch_queue_lock_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
