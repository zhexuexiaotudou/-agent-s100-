#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
service_name="${2:-dream7b-bpu-batch-queue.service}"
queue_dir="${3:-/mnt/nas/openclaw/queues/dream7b-bpu}"
output_dir="${4:-/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd}"
request_count="${DREAM7B_BPU_SYSTEMD_DRAIN_REQUEST_COUNT:-16}"
timeout_sec="${DREAM7B_BPU_SYSTEMD_DRAIN_TIMEOUT_SEC:-600}"
poll_interval_sec="${DREAM7B_BPU_SYSTEMD_DRAIN_POLL_INTERVAL_SEC:-2}"
expected_max_batch_size=16

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

if ! [[ "$request_count" =~ ^[0-9]+$ ]] || (( request_count < 16 || request_count > 32 )); then
  echo "DREAM7B_BPU_SYSTEMD_DRAIN_REQUEST_COUNT must be an integer from 16 to 32." >&2
  exit 2
fi
if ! [[ "$timeout_sec" =~ ^[0-9]+$ ]] || (( timeout_sec < 1 )); then
  echo "DREAM7B_BPU_SYSTEMD_DRAIN_TIMEOUT_SEC must be a positive integer." >&2
  exit 2
fi
if ! [[ "$poll_interval_sec" =~ ^[0-9]+$ ]] || (( poll_interval_sec < 1 )); then
  echo "DREAM7B_BPU_SYSTEMD_DRAIN_POLL_INTERVAL_SEC must be a positive integer." >&2
  exit 2
fi

if (( EUID == 0 )); then
  sudo_cmd=()
else
  sudo_cmd=(sudo -n)
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_batch_queue_systemd_drain_$stamp"
mkdir -p "$run_dir"
job_name="systemd_drain_${stamp}.jsonl"
job_path="$run_dir/$job_name"

service_status_before="$(systemctl is-active "$service_name" 2>/dev/null || true)"
service_enabled_before="$(systemctl is-enabled "$service_name" 2>/dev/null || true)"
unit_path="$(systemctl show "$service_name" -p FragmentPath --value 2>/dev/null || true)"
exec_start="$(systemctl show "$service_name" -p ExecStart --value 2>/dev/null || true)"
systemctl --no-pager --full status "$service_name" > "$run_dir/systemctl_status_before.txt" 2>&1 || true

if [[ "$service_status_before" != "active" ]]; then
  echo "Service is not active before drain probe: $service_status_before" >&2
  exit 3
fi

python3 - "$job_path" "$stamp" "$request_count" <<'PY'
import json
import sys
from pathlib import Path

job_path = Path(sys.argv[1])
stamp = sys.argv[2]
request_count = int(sys.argv[3])
rows = []
for index in range(request_count):
    base = (index + 1) * 100
    rows.append(
        {
            "request_id": f"systemd-drain-{stamp}-{index + 1:03d}",
            "tokens": [base + offset for offset in range(1, 17)],
        }
    )
job_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
PY

"${sudo_cmd[@]}" mkdir -p "$queue_dir/pending" "$queue_dir/processing" "$queue_dir/done" "$queue_dir/failed"
"${sudo_cmd[@]}" test ! -e "$queue_dir/pending/$job_name"
"${sudo_cmd[@]}" test ! -e "$queue_dir/processing/$job_name"
"${sudo_cmd[@]}" test ! -e "$queue_dir/done/$job_name"
"${sudo_cmd[@]}" test ! -e "$queue_dir/failed/$job_name"
"${sudo_cmd[@]}" install -m 0644 "$job_path" "$queue_dir/pending/$job_name.upload"
"${sudo_cmd[@]}" mv "$queue_dir/pending/$job_name.upload" "$queue_dir/pending/$job_name"

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

service_status_after="$(systemctl is-active "$service_name" 2>/dev/null || true)"
service_enabled_after="$(systemctl is-enabled "$service_name" 2>/dev/null || true)"
systemctl --no-pager --full status "$service_name" > "$run_dir/systemctl_status_after.txt" 2>&1 || true

summary_path="$output_dir/jobs/${job_name%.jsonl}/queue_summary.json"
job_status="missing"
for candidate in done failed processing pending; do
  if "${sudo_cmd[@]}" test -f "$queue_dir/$candidate/$job_name"; then
    job_status="$candidate"
    break
  fi
