#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
queue_dir="${2:-/mnt/nas/openclaw/queues/dream7b-bpu-selected-pair-cross-job-candidate-50pct}"
service_output_dir="${3:-/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_candidate_50pct_service}"
service_name="${DREAM7B_BPU_50PCT_PREFETCH_SERVICE_NAME:-dream7b-bpu-selected-pair-cross-job-candidate-50pct.service}"
prefill_with_service_pause="${DREAM7B_BPU_50PCT_PREFETCH_PREFILL_WITH_SERVICE_PAUSE:-1}"
total_job_count="${DREAM7B_BPU_50PCT_PREFETCH_TOTAL_JOB_COUNT:-24}"
target_pending_jobs="${DREAM7B_BPU_50PCT_PREFETCH_TARGET_PENDING_JOBS:-12}"
request_count="${DREAM7B_BPU_50PCT_PREFETCH_REQUEST_COUNT:-192}"
timeout_sec="${DREAM7B_BPU_50PCT_PREFETCH_TIMEOUT_SEC:-2400}"
monitor_delay_ms="${DREAM7B_BPU_50PCT_PREFETCH_MONITOR_DELAY_MS:-100}"
monitor_sample_count="${DREAM7B_BPU_50PCT_PREFETCH_MONITOR_SAMPLE_COUNT:-24000}"
baseline_avg_bpu="${DREAM7B_BPU_50PCT_PREFETCH_BASELINE_AVG_BPU:-53.459}"
baseline_load_to_run_ratio="${DREAM7B_BPU_50PCT_PREFETCH_BASELINE_LOAD_TO_RUN_RATIO:-0.734513}"
target_avg_bpu="${DREAM7B_BPU_50PCT_PREFETCH_TARGET_AVG_BPU:-70.0}"
target_load_to_run_ratio="${DREAM7B_BPU_50PCT_PREFETCH_TARGET_LOAD_TO_RUN_RATIO:-0.6}"

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

if ! [[ "$total_job_count" =~ ^[1-9][0-9]*$ ]] || (( total_job_count < 12 || total_job_count > 48 )); then
  echo "DREAM7B_BPU_50PCT_PREFETCH_TOTAL_JOB_COUNT must be 12..48." >&2
  exit 2
fi
if ! [[ "$target_pending_jobs" =~ ^[1-9][0-9]*$ ]] || (( target_pending_jobs < 2 || target_pending_jobs > 12 )); then
  echo "DREAM7B_BPU_50PCT_PREFETCH_TARGET_PENDING_JOBS must be 2..12." >&2
  exit 2
fi
if ! [[ "$request_count" =~ ^[1-9][0-9]*$ ]] || (( request_count < 1 || request_count > 192 )); then
  echo "DREAM7B_BPU_50PCT_PREFETCH_REQUEST_COUNT must be 1..192." >&2
  exit 2
fi
case "$prefill_with_service_pause" in
  0|1) ;;
  *)
    echo "DREAM7B_BPU_50PCT_PREFETCH_PREFILL_WITH_SERVICE_PAUSE must be 0 or 1." >&2
    exit 2
    ;;
