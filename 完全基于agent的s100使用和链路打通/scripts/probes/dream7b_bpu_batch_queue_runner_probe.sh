#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

if ! command -v dream7b-bpu-batch-queue-runner >/dev/null 2>&1; then
  echo "Missing deployed command: dream7b-bpu-batch-queue-runner" >&2
  exit 4
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_batch_queue_runner_$stamp"
mkdir -p "$run_dir"
request_jsonl="$run_dir/requests.jsonl"
stdout="$run_dir.stdout"
stderr="$run_dir.stderr"

cat > "$request_jsonl" <<'JSONL'
{"request_id":"req-001","tokens":[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16]}
{"request_id":"req-002","tokens":[16,15,14,13,12,11,10,9,8,7,6,5,4,3,2,1]}
{"request_id":"req-003","tokens":[101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116]}
{"request_id":"req-004","tokens":[201,202,203,204,205,206,207,208,209,210,211,212,213,214,215,216]}
JSONL

dream7b-bpu-batch-queue-runner \
  "$request_jsonl" \
  "$run_dir" \
  --max-batch-size 3 \
  --top-k 3 > "$stdout" 2> "$stderr"

python3 - "$run_dir/queue_summary.json" "$run_dir" <<'PY'
import json
import sys
from pathlib import Path

summary_path = Path(sys.argv[1])
run_dir = Path(sys.argv[2])
data = json.loads(summary_path.read_text(encoding="utf-8"))
errors = []
if data.get("verdict") != "ok_dream7b_bpu_batch_queue_runner":
    errors.append(f"unexpected verdict: {data.get('verdict')}")
if data.get("accepted_count") != 3:
    errors.append(f"unexpected accepted_count: {data.get('accepted_count')}")
if data.get("deferred_count") != 1:
    errors.append(f"unexpected deferred_count: {data.get('deferred_count')}")
if data.get("deferred_request_ids") != ["req-004"]:
    errors.append(f"unexpected deferred_request_ids: {data.get('deferred_request_ids')}")
if data.get("batch_run_count") != 1:
    errors.append(f"unexpected batch_run_count: {data.get('batch_run_count')}")
batch_runs = data.get("batch_runs", [])
first_metrics = batch_runs[0].get("metrics", {}) if batch_runs else {}
if first_metrics.get("execution_mode") != "pair_window_batch":
    errors.append(f"unexpected execution_mode: {first_metrics.get('execution_mode')}")
if first_metrics.get("window_execution_mode") != "window-batch":
    errors.append(f"unexpected window_execution_mode: {first_metrics.get('window_execution_mode')}")
if first_metrics.get("child_process_count") != 0:
    errors.append(f"unexpected child_process_count: {first_metrics.get('child_process_count')}")
if first_metrics.get("batch_count") != 3:
    errors.append(f"unexpected batch_count: {first_metrics.get('batch_count')}")
metrics = data.get("forward_metrics", {})
for metric in ("total_wall_ms", "total_load_ms", "total_run_ms", "amortized_wall_ms_per_processed_request"):
    value = metrics.get(metric)
    if not isinstance(value, (int, float)) or value <= 0:
        errors.append(f"unexpected {metric}: {value}")
results = data.get("results", [])
if len(results) != 3:
    errors.append(f"unexpected result count: {len(results)}")
for index, result in enumerate(results):
    if result.get("batch_index") != index:
        errors.append(f"unexpected batch_index for result {index}: {result.get('batch_index')}")
    if result.get("final_shape") != [1, 16, 152064]:
        errors.append(f"unexpected final_shape for result {index}: {result.get('final_shape')}")

payload = {
    "verdict": "ok_dream7b_bpu_batch_queue_runner_probe" if not errors else "failed_dream7b_bpu_batch_queue_runner_probe",
    "summary": str(summary_path),
    "run_dir": str(run_dir),
    "errors": errors,
    "checked": {
        "accepted_count": data.get("accepted_count"),
        "deferred_count": data.get("deferred_count"),
        "deferred_request_ids": data.get("deferred_request_ids"),
        "batch_run_count": data.get("batch_run_count"),
        "execution_mode": first_metrics.get("execution_mode"),
        "window_execution_mode": first_metrics.get("window_execution_mode"),
        "child_process_count": first_metrics.get("child_process_count"),
        "batch_count": first_metrics.get("batch_count"),
        "total_wall_ms": metrics.get("total_wall_ms"),
        "amortized_wall_ms_per_processed_request": metrics.get("amortized_wall_ms_per_processed_request"),
        "result_count": len(results),
    },
}
(run_dir / "batch_queue_runner_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(run_dir / "batch_queue_runner_probe.md").write_text(
    "\n".join([
        "# Dream 7B BPU Batch Queue Runner Probe",
        "",
        f"- verdict: {payload['verdict']}",
        f"- summary: {payload['summary']}",
        f"- accepted_count: {payload['checked']['accepted_count']}",
        f"- deferred_count: {payload['checked']['deferred_count']}",
        f"- deferred_request_ids: {payload['checked']['deferred_request_ids']}",
        f"- batch_run_count: {payload['checked']['batch_run_count']}",
        f"- execution_mode: {payload['checked']['execution_mode']}",
        f"- window_execution_mode: {payload['checked']['window_execution_mode']}",
        f"- child_process_count: {payload['checked']['child_process_count']}",
        f"- batch_count: {payload['checked']['batch_count']}",
        f"- total_wall_ms: {payload['checked']['total_wall_ms']}",
        f"- amortized_wall_ms_per_processed_request: {payload['checked']['amortized_wall_ms_per_processed_request']}",
        f"- result_count: {payload['checked']['result_count']}",
        "",
    ]) + "\n",
    encoding="utf-8",
)
print(run_dir / "batch_queue_runner_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
