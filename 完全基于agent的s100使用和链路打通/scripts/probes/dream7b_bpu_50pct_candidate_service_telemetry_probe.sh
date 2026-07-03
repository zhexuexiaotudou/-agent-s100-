#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
queue_dir="${2:-/mnt/nas/openclaw/queues/dream7b-bpu-selected-pair-cross-job-candidate-50pct}"
service_output_dir="${3:-/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_candidate_50pct_service}"
service_name="${DREAM7B_BPU_50PCT_SERVICE_NAME:-dream7b-bpu-selected-pair-cross-job-candidate-50pct.service}"
job_count="${DREAM7B_BPU_50PCT_SERVICE_JOB_COUNT:-2}"
request_count="${DREAM7B_BPU_50PCT_SERVICE_REQUEST_COUNT:-192}"
timeout_sec="${DREAM7B_BPU_50PCT_SERVICE_TIMEOUT_SEC:-900}"
monitor_delay_ms="${DREAM7B_BPU_50PCT_SERVICE_MONITOR_DELAY_MS:-100}"
monitor_sample_count="${DREAM7B_BPU_50PCT_SERVICE_MONITOR_SAMPLE_COUNT:-9000}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing report path outside approved report directories: $report_root" >&2
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

case "$service_output_dir" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing service output path outside approved report directories: $service_output_dir" >&2
    exit 2
    ;;
esac

case "$service_name" in
  dream7b-bpu-selected-pair-cross-job-candidate-50pct.service) ;;
  *)
    echo "Refusing unexpected service name: $service_name" >&2
    exit 2
    ;;
esac

if ! [[ "$job_count" =~ ^[1-9][0-9]*$ ]] || (( job_count < 2 || job_count > 12 )); then
  echo "DREAM7B_BPU_50PCT_SERVICE_JOB_COUNT must be 2..12." >&2
  exit 2
fi
if ! [[ "$request_count" =~ ^[1-9][0-9]*$ ]] || (( request_count < 1 || request_count > 192 )); then
  echo "DREAM7B_BPU_50PCT_SERVICE_REQUEST_COUNT must be 1..192." >&2
  exit 2