done

python3 - \
  "$run_dir" \
  "$service_name" \
  "$queue_dir" \
  "$output_dir" \
  "$job_name" \
  "$job_status" \
  "$summary_path" \
  "$request_count" \
  "$timeout_sec" \
  "$poll_interval_sec" \
  "$expected_max_batch_size" \
  "$service_status_before" \
  "$service_enabled_before" \
  "$service_status_after" \
  "$service_enabled_after" \
  "$unit_path" \
  "$exec_start" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
service_name = sys.argv[2]
queue_dir = sys.argv[3]
output_dir = sys.argv[4]
job_name = sys.argv[5]
job_status = sys.argv[6]
summary_path = Path(sys.argv[7])
request_count = int(sys.argv[8])
timeout_sec = int(sys.argv[9])
poll_interval_sec = int(sys.argv[10])
expected_max_batch_size = int(sys.argv[11])
service_status_before = sys.argv[12]
service_enabled_before = sys.argv[13]
service_status_after = sys.argv[14]
service_enabled_after = sys.argv[15]
unit_path = sys.argv[16]
exec_start = sys.argv[17]

errors = []
summary = None
if summary_path.is_file():
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
else:
    errors.append(f"missing queue_summary.json: {summary_path}")

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
for text in ("dream7b-bpu-batch-queue-service", "/mnt/nas/openclaw/queues/dream7b-bpu", "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd", "/run/lock/dream7b_bpu_batch_queue_runner.lock", "--max-batch-size 16", "--drain-all"):
    if text not in exec_start:
        errors.append(f"ExecStart missing {text}: {exec_start}")
if job_status != "done":
    errors.append(f"unexpected job_status: {job_status}")

batch_counts = []
child_process_counts = []
execution_modes = []
window_execution_modes = []
total_wall_ms = 0.0
amortized_wall_ms = 0.0
processed_count = None
accepted_count = None
deferred_count = None
result_count = 0
batch_run_count = None
max_batch_size = None
drain_all = None
expected_batch_counts = []
remaining = request_count
while remaining > 0:
    batch_size = min(expected_max_batch_size, remaining)
    expected_batch_counts.append(batch_size)
    remaining -= batch_size