esac
if ! [[ "$timeout_sec" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_50PCT_PREFETCH_TIMEOUT_SEC must be a positive integer." >&2
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
job_prefix="service_50pct_prefetch_${stamp}"
run_dir="$report_root/dream7b_bpu_50pct_candidate_service_continuous_prefetch_$stamp"
jobs_dir="$run_dir/jobs"
mkdir -p "$run_dir" "$jobs_dir" "$queue_dir/pending" "$queue_dir/processing" "$queue_dir/done" "$queue_dir/failed"
started_epoch="$(date +%s)"

pending_busy_count="$(find "$queue_dir/pending" "$queue_dir/processing" -maxdepth 1 -type f -name '*.jsonl' 2>/dev/null | wc -l | tr -d ' ')"
if [[ "$pending_busy_count" != "0" ]]; then
  echo "Refusing to start while candidate queue has pending or processing jobs: $pending_busy_count" >&2
  exit 6
fi

python3 - "$jobs_dir" "$job_prefix" "$total_job_count" "$request_count" <<'PY'
import json
import sys
from pathlib import Path

jobs_dir = Path(sys.argv[1])
job_prefix = sys.argv[2]
total_job_count = int(sys.argv[3])
request_count = int(sys.argv[4])

for job_index in range(total_job_count):
    rows = []
    for request_index in range(request_count):
        ordinal = job_index * request_count + request_index
        base = 1000 + ((ordinal * 17) % 120000)
        rows.append(
            {
                "request_id": f"{job_prefix}-{job_index + 1:03d}-{request_index + 1:03d}",
                "tokens": [base + offset for offset in range(1, 17)],
            }
        )
    (jobs_dir / f"{job_prefix}_{job_index + 1:03d}.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
PY

monitor_stdout="$run_dir/hrt_ucp_monitor.stdout"
monitor_stderr="$run_dir/hrt_ucp_monitor.stderr"
feeder_log="$run_dir/feeder.log"
service_status_before="$run_dir/service_status_before.txt"
service_status_after="$run_dir/service_status_after.txt"
systemctl --no-pager --full status "$service_name" > "$service_status_before" 2>&1 || true

service_paused=0
if [[ "$prefill_with_service_pause" == "1" ]]; then
  sudo systemctl stop "$service_name"
  service_paused=1
fi

hrt_ucp_monitor -b -e bpu -d "$monitor_delay_ms" -n "$monitor_sample_count" > "$monitor_stdout" 2> "$monitor_stderr" &
monitor_pid="$!"

cleanup_monitor() {
  if kill -0 "$monitor_pid" >/dev/null 2>&1; then
    kill "$monitor_pid" >/dev/null 2>&1 || true
    wait "$monitor_pid" >/dev/null 2>&1 || true
  fi
}
restore_service_if_paused() {
  if (( service_paused == 1 )); then
    sudo systemctl start "$service_name" >/dev/null 2>&1 || true
    service_paused=0
  fi
}
cleanup() {
  cleanup_monitor
  restore_service_if_paused
}
trap cleanup EXIT

deadline=$(( $(date +%s) + timeout_sec ))
generated_count=0

own_count_in_dir() {
  local subdir="$1"
  find "$queue_dir/$subdir" -maxdepth 1 -type f -name "${job_prefix}_*.jsonl" 2>/dev/null | wc -l | tr -d ' '
}

copy_next_job() {
  generated_count=$((generated_count + 1))
  local source="$jobs_dir/${job_prefix}_$(printf '%03d' "$generated_count").jsonl"
  local target="$queue_dir/pending/$(basename "$source")"
  local tmp_target="$target.tmp.$$"
  cp "$source" "$tmp_target"
  mv "$tmp_target" "$target"
  printf '%s generated=%s pending=%s processing=%s done=%s failed=%s\n' \
    "$(date --iso-8601=seconds)" \
    "$generated_count" \
    "$(own_count_in_dir pending)" \
    "$(own_count_in_dir processing)" \
    "$(own_count_in_dir done)" \
    "$(own_count_in_dir failed)" >> "$feeder_log"
}

while true; do
  pending_count="$(own_count_in_dir pending)"
  while (( generated_count < total_job_count && pending_count < target_pending_jobs )); do
    copy_next_job
    pending_count="$(own_count_in_dir pending)"
  done
  if (( service_paused == 1 )); then
    sudo systemctl start "$service_name"
    service_paused=0
    printf '%s service_started_after_prefill pending=%s\n' \
      "$(date --iso-8601=seconds)" \
      "$(own_count_in_dir pending)" >> "$feeder_log"
  fi

  done_count="$(own_count_in_dir done)"
  failed_count="$(own_count_in_dir failed)"
  processing_count="$(own_count_in_dir processing)"
  printf '%s heartbeat generated=%s pending=%s processing=%s done=%s failed=%s\n' \
    "$(date --iso-8601=seconds)" \
    "$generated_count" "$pending_count" "$processing_count" "$done_count" "$failed_count" >> "$feeder_log"

  if (( done_count + failed_count >= total_job_count )); then
    break
  fi
  if (( $(date +%s) >= deadline )); then
    break
  fi
  sleep 2
done

cleanup_monitor
trap - EXIT
systemctl --no-pager --full status "$service_name" > "$service_status_after" 2>&1 || true

python3 - \
  "$run_dir" \
  "$queue_dir" \
  "$service_output_dir" \
  "$service_name" \
  "$job_prefix" \
  "$started_epoch" \
  "$prefill_with_service_pause" \
  "$total_job_count" \
  "$target_pending_jobs" \
  "$request_count" \
  "$timeout_sec" \
  "$monitor_delay_ms" \
  "$monitor_sample_count" \
  "$baseline_avg_bpu" \
  "$baseline_load_to_run_ratio" \
  "$target_avg_bpu" \
  "$target_load_to_run_ratio" <<'PY'
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
job_prefix = sys.argv[5]
started_epoch = int(sys.argv[6])
prefill_with_service_pause = sys.argv[7] == "1"
total_job_count = int(sys.argv[8])
target_pending_jobs = int(sys.argv[9])
request_count = int(sys.argv[10])
timeout_sec = int(sys.argv[11])
monitor_delay_ms = int(sys.argv[12])
monitor_sample_count = int(sys.argv[13])
baseline_avg_bpu = float(sys.argv[14])
baseline_load_to_run_ratio = float(sys.argv[15])
target_avg_bpu = float(sys.argv[16])
target_load_to_run_ratio = float(sys.argv[17])

errors = []
warnings = []
done_jobs = sorted((queue_dir / "done").glob(f"{job_prefix}_*.jsonl"))
failed_jobs = sorted((queue_dir / "failed").glob(f"{job_prefix}_*.jsonl"))
pending_jobs = sorted((queue_dir / "pending").glob(f"{job_prefix}_*.jsonl"))
processing_jobs = sorted((queue_dir / "processing").glob(f"{job_prefix}_*.jsonl"))

if len(done_jobs) + len(failed_jobs) != total_job_count:
    errors.append(
        f"terminal job count mismatch: done={len(done_jobs)} failed={len(failed_jobs)} expected={total_job_count}"
    )
if failed_jobs:
    errors.append(f"failed job count is nonzero: {len(failed_jobs)}")
if pending_jobs or processing_jobs:
    errors.append(f"jobs left nonterminal: pending={len(pending_jobs)} processing={len(processing_jobs)}")

summary_candidates = []
for raw in glob.glob(str(service_output_dir / "runs" / "*" / "cross_job_queue_summary.json")):
    path = Path(raw)
    if path.stat().st_mtime < started_epoch:
        continue
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        continue
    result_ids = [item.get("request_id", "") for item in data.get("results") or []]
    if any(str(item).startswith(job_prefix) for item in result_ids):
        summary_candidates.append((path, data))
summary_candidates.sort(key=lambda item: item[0].stat().st_mtime)

if not summary_candidates:
    errors.append("missing service runner summaries for continuous prefetch jobs")

processed_job_count = sum(int(data.get("processed_job_count") or 0) for _, data in summary_candidates)
processed_request_count = sum(int(data.get("processed_request_count") or 0) for _, data in summary_candidates)
runner_failed_job_count = sum(int(data.get("failed_job_count") or 0) for _, data in summary_candidates)
expected_processed = total_job_count * request_count
if processed_job_count != len(done_jobs):
    errors.append(f"processed_job_count mismatch: {processed_job_count} != done_job_count {len(done_jobs)}")
if processed_request_count != expected_processed:
    errors.append(f"processed_request_count mismatch: {processed_request_count} != expected {expected_processed}")
if runner_failed_job_count:
    errors.append(f"runner failed_job_count is nonzero: {runner_failed_job_count}")

weighted_load = sum(float(data.get("selected_total_load_ms") or 0.0) for _, data in summary_candidates)
weighted_run = sum(float(data.get("run_ms") or 0.0) for _, data in summary_candidates)
weighted_wall = sum(float(data.get("wall_ms") or 0.0) for _, data in summary_candidates)
aggregate_load_to_run_ratio = round(weighted_load / weighted_run, 6) if weighted_run else None
amortized_wall_ms = round(weighted_wall / processed_request_count, 3) if processed_request_count else None
amortized_load_ms = round(weighted_load / processed_request_count, 3) if processed_request_count else None
amortized_run_ms = round(weighted_run / processed_request_count, 3) if processed_request_count else None

monitor_text = (run_dir / "hrt_ucp_monitor.stdout").read_text(encoding="utf-8", errors="replace")
bpu_loading_samples = [float(item) for item in re.findall(r"\|\s*BPU0\s+([0-9]+(?:[.][0-9]+)?)\s*\|", monitor_text)]
avg_bpu_loading = statistics.fmean(bpu_loading_samples) if bpu_loading_samples else 0.0
max_bpu_loading = max(bpu_loading_samples) if bpu_loading_samples else 0.0
nonzero_count = sum(1 for item in bpu_loading_samples if item > 0.0)
if not bpu_loading_samples:
    errors.append("hrt_ucp_monitor produced no BPU0 loading samples")
if nonzero_count <= 0:
    errors.append("hrt_ucp_monitor produced no nonzero BPU0 loading samples")

avg_bpu_delta_vs_baseline = round(avg_bpu_loading - baseline_avg_bpu, 3)
ratio_delta_vs_baseline = (
    round(float(aggregate_load_to_run_ratio) - baseline_load_to_run_ratio, 6)
    if aggregate_load_to_run_ratio is not None
    else None
)

if avg_bpu_loading < target_avg_bpu:
    warnings.append(f"continuous prefetch avg BPU remains below {target_avg_bpu}%")
if aggregate_load_to_run_ratio is not None and aggregate_load_to_run_ratio > target_load_to_run_ratio:
    warnings.append(
        f"continuous prefetch load_to_run_ratio {aggregate_load_to_run_ratio} remains above target {target_load_to_run_ratio}"
    )
if avg_bpu_delta_vs_baseline < 2.0:
    warnings.append("continuous prefetch did not materially improve average BPU versus 12x192 backlog baseline")

decision = "continuous_prefetch_plateau_below_70_percent"
if avg_bpu_loading >= target_avg_bpu:
    decision = "continuous_prefetch_progress_candidate"
if aggregate_load_to_run_ratio is not None and aggregate_load_to_run_ratio <= target_load_to_run_ratio:
    decision = "continuous_prefetch_ratio_progress_candidate"
if (
    avg_bpu_loading >= target_avg_bpu
    and aggregate_load_to_run_ratio is not None
    and aggregate_load_to_run_ratio <= target_load_to_run_ratio
):
    decision = "continuous_prefetch_meets_stage2_gate"

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_50pct_candidate_service_continuous_prefetch_probe" if not errors else "failed_dream7b_bpu_50pct_candidate_service_continuous_prefetch_probe",
    "decision": decision,
    "run_dir": str(run_dir),
    "service_name": service_name,
    "prefill_with_service_pause": prefill_with_service_pause,
    "queue_dir": str(queue_dir),
    "service_output_dir": str(service_output_dir),
    "job_prefix": job_prefix,
    "total_job_count": total_job_count,
    "target_pending_jobs": target_pending_jobs,
    "request_count": request_count,
    "processed_job_count": processed_job_count,
    "processed_request_count": processed_request_count,
    "failed_job_count": runner_failed_job_count,
    "done_job_count": len(done_jobs),
    "queue_failed_job_count": len(failed_jobs),
    "pending_job_count": len(pending_jobs),
    "processing_job_count": len(processing_jobs),
    "runner_summary_count": len(summary_candidates),
    "runner_summaries": [str(path) for path, _ in summary_candidates],
    "timeout_sec": timeout_sec,
    "monitor_delay_ms": monitor_delay_ms,
    "monitor_sample_count": monitor_sample_count,
    "bpu_loading_sample_count": len(bpu_loading_samples),
    "nonzero_bpu_loading_sample_count": nonzero_count,
    "avg_bpu_loading": round(avg_bpu_loading, 3),
    "max_bpu_loading": round(max_bpu_loading, 3),
    "baseline_avg_bpu_loading": baseline_avg_bpu,
    "avg_bpu_delta_vs_baseline": avg_bpu_delta_vs_baseline,
    "aggregate_load_to_run_ratio": aggregate_load_to_run_ratio,
    "baseline_load_to_run_ratio": baseline_load_to_run_ratio,
    "load_to_run_ratio_delta_vs_baseline": ratio_delta_vs_baseline,
    "amortized_wall_ms_per_processed_request": amortized_wall_ms,
    "amortized_total_load_ms_per_processed_request": amortized_load_ms,
    "amortized_run_ms_per_processed_request": amortized_run_ms,
    "target_avg_bpu": target_avg_bpu,
    "target_load_to_run_ratio": target_load_to_run_ratio,
    "default_service_replaced": False,
    "rollback_command": "sudo systemctl disable --now dream7b-bpu-selected-pair-cross-job-candidate-50pct.service",
    "next_actions": [
        "if this remains below 70 percent, stop treating outer queue refill as the primary bottleneck",
        "move the next optimization to resident segment topology and load-once execution",
        "keep the vendor package focused on Dream adapter, HBM layout, and runtime memory pool because load_to_run_ratio remains above the 90 percent gate",
    ],
    "warnings": warnings,
    "errors": errors,
}

(run_dir / "50pct_candidate_service_continuous_prefetch_probe.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

lines = [
    "# Dream 7B 50 Percent Candidate Service Continuous Prefetch Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- decision: {payload['decision']}",
    f"- service_name: {service_name}",
    f"- prefill_with_service_pause: {payload['prefill_with_service_pause']}",
    f"- total_job_count: {payload['total_job_count']}",
    f"- target_pending_jobs: {payload['target_pending_jobs']}",
    f"- processed_request_count: {payload['processed_request_count']}",
    f"- failed_job_count: {payload['failed_job_count']}",
    f"- runner_summary_count: {payload['runner_summary_count']}",
    f"- avg_bpu_loading: {payload['avg_bpu_loading']}",
    f"- avg_bpu_delta_vs_baseline: {payload['avg_bpu_delta_vs_baseline']}",
    f"- max_bpu_loading: {payload['max_bpu_loading']}",
    f"- aggregate_load_to_run_ratio: {payload['aggregate_load_to_run_ratio']}",
    f"- load_to_run_ratio_delta_vs_baseline: {payload['load_to_run_ratio_delta_vs_baseline']}",
    f"- amortized_wall_ms_per_processed_request: {payload['amortized_wall_ms_per_processed_request']}",
    f"- default_service_replaced: {payload['default_service_replaced']}",
    f"- rollback_command: `{payload['rollback_command']}`",
    "",
    "## Runner Summaries",
    "",
]
lines.extend(f"- {item}" for item in payload["runner_summaries"]) if payload["runner_summaries"] else lines.append("- none")
lines.extend(["", "## Next Actions", ""])
for item in payload["next_actions"]:
    lines.append(f"- {item}")
lines.extend(["", "## Errors", ""])
lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
lines.extend(["", "## Warnings", ""])
lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- none")
(run_dir / "50pct_candidate_service_continuous_prefetch_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "50pct_candidate_service_continuous_prefetch_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
