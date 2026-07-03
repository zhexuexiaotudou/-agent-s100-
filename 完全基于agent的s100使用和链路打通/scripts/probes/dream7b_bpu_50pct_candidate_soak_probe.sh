#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
queue_dir="${2:-/tmp/dream7b-bpu-50pct-candidate-soak}"
target_duration_sec="${DREAM7B_BPU_50PCT_SOAK_TARGET_DURATION_SEC:-1800}"
min_iteration_count="${DREAM7B_BPU_50PCT_SOAK_MIN_ITERATION_COUNT:-2}"
job_count="${DREAM7B_BPU_50PCT_SOAK_JOB_COUNT:-2}"
request_count="${DREAM7B_BPU_50PCT_SOAK_REQUEST_COUNT:-192}"
request_count_limit="${DREAM7B_BPU_50PCT_SOAK_REQUEST_COUNT_LIMIT:-256}"
min_avg_bpu="${DREAM7B_BPU_50PCT_SOAK_MIN_AVG_BPU:-45.0}"
max_load_to_run_ratio="${DREAM7B_BPU_50PCT_SOAK_MAX_LOAD_TO_RUN_RATIO:-1.5}"
base_probe="${DREAM7B_BPU_50PCT_SOAK_BASE_PROBE:-scripts/probes/dream7b_bpu_selected_pair_cross_job_queue_telemetry_probe.sh}"
forward_probe_cmd="${DREAM7B_BPU_50PCT_SOAK_FORWARD_PROBE_CMD:-bash scripts/probes/dream7b_bpu_selected_pair_forward_path_probe.sh}"

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

