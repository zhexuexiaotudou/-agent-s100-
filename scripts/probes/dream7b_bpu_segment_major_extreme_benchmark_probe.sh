#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
runtime_dir="${DREAM7B_BPU_SEGMENT_MAJOR_RUNTIME_DIR:-/mnt/nas/openclaw/runtimes/dream7b-bpu-segment-major-default}"
hbm_python="${DREAM7B_BPU_SEGMENT_MAJOR_HBM_PYTHON:-/mnt/nas/openclaw/runtimes/hbm-runtime-venv/bin/python}"
runner_path="${DREAM7B_BPU_EXTREME_RUNNER:-$runtime_dir/scripts/dream7b_bpu_segment_major_load_once_queue_runner.py}"
runner_extra_args_csv="${DREAM7B_BPU_EXTREME_RUNNER_EXTRA_ARGS_CSV:-}"
job_count="${DREAM7B_BPU_EXTREME_JOB_COUNT:-24}"
request_count="${DREAM7B_BPU_EXTREME_REQUEST_COUNT:-256}"
wave_count="${DREAM7B_BPU_EXTREME_WAVE_COUNT:-1}"
top_k="${DREAM7B_BPU_EXTREME_TOP_K:-0}"
monitor_delay_ms="${DREAM7B_BPU_EXTREME_MONITOR_DELAY_MS:-100}"
monitor_sample_count="${DREAM7B_BPU_EXTREME_MONITOR_SAMPLE_COUNT:-15000}"
timeout_sec="${DREAM7B_BPU_EXTREME_TIMEOUT_SEC:-1800}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *) echo "Refusing report path outside approved report directories: $report_root" >&2; exit 2 ;;
esac
case "$runtime_dir" in
  /mnt/nas/openclaw/runtimes/dream7b-bpu-segment-major-default|/mnt/nas/openclaw/tmp/cross_job_queue_repo) ;;
  *) echo "Refusing runtime path outside approved Dream 7B runtime directories: $runtime_dir" >&2; exit 2 ;;
esac
if ! [[ "$job_count" =~ ^[1-9][0-9]*$ ]] || (( job_count < 2 || job_count > 24 )); then
  echo "DREAM7B_BPU_EXTREME_JOB_COUNT must be 2..24." >&2
  exit 2
fi
if ! [[ "$request_count" =~ ^[1-9][0-9]*$ ]] || (( request_count < 1 || request_count > 256 )); then
  echo "DREAM7B_BPU_EXTREME_REQUEST_COUNT must be 1..256." >&2
  exit 2
fi
if ! [[ "$wave_count" =~ ^[1-9][0-9]*$ ]] || (( wave_count < 1 || wave_count > 4 )); then
  echo "DREAM7B_BPU_EXTREME_WAVE_COUNT must be 1..4." >&2
  exit 2
fi
if ! [[ "$top_k" =~ ^[0-9]+$ ]] || (( top_k > 10 )); then
  echo "DREAM7B_BPU_EXTREME_TOP_K must be 0..10." >&2
  exit 2
fi
if [[ ! -x "$hbm_python" ]]; then
  echo "HBM runtime Python is not executable: $hbm_python" >&2
  exit 2
fi
case "$runner_path" in
  "$runtime_dir"/scripts/dream7b_bpu_segment_major_load_once_queue_runner.py|/tmp/dream7b_bpu_segment_major_lite_queue_runner.py|/tmp/dream7b_bpu_segment_major_lite_nogc_queue_runner.py) ;;
  *) echo "Refusing runner path outside approved benchmark runner paths: $runner_path" >&2; exit 2 ;;
esac
runner_extra_args=()
if [[ -n "$runner_extra_args_csv" ]]; then
  IFS=',' read -r -a runner_extra_args <<< "$runner_extra_args_csv"
  for extra_arg in "${runner_extra_args[@]}"; do
    case "$extra_arg" in
      --lite-results|--skip-segment-gc) ;;
      *) echo "Refusing unexpected runner extra arg: $extra_arg" >&2; exit 2 ;;
    esac
  done
fi
if ! command -v hrt_ucp_monitor >/dev/null 2>&1; then
  echo "Missing deployed command: hrt_ucp_monitor" >&2
  exit 4
fi

stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_segment_major_extreme_benchmark_$stamp"
queue_dir="/tmp/dream7b-bpu-extreme-benchmark-$stamp"
jobs_dir="$run_dir/jobs"
mkdir -p "$queue_dir/pending" "$queue_dir/processing" "$queue_dir/done" "$queue_dir/failed" "$jobs_dir"

python3 - "$jobs_dir" "$queue_dir/pending" "$stamp" "$job_count" "$request_count" <<'PY'
import json
import sys
from pathlib import Path

