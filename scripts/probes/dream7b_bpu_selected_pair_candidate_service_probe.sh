#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
service_name="${2:-dream7b-bpu-selected-pair-candidate.service}"
queue_dir="${3:-/mnt/nas/openclaw/queues/dream7b-bpu-selected-pair-candidate}"
output_dir="${4:-/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_candidate_service_systemd}"
request_count="${DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_SERVICE_REQUEST_COUNT:-16}"
timeout_sec="${DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_SERVICE_TIMEOUT_SEC:-480}"
poll_interval_sec="${DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_SERVICE_POLL_INTERVAL_SEC:-2}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

case "$service_name" in
  dream7b-bpu-selected-pair-candidate.service|dream7b-bpu-selected-pair-candidate-*.service) ;;
  *)
    echo "Refusing unexpected selected-pair candidate service name: $service_name" >&2
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

if ! [[ "$request_count" =~ ^[0-9]+$ ]] || (( request_count < 1 || request_count > 16 )); then
  echo "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_SERVICE_REQUEST_COUNT must be an integer from 1 to 16." >&2
  exit 2
fi
if ! [[ "$timeout_sec" =~ ^[0-9]+$ ]] || (( timeout_sec < 1 )); then
  echo "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_SERVICE_TIMEOUT_SEC must be a positive integer." >&2
  exit 2
fi
if ! [[ "$poll_interval_sec" =~ ^[0-9]+$ ]] || (( poll_interval_sec < 1 )); then
  echo "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_SERVICE_POLL_INTERVAL_SEC must be a positive integer." >&2
  exit 2
fi

if (( EUID == 0 )); then
  sudo_cmd=()
else
  sudo_cmd=(sudo -n)
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_selected_pair_candidate_service_$stamp"
mkdir -p "$run_dir"
job_name="selected_pair_candidate_service_${stamp}.jsonl"
job_path="$run_dir/$job_name"

service_status_before="$(systemctl is-active "$service_name" 2>/dev/null || true)"
service_enabled_before="$(systemctl is-enabled "$service_name" 2>/dev/null || true)"
unit_path="$(systemctl show "$service_name" -p FragmentPath --value 2>/dev/null || true)"
exec_start="$(systemctl show "$service_name" -p ExecStart --value 2>/dev/null || true)"
default_service_status="$(systemctl is-active dream7b-bpu-batch-queue.service 2>/dev/null || true)"
default_service_enabled="$(systemctl is-enabled dream7b-bpu-batch-queue.service 2>/dev/null || true)"
systemctl --no-pager --full status "$service_name" > "$run_dir/systemctl_status_before.txt" 2>&1 || true