if isinstance(summary, dict):
    if summary.get("verdict") != "ok_dream7b_bpu_batch_queue_runner":
        errors.append(f"unexpected runner verdict: {summary.get('verdict')}")
    drain_all = summary.get("drain_all")
    max_batch_size = summary.get("max_batch_size")
    processed_count = summary.get("processed_count")
    accepted_count = summary.get("accepted_count")
    deferred_count = summary.get("deferred_count")
    batch_run_count = summary.get("batch_run_count")
    if drain_all is not True:
        errors.append(f"unexpected drain_all: {drain_all}")
    if max_batch_size != expected_max_batch_size:
        errors.append(f"unexpected max_batch_size: {max_batch_size}")
    if processed_count != request_count:
        errors.append(f"unexpected processed_count: {processed_count}")
    if accepted_count != request_count:
        errors.append(f"unexpected accepted_count: {accepted_count}")
    if deferred_count != 0:
        errors.append(f"unexpected deferred_count: {deferred_count}")
    if batch_run_count != len(expected_batch_counts):
        errors.append(f"unexpected batch_run_count: {batch_run_count}")
    lock = summary.get("bpu_lock") or {}
    if lock.get("path") != "/run/lock/dream7b_bpu_batch_queue_runner.lock":
        errors.append(f"unexpected bpu_lock.path: {lock.get('path')}")
    for batch_run in summary.get("batch_runs") or []:
        metrics = batch_run.get("metrics") or {}
        batch_counts.append(metrics.get("batch_count"))
        execution_modes.append(metrics.get("execution_mode"))
        window_execution_modes.append(metrics.get("window_execution_mode"))
        child_process_counts.append(metrics.get("child_process_count"))
    if batch_counts != expected_batch_counts:
        errors.append(f"unexpected batch_counts: {batch_counts}")
    for item in execution_modes:
        if item != "pair_window_batch":
            errors.append(f"unexpected execution_mode: {item}")
    for item in window_execution_modes:
        if item != "window-batch":
            errors.append(f"unexpected window_execution_mode: {item}")
    for item in child_process_counts:
        if item != 0:
            errors.append(f"unexpected child_process_count: {item}")
    results = summary.get("results") or []
    result_count = len(results)
    if result_count != request_count:
        errors.append(f"unexpected result_count: {result_count}")
    for result in results:
        if result.get("final_shape") != [1, 16, 152064]:
            errors.append(f"unexpected final_shape for {result.get('request_id')}: {result.get('final_shape')}")
    forward_metrics = summary.get("forward_metrics") or {}
    total_wall_ms = float(forward_metrics.get("total_wall_ms") or 0.0)
    amortized_wall_ms = float(forward_metrics.get("amortized_wall_ms_per_processed_request") or 0.0)
    if total_wall_ms <= 0:
        errors.append(f"unexpected total_wall_ms: {total_wall_ms}")
    if amortized_wall_ms <= 0:
        errors.append(f"unexpected amortized_wall_ms_per_processed_request: {amortized_wall_ms}")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_batch_queue_systemd_drain_probe" if not errors else "failed_dream7b_bpu_batch_queue_systemd_drain_probe",
    "service_name": service_name,
    "queue_dir": queue_dir,
    "output_dir": output_dir,
    "job_name": job_name,
    "job_status": job_status,
    "summary_path": str(summary_path),
    "request_count": request_count,
    "timeout_sec": timeout_sec,
    "poll_interval_sec": poll_interval_sec,
    "expected_max_batch_size": expected_max_batch_size,
    "expected_batch_counts": expected_batch_counts,
    "service_status_before": service_status_before,
    "service_enabled_before": service_enabled_before,
    "service_status_after": service_status_after,
    "service_enabled_after": service_enabled_after,
    "unit_path": unit_path,
    "exec_start": exec_start,
    "drain_all": drain_all,
    "max_batch_size": max_batch_size,
    "processed_count": processed_count,
    "accepted_count": accepted_count,
    "deferred_count": deferred_count,
    "batch_run_count": batch_run_count,
    "batch_counts": batch_counts,
    "result_count": result_count,
    "execution_modes": execution_modes,
    "window_execution_modes": window_execution_modes,
    "child_process_counts": child_process_counts,
    "total_wall_ms": round(total_wall_ms, 3),
    "amortized_wall_ms_per_processed_request": round(amortized_wall_ms, 3),
    "errors": errors,
}
(run_dir / "systemd_drain_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
error_lines = [f"- {item}" for item in errors] if errors else ["- none"]
(run_dir / "systemd_drain_probe.md").write_text(
    "\n".join([
        "# Dream 7B BPU Batch Queue Systemd Drain Probe",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- service_name: {payload['service_name']}",
        f"- queue_dir: {payload['queue_dir']}",
        f"- output_dir: {payload['output_dir']}",
        f"- job_name: {payload['job_name']}",
        f"- job_status: {payload['job_status']}",
        f"- summary_path: {payload['summary_path']}",
        f"- request_count: {payload['request_count']}",
        f"- expected_max_batch_size: {payload['expected_max_batch_size']}",
        f"- expected_batch_counts: {payload['expected_batch_counts']}",
        f"- drain_all: {payload['drain_all']}",
        f"- max_batch_size: {payload['max_batch_size']}",
        f"- processed_count: {payload['processed_count']}",
        f"- accepted_count: {payload['accepted_count']}",
        f"- deferred_count: {payload['deferred_count']}",
        f"- batch_run_count: {payload['batch_run_count']}",
        f"- batch_counts: {payload['batch_counts']}",
        f"- result_count: {payload['result_count']}",
        f"- execution_modes: {payload['execution_modes']}",
        f"- window_execution_modes: {payload['window_execution_modes']}",
        f"- child_process_counts: {payload['child_process_counts']}",
        f"- total_wall_ms: {payload['total_wall_ms']}",
        f"- amortized_wall_ms_per_processed_request: {payload['amortized_wall_ms_per_processed_request']}",
        f"- service_status_before: {payload['service_status_before']}",
        f"- service_status_after: {payload['service_status_after']}",
        f"- exec_start: {payload['exec_start']}",
        "",
        "## Errors",
        "",
        *error_lines,
        "",
    ]) + "\n",
    encoding="utf-8",
)
print(run_dir / "systemd_drain_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