jobs_dir = Path(sys.argv[1])
pending_dir = Path(sys.argv[2])
stamp = sys.argv[3]
job_count = int(sys.argv[4])
request_count = int(sys.argv[5])
for job_index in range(job_count):
    rows = []
    for request_index in range(request_count):
        base = 1000 + ((job_index * request_count + request_index) * 31) % 120000
        rows.append({
            "request_id": f"extreme-segment-major-{stamp}-{job_index + 1:03d}-{request_index + 1:03d}",
            "tokens": [base + offset for offset in range(16)],
        })
    name = f"extreme_segment_major_{stamp}_{job_index + 1:03d}.jsonl"
    text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    (jobs_dir / name).write_text(text, encoding="utf-8")
    (pending_dir / name).write_text(text, encoding="utf-8")
PY

monitor_stdout="$run_dir/hrt_ucp_monitor.stdout"
monitor_stderr="$run_dir/hrt_ucp_monitor.stderr"
runner_stdout="$run_dir/runner.stdout"
runner_stderr="$run_dir/runner.stderr"

hrt_ucp_monitor -b -e bpu -d "$monitor_delay_ms" -n "$monitor_sample_count" > "$monitor_stdout" 2> "$monitor_stderr" &
monitor_pid="$!"
cleanup_monitor() {
  if kill -0 "$monitor_pid" >/dev/null 2>&1; then
    kill "$monitor_pid" >/dev/null 2>&1 || true
    wait "$monitor_pid" >/dev/null 2>&1 || true
  fi
}
trap cleanup_monitor EXIT

runner_status=0
for wave_index in $(seq 1 "$wave_count"); do
  wave_dir="$run_dir/wave_$(printf '%03d' "$wave_index")"
  mkdir -p "$wave_dir"
  if [[ "$wave_index" -gt 1 ]]; then
    rm -f "$queue_dir/pending"/*.jsonl "$queue_dir/processing"/*.jsonl "$queue_dir/done"/*.jsonl "$queue_dir/failed"/*.jsonl 2>/dev/null || true
    python3 - "$jobs_dir" "$queue_dir/pending" "$stamp-wave$wave_index" "$job_count" "$request_count" <<'PY'
import json
import sys
from pathlib import Path

jobs_dir = Path(sys.argv[1])
pending_dir = Path(sys.argv[2])
stamp = sys.argv[3]
job_count = int(sys.argv[4])
request_count = int(sys.argv[5])
for job_index in range(job_count):
    rows = []
    for request_index in range(request_count):
        base = 1000 + ((job_index * request_count + request_index) * 31) % 120000
        rows.append({
            "request_id": f"extreme-segment-major-{stamp}-{job_index + 1:03d}-{request_index + 1:03d}",
            "tokens": [base + offset for offset in range(16)],
        })
    name = f"extreme_segment_major_{stamp}_{job_index + 1:03d}.jsonl"
    text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    (jobs_dir / name).write_text(text, encoding="utf-8")
    (pending_dir / name).write_text(text, encoding="utf-8")
PY
  fi
  set +e
  "$hbm_python" "$runner_path" \
    "$queue_dir" "$wave_dir" \
    --max-job-count "$job_count" \
    --max-job-count-limit 24 \
    --max-batch-size "$request_count" \
    --max-batch-size-limit 256 \
    --top-k "$top_k" \
    --timeout-sec "$timeout_sec" \
    --bpu-lock-path /run/lock/dream7b_bpu_batch_queue_runner.lock \
    "${runner_extra_args[@]}" \
    > "$wave_dir/runner.stdout" 2> "$wave_dir/runner.stderr"
  current_status="$?"
  set -e
  cat "$wave_dir/runner.stdout" >> "$runner_stdout" 2>/dev/null || true
  cat "$wave_dir/runner.stderr" >> "$runner_stderr" 2>/dev/null || true
  if [[ "$current_status" != "0" ]]; then
    runner_status="$current_status"
    break
  fi
done

cleanup_monitor
trap - EXIT

python3 - "$run_dir" "$queue_dir" "$job_count" "$request_count" "$wave_count" "$top_k" "$monitor_delay_ms" "$runner_status" <<'PY'
import json
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
queue_dir = Path(sys.argv[2])
job_count = int(sys.argv[3])
request_count = int(sys.argv[4])
wave_count = int(sys.argv[5])
top_k = int(sys.argv[6])
delay_ms = int(sys.argv[7])
runner_status = int(sys.argv[8])
wave_summaries = sorted(run_dir.glob("wave_*/segment_major_queue_summary.json"))
summaries = [json.loads(path.read_text(encoding="utf-8")) for path in wave_summaries]
summary_path = wave_summaries[-1] if wave_summaries else run_dir / "segment_major_queue_summary.json"
summary = summaries[-1] if summaries else {}
monitor_text = (run_dir / "hrt_ucp_monitor.stdout").read_text(encoding="utf-8", errors="replace")
samples = [float(item) for item in re.findall(r"\|\s*BPU0\s+([0-9]+(?:[.][0-9]+)?)\s*\|", monitor_text)]

