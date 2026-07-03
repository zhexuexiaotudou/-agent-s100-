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
run_dir="$report_root/dream7b_bpu_batch_queue_control_$stamp"
mkdir -p "$run_dir"
request_jsonl="$run_dir/requests.jsonl"
stdout="$run_dir.stdout"
stderr="$run_dir.stderr"

cat > "$request_jsonl" <<'JSONL'
{"request_id":"control-001","tokens":[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16]}
{"request_id":"control-cancelled","tokens":[16,15,14,13,12,11,10,9,8,7,6,5,4,3,2,1],"cancelled":true}
{"request_id":"control-expired","tokens":[101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116],"not_after_epoch_ms":1}
{"request_id":"control-002","tokens":[201,202,203,204,205,206,207,208,209,210,211,212,213,214,215,216]}
JSONL

dream7b-bpu-batch-queue-runner \
  "$request_jsonl" \
  "$run_dir" \
  --max-batch-size 4 \
  --top-k 3 \
  --drain-all > "$stdout" 2> "$stderr"

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
if data.get("request_count") != 4:
    errors.append(f"unexpected request_count: {data.get('request_count')}")
if data.get("runnable_count") != 2:
    errors.append(f"unexpected runnable_count: {data.get('runnable_count')}")
if data.get("processed_count") != 2:
    errors.append(f"unexpected processed_count: {data.get('processed_count')}")
if data.get("skipped_count") != 2:
    errors.append(f"unexpected skipped_count: {data.get('skipped_count')}")
if data.get("deferred_count") != 0:
    errors.append(f"unexpected deferred_count: {data.get('deferred_count')}")
skipped = {item.get("request_id"): item.get("reason") for item in data.get("skipped_requests", [])}
if skipped != {"control-cancelled": "cancelled", "control-expired": "expired"}:
    errors.append(f"unexpected skipped_requests: {data.get('skipped_requests')}")
durable_state = data.get("durable_state", {})
for key in ("accepted_requests_jsonl", "deferred_requests_jsonl", "skipped_requests_jsonl", "results_jsonl"):
    path = durable_state.get(key)
    if not path or not Path(path).is_file():
        errors.append(f"missing durable state file: {key}={path}")
results = data.get("results", [])
if [item.get("request_id") for item in results] != ["control-001", "control-002"]:
    errors.append(f"unexpected result request ids: {[item.get('request_id') for item in results]}")
for result in results:
    if result.get("final_shape") != [1, 16, 152064]:
        errors.append(f"unexpected final_shape for {result.get('request_id')}: {result.get('final_shape')}")

payload = {
    "verdict": "ok_dream7b_bpu_batch_queue_control_probe" if not errors else "failed_dream7b_bpu_batch_queue_control_probe",
    "summary": str(summary_path),
    "run_dir": str(run_dir),
    "errors": errors,
    "checked": {
        "request_count": data.get("request_count"),
        "runnable_count": data.get("runnable_count"),
        "processed_count": data.get("processed_count"),
        "skipped_count": data.get("skipped_count"),
        "deferred_count": data.get("deferred_count"),
        "skipped_requests": data.get("skipped_requests"),
        "durable_state": durable_state,
        "result_request_ids": [item.get("request_id") for item in results],
    },
}
(run_dir / "batch_queue_control_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(run_dir / "batch_queue_control_probe.md").write_text(
    "\n".join([
        "# Dream 7B BPU Batch Queue Control Probe",
        "",
        f"- verdict: {payload['verdict']}",
        f"- summary: {payload['summary']}",
        f"- request_count: {payload['checked']['request_count']}",
        f"- runnable_count: {payload['checked']['runnable_count']}",
        f"- processed_count: {payload['checked']['processed_count']}",
        f"- skipped_count: {payload['checked']['skipped_count']}",
        f"- deferred_count: {payload['checked']['deferred_count']}",
        f"- result_request_ids: {payload['checked']['result_request_ids']}",
        f"- skipped_requests: {payload['checked']['skipped_requests']}",
        "",
    ]) + "\n",
    encoding="utf-8",
)
print(run_dir / "batch_queue_control_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
