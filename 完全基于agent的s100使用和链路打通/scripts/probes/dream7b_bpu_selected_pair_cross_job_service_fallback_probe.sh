#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-${DREAM7B_BPU_CROSS_JOB_SERVICE_FALLBACK_REPORT_ROOT:-/mnt/nas/openclaw/reports/models}}"
queue_dir="${DREAM7B_BPU_CROSS_JOB_SERVICE_FALLBACK_QUEUE_DIR:-/mnt/nas/openclaw/queues/dream7b-bpu-selected-pair-cross-job-fallback-probe}"
service_cmd="${DREAM7B_BPU_CROSS_JOB_SERVICE_FALLBACK_SERVICE_CMD:-python3 scripts/dream7b_bpu_selected_pair_cross_job_queue_service.py}"
runner_cmd="${DREAM7B_BPU_CROSS_JOB_SERVICE_FALLBACK_RUNNER_CMD:-python3 scripts/dream7b_bpu_selected_pair_cross_job_queue_runner.py}"
forward_probe_cmd="${DREAM7B_BPU_CROSS_JOB_SERVICE_FALLBACK_FORWARD_PROBE_CMD:-bash scripts/probes/dream7b_bpu_selected_pair_forward_path_probe.sh}"
request_count="${DREAM7B_BPU_CROSS_JOB_SERVICE_FALLBACK_REQUEST_COUNT:-1}"
flush_timeout_sec="${DREAM7B_BPU_CROSS_JOB_SERVICE_FALLBACK_FLUSH_TIMEOUT_SEC:-0}"
timeout_sec="${DREAM7B_BPU_CROSS_JOB_SERVICE_FALLBACK_TIMEOUT_SEC:-3600}"
top_k="${DREAM7B_BPU_CROSS_JOB_SERVICE_FALLBACK_TOP_K:-3}"
bpu_lock_path="${DREAM7B_BPU_CROSS_JOB_SERVICE_FALLBACK_BPU_LOCK_PATH:-/tmp/dream7b_bpu_batch_queue_runner.lock}"

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

for value_name in request_count timeout_sec top_k; do
  value="${!value_name}"
  if ! [[ "$value" =~ ^[0-9]+$ ]]; then
    echo "$value_name must be an integer." >&2
    exit 2
  fi
done
if (( request_count < 1 || request_count > 16 )); then
  echo "request_count must be from 1 to 16." >&2
  exit 2
fi

stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_selected_pair_cross_job_service_fallback_$stamp"
service_output_dir="$run_dir/service"
mkdir -p "$run_dir" "$service_output_dir"
rm -rf "$queue_dir"
mkdir -p "$queue_dir/pending" "$queue_dir/processing" "$queue_dir/done" "$queue_dir/failed"

python3 - "$queue_dir/pending/single_job.jsonl" "$request_count" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
request_count = int(sys.argv[2])
rows = []
for index in range(request_count):
    rows.append(
        {
            "request_id": f"single-fallback-{index:04d}",
            "tokens": [151643] + [198 + ((index + step) % 50) for step in range(15)],
        }
    )
path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
PY

service_cmd_array=( $service_cmd )
set +e
"${service_cmd_array[@]}" \
  "$queue_dir" \
  "$service_output_dir" \
  --runner-cmd "$runner_cmd" \
  --forward-probe-cmd "$forward_probe_cmd" \
  --min-job-count 2 \
  --max-job-count 12 \
  --max-batch-size "$request_count" \
  --top-k "$top_k" \
  --timeout-sec "$timeout_sec" \
  --bpu-lock-path "$bpu_lock_path" \
  --poll-interval-sec 0 \
  --single-job-flush-timeout-sec "$flush_timeout_sec" \
  --once >"$run_dir/service.stdout" 2>"$run_dir/service.stderr"
service_rc=$?
set -e

python3 - "$run_dir" "$queue_dir" "$service_output_dir" "$service_rc" "$request_count" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
queue_dir = Path(sys.argv[2])
service_output_dir = Path(sys.argv[3])
service_rc = int(sys.argv[4])
request_count = int(sys.argv[5])
summary_path = service_output_dir / "cross_job_queue_service_summary.json"
summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.is_file() else {}
runs = summary.get("runs") or []
last_run = runs[-1] if runs else {}
runner_summary_path = Path(last_run.get("runner_summary_json") or "")
runner = json.loads(runner_summary_path.read_text(encoding="utf-8")) if runner_summary_path.is_file() else {}
done_count = len(list((queue_dir / "done").glob("*.jsonl"))) if (queue_dir / "done").is_dir() else 0
failed_count = len(list((queue_dir / "failed").glob("*.jsonl"))) if (queue_dir / "failed").is_dir() else 0
errors = []
if service_rc != 0:
    errors.append(f"service returned {service_rc}")
if summary.get("verdict") != "ok_dream7b_bpu_selected_pair_cross_job_queue_service":
    errors.append(f"unexpected service verdict: {summary.get('verdict')}")
if last_run.get("run_reason") != "single_job_flush_timeout":
    errors.append(f"unexpected run_reason: {last_run.get('run_reason')}")
if runner.get("processed_job_count") != 1:
    errors.append(f"unexpected processed_job_count: {runner.get('processed_job_count')}")
if runner.get("processed_request_count") != request_count:
    errors.append(f"unexpected processed_request_count: {runner.get('processed_request_count')}")
if runner.get("failed_job_count") != 0:
    errors.append(f"unexpected failed_job_count: {runner.get('failed_job_count')}")
if done_count != 1 or failed_count != 0:
    errors.append(f"unexpected queue done/failed counts: {done_count}/{failed_count}")
payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_selected_pair_cross_job_service_fallback_probe" if not errors else "failed_dream7b_bpu_selected_pair_cross_job_service_fallback_probe",
    "run_dir": str(run_dir),
    "queue_dir": str(queue_dir),
    "service_output_dir": str(service_output_dir),
    "service_returncode": service_rc,
    "service_summary_json": str(summary_path) if summary_path.is_file() else "",
    "runner_summary_json": str(runner_summary_path) if runner_summary_path.is_file() else "",
    "single_job_fallback_ok": not errors,
    "run_reason": last_run.get("run_reason"),
    "processed_job_count": runner.get("processed_job_count"),
    "processed_request_count": runner.get("processed_request_count"),
    "failed_job_count": runner.get("failed_job_count"),
    "load_to_run_ratio": runner.get("load_to_run_ratio"),
    "amortized_wall_ms_per_processed_request": runner.get("amortized_wall_ms_per_processed_request"),
    "queue_done_count": done_count,
    "queue_failed_count": failed_count,
    "errors": errors,
}
(run_dir / "cross_job_service_fallback_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
lines = [
    "# Dream 7B Cross-Job Service Single-Job Fallback Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- single_job_fallback_ok: {payload['single_job_fallback_ok']}",
    f"- run_reason: {payload['run_reason']}",
    f"- processed_request_count: {payload['processed_request_count']}",
    f"- failed_job_count: {payload['failed_job_count']}",
    f"- load_to_run_ratio: {payload['load_to_run_ratio']}",
    f"- amortized_wall_ms_per_processed_request: {payload['amortized_wall_ms_per_processed_request']}",
    "",
    "## Errors",
    "",
]
lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
(run_dir / "cross_job_service_fallback_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "cross_job_service_fallback_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