def best_window(window):
    if not samples:
        return {"window": window, "avg": 0.0, "start": None, "end": None}
    window = min(window, len(samples))
    current = sum(samples[:window])
    best = current
    best_start = 0
    for idx in range(window, len(samples)):
        current += samples[idx] - samples[idx - window]
        if current > best:
            best = current
            best_start = idx - window + 1
    return {"window": window, "avg": round(best / window, 3), "start": best_start, "end": best_start + window - 1}

nonzero = [item for item in samples if item > 0]
errors = []
if runner_status != 0:
    errors.append(f"runner_status={runner_status}")
if any(item.get("verdict") != "ok_dream7b_bpu_segment_major_load_once_queue_runner" for item in summaries):
    errors.append("one_or_more_runner_verdicts_failed")
total_processed = sum(int(item.get("processed_request_count") or 0) for item in summaries)
total_failed = sum(int(item.get("failed_job_count") or 0) for item in summaries)
if total_processed != job_count * request_count * wave_count:
    errors.append("processed_request_count_mismatch")
if total_failed != 0:
    errors.append("failed_job_count_nonzero")
payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_segment_major_extreme_benchmark_probe" if not errors else "failed_dream7b_bpu_segment_major_extreme_benchmark_probe",
    "run_dir": str(run_dir),
    "queue_dir": str(queue_dir),
    "job_count": job_count,
    "request_count": request_count,
    "wave_count": wave_count,
    "top_k": top_k,
    "runner_status": runner_status,
    "runner_summary_json": str(summary_path),
    "wave_summary_jsons": [str(path) for path in wave_summaries],
    "processed_request_count": total_processed,
    "failed_job_count": total_failed,
    "load_to_run_ratio": summary.get("load_to_run_ratio"),
    "amortized_wall_ms_per_processed_request": round(
        sum(float(item.get("wall_ms") or 0.0) for item in summaries) / max(1, total_processed), 3
    ) if summaries else None,
    "amortized_run_ms_per_processed_request": round(
        sum(float(item.get("total_run_ms") or 0.0) for item in summaries) / max(1, total_processed), 3
    ) if summaries else None,
    "monitor_delay_ms": delay_ms,
    "bpu_loading_sample_count": len(samples),
    "nonzero_bpu_loading_sample_count": len(nonzero),
    "avg_bpu_loading": round(statistics.fmean(samples), 3) if samples else 0.0,
    "avg_nonzero_bpu_loading": round(statistics.fmean(nonzero), 3) if nonzero else 0.0,
    "max_bpu_loading": max(samples) if samples else 0.0,
    "best_windows": {
        "30s": best_window(max(1, int(30 * 1000 / delay_ms))),
        "60s": best_window(max(1, int(60 * 1000 / delay_ms))),
        "120s": best_window(max(1, int(120 * 1000 / delay_ms))),
        "300s": best_window(max(1, int(300 * 1000 / delay_ms))),
        "600s": best_window(max(1, int(600 * 1000 / delay_ms))),
    },
    "default_service_replaced": False,
    "errors": errors,
}
(run_dir / "extreme_benchmark_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
lines = [
    "# Dream 7B Segment-Major Extreme Benchmark Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- job_count: {job_count}",
    f"- request_count: {request_count}",
    f"- wave_count: {wave_count}",
    f"- top_k: {top_k}",
    f"- processed_request_count: {payload['processed_request_count']}",
    f"- failed_job_count: {payload['failed_job_count']}",
    f"- avg_bpu_loading: {payload['avg_bpu_loading']}",
    f"- avg_nonzero_bpu_loading: {payload['avg_nonzero_bpu_loading']}",
    f"- max_bpu_loading: {payload['max_bpu_loading']}",
    f"- load_to_run_ratio: {payload['load_to_run_ratio']}",
    f"- default_service_replaced: False",
    "",
    "## Best Windows",
    "",
]
for name, item in payload["best_windows"].items():
    lines.append(f"- {name}: avg `{item['avg']}` samples `{item['start']}..{item['end']}`")
lines.extend(["", "## Errors", ""])
lines.extend([f"- {item}" for item in errors] or ["- none"])
(run_dir / "extreme_benchmark_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "extreme_benchmark_probe.md")
if errors:
    raise SystemExit(2)
PY
