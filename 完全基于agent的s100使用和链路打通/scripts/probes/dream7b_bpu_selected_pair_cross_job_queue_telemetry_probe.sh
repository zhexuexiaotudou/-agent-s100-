#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
queue_dir="${2:-/tmp/dream7b-bpu-selected-pair-cross-job-telemetry}"
runner_cmd="${DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_RUNNER_CMD:-python3 scripts/dream7b_bpu_selected_pair_cross_job_queue_runner.py}"
forward_probe_cmd="${DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_FORWARD_PROBE_CMD:-scripts/probes/dream7b_bpu_selected_pair_forward_path_probe.sh}"
job_count="${DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_JOB_COUNT:-6}"
job_count_limit="${DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_JOB_COUNT_LIMIT:-12}"
request_count="${DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_REQUEST_COUNT:-16}"
request_count_limit="${DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_REQUEST_COUNT_LIMIT:-16}"
timeout_sec="${DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_TIMEOUT_SEC:-3600}"
monitor_delay_ms="${DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_MONITOR_DELAY_MS:-100}"
monitor_sample_count="${DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_MONITOR_SAMPLE_COUNT:-5000}"
top_k="${DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_TOP_K:-3}"

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

if ! [[ "$job_count_limit" =~ ^[1-9][0-9]*$ ]] || (( job_count_limit < 2 || job_count_limit > 32 )); then
  echo "DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_JOB_COUNT_LIMIT must be an integer from 2 to 32." >&2
  exit 2
fi
if ! [[ "$job_count" =~ ^[1-9][0-9]*$ ]] || (( job_count < 2 || job_count > job_count_limit )); then
  echo "DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_JOB_COUNT must be an integer from 2 to $job_count_limit." >&2
  exit 2
fi
if ! [[ "$request_count_limit" =~ ^[1-9][0-9]*$ ]] || (( request_count_limit < 1 || request_count_limit > 256 )); then
  echo "DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_REQUEST_COUNT_LIMIT must be an integer from 1 to 256." >&2
  exit 2
fi
if ! [[ "$request_count" =~ ^[1-9][0-9]*$ ]] || (( request_count > request_count_limit )); then
  echo "DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_REQUEST_COUNT must be an integer from 1 to $request_count_limit." >&2
  exit 2
