#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
service_name="${2:-dream7b-bpu-batch-queue.service}"
queue_dir="${3:-/mnt/nas/openclaw/queues/dream7b-bpu}"
output_dir="${4:-/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd}"
job_count="${DREAM7B_BPU_SYSTEMD_TELEMETRY_JOB_COUNT:-3}"
request_count="${DREAM7B_BPU_SYSTEMD_TELEMETRY_REQUEST_COUNT:-16}"
timeout_sec="${DREAM7B_BPU_SYSTEMD_TELEMETRY_TIMEOUT_SEC:-900}"
poll_interval_sec="${DREAM7B_BPU_SYSTEMD_TELEMETRY_POLL_INTERVAL_SEC:-2}"
monitor_delay_ms="${DREAM7B_BPU_SYSTEMD_TELEMETRY_MONITOR_DELAY_MS:-100}"
monitor_sample_count="${DREAM7B_BPU_SYSTEMD_TELEMETRY_MONITOR_SAMPLE_COUNT:-1200}"

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

if ! [[ "$job_count" =~ ^[0-9]+$ ]] || (( job_count < 1 || job_count > 8 )); then
  echo "DREAM7B_BPU_SYSTEMD_TELEMETRY_JOB_COUNT must be an integer from 1 to 8." >&2
  exit 2
fi
if ! [[ "$request_count" =~ ^[0-9]+$ ]] || (( request_count < 1 || request_count > 16 )); then
  echo "DREAM7B_BPU_SYSTEMD_TELEMETRY_REQUEST_COUNT must be an integer from 1 to 16." >&2
  exit 2
fi
if ! [[ "$timeout_sec" =~ ^[0-9]+$ ]] || (( timeout_sec < 1 )); then
  echo "DREAM7B_BPU_SYSTEMD_TELEMETRY_TIMEOUT_SEC must be a positive integer." >&2
  exit 2
fi
if ! [[ "$poll_interval_sec" =~ ^[0-9]+$ ]] || (( poll_interval_sec < 1 )); then
  echo "DREAM7B_BPU_SYSTEMD_TELEMETRY_POLL_INTERVAL_SEC must be a positive integer." >&2
  exit 2
fi
if ! [[ "$monitor_delay_ms" =~ ^[0-9]+$ ]] || (( monitor_delay_ms < 100 || monitor_delay_ms > 10000 )); then
  echo "DREAM7B_BPU_SYSTEMD_TELEMETRY_MONITOR_DELAY_MS must be an integer from 100 to 10000." >&2
  exit 2
