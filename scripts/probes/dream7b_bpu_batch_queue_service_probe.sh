#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/tmp/dream7b_bpu_batch_queue_service_probe}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

service_script="${DREAM7B_BPU_BATCH_QUEUE_SERVICE_SCRIPT:-/mnt/nas/openclaw/runtimes/dream7b-bpu-forward/dream7b_bpu_batch_queue_service.py}"
runner_script="${DREAM7B_BPU_BATCH_QUEUE_RUNNER_SCRIPT:-/mnt/nas/openclaw/runtimes/dream7b-bpu-forward/dream7b_bpu_batch_queue_runner.py}"
if [[ ! -f "$service_script" && -f scripts/dream7b_bpu_batch_queue_service.py ]]; then
  service_script="scripts/dream7b_bpu_batch_queue_service.py"
fi
if [[ ! -f "$runner_script" && -f scripts/dream7b_bpu_batch_queue_runner.py ]]; then
  runner_script="scripts/dream7b_bpu_batch_queue_runner.py"
fi
if [[ ! -f "$service_script" ]]; then
  echo "Missing service script: $service_script" >&2
  exit 4
fi
if [[ ! -f "$runner_script" ]]; then
  echo "Missing runner script: $runner_script" >&2
  exit 4
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_batch_queue_service_$stamp"
queue_dir="$run_dir/queue"
output_dir="$run_dir/output"
mkdir -p "$queue_dir/pending" "$output_dir"
fake_forward="$run_dir/fake_forward.py"
runner_wrapper="$run_dir/runner_wrapper.sh"
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

sleep_sec = float(os.environ.get("DREAM7B_FAKE_FORWARD_SLEEP_SEC", "0.1"))
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

cat > "$runner_wrapper" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec python3 "$runner_script" "\$@"
EOF
chmod +x "$runner_wrapper"

cat > "$queue_dir/pending/job_001.jsonl" <<'JSONL'
{"request_id":"service-001","tokens":[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16]}
{"request_id":"service-002","tokens":[16,15,14,13,12,11,10,9,8,7,6,5,4,3,2,1]}
JSONL

python3 "$service_script" \
  "$queue_dir" \
  "$output_dir" \
  --runner-cmd "$runner_wrapper" \
  --max-batch-size 2 \
  --top-k 1 \
  --forward-cmd "$fake_forward" \
  --bpu-lock-path "$lock_path" \
  --bpu-lock-timeout-sec 30 \
  --once > "$run_dir/service.stdout" 2> "$run_dir/service.stderr"

python3 - "$run_dir" <<'PY'
import json
import sys
from pathlib import Path

run_dir = Path(sys.argv[1])
output_dir = run_dir / "output"
queue_dir = run_dir / "queue"
data = json.loads((output_dir / "service_summary.json").read_text(encoding="utf-8"))
errors = []
if data.get("verdict") != "ok_dream7b_bpu_batch_queue_service":
    errors.append(f"unexpected service verdict: {data.get('verdict')}")
if data.get("processed_job_count") != 1:
    errors.append(f"unexpected processed_job_count: {data.get('processed_job_count')}")
if data.get("failed_job_count") != 0:
    errors.append(f"unexpected failed_job_count: {data.get('failed_job_count')}")
jobs = data.get("jobs", [])
if len(jobs) != 1:
    errors.append(f"unexpected job count: {len(jobs)}")
else:
    job = jobs[0]
    if job.get("runner_verdict") != "ok_dream7b_bpu_batch_queue_runner":
        errors.append(f"unexpected runner_verdict: {job.get('runner_verdict')}")
    if job.get("processed_count") != 2:
        errors.append(f"unexpected processed_count: {job.get('processed_count')}")
    lock = job.get("bpu_lock") or {}
    if lock.get("acquired") is not True:
        errors.append(f"unexpected bpu_lock: {lock}")
done_files = sorted(path.name for path in (queue_dir / "done").glob("*.jsonl"))
failed_files = sorted(path.name for path in (queue_dir / "failed").glob("*.jsonl"))
if done_files != ["job_001.jsonl"]:
    errors.append(f"unexpected done files: {done_files}")
if failed_files:
    errors.append(f"unexpected failed files: {failed_files}")

payload = {
    "verdict": "ok_dream7b_bpu_batch_queue_service_probe" if not errors else "failed_dream7b_bpu_batch_queue_service_probe",
    "run_dir": str(run_dir),
    "summary": str(output_dir / "service_summary.json"),
    "errors": errors,
    "checked": {
        "processed_job_count": data.get("processed_job_count"),
        "failed_job_count": data.get("failed_job_count"),
        "done_files": done_files,
        "failed_files": failed_files,
        "job_runner_verdict": jobs[0].get("runner_verdict") if jobs else None,
        "job_processed_count": jobs[0].get("processed_count") if jobs else None,
        "job_bpu_lock": jobs[0].get("bpu_lock") if jobs else None,
    },
}
(run_dir / "batch_queue_service_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(run_dir / "batch_queue_service_probe.md").write_text(
    "\n".join([
        "# Dream 7B BPU Batch Queue Service Probe",
        "",
        f"- verdict: {payload['verdict']}",
        f"- summary: {payload['summary']}",
        f"- processed_job_count: {payload['checked']['processed_job_count']}",
        f"- failed_job_count: {payload['checked']['failed_job_count']}",
        f"- done_files: {payload['checked']['done_files']}",
        f"- failed_files: {payload['checked']['failed_files']}",
        f"- job_runner_verdict: {payload['checked']['job_runner_verdict']}",
        f"- job_processed_count: {payload['checked']['job_processed_count']}",
        f"- job_bpu_lock: {payload['checked']['job_bpu_lock']}",
        "",
    ]) + "\n",
    encoding="utf-8",
)
print(run_dir / "batch_queue_service_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