fi
if ! [[ "$timeout_sec" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_TIMEOUT_SEC must be a positive integer." >&2
  exit 2
fi
if ! [[ "$monitor_delay_ms" =~ ^[0-9]+$ ]] || (( monitor_delay_ms < 100 || monitor_delay_ms > 10000 )); then
  echo "DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_MONITOR_DELAY_MS must be an integer from 100 to 10000." >&2
  exit 2
fi
if ! [[ "$monitor_sample_count" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_MONITOR_SAMPLE_COUNT must be a positive integer." >&2
  exit 2
fi
if ! [[ "$top_k" =~ ^[0-9]+$ ]]; then
  echo "DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_TOP_K must be a non-negative integer." >&2
  exit 2
fi
if ! command -v hrt_ucp_monitor >/dev/null 2>&1; then
  echo "Missing deployed command: hrt_ucp_monitor" >&2
  exit 4
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_selected_pair_cross_job_queue_telemetry_$stamp"
runner_output_dir="$run_dir/runner"
jobs_dir="$run_dir/jobs"
mkdir -p "$run_dir" "$runner_output_dir" "$jobs_dir"
rm -rf "$queue_dir"
mkdir -p "$queue_dir/pending" "$queue_dir/processing" "$queue_dir/done" "$queue_dir/failed"

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
                "request_id": f"cross-job-telemetry-{stamp}-{job_index + 1:03d}-{request_index + 1:03d}",
                "tokens": [base + offset for offset in range(1, 17)],
            }
        )
    (jobs_dir / f"job_{job_index + 1:03d}.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
PY

for job_path in "$jobs_dir"/*.jsonl; do
  cp "$job_path" "$queue_dir/pending/$(basename "$job_path")"
done

monitor_stdout="$run_dir/hrt_ucp_monitor.stdout"
monitor_stderr="$run_dir/hrt_ucp_monitor.stderr"
runner_stdout="$run_dir/runner.stdout"
runner_stderr="$run_dir/runner.stderr"

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

set +e
$runner_cmd \
  "$queue_dir" \
  "$runner_output_dir" \
  --max-job-count "$job_count" \
  --max-job-count-limit "$job_count_limit" \
  --max-batch-size "$request_count" \
  --max-batch-size-limit "$request_count_limit" \
  --top-k "$top_k" \
  --timeout-sec "$timeout_sec" \
  --bpu-lock-path /tmp/dream7b_cross_job_queue_telemetry.lock \
  --forward-probe-cmd "$forward_probe_cmd" > "$runner_stdout" 2> "$runner_stderr"
runner_status="$?"
set -e

cleanup_monitor
trap - EXIT

python3 - \
  "$run_dir" \
  "$queue_dir" \
  "$runner_output_dir" \
  "$job_count" \
  "$request_count" \
  "$timeout_sec" \
  "$monitor_delay_ms" \
  "$monitor_sample_count" \
  "$runner_status" <<'PY'
import json
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
queue_dir = Path(sys.argv[2])
runner_output_dir = Path(sys.argv[3])
job_count = int(sys.argv[4])
request_count = int(sys.argv[5])
timeout_sec = int(sys.argv[6])
monitor_delay_ms = int(sys.argv[7])
monitor_sample_count = int(sys.argv[8])
runner_status = int(sys.argv[9])

errors = []
warnings = []
monitor_text = (run_dir / "hrt_ucp_monitor.stdout").read_text(encoding="utf-8", errors="replace")
monitor_err = (run_dir / "hrt_ucp_monitor.stderr").read_text(encoding="utf-8", errors="replace")
bpu_loading_samples = [float(item) for item in re.findall(r"\|\s*BPU0\s+([0-9]+(?:[.][0-9]+)?)\s*\|", monitor_text)]
max_bpu_loading = max(bpu_loading_samples) if bpu_loading_samples else 0.0
avg_bpu_loading = statistics.fmean(bpu_loading_samples) if bpu_loading_samples else 0.0
nonzero_bpu_loading_sample_count = sum(1 for item in bpu_loading_samples if item > 0.0)
if not bpu_loading_samples:
    errors.append("hrt_ucp_monitor produced no BPU0 loading samples")
if nonzero_bpu_loading_sample_count <= 0:
    errors.append("hrt_ucp_monitor produced no nonzero BPU0 loading samples")
if runner_status != 0:
    errors.append(f"cross-job queue runner returned {runner_status}")

summary_path = runner_output_dir / "cross_job_queue_summary.json"
runner = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.is_file() else {}
if not summary_path.is_file():
    errors.append(f"missing runner summary: {summary_path}")
if runner.get("verdict") != "ok_dream7b_bpu_selected_pair_cross_job_queue_runner":
    errors.append(f"unexpected runner verdict: {runner.get('verdict')}")
if int(runner.get("processed_job_count") or 0) != job_count:
    errors.append(f"unexpected processed_job_count: {runner.get('processed_job_count')}")
expected_request_total = job_count * request_count
if int(runner.get("processed_request_count") or 0) != expected_request_total:
    errors.append(f"unexpected processed_request_count: {runner.get('processed_request_count')}")
if int(runner.get("failed_job_count") or 0) != 0:
    errors.append(f"unexpected failed_job_count: {runner.get('failed_job_count')}")
if runner.get("selected_pair") != [1, 8]:
    errors.append(f"unexpected selected_pair: {runner.get('selected_pair')}")
if runner.get("selected_pair_covers_all_segments") is not True:
    errors.append(f"selected_pair_covers_all_segments is not true: {runner.get('selected_pair_covers_all_segments')}")
if runner.get("errors"):
    errors.extend(f"runner error: {item}" for item in runner.get("errors", []))

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_selected_pair_cross_job_queue_telemetry_probe" if not errors else "failed_dream7b_bpu_selected_pair_cross_job_queue_telemetry_probe",
    "run_dir": str(run_dir),
    "queue_dir": str(queue_dir),
    "runner_output_dir": str(runner_output_dir),
    "runner_summary_json": str(summary_path),
    "job_count": job_count,
    "request_count": request_count,
    "processed_request_count": runner.get("processed_request_count"),
    "failed_job_count": runner.get("failed_job_count"),
    "timeout_sec": timeout_sec,
    "monitor_delay_ms": monitor_delay_ms,
    "monitor_sample_count": monitor_sample_count,
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
(run_dir / "cross_job_queue_telemetry_probe.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
lines = [
    "# Dream 7B Selected-Pair Cross-Job Queue Telemetry Probe",
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
(run_dir / "cross_job_queue_telemetry_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "cross_job_queue_telemetry_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
