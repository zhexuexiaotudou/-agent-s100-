#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
queue_dir="${2:-/mnt/nas/openclaw/queues/dream7b-bpu-segment-major-load-once-candidate}"
service_output_dir="${3:-/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_load_once_candidate_service}"
service_name="${DREAM7B_BPU_SEGMENT_MAJOR_SERVICE_NAME:-dream7b-bpu-segment-major-load-once-candidate.service}"
job_count="${DREAM7B_BPU_SEGMENT_MAJOR_SERVICE_JOB_COUNT:-12}"
request_count="${DREAM7B_BPU_SEGMENT_MAJOR_SERVICE_REQUEST_COUNT:-192}"
timeout_sec="${DREAM7B_BPU_SEGMENT_MAJOR_SERVICE_TIMEOUT_SEC:-1500}"
monitor_delay_ms="${DREAM7B_BPU_SEGMENT_MAJOR_SERVICE_MONITOR_DELAY_MS:-100}"
monitor_sample_count="${DREAM7B_BPU_SEGMENT_MAJOR_SERVICE_MONITOR_SAMPLE_COUNT:-15000}"

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
  dream7b-bpu-batch-queue.service|dream7b-bpu-segment-major-load-once-candidate.service|dream7b-bpu-segment-major-load-once-candidate-*.service) ;;
  *)
    echo "Refusing unexpected service name: $service_name" >&2
    exit 2
    ;;
esac

if ! [[ "$job_count" =~ ^[1-9][0-9]*$ ]] || (( job_count < 2 || job_count > 24 )); then
  echo "DREAM7B_BPU_SEGMENT_MAJOR_SERVICE_JOB_COUNT must be 2..24." >&2
  exit 2
fi
if ! [[ "$request_count" =~ ^[1-9][0-9]*$ ]] || (( request_count < 1 || request_count > 256 )); then
  echo "DREAM7B_BPU_SEGMENT_MAJOR_SERVICE_REQUEST_COUNT must be 1..256." >&2
  exit 2
