#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-${DREAM7B_BPU_CROSS_JOB_DEFAULT_TELEMETRY_REPORT_ROOT:-/mnt/nas/openclaw/reports/models}}"
service_name="${DREAM7B_BPU_CROSS_JOB_DEFAULT_TELEMETRY_SERVICE_NAME:-dream7b-bpu-batch-queue.service}"
queue_dir="${DREAM7B_BPU_CROSS_JOB_DEFAULT_TELEMETRY_QUEUE_DIR:-/mnt/nas/openclaw/queues/dream7b-bpu}"
service_output_dir="${DREAM7B_BPU_CROSS_JOB_DEFAULT_TELEMETRY_SERVICE_OUTPUT_DIR:-/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd}"
job_count="${DREAM7B_BPU_CROSS_JOB_DEFAULT_TELEMETRY_JOB_COUNT:-12}"
request_count="${DREAM7B_BPU_CROSS_JOB_DEFAULT_TELEMETRY_REQUEST_COUNT:-16}"
timeout_sec="${DREAM7B_BPU_CROSS_JOB_DEFAULT_TELEMETRY_TIMEOUT_SEC:-1200}"
monitor_delay_ms="${DREAM7B_BPU_CROSS_JOB_DEFAULT_TELEMETRY_MONITOR_DELAY_MS:-100}"
monitor_sample_count="${DREAM7B_BPU_CROSS_JOB_DEFAULT_TELEMETRY_MONITOR_SAMPLE_COUNT:-5000}"

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
case "$service_output_dir" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing service output path outside approved report directories: $service_output_dir" >&2
    exit 2
    ;;
esac
for value_name in job_count request_count timeout_sec monitor_delay_ms monitor_sample_count; do
  value="${!value_name}"
  if ! [[ "$value" =~ ^[1-9][0-9]*$ ]]; then
    echo "$value_name must be a positive integer." >&2
    exit 2
  fi
done
if (( job_count < 2 || job_count > 12 )); then
  echo "job_count must be from 2 to 12." >&2
  exit 2
fi
if (( request_count < 1 || request_count > 16 )); then
  echo "request_count must be from 1 to 16." >&2
  exit 2
fi
if ! command -v hrt_ucp_monitor >/dev/null 2>&1; then
  echo "Missing deployed command: hrt_ucp_monitor" >&2
  exit 4
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_cross_job_default_service_telemetry_$stamp"
jobs_dir="$run_dir/jobs"
mkdir -p "$run_dir" "$jobs_dir" "$queue_dir/pending" "$queue_dir/processing" "$queue_dir/done" "$queue_dir/failed"

if [[ "$(systemctl is-active "$service_name" 2>/dev/null || true)" != "active" ]]; then
  echo "$service_name is not active" >&2
  exit 4
fi
default_exec_start="$(systemctl show "$service_name" -p ExecStart --value)"
if [[ "$default_exec_start" != *"dream7b_bpu_selected_pair_cross_job_queue_service.py"* ]]; then
  echo "$service_name is not promoted to cross-job service" >&2
  exit 4
fi

pending_count="$(find "$queue_dir/pending" -maxdepth 1 -type f -name '*.jsonl' | wc -l)"
if [[ "$pending_count" != "0" ]]; then
  echo "Refusing telemetry while default queue has pending jobs: $pending_count" >&2
  exit 3