if [[ "$service_status_before" != "active" ]]; then
  echo "Selected-pair candidate service is not active before probe: $service_status_before" >&2
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
    base = 1100 + (index * 16)
    rows.append(
        {
            "request_id": f"selected-pair-candidate-service-{stamp}-{index + 1:03d}",
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
  "$service_status_before" \
  "$service_enabled_before" \
  "$service_status_after" \
  "$service_enabled_after" \
  "$unit_path" \
  "$exec_start" \
  "$default_service_status" \
  "$default_service_enabled" <<'PY'
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
service_status_before = sys.argv[11]
service_enabled_before = sys.argv[12]
service_status_after = sys.argv[13]
service_enabled_after = sys.argv[14]
unit_path = sys.argv[15]
exec_start = sys.argv[16]
default_service_status = sys.argv[17]
default_service_enabled = sys.argv[18]

errors = []
summary = None
forward_summary = None
forward_summary_path = None
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
if not unit_path.endswith(f"/{service_name}"):
    errors.append(f"unexpected unit_path: {unit_path}")
for text in (
    "dream7b-bpu-batch-queue-service",
    "/mnt/nas/openclaw/queues/dream7b-bpu-selected-pair-candidate",
    "/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_candidate_service_systemd",
    "--forward-cmd dream7b-bpu-selected-pair-batch-forward",
    "/run/lock/dream7b_bpu_batch_queue_runner.lock",
    "--max-batch-size 16",
    "--drain-all",
):
    if text not in exec_start:
        errors.append(f"ExecStart missing {text}: {exec_start}")
if job_status != "done":
    errors.append(f"unexpected job_status: {job_status}")

processed_count = None
accepted_count = None
deferred_count = None
skipped_count = None
max_batch_size = None
drain_all = None
forward_command = None
batch_run_count = None
batch_count = None
result_count = 0
execution_mode = None
window_execution_mode = None
child_process_count = None
selected_pair_candidate = None
selected_pair = None
selected_segments = None
selected_pair_covers_all_segments = None
total_wall_ms = 0.0
amortized_wall_ms = 0.0
bpu_lock_path = None
final_shapes = []

if isinstance(summary, dict):
    if summary.get("verdict") != "ok_dream7b_bpu_batch_queue_runner":
        errors.append(f"unexpected runner verdict: {summary.get('verdict')}")
    forward_command = summary.get("forward_command")
    drain_all = summary.get("drain_all")
    max_batch_size = summary.get("max_batch_size")
    processed_count = summary.get("processed_count")
    accepted_count = summary.get("accepted_count")
    deferred_count = summary.get("deferred_count")
    skipped_count = summary.get("skipped_count")
    batch_run_count = summary.get("batch_run_count")
    if forward_command != "dream7b-bpu-selected-pair-batch-forward":
        errors.append(f"unexpected forward_command: {forward_command}")
    if drain_all is not True:
        errors.append(f"unexpected drain_all: {drain_all}")
    if max_batch_size != 16:
        errors.append(f"unexpected max_batch_size: {max_batch_size}")
    if processed_count != request_count:
        errors.append(f"unexpected processed_count: {processed_count}")
    if accepted_count != request_count:
        errors.append(f"unexpected accepted_count: {accepted_count}")
    if deferred_count != 0:
        errors.append(f"unexpected deferred_count: {deferred_count}")
    if skipped_count != 0:
        errors.append(f"unexpected skipped_count: {skipped_count}")
    if batch_run_count != 1:
        errors.append(f"unexpected batch_run_count: {batch_run_count}")
    lock = summary.get("bpu_lock") or {}
    bpu_lock_path = lock.get("path")
    if bpu_lock_path != "/run/lock/dream7b_bpu_batch_queue_runner.lock":
        errors.append(f"unexpected bpu_lock.path: {bpu_lock_path}")
    batch_runs = summary.get("batch_runs") or []
    metrics = batch_runs[0].get("metrics", {}) if batch_runs else {}
    batch_count = metrics.get("batch_count")
    execution_mode = metrics.get("execution_mode")
    window_execution_mode = metrics.get("window_execution_mode")
    child_process_count = metrics.get("child_process_count")
    if batch_count != request_count:
        errors.append(f"unexpected batch_count: {batch_count}")
    if execution_mode != "pair_window_batch":
        errors.append(f"unexpected execution_mode: {execution_mode}")
    if window_execution_mode != "selected-pair-resident":
        errors.append(f"unexpected window_execution_mode: {window_execution_mode}")
    if child_process_count != 2:
        errors.append(f"unexpected child_process_count: {child_process_count}")
    if batch_runs:
        forward_summary_path = Path(batch_runs[0].get("forward_summary") or "")
        if forward_summary_path.is_file():
            forward_summary = json.loads(forward_summary_path.read_text(encoding="utf-8"))
        else:
            errors.append(f"missing forward summary: {forward_summary_path}")
    results = summary.get("results") or []
    result_count = len(results)
    if result_count != request_count:
        errors.append(f"unexpected result_count: {result_count}")
    for result in results:
        final_shape = result.get("final_shape")
        final_shapes.append(final_shape)
        if final_shape != [1, 16, 152064]:
            errors.append(f"unexpected final_shape for {result.get('request_id')}: {final_shape}")
    forward_metrics = summary.get("forward_metrics") or {}
    total_wall_ms = float(forward_metrics.get("total_wall_ms") or 0.0)
    amortized_wall_ms = float(forward_metrics.get("amortized_wall_ms_per_processed_request") or 0.0)
    if total_wall_ms <= 0:
        errors.append(f"unexpected total_wall_ms: {total_wall_ms}")
    if amortized_wall_ms <= 0:
        errors.append(f"unexpected amortized_wall_ms_per_processed_request: {amortized_wall_ms}")

if isinstance(forward_summary, dict):
    if forward_summary.get("verdict") != "ok_dream7b_segmented_hbm_python_forward":
        errors.append(f"unexpected forward verdict: {forward_summary.get('verdict')}")
    selected_pair_candidate = forward_summary.get("selected_pair_candidate")
    selected_pair = forward_summary.get("selected_pair")
    selected_segments = forward_summary.get("selected_segments")
    selected_pair_covers_all_segments = forward_summary.get("selected_pair_covers_all_segments")
    if selected_pair_candidate is not True:
        errors.append(f"selected_pair_candidate is not true: {selected_pair_candidate}")
    if selected_pair != [1, 8]:
        errors.append(f"unexpected selected_pair: {selected_pair}")
    if selected_segments != ["seg02_04", "seg24_26"]:
        errors.append(f"unexpected selected_segments: {selected_segments}")
    if selected_pair_covers_all_segments is not True:
        errors.append(f"selected_pair_covers_all_segments is not true: {selected_pair_covers_all_segments}")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_selected_pair_candidate_service_probe" if not errors else "failed_dream7b_bpu_selected_pair_candidate_service_probe",
    "service_name": service_name,
    "queue_dir": queue_dir,
    "output_dir": output_dir,
    "job_name": job_name,
    "job_status": job_status,
    "summary_path": str(summary_path),
    "request_count": request_count,
    "timeout_sec": timeout_sec,
    "poll_interval_sec": poll_interval_sec,
    "service_status_before": service_status_before,
    "service_enabled_before": service_enabled_before,
    "service_status_after": service_status_after,
    "service_enabled_after": service_enabled_after,
    "default_service_status": default_service_status,
    "default_service_enabled": default_service_enabled,
    "unit_path": unit_path,
    "exec_start": exec_start,
    "forward_command": forward_command,
    "drain_all": drain_all,
    "max_batch_size": max_batch_size,
    "processed_count": processed_count,
    "accepted_count": accepted_count,
    "deferred_count": deferred_count,
    "skipped_count": skipped_count,
    "batch_run_count": batch_run_count,
    "batch_count": batch_count,
    "result_count": result_count,
    "execution_mode": execution_mode,
    "window_execution_mode": window_execution_mode,
    "child_process_count": child_process_count,
    "bpu_lock_path": bpu_lock_path,
    "final_shapes": final_shapes,
    "total_wall_ms": round(total_wall_ms, 3),
    "amortized_wall_ms_per_processed_request": round(amortized_wall_ms, 3),
    "forward_summary_path": str(forward_summary_path) if forward_summary_path else "",
    "selected_pair_candidate": selected_pair_candidate,
    "selected_pair": selected_pair,
    "selected_segments": selected_segments,
    "selected_pair_covers_all_segments": selected_pair_covers_all_segments,
    "default_service_replaced": False,
    "next_optimization_target": "rerun deployment acceptance with selected_pair_candidate_service included before considering any default service replacement",
    "errors": errors,
}
(run_dir / "selected_pair_candidate_service_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
error_lines = [f"- {item}" for item in errors] if errors else ["- none"]
(run_dir / "selected_pair_candidate_service_probe.md").write_text(
    "\n".join([
        "# Dream 7B BPU Selected-Pair Candidate Service Probe",
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
        f"- processed_count: {payload['processed_count']}",
        f"- accepted_count: {payload['accepted_count']}",
        f"- deferred_count: {payload['deferred_count']}",
        f"- skipped_count: {payload['skipped_count']}",
        f"- forward_command: {payload['forward_command']}",
        f"- drain_all: {payload['drain_all']}",
        f"- max_batch_size: {payload['max_batch_size']}",
        f"- batch_run_count: {payload['batch_run_count']}",
        f"- batch_count: {payload['batch_count']}",
        f"- result_count: {payload['result_count']}",
        f"- execution_mode: {payload['execution_mode']}",
        f"- window_execution_mode: {payload['window_execution_mode']}",
        f"- child_process_count: {payload['child_process_count']}",
        f"- bpu_lock_path: {payload['bpu_lock_path']}",
        f"- selected_pair_candidate: {payload['selected_pair_candidate']}",
        f"- selected_pair: {payload['selected_pair']}",
        f"- selected_segments: {payload['selected_segments']}",
        f"- selected_pair_covers_all_segments: {payload['selected_pair_covers_all_segments']}",
        f"- default_service_replaced: {payload['default_service_replaced']}",
        f"- default_service_status: {payload['default_service_status']}",
        f"- default_service_enabled: {payload['default_service_enabled']}",
        f"- final_shapes: {payload['final_shapes']}",
        f"- total_wall_ms: {payload['total_wall_ms']}",
        f"- amortized_wall_ms_per_processed_request: {payload['amortized_wall_ms_per_processed_request']}",
        f"- forward_summary_path: {payload['forward_summary_path']}",
        f"- exec_start: {payload['exec_start']}",
        f"- next_optimization_target: {payload['next_optimization_target']}",
        "",
        "## Errors",
        "",
        *error_lines,
        "",
    ]) + "\n",
    encoding="utf-8",
)
print(run_dir / "selected_pair_candidate_service_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