fi
if ! [[ "$timeout_sec" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_SEGMENT_MAJOR_SERVICE_TIMEOUT_SEC must be a positive integer." >&2
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
run_dir="$report_root/dream7b_bpu_segment_major_candidate_service_telemetry_$stamp"
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
        base = 1000 + ((job_index * request_count + request_index) * 31) % 120000
        rows.append(
            {
                "request_id": f"segment-major-service-{stamp}-{job_index + 1:03d}-{request_index + 1:03d}",
                "tokens": [base + offset for offset in range(16)],
            }
        )
    (jobs_dir / f"segment_major_service_{stamp}_{job_index + 1:03d}.jsonl").write_text(
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
  cp "$job_path" "$queue_dir/pending/$(basename "$job_path").tmp"
done
for tmp_path in "$queue_dir/pending"/segment_major_service_"$stamp"_*.jsonl.tmp; do
  mv "$tmp_path" "${tmp_path%.tmp}"
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
done_jobs = sorted((queue_dir / "done").glob(f"segment_major_service_{stamp}_*.jsonl"))
failed_jobs = sorted((queue_dir / "failed").glob(f"segment_major_service_{stamp}_*.jsonl"))
if len(done_jobs) != job_count:
    errors.append(f"done job count mismatch: {len(done_jobs)} != {job_count}")
if failed_jobs:
    errors.append(f"failed job count is nonzero: {len(failed_jobs)}")

expected_prefix = f"segment-major-service-{stamp}-"
expected_processed = job_count * request_count
summary_candidates = []
for path in glob.glob(str(service_output_dir / "runs" / "*" / "segment_major_queue_summary.json")):
    item = Path(path)
    if item.stat().st_mtime >= started_epoch:
        summary_candidates.append(item)
summary_candidates.sort(key=lambda item: item.stat().st_mtime)

runner_summary_path = None
runner = {}
matched_result_count = 0
for item in summary_candidates:
    current = json.loads(item.read_text(encoding="utf-8"))
    durable = current.get("durable_state") or {}
    results_path = Path(durable.get("results_jsonl") or "")
    if results_path.is_file():
        count = 0
        for raw in results_path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            row = json.loads(raw)
            if str(row.get("request_id", "")).startswith(expected_prefix):
                count += 1
        if count > matched_result_count:
            matched_result_count = count
            runner_summary_path = item
            runner = current

if runner_summary_path is None and summary_candidates:
    runner_summary_path = summary_candidates[-1]
    runner = json.loads(runner_summary_path.read_text(encoding="utf-8"))
    warnings.append("falling back to newest segment-major runner summary; request-id match was not found")
if runner_summary_path is None:
    errors.append("missing segment-major service runner summary after telemetry start")

monitor_text = (run_dir / "hrt_ucp_monitor.stdout").read_text(encoding="utf-8", errors="replace")
bpu_loading_samples = [float(item) for item in re.findall(r"\|\s*BPU0\s+([0-9]+(?:[.][0-9]+)?)\s*\|", monitor_text)]
avg_bpu_loading = statistics.fmean(bpu_loading_samples) if bpu_loading_samples else 0.0
max_bpu_loading = max(bpu_loading_samples) if bpu_loading_samples else 0.0
nonzero_count = sum(1 for item in bpu_loading_samples if item > 0.0)
first_nonzero_index = next((index for index, item in enumerate(bpu_loading_samples) if item > 0.0), None)
last_nonzero_index = None
if first_nonzero_index is not None:
    last_nonzero_index = len(bpu_loading_samples) - 1 - next(
        index for index, item in enumerate(reversed(bpu_loading_samples)) if item > 0.0
    )
active_bpu_loading_samples = (
    bpu_loading_samples[first_nonzero_index : last_nonzero_index + 1]
    if first_nonzero_index is not None and last_nonzero_index is not None
    else []
)
active_avg_bpu_loading = statistics.fmean(active_bpu_loading_samples) if active_bpu_loading_samples else 0.0
active_zero_bpu_loading_sample_count = sum(1 for item in active_bpu_loading_samples if item == 0.0)
leading_idle_bpu_loading_sample_count = first_nonzero_index if first_nonzero_index is not None else len(bpu_loading_samples)
trailing_idle_bpu_loading_sample_count = (
    len(bpu_loading_samples) - 1 - last_nonzero_index if last_nonzero_index is not None else 0
)
if not bpu_loading_samples:
    errors.append("hrt_ucp_monitor produced no BPU0 loading samples")
if nonzero_count <= 0:
    errors.append("hrt_ucp_monitor produced no nonzero BPU0 loading samples")

if runner:
    if runner.get("verdict") != "ok_dream7b_bpu_segment_major_load_once_queue_runner":
        errors.append(f"unexpected runner verdict: {runner.get('verdict')}")
    if int(runner.get("processed_job_count") or 0) != job_count:
        errors.append(f"unexpected processed_job_count: {runner.get('processed_job_count')}")
    if int(runner.get("processed_request_count") or 0) != expected_processed:
        errors.append(f"unexpected processed_request_count: {runner.get('processed_request_count')}")
    if int(runner.get("failed_job_count") or 0) != 0:
        errors.append(f"runner failed_job_count is nonzero: {runner.get('failed_job_count')}")
    if runner.get("segment_major_load_once") is not True:
        errors.append("segment_major_load_once is not true")
    if matched_result_count and matched_result_count != expected_processed:
        errors.append(f"matched result count mismatch: {matched_result_count} != {expected_processed}")

load_to_run_ratio = runner.get("load_to_run_ratio") if runner else None
if avg_bpu_loading < 80.0:
    warnings.append(f"avg_bpu_loading below serviceization target 80.0: {avg_bpu_loading:.3f}")
if load_to_run_ratio is None or float(load_to_run_ratio) > 0.15:
    warnings.append(f"load_to_run_ratio above serviceization target 0.15: {load_to_run_ratio}")

if errors:
    decision = "segment_major_service_telemetry_failed"
elif avg_bpu_loading >= 90.0 and load_to_run_ratio is not None and float(load_to_run_ratio) <= 0.15:
    decision = "segment_major_service_meets_90pct_goal"
elif avg_bpu_loading >= 80.0 and load_to_run_ratio is not None and float(load_to_run_ratio) <= 0.15:
    decision = "segment_major_service_near_90pct_candidate"
elif avg_bpu_loading >= 70.0:
    decision = "segment_major_service_stage3_progress_candidate"
else:
    decision = "segment_major_service_below_stage3_target"

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_segment_major_candidate_service_telemetry_probe" if not errors else "failed_dream7b_bpu_segment_major_candidate_service_telemetry_probe",
    "decision": decision,
    "run_dir": str(run_dir),
    "service_name": service_name,
    "queue_dir": str(queue_dir),
    "service_output_dir": str(service_output_dir),
    "runner_summary_json": str(runner_summary_path) if runner_summary_path else "",
    "job_count": job_count,
    "request_count": request_count,
    "expected_processed_request_count": expected_processed,
    "matched_result_count": matched_result_count,
    "processed_request_count": runner.get("processed_request_count") if runner else None,
    "failed_job_count": runner.get("failed_job_count") if runner else None,
    "done_job_count": len(done_jobs),
    "queue_failed_job_count": len(failed_jobs),
    "timeout_sec": timeout_sec,
    "monitor_delay_ms": monitor_delay_ms,
    "monitor_sample_count": monitor_sample_count,
    "bpu_loading_sample_count": len(bpu_loading_samples),
    "nonzero_bpu_loading_sample_count": nonzero_count,
    "avg_bpu_loading": round(avg_bpu_loading, 3),
    "max_bpu_loading": round(max_bpu_loading, 3),
    "active_bpu_loading_sample_count": len(active_bpu_loading_samples),
    "active_avg_bpu_loading": round(active_avg_bpu_loading, 3),
    "active_zero_bpu_loading_sample_count": active_zero_bpu_loading_sample_count,
    "leading_idle_bpu_loading_sample_count": leading_idle_bpu_loading_sample_count,
    "trailing_idle_bpu_loading_sample_count": trailing_idle_bpu_loading_sample_count,
    "first_nonzero_bpu_loading_sample_index": first_nonzero_index,
    "last_nonzero_bpu_loading_sample_index": last_nonzero_index,
    "load_to_run_ratio": load_to_run_ratio,
    "load_event_count": runner.get("load_event_count") if runner else None,
    "load_event_reduction_ratio": runner.get("load_event_reduction_ratio") if runner else None,
    "amortized_wall_ms_per_processed_request": runner.get("amortized_wall_ms_per_processed_request") if runner else None,
    "amortized_total_load_ms_per_processed_request": runner.get("amortized_total_load_ms_per_processed_request") if runner else None,
    "amortized_run_ms_per_processed_request": runner.get("amortized_run_ms_per_processed_request") if runner else None,
    "peak_live_mib": runner.get("peak_live_mib") if runner else None,
    "segment_major_load_once": runner.get("segment_major_load_once") if runner else None,
    "default_service_replaced": service_name == "dream7b-bpu-batch-queue.service",
    "rollback_command": "dream7b-default-rollback"
    if service_name == "dream7b-bpu-batch-queue.service"
    else f"sudo systemctl disable --now {service_name}",
    "warnings": warnings,
    "errors": errors,
}
(run_dir / "segment_major_candidate_service_telemetry_probe.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
lines = [
    "# Dream 7B Segment-Major Candidate Service Telemetry Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- decision: {payload['decision']}",
    f"- service_name: {service_name}",
    f"- processed_request_count: {payload['processed_request_count']}",
    f"- failed_job_count: {payload['failed_job_count']}",
    f"- done_job_count: {payload['done_job_count']}",
    f"- matched_result_count: {payload['matched_result_count']}",
    f"- avg_bpu_loading: {payload['avg_bpu_loading']}",
    f"- max_bpu_loading: {payload['max_bpu_loading']}",
    f"- active_avg_bpu_loading: {payload['active_avg_bpu_loading']}",
    f"- leading_idle_bpu_loading_sample_count: {payload['leading_idle_bpu_loading_sample_count']}",
    f"- trailing_idle_bpu_loading_sample_count: {payload['trailing_idle_bpu_loading_sample_count']}",
    f"- load_to_run_ratio: {payload['load_to_run_ratio']}",
    f"- load_event_reduction_ratio: {payload['load_event_reduction_ratio']}",
    f"- peak_live_mib: {payload['peak_live_mib']}",
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
(run_dir / "segment_major_candidate_service_telemetry_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "segment_major_candidate_service_telemetry_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