fi

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
        base = (job_index + 1) * 10000 + (request_index + 1) * 100
        rows.append(
            {
                "request_id": f"default-cross-job-telemetry-{stamp}-{job_index + 1:03d}-{request_index + 1:03d}",
                "tokens": [base + offset for offset in range(1, 17)],
            }
        )
    (jobs_dir / f"default_cross_job_telemetry_{stamp}_{job_index + 1:03d}.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
PY

monitor_stdout="$run_dir/hrt_ucp_monitor.stdout"
monitor_stderr="$run_dir/hrt_ucp_monitor.stderr"
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

python3 - "$queue_dir" "$service_output_dir" "$stamp" "$job_count" "$timeout_sec" <<'PY'
import sys
import time
from pathlib import Path

queue_dir = Path(sys.argv[1])
service_output_dir = Path(sys.argv[2])
stamp = sys.argv[3]
job_count = int(sys.argv[4])
timeout_sec = int(sys.argv[5])
started = time.monotonic()
names = [f"default_cross_job_telemetry_{stamp}_{index + 1:03d}.jsonl" for index in range(job_count)]
while True:
    done = sum((queue_dir / "done" / name).is_file() for name in names)
    failed = sum((queue_dir / "failed" / name).is_file() for name in names)
    if done + failed >= job_count:
        break
    if time.monotonic() - started >= timeout_sec:
        raise SystemExit(f"timed out waiting for default service telemetry jobs: done={done} failed={failed}")
    time.sleep(1)
PY

cleanup_monitor
trap - EXIT

python3 - "$run_dir" "$queue_dir" "$service_output_dir" "$stamp" "$service_name" "$job_count" "$request_count" "$monitor_delay_ms" "$monitor_sample_count" "$default_exec_start" <<'PY'
import json
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
queue_dir = Path(sys.argv[2])
service_output_dir = Path(sys.argv[3])
stamp = sys.argv[4]
service_name = sys.argv[5]
job_count = int(sys.argv[6])
request_count = int(sys.argv[7])
monitor_delay_ms = int(sys.argv[8])
monitor_sample_count = int(sys.argv[9])
default_exec_start = sys.argv[10]
errors = []
warnings = []
job_names = [f"default_cross_job_telemetry_{stamp}_{index + 1:03d}.jsonl" for index in range(job_count)]
done_count = sum((queue_dir / "done" / name).is_file() for name in job_names)
failed_count = sum((queue_dir / "failed" / name).is_file() for name in job_names)
summary_paths = sorted(
    service_output_dir.glob("runs/*/cross_job_queue_summary.json"),
    key=lambda item: item.stat().st_mtime,
)
runner = {}
summary_path = None
for path in reversed(summary_paths):
    data = json.loads(path.read_text(encoding="utf-8"))
    if int(data.get("processed_job_count") or 0) == job_count and int(data.get("processed_request_count") or 0) == job_count * request_count:
        summary_path = path
        runner = data
        break
if summary_path is None:
    errors.append("could not locate matching default service cross-job summary")
monitor_text = (run_dir / "hrt_ucp_monitor.stdout").read_text(encoding="utf-8", errors="replace")
monitor_err = (run_dir / "hrt_ucp_monitor.stderr").read_text(encoding="utf-8", errors="replace")
bpu_loading_samples = [float(item) for item in re.findall(r"\|\s*BPU0\s+([0-9]+(?:[.][0-9]+)?)\s*\|", monitor_text)]
max_bpu_loading = max(bpu_loading_samples) if bpu_loading_samples else 0.0
avg_bpu_loading = statistics.fmean(bpu_loading_samples) if bpu_loading_samples else 0.0
nonzero_bpu_loading_sample_count = sum(1 for item in bpu_loading_samples if item > 0.0)
if done_count != job_count or failed_count != 0:
    errors.append(f"unexpected done/failed job counts: {done_count}/{failed_count}")
if runner.get("verdict") != "ok_dream7b_bpu_selected_pair_cross_job_queue_runner":
    errors.append(f"unexpected runner verdict: {runner.get('verdict')}")
if int(runner.get("failed_job_count") or 0) != 0:
    errors.append(f"unexpected failed_job_count: {runner.get('failed_job_count')}")
if not bpu_loading_samples:
    errors.append("hrt_ucp_monitor produced no BPU0 loading samples")
if nonzero_bpu_loading_sample_count <= 0:
    errors.append("hrt_ucp_monitor produced no nonzero BPU0 loading samples")
payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_cross_job_default_service_telemetry_probe" if not errors else "failed_dream7b_bpu_cross_job_default_service_telemetry_probe",
    "run_dir": str(run_dir),
    "service_name": service_name,
    "queue_dir": str(queue_dir),
    "service_output_dir": str(service_output_dir),
    "default_exec_start": default_exec_start,
    "runner_summary_json": str(summary_path) if summary_path else "",
    "job_count": job_count,
    "request_count": request_count,
    "processed_job_count": runner.get("processed_job_count"),
    "processed_request_count": runner.get("processed_request_count"),
    "failed_job_count": runner.get("failed_job_count"),
    "queue_done_count": done_count,
    "queue_failed_count": failed_count,
    "bpu_loading_sample_count": len(bpu_loading_samples),
    "nonzero_bpu_loading_sample_count": nonzero_bpu_loading_sample_count,
    "max_bpu_loading": round(max_bpu_loading, 3),
    "avg_bpu_loading": round(avg_bpu_loading, 3),
    "load_to_run_ratio": runner.get("load_to_run_ratio"),
    "amortized_wall_ms_per_processed_request": runner.get("amortized_wall_ms_per_processed_request"),
    "amortized_total_load_ms_per_processed_request": runner.get("amortized_total_load_ms_per_processed_request"),
    "amortized_run_ms_per_processed_request": runner.get("amortized_run_ms_per_processed_request"),
    "selected_pair": runner.get("selected_pair"),
    "selected_segments": runner.get("selected_segments"),
    "selected_pair_covers_all_segments": runner.get("selected_pair_covers_all_segments"),
    "monitor_stdout": str(run_dir / "hrt_ucp_monitor.stdout"),
    "monitor_stderr": str(run_dir / "hrt_ucp_monitor.stderr"),
    "monitor_stderr_excerpt": monitor_err[:500],
    "warnings": warnings,
    "errors": errors,
}
(run_dir / "default_service_telemetry_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
lines = [
    "# Dream 7B Cross-Job Default Service Telemetry Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- processed_request_count: {payload['processed_request_count']}",
    f"- failed_job_count: {payload['failed_job_count']}",
    f"- load_to_run_ratio: {payload['load_to_run_ratio']}",
    f"- amortized_wall_ms_per_processed_request: {payload['amortized_wall_ms_per_processed_request']}",
    f"- avg_bpu_loading: {payload['avg_bpu_loading']}",
    f"- max_bpu_loading: {payload['max_bpu_loading']}",
    "",
    "## Errors",
    "",
]
lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
(run_dir / "default_service_telemetry_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "default_service_telemetry_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