if ! [[ "$target_duration_sec" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_50PCT_SOAK_TARGET_DURATION_SEC must be a positive integer." >&2
  exit 2
fi
if ! [[ "$min_iteration_count" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_50PCT_SOAK_MIN_ITERATION_COUNT must be a positive integer." >&2
  exit 2
fi
if ! [[ "$job_count" =~ ^[1-9][0-9]*$ ]] || (( job_count < 2 || job_count > 32 )); then
  echo "DREAM7B_BPU_50PCT_SOAK_JOB_COUNT must be an integer from 2 to 32." >&2
  exit 2
fi
if ! [[ "$request_count" =~ ^[1-9][0-9]*$ ]] || (( request_count > request_count_limit )); then
  echo "DREAM7B_BPU_50PCT_SOAK_REQUEST_COUNT must be an integer from 1 to request_count_limit." >&2
  exit 2
fi
if [[ ! -f "$base_probe" ]]; then
  echo "Missing base telemetry probe: $base_probe" >&2
  exit 4
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_50pct_candidate_soak_$stamp"
mkdir -p "$run_dir/iterations"

started_epoch="$(date +%s)"
iteration=0
base_jsonl="$run_dir/base_reports.jsonl"
: > "$base_jsonl"

while true; do
  iteration=$((iteration + 1))
  iter_dir="$run_dir/iterations/$(printf '%03d' "$iteration")"
  mkdir -p "$iter_dir"
  iter_stdout="$iter_dir/base_probe.stdout"
  iter_stderr="$iter_dir/base_probe.stderr"
  iter_queue_dir="$queue_dir/$(printf '%03d' "$iteration")"

  set +e
  DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_JOB_COUNT="$job_count" \
  DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_JOB_COUNT_LIMIT="$job_count" \
  DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_REQUEST_COUNT="$request_count" \
  DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_REQUEST_COUNT_LIMIT="$request_count_limit" \
  DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_FORWARD_PROBE_CMD="$forward_probe_cmd" \
  bash "$base_probe" "$report_root" "$iter_queue_dir" > "$iter_stdout" 2> "$iter_stderr"
  iter_status="$?"
  set -e

  python3 - "$iter_stdout" "$iter_stderr" "$iter_status" "$base_jsonl" <<'PY'
import json
import sys
from pathlib import Path

stdout_path = Path(sys.argv[1])
stderr_path = Path(sys.argv[2])
status = int(sys.argv[3])
jsonl_path = Path(sys.argv[4])

report_json = ""
for raw in reversed(stdout_path.read_text(encoding="utf-8", errors="replace").splitlines()):
    line = raw.strip()
    if line.endswith("cross_job_queue_telemetry_probe.md"):
        candidate = Path(line).with_suffix(".json")
        if candidate.is_file():
            report_json = str(candidate)
        break

payload = {
    "base_status": status,
    "base_stdout": str(stdout_path),
    "base_stderr": str(stderr_path),
    "base_report_json": report_json,
}
if report_json:
    payload.update(json.loads(Path(report_json).read_text(encoding="utf-8")))
else:
    payload["errors"] = [f"base telemetry status={status}; no JSON found"]
with jsonl_path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
if status != 0:
    raise SystemExit(status)
PY

  now_epoch="$(date +%s)"
  elapsed_sec=$((now_epoch - started_epoch))
  if (( iteration >= min_iteration_count && elapsed_sec >= target_duration_sec )); then
    break
  fi
done

python3 - \
  "$run_dir" \
  "$base_jsonl" \
  "$started_epoch" \
  "$target_duration_sec" \
  "$min_iteration_count" \
  "$job_count" \
  "$request_count" \
  "$min_avg_bpu" \
  "$max_load_to_run_ratio" <<'PY'
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
base_jsonl = Path(sys.argv[2])
started_epoch = int(sys.argv[3])
target_duration_sec = int(sys.argv[4])
min_iteration_count = int(sys.argv[5])
job_count = int(sys.argv[6])
request_count = int(sys.argv[7])
min_avg_bpu = float(sys.argv[8])
max_load_to_run_ratio = float(sys.argv[9])

rows = [json.loads(line) for line in base_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
elapsed_sec = int(time.time()) - started_epoch
errors = []
warnings = []

iteration_count = len(rows)
processed = sum(int(row.get("processed_request_count") or 0) for row in rows)
failed_jobs = sum(int(row.get("failed_job_count") or 0) for row in rows)
avg_bpus = [float(row.get("avg_bpu_loading")) for row in rows if row.get("avg_bpu_loading") is not None]
ratios = [float(row.get("load_to_run_ratio")) for row in rows if row.get("load_to_run_ratio") is not None]
walls = [float(row.get("amortized_wall_ms_per_processed_request")) for row in rows if row.get("amortized_wall_ms_per_processed_request") is not None]
weighted_avg_bpu = statistics.fmean(avg_bpus) if avg_bpus else 0.0
avg_ratio = statistics.fmean(ratios) if ratios else 0.0
avg_wall = statistics.fmean(walls) if walls else 0.0
min_iteration_bpu = min(avg_bpus) if avg_bpus else 0.0
max_iteration_ratio = max(ratios) if ratios else 0.0

for index, row in enumerate(rows, start=1):
    if row.get("verdict") != "ok_dream7b_bpu_selected_pair_cross_job_queue_telemetry_probe":
        errors.append(f"iteration {index} unexpected verdict: {row.get('verdict')}")
    if int(row.get("failed_job_count") or 0) != 0:
        errors.append(f"iteration {index} failed_job_count is nonzero: {row.get('failed_job_count')}")

if elapsed_sec < target_duration_sec:
    errors.append(f"elapsed_sec below target: {elapsed_sec} < {target_duration_sec}")
if iteration_count < min_iteration_count:
    errors.append(f"iteration_count below target: {iteration_count} < {min_iteration_count}")
if failed_jobs != 0:
    errors.append(f"failed_job_count is nonzero: {failed_jobs}")
if weighted_avg_bpu < min_avg_bpu:
    errors.append(f"avg_bpu_loading below target: {weighted_avg_bpu:.3f} < {min_avg_bpu}")
if max_iteration_ratio > max_load_to_run_ratio:
    errors.append(f"max iteration load_to_run_ratio above target: {max_iteration_ratio:.6f} > {max_load_to_run_ratio}")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_50pct_candidate_soak_probe" if not errors else "failed_dream7b_bpu_50pct_candidate_soak_probe",
    "run_dir": str(run_dir),
    "base_reports_jsonl": str(base_jsonl),
    "target_duration_sec": target_duration_sec,
    "elapsed_sec": elapsed_sec,
    "min_iteration_count": min_iteration_count,
    "iteration_count": iteration_count,
    "job_count_per_iteration": job_count,
    "request_count_per_job": request_count,
    "processed_request_count": processed,
    "failed_job_count": failed_jobs,
    "avg_bpu_loading": round(weighted_avg_bpu, 3),
    "min_iteration_avg_bpu_loading": round(min_iteration_bpu, 3),
    "avg_load_to_run_ratio": round(avg_ratio, 6),
    "max_iteration_load_to_run_ratio": round(max_iteration_ratio, 6),
    "avg_amortized_wall_ms_per_processed_request": round(avg_wall, 3),
    "min_avg_bpu": min_avg_bpu,
    "max_load_to_run_ratio": max_load_to_run_ratio,
    "default_service_replaced": False,
    "rollback_status": "rollback_safe_candidate_only",
    "warnings": warnings,
    "errors": errors,
    "iterations": rows,
}
(run_dir / "50pct_candidate_soak_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
lines = [
    "# Dream 7B 50 Percent Candidate Soak Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- elapsed_sec: {payload['elapsed_sec']}",
    f"- iteration_count: {payload['iteration_count']}",
    f"- processed_request_count: {payload['processed_request_count']}",
    f"- failed_job_count: {payload['failed_job_count']}",
    f"- avg_bpu_loading: {payload['avg_bpu_loading']}",
    f"- min_iteration_avg_bpu_loading: {payload['min_iteration_avg_bpu_loading']}",
    f"- avg_load_to_run_ratio: {payload['avg_load_to_run_ratio']}",
    f"- max_iteration_load_to_run_ratio: {payload['max_iteration_load_to_run_ratio']}",
    f"- rollback_status: {payload['rollback_status']}",
    f"- default_service_replaced: {payload['default_service_replaced']}",
    "",
    "## Iterations",
    "",
]
for index, row in enumerate(rows, start=1):
    lines.append(
        f"- {index}: report=`{row.get('base_report_json')}` "
        f"avg_bpu={row.get('avg_bpu_loading')} "
        f"load_to_run={row.get('load_to_run_ratio')} "
        f"processed={row.get('processed_request_count')} "
        f"failed={row.get('failed_job_count')}"
    )
lines.extend(["", "## Errors", ""])
lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
(run_dir / "50pct_candidate_soak_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "50pct_candidate_soak_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