fi
if ! [[ "$timeout_sec" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_50PCT_SERVICE_TIMEOUT_SEC must be a positive integer." >&2
  exit 2
fi
if ! command -v hrt_ucp_monitor >/dev/null 2>&1; then
  echo "Missing deployed command: hrt_ucp_monitor" >&2
  exit 4
fi
if ! systemctl is-active --quiet "$service_name"; then
  echo "Service is not active: $service_name" >&2
  exit 5
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_50pct_candidate_service_telemetry_$stamp"
jobs_dir="$run_dir/jobs"
mkdir -p "$run_dir" "$jobs_dir" "$queue_dir/pending" "$queue_dir/processing" "$queue_dir/done" "$queue_dir/failed"
started_epoch="$(date +%s)"

python3 - "$jobs_dir" "$stamp" "$job_count" "$request_count" <<'PY'
import json
import sys
from pathlib import Path

jobs_dir = Path(sys.argv[1])
stamp = sys.argv[2]
job_count = int(sys.argv[3])
request_count = int(sys.argv[4])
for job_index in range(job_count):
    rows = []
    for request_index in range(request_count):
        base = (job_index + 1) * 20000 + (request_index + 1) * 100
        rows.append(
            {
                "request_id": f"service-50pct-{stamp}-{job_index + 1:03d}-{request_index + 1:03d}",
                "tokens": [base + offset for offset in range(1, 17)],
            }
        )
    (jobs_dir / f"service_50pct_{stamp}_{job_index + 1:03d}.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
PY

monitor_stdout="$run_dir/hrt_ucp_monitor.stdout"
monitor_stderr="$run_dir/hrt_ucp_monitor.stderr"
service_status_before="$run_dir/service_status_before.txt"
service_status_after="$run_dir/service_status_after.txt"
systemctl --no-pager --full status "$service_name" > "$service_status_before" 2>&1 || true

hrt_ucp_monitor -b -e bpu -d "$monitor_delay_ms" -n "$monitor_sample_count" > "$monitor_stdout" 2> "$monitor_stderr" &
monitor_pid="$!"

cleanup_monitor() {
  if kill -0 "$monitor_pid" >/dev/null 2>&1; then
    kill "$monitor_pid" >/dev/null 2>&1 || true
    wait "$monitor_pid" >/dev/null 2>&1 || true
  fi
}
trap cleanup_monitor EXIT

for job_path in "$jobs_dir"/*.jsonl; do
  cp "$job_path" "$queue_dir/pending/$(basename "$job_path")"
done

deadline=$(( $(date +%s) + timeout_sec ))
while true; do
  done_count=0
  failed_count=0
  for job_path in "$jobs_dir"/*.jsonl; do
    name="$(basename "$job_path")"
    [[ -f "$queue_dir/done/$name" ]] && done_count=$((done_count + 1))
    [[ -f "$queue_dir/failed/$name" ]] && failed_count=$((failed_count + 1))
  done
  if (( done_count + failed_count >= job_count )); then
    break
  fi
  if (( $(date +%s) >= deadline )); then
    break
  fi
  sleep 1
done

cleanup_monitor
trap - EXIT
systemctl --no-pager --full status "$service_name" > "$service_status_after" 2>&1 || true

python3 - \
  "$run_dir" \
  "$queue_dir" \
  "$service_output_dir" \
  "$service_name" \
  "$stamp" \
  "$started_epoch" \
  "$job_count" \
  "$request_count" \
  "$timeout_sec" \
  "$monitor_delay_ms" \
  "$monitor_sample_count" <<'PY'
import glob
import json
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
queue_dir = Path(sys.argv[2])
service_output_dir = Path(sys.argv[3])
service_name = sys.argv[4]
stamp = sys.argv[5]
started_epoch = int(sys.argv[6])
job_count = int(sys.argv[7])
request_count = int(sys.argv[8])
timeout_sec = int(sys.argv[9])
monitor_delay_ms = int(sys.argv[10])
monitor_sample_count = int(sys.argv[11])

errors = []
warnings = []
done_jobs = sorted((queue_dir / "done").glob(f"service_50pct_{stamp}_*.jsonl"))
failed_jobs = sorted((queue_dir / "failed").glob(f"service_50pct_{stamp}_*.jsonl"))
if len(done_jobs) != job_count:
    errors.append(f"done job count mismatch: {len(done_jobs)} != {job_count}")
if failed_jobs:
    errors.append(f"failed job count is nonzero: {len(failed_jobs)}")

summary_candidates = []
for path in glob.glob(str(service_output_dir / "runs" / "*" / "cross_job_queue_summary.json")):
    item = Path(path)
    if item.stat().st_mtime >= started_epoch:
        summary_candidates.append(item)
summary_candidates.sort(key=lambda item: item.stat().st_mtime)
runner_summary_path = summary_candidates[-1] if summary_candidates else None
runner = {}
if runner_summary_path and runner_summary_path.is_file():
    runner = json.loads(runner_summary_path.read_text(encoding="utf-8"))
else:
    errors.append("missing service runner summary after canary start")

monitor_text = (run_dir / "hrt_ucp_monitor.stdout").read_text(encoding="utf-8", errors="replace")
bpu_loading_samples = [float(item) for item in re.findall(r"\|\s*BPU0\s+([0-9]+(?:[.][0-9]+)?)\s*\|", monitor_text)]
avg_bpu_loading = statistics.fmean(bpu_loading_samples) if bpu_loading_samples else 0.0
max_bpu_loading = max(bpu_loading_samples) if bpu_loading_samples else 0.0
nonzero_count = sum(1 for item in bpu_loading_samples if item > 0.0)
if not bpu_loading_samples:
    errors.append("hrt_ucp_monitor produced no BPU0 loading samples")
if nonzero_count <= 0:
    errors.append("hrt_ucp_monitor produced no nonzero BPU0 loading samples")

expected_processed = job_count * request_count
if runner:
    if runner.get("verdict") != "ok_dream7b_bpu_selected_pair_cross_job_queue_runner":
        errors.append(f"unexpected runner verdict: {runner.get('verdict')}")
    if int(runner.get("processed_job_count") or 0) != job_count:
        errors.append(f"unexpected processed_job_count: {runner.get('processed_job_count')}")
    if int(runner.get("processed_request_count") or 0) != expected_processed:
        errors.append(f"unexpected processed_request_count: {runner.get('processed_request_count')}")
    if int(runner.get("failed_job_count") or 0) != 0:
        errors.append(f"runner failed_job_count is nonzero: {runner.get('failed_job_count')}")
    if runner.get("selected_pair") != [1, 8]:
        errors.append(f"unexpected selected_pair: {runner.get('selected_pair')}")
    if runner.get("selected_pair_covers_all_segments") is not True:
        errors.append("selected_pair_covers_all_segments is not true")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_50pct_candidate_service_telemetry_probe" if not errors else "failed_dream7b_bpu_50pct_candidate_service_telemetry_probe",
    "run_dir": str(run_dir),
    "service_name": service_name,
    "queue_dir": str(queue_dir),
    "service_output_dir": str(service_output_dir),
    "runner_summary_json": str(runner_summary_path) if runner_summary_path else "",
    "job_count": job_count,
    "request_count": request_count,
    "processed_request_count": runner.get("processed_request_count"),
    "failed_job_count": runner.get("failed_job_count"),
    "done_job_count": len(done_jobs),
    "queue_failed_job_count": len(failed_jobs),
    "timeout_sec": timeout_sec,
    "monitor_delay_ms": monitor_delay_ms,
    "monitor_sample_count": monitor_sample_count,
    "bpu_loading_sample_count": len(bpu_loading_samples),
    "nonzero_bpu_loading_sample_count": nonzero_count,
    "avg_bpu_loading": round(avg_bpu_loading, 3),
    "max_bpu_loading": round(max_bpu_loading, 3),
    "load_to_run_ratio": runner.get("load_to_run_ratio"),
    "amortized_wall_ms_per_processed_request": runner.get("amortized_wall_ms_per_processed_request"),
    "amortized_total_load_ms_per_processed_request": runner.get("amortized_total_load_ms_per_processed_request"),
    "amortized_run_ms_per_processed_request": runner.get("amortized_run_ms_per_processed_request"),
    "selected_pair": runner.get("selected_pair"),
    "selected_segments": runner.get("selected_segments"),
    "selected_pair_covers_all_segments": runner.get("selected_pair_covers_all_segments"),
    "default_service_replaced": False,
    "rollback_command": "sudo systemctl disable --now dream7b-bpu-selected-pair-cross-job-candidate-50pct.service",
    "warnings": warnings,
    "errors": errors,
}
(run_dir / "50pct_candidate_service_telemetry_probe.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
lines = [
    "# Dream 7B 50 Percent Candidate Service Telemetry Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- service_name: {service_name}",
    f"- processed_request_count: {payload['processed_request_count']}",
    f"- failed_job_count: {payload['failed_job_count']}",
    f"- done_job_count: {payload['done_job_count']}",
    f"- avg_bpu_loading: {payload['avg_bpu_loading']}",
    f"- max_bpu_loading: {payload['max_bpu_loading']}",
    f"- load_to_run_ratio: {payload['load_to_run_ratio']}",
    f"- amortized_wall_ms_per_processed_request: {payload['amortized_wall_ms_per_processed_request']}",
    f"- runner_summary_json: {payload['runner_summary_json']}",
    f"- default_service_replaced: {payload['default_service_replaced']}",
    f"- rollback_command: `{payload['rollback_command']}`",
    "",
    "## Errors",
    "",
]
lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
lines.extend(["", "## Warnings", ""])
lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- none")
(run_dir / "50pct_candidate_service_telemetry_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "50pct_candidate_service_telemetry_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