fi
if ! [[ "$monitor_sample_count" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_SYSTEMD_TELEMETRY_MONITOR_SAMPLE_COUNT must be a positive integer." >&2
  exit 2
fi

if ! command -v hrt_ucp_monitor >/dev/null 2>&1; then
  echo "Missing deployed command: hrt_ucp_monitor" >&2
  exit 4
fi

if (( EUID == 0 )); then
  sudo_cmd=()
else
  sudo_cmd=(sudo -n)
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_batch_queue_systemd_telemetry_$stamp"
mkdir -p "$run_dir/jobs"
monitor_stdout="$run_dir/hrt_ucp_monitor.stdout"
monitor_stderr="$run_dir/hrt_ucp_monitor.stderr"
somstatus_before="$run_dir/hrut_somstatus_before.txt"
somstatus_after="$run_dir/hrut_somstatus_after.txt"

service_status_before="$(systemctl is-active "$service_name" 2>/dev/null || true)"
service_enabled_before="$(systemctl is-enabled "$service_name" 2>/dev/null || true)"
unit_path="$(systemctl show "$service_name" -p FragmentPath --value 2>/dev/null || true)"
exec_start="$(systemctl show "$service_name" -p ExecStart --value 2>/dev/null || true)"
systemctl --no-pager --full status "$service_name" > "$run_dir/systemctl_status_before.txt" 2>&1 || true

if [[ "$service_status_before" != "active" ]]; then
  echo "Service is not active before telemetry probe: $service_status_before" >&2
  exit 3
fi

"${sudo_cmd[@]}" mkdir -p "$queue_dir/pending" "$queue_dir/processing" "$queue_dir/done" "$queue_dir/failed"

python3 - "$run_dir/jobs" "$stamp" "$job_count" "$request_count" <<'PY'
import json
import sys
from pathlib import Path

jobs_dir = Path(sys.argv[1])
stamp = sys.argv[2]
job_count = int(sys.argv[3])
request_count = int(sys.argv[4])
for job_index in range(job_count):
    job_name = f"systemd_telemetry_{stamp}_{job_index + 1:03d}.jsonl"
    rows = []
    for request_index in range(request_count):
        base = (job_index + 1) * 10000 + (request_index + 1) * 100
        rows.append(
            {
                "request_id": f"systemd-telemetry-{stamp}-{job_index + 1:03d}-{request_index + 1:03d}",
                "tokens": [base + offset for offset in range(1, 17)],
            }
        )
    (jobs_dir / job_name).write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
PY

submitted_jobs=()
hrut_somstatus > "$somstatus_before" 2>&1 || true
hrt_ucp_monitor -b -e bpu -d "$monitor_delay_ms" -n "$monitor_sample_count" > "$monitor_stdout" 2> "$monitor_stderr" &
monitor_pid="$!"
sleep 0.3

cleanup_monitor() {
  if kill -0 "$monitor_pid" >/dev/null 2>&1; then
    kill "$monitor_pid" >/dev/null 2>&1 || true
    wait "$monitor_pid" >/dev/null 2>&1 || true
  fi
}
trap cleanup_monitor EXIT

for job_path in "$run_dir"/jobs/*.jsonl; do
  job_name="$(basename "$job_path")"
  submitted_jobs+=("$job_name")
  "${sudo_cmd[@]}" test ! -e "$queue_dir/pending/$job_name"
  "${sudo_cmd[@]}" test ! -e "$queue_dir/processing/$job_name"
  "${sudo_cmd[@]}" test ! -e "$queue_dir/done/$job_name"
  "${sudo_cmd[@]}" test ! -e "$queue_dir/failed/$job_name"
  "${sudo_cmd[@]}" install -m 0644 "$job_path" "$queue_dir/pending/$job_name.upload"
  "${sudo_cmd[@]}" mv "$queue_dir/pending/$job_name.upload" "$queue_dir/pending/$job_name"
done

deadline=$((SECONDS + timeout_sec))
while (( SECONDS < deadline )); do
  all_finished=1
  for job_name in "${submitted_jobs[@]}"; do
    if "${sudo_cmd[@]}" test -f "$queue_dir/done/$job_name"; then
      continue
    fi
    if "${sudo_cmd[@]}" test -f "$queue_dir/failed/$job_name"; then
      continue
    fi
    all_finished=0
    break
  done
  if (( all_finished == 1 )); then
    break
  fi
  sleep "$poll_interval_sec"
done

cleanup_monitor
trap - EXIT
hrut_somstatus > "$somstatus_after" 2>&1 || true

service_status_after="$(systemctl is-active "$service_name" 2>/dev/null || true)"
service_enabled_after="$(systemctl is-enabled "$service_name" 2>/dev/null || true)"
systemctl --no-pager --full status "$service_name" > "$run_dir/systemctl_status_after.txt" 2>&1 || true

job_status_json="$run_dir/job_status.json"
python3 - "$job_status_json" "$queue_dir" "$output_dir" "${submitted_jobs[@]}" <<'PY'
import json
import sys
from pathlib import Path

out_path = Path(sys.argv[1])
queue_dir = Path(sys.argv[2])
output_dir = Path(sys.argv[3])
jobs = sys.argv[4:]
rows = []
for job_name in jobs:
    stem = Path(job_name).stem
    status = "missing"
    for candidate in ("done", "failed", "processing", "pending"):
        if (queue_dir / candidate / job_name).is_file():
            status = candidate
            break
    summary_path = output_dir / "jobs" / stem / "queue_summary.json"
    summary = None
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    rows.append(
        {
            "job_name": job_name,
            "status": status,
            "summary_path": str(summary_path),
            "summary": summary,
        }
    )
out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

python3 - \
  "$run_dir" \
  "$service_name" \
  "$queue_dir" \
  "$output_dir" \
  "$job_count" \
  "$request_count" \
  "$timeout_sec" \
  "$poll_interval_sec" \
  "$monitor_delay_ms" \
  "$monitor_sample_count" \
  "$service_status_before" \
  "$service_enabled_before" \
  "$service_status_after" \
  "$service_enabled_after" \
  "$unit_path" \
  "$exec_start" \
  "$job_status_json" <<'PY'
import json
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
service_name = sys.argv[2]
queue_dir = sys.argv[3]
output_dir = sys.argv[4]
job_count = int(sys.argv[5])
request_count = int(sys.argv[6])
timeout_sec = int(sys.argv[7])
poll_interval_sec = int(sys.argv[8])
monitor_delay_ms = int(sys.argv[9])
monitor_sample_count = int(sys.argv[10])
service_status_before = sys.argv[11]
service_enabled_before = sys.argv[12]
service_status_after = sys.argv[13]
service_enabled_after = sys.argv[14]
unit_path = sys.argv[15]
exec_start = sys.argv[16]
job_rows = json.loads(Path(sys.argv[17]).read_text(encoding="utf-8"))
monitor_stdout = run_dir / "hrt_ucp_monitor.stdout"
monitor_stderr = run_dir / "hrt_ucp_monitor.stderr"
somstatus_before = run_dir / "hrut_somstatus_before.txt"
somstatus_after = run_dir / "hrut_somstatus_after.txt"

errors = []
monitor_text = monitor_stdout.read_text(encoding="utf-8", errors="replace") if monitor_stdout.is_file() else ""
monitor_err = monitor_stderr.read_text(encoding="utf-8", errors="replace") if monitor_stderr.is_file() else ""
bpu_loading_samples = [float(item) for item in re.findall(r"\|\s*BPU0\s+([0-9]+(?:[.][0-9]+)?)\s*\|", monitor_text)]
cma_used_values = re.findall(r"\|\s*cma_reserved\s+\S+\s+(\S+)\s+\S+\s*\|", monitor_text)
carveout_used_values = re.findall(r"\|\s*carveout\s+\S+\s+(\S+)\s+\S+\s*\|", monitor_text)
max_bpu_loading = max(bpu_loading_samples) if bpu_loading_samples else 0.0
avg_bpu_loading = statistics.fmean(bpu_loading_samples) if bpu_loading_samples else 0.0
nonzero_bpu_loading_sample_count = sum(1 for item in bpu_loading_samples if item > 0.0)

if not bpu_loading_samples:
    errors.append("hrt_ucp_monitor produced no BPU0 loading samples")
if max_bpu_loading <= 0.0:
    errors.append(f"max_bpu_loading did not exceed zero: {max_bpu_loading}")
if nonzero_bpu_loading_sample_count <= 0:
    errors.append(f"nonzero_bpu_loading_sample_count did not exceed zero: {nonzero_bpu_loading_sample_count}")

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
    "--drain-all",
):
    if text not in exec_start:
        errors.append(f"ExecStart missing {text}: {exec_start}")

completed_job_count = 0
failed_job_count = 0
processed_request_count = 0
accepted_request_count = 0
deferred_request_count = 0
result_count = 0
total_wall_ms = 0.0
total_load_ms = 0.0
total_run_ms = 0.0
batch_counts = []
summary_rows = []
for row in job_rows:
    job_name = row.get("job_name")
    summary_path = row.get("summary_path")
    summary = row.get("summary")
    if row.get("status") == "done":
        completed_job_count += 1
    elif row.get("status") == "failed":
        failed_job_count += 1
    else:
        errors.append(f"job did not finish: {job_name} status={row.get('status')}")
    if not isinstance(summary, dict):
        errors.append(f"missing queue_summary.json for {job_name}: {summary_path}")
        summary_rows.append(
            {
                "job_name": job_name,
                "status": row.get("status"),
                "summary_path": summary_path,
                "runner_verdict": None,
                "processed_count": None,
                "batch_count": None,
                "total_wall_ms": None,
            }
        )
        continue
    if summary.get("verdict") != "ok_dream7b_bpu_batch_queue_runner":
        errors.append(f"unexpected runner verdict for {job_name}: {summary.get('verdict')}")
    if summary.get("processed_count") != request_count:
        errors.append(f"unexpected processed_count for {job_name}: {summary.get('processed_count')}")
    if summary.get("accepted_count") != request_count:
        errors.append(f"unexpected accepted_count for {job_name}: {summary.get('accepted_count')}")
    if summary.get("deferred_count") != 0:
        errors.append(f"unexpected deferred_count for {job_name}: {summary.get('deferred_count')}")
    if summary.get("max_batch_size") != 16:
        errors.append(f"unexpected max_batch_size for {job_name}: {summary.get('max_batch_size')}")
    if summary.get("batch_run_count") != 1:
        errors.append(f"unexpected batch_run_count for {job_name}: {summary.get('batch_run_count')}")
    lock = summary.get("bpu_lock") or {}
    if lock.get("path") != "/run/lock/dream7b_bpu_batch_queue_runner.lock":
        errors.append(f"unexpected bpu_lock.path for {job_name}: {lock.get('path')}")
    batch_runs = summary.get("batch_runs") or []
    metrics = batch_runs[0].get("metrics", {}) if batch_runs else {}
    batch_count = metrics.get("batch_count")
    batch_counts.append(batch_count)
    if batch_count != request_count:
        errors.append(f"unexpected batch_count for {job_name}: {batch_count}")
    if metrics.get("execution_mode") != "pair_window_batch":
        errors.append(f"unexpected execution_mode for {job_name}: {metrics.get('execution_mode')}")
    if metrics.get("window_execution_mode") != "window-batch":
        errors.append(f"unexpected window_execution_mode for {job_name}: {metrics.get('window_execution_mode')}")
    if metrics.get("child_process_count") != 0:
        errors.append(f"unexpected child_process_count for {job_name}: {metrics.get('child_process_count')}")
    results = summary.get("results") or []
    if len(results) != request_count:
        errors.append(f"unexpected result count for {job_name}: {len(results)}")
    for result in results:
        if result.get("final_shape") != [1, 16, 152064]:
            errors.append(f"unexpected final_shape for {result.get('request_id')}: {result.get('final_shape')}")
    forward_metrics = summary.get("forward_metrics") or {}
    processed_request_count += int(summary.get("processed_count") or 0)
    accepted_request_count += int(summary.get("accepted_count") or 0)
    deferred_request_count += int(summary.get("deferred_count") or 0)
    result_count += len(results)
    total_wall_ms += float(forward_metrics.get("total_wall_ms") or 0.0)
    total_load_ms += float(forward_metrics.get("total_load_ms") or 0.0)
    total_run_ms += float(forward_metrics.get("total_run_ms") or 0.0)
    summary_rows.append(
        {
            "job_name": job_name,
            "status": row.get("status"),
            "summary_path": summary_path,
            "runner_verdict": summary.get("verdict"),
            "processed_count": summary.get("processed_count"),
            "batch_count": batch_count,
            "total_wall_ms": round(float(forward_metrics.get("total_wall_ms") or 0.0), 3),
        }
    )

if completed_job_count != job_count:
    errors.append(f"unexpected completed_job_count: {completed_job_count}")
if failed_job_count != 0:
    errors.append(f"unexpected failed_job_count: {failed_job_count}")
expected_request_total = job_count * request_count
if processed_request_count != expected_request_total:
    errors.append(f"unexpected processed_request_count: {processed_request_count}")
if accepted_request_count != expected_request_total:
    errors.append(f"unexpected accepted_request_count: {accepted_request_count}")
if deferred_request_count != 0:
    errors.append(f"unexpected deferred_request_count: {deferred_request_count}")
if result_count != expected_request_total:
    errors.append(f"unexpected result_count: {result_count}")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_batch_queue_systemd_telemetry_probe" if not errors else "failed_dream7b_bpu_batch_queue_systemd_telemetry_probe",
    "run_dir": str(run_dir),
    "service_name": service_name,
    "queue_dir": queue_dir,
    "output_dir": output_dir,
    "job_count": job_count,
    "request_count": request_count,
    "expected_request_total": expected_request_total,
    "timeout_sec": timeout_sec,
    "poll_interval_sec": poll_interval_sec,
    "monitor_delay_ms": monitor_delay_ms,
    "monitor_sample_count": monitor_sample_count,
    "service_status_before": service_status_before,
    "service_enabled_before": service_enabled_before,
    "service_status_after": service_status_after,
    "service_enabled_after": service_enabled_after,
    "unit_path": unit_path,
    "exec_start": exec_start,
    "completed_job_count": completed_job_count,
    "failed_job_count": failed_job_count,
    "processed_request_count": processed_request_count,
    "accepted_request_count": accepted_request_count,
    "deferred_request_count": deferred_request_count,
    "result_count": result_count,
    "batch_counts": batch_counts,
    "total_wall_ms": round(total_wall_ms, 3),
    "total_load_ms": round(total_load_ms, 3),
    "total_run_ms": round(total_run_ms, 3),
    "amortized_wall_ms_per_processed_request": round(total_wall_ms / processed_request_count, 3) if processed_request_count else 0.0,
    "amortized_load_ms_per_processed_request": round(total_load_ms / processed_request_count, 3) if processed_request_count else 0.0,
    "amortized_run_ms_per_processed_request": round(total_run_ms / processed_request_count, 3) if processed_request_count else 0.0,
    "bpu_loading_sample_count": len(bpu_loading_samples),
    "nonzero_bpu_loading_sample_count": nonzero_bpu_loading_sample_count,
    "max_bpu_loading": round(max_bpu_loading, 3),
    "avg_bpu_loading": round(avg_bpu_loading, 3),
    "cma_reserved_used_values": cma_used_values[:10],
    "carveout_used_values": carveout_used_values[:10],
    "monitor_stdout": str(monitor_stdout),
    "monitor_stderr": str(monitor_stderr),
    "monitor_stderr_excerpt": monitor_err[:500],
    "somstatus_before": str(somstatus_before),
    "somstatus_after": str(somstatus_after),
    "jobs": summary_rows,
    "errors": errors,
}
(run_dir / "systemd_telemetry_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
error_lines = [f"- {item}" for item in errors] if errors else ["- none"]
job_lines = [
    f"| {item['job_name']} | {item['status']} | {item['runner_verdict']} | {item['processed_count']} | {item['batch_count']} | {item['total_wall_ms']} | {item['summary_path']} |"
    for item in payload["jobs"]
]
(run_dir / "systemd_telemetry_probe.md").write_text(
    "\n".join([
        "# Dream 7B BPU Batch Queue Systemd Telemetry Probe",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- run_dir: {payload['run_dir']}",
        f"- service_name: {payload['service_name']}",
        f"- queue_dir: {payload['queue_dir']}",
        f"- output_dir: {payload['output_dir']}",
        f"- job_count: {payload['job_count']}",
        f"- request_count: {payload['request_count']}",
        f"- expected_request_total: {payload['expected_request_total']}",
        f"- completed_job_count: {payload['completed_job_count']}",
        f"- failed_job_count: {payload['failed_job_count']}",
        f"- processed_request_count: {payload['processed_request_count']}",
        f"- accepted_request_count: {payload['accepted_request_count']}",
        f"- deferred_request_count: {payload['deferred_request_count']}",
        f"- result_count: {payload['result_count']}",
        f"- batch_counts: {payload['batch_counts']}",
        f"- total_wall_ms: {payload['total_wall_ms']}",
        f"- total_load_ms: {payload['total_load_ms']}",
        f"- total_run_ms: {payload['total_run_ms']}",
        f"- amortized_wall_ms_per_processed_request: {payload['amortized_wall_ms_per_processed_request']}",
        f"- amortized_load_ms_per_processed_request: {payload['amortized_load_ms_per_processed_request']}",
        f"- amortized_run_ms_per_processed_request: {payload['amortized_run_ms_per_processed_request']}",
        f"- monitor_delay_ms: {payload['monitor_delay_ms']}",
        f"- monitor_sample_count: {payload['monitor_sample_count']}",
        f"- bpu_loading_sample_count: {payload['bpu_loading_sample_count']}",
        f"- nonzero_bpu_loading_sample_count: {payload['nonzero_bpu_loading_sample_count']}",
        f"- max_bpu_loading: {payload['max_bpu_loading']}",
        f"- avg_bpu_loading: {payload['avg_bpu_loading']}",
        f"- service_status_before: {payload['service_status_before']}",
        f"- service_status_after: {payload['service_status_after']}",
        f"- exec_start: {payload['exec_start']}",
        "",
        "## Jobs",
        "",
        "| job_name | status | runner_verdict | processed_count | batch_count | total_wall_ms | summary_path |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
        *job_lines,
        "",
        "## Errors",
        "",
        *error_lines,
        "",
    ]) + "\n",
    encoding="utf-8",
)
print(run_dir / "systemd_telemetry_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
