#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
runner_path="${DREAM7B_BPU_PHASE_TIMING_RUNNER:-/tmp/dream7b_bpu_segment_major_lite_queue_runner.py}"
hbm_python="${DREAM7B_BPU_PHASE_TIMING_HBM_PYTHON:-/mnt/nas/openclaw/runtimes/hbm-runtime-venv/bin/python}"
job_count="${DREAM7B_BPU_PHASE_TIMING_JOB_COUNT:-2}"
request_count="${DREAM7B_BPU_PHASE_TIMING_REQUEST_COUNT:-16}"
top_k="${DREAM7B_BPU_PHASE_TIMING_TOP_K:-0}"
monitor_delay_ms="${DREAM7B_BPU_PHASE_TIMING_MONITOR_DELAY_MS:-100}"
monitor_sample_count="${DREAM7B_BPU_PHASE_TIMING_MONITOR_SAMPLE_COUNT:-1200}"
timeout_sec="${DREAM7B_BPU_PHASE_TIMING_TIMEOUT_SEC:-600}"
raw_final="${DREAM7B_BPU_PHASE_TIMING_RAW_FINAL:-0}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *) echo "Refusing report path outside approved report directories: $report_root" >&2; exit 2 ;;
esac
case "$runner_path" in
  /tmp/dream7b_bpu_segment_major_lite_queue_runner.py|/tmp/dream7b_bpu_segment_major_lite_nogc_queue_runner.py|/mnt/nas/openclaw/runtimes/dream7b-bpu-segment-major-default/scripts/dream7b_bpu_segment_major_load_once_queue_runner.py) ;;
  *) echo "Refusing runner path outside approved benchmark runner paths: $runner_path" >&2; exit 2 ;;
esac
if ! [[ "$job_count" =~ ^[1-9][0-9]*$ ]] || (( job_count < 2 || job_count > 24 )); then
  echo "DREAM7B_BPU_PHASE_TIMING_JOB_COUNT must be 2..24." >&2
  exit 2
fi
if ! [[ "$request_count" =~ ^[1-9][0-9]*$ ]] || (( request_count < 1 || request_count > 256 )); then
  echo "DREAM7B_BPU_PHASE_TIMING_REQUEST_COUNT must be 1..256." >&2
  exit 2
fi
if ! [[ "$top_k" =~ ^[0-9]+$ ]] || (( top_k > 10 )); then
  echo "DREAM7B_BPU_PHASE_TIMING_TOP_K must be 0..10." >&2
  exit 2
fi
if [[ "$raw_final" != "0" && "$raw_final" != "1" ]]; then
  echo "DREAM7B_BPU_PHASE_TIMING_RAW_FINAL must be 0 or 1." >&2
  exit 2
fi
if [[ ! -x "$hbm_python" ]]; then
  echo "HBM runtime Python is not executable: $hbm_python" >&2
  exit 2
fi
if [[ ! -f "$runner_path" ]]; then
  echo "Missing phase timing runner: $runner_path" >&2
  exit 4
fi
if ! command -v hrt_ucp_monitor >/dev/null 2>&1; then
  echo "Missing deployed command: hrt_ucp_monitor" >&2
  exit 4
fi

stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_segment_major_phase_timing_$stamp"
queue_dir="/tmp/dream7b-bpu-phase-timing-$stamp"
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
            "request_id": f"phase-timing-{stamp}-{job_index + 1:03d}-{request_index + 1:03d}",
            "tokens": [base + offset for offset in range(16)],
        })
    name = f"phase_timing_{stamp}_{job_index + 1:03d}.jsonl"
    text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    (jobs_dir / name).write_text(text, encoding="utf-8")
    (pending_dir / name).write_text(text, encoding="utf-8")
PY

monitor_stdout="$run_dir/hrt_ucp_monitor.stdout"
monitor_stderr="$run_dir/hrt_ucp_monitor.stderr"
runner_stdout="$run_dir/runner.stdout"
runner_stderr="$run_dir/runner.stderr"
summary_json="$run_dir/segment_major_queue_summary.json"
summary_md="$run_dir/segment_major_queue_summary.md"

hrt_ucp_monitor -b -e bpu -d "$monitor_delay_ms" -n "$monitor_sample_count" > "$monitor_stdout" 2> "$monitor_stderr" &
monitor_pid="$!"
cleanup_monitor() {
  if kill -0 "$monitor_pid" >/dev/null 2>&1; then
    kill "$monitor_pid" >/dev/null 2>&1 || true
    wait "$monitor_pid" >/dev/null 2>&1 || true
  fi
}
trap cleanup_monitor EXIT

set +e
DREAM7B_BPU_SEGMENT_MAJOR_PHASE_TIMING=1 DREAM7B_BPU_SEGMENT_MAJOR_RAW_FINAL="$raw_final" "$hbm_python" "$runner_path" \
  "$queue_dir" "$run_dir" \
  --max-job-count "$job_count" \
  --max-job-count-limit 24 \
  --max-batch-size "$request_count" \
  --max-batch-size-limit 256 \
  --top-k "$top_k" \
  --timeout-sec "$timeout_sec" \
  --bpu-lock-path "/tmp/dream7b_bpu_phase_timing.lock" \
  > "$runner_stdout" 2> "$runner_stderr"
runner_status="$?"
set -e

cleanup_monitor
trap - EXIT

python3 - "$run_dir" "$job_count" "$request_count" "$top_k" "$monitor_delay_ms" "$runner_status" "$raw_final" <<'PY'
import json
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
job_count = int(sys.argv[2])
request_count = int(sys.argv[3])
top_k = int(sys.argv[4])
monitor_delay_ms = int(sys.argv[5])
runner_status = int(sys.argv[6])
raw_final = sys.argv[7] == "1"
summary_path = run_dir / "segment_major_queue_summary.json"
summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
monitor_text = (run_dir / "hrt_ucp_monitor.stdout").read_text(encoding="utf-8", errors="replace")
samples = [float(item) for item in re.findall(r"\|\s*BPU0\s+([0-9]+(?:[.][0-9]+)?)\s*\|", monitor_text)]
nonzero = [item for item in samples if item > 0.0]
progress_rows = []
for path in sorted(run_dir.glob("segment_*_progress.json")):
    progress_rows.append(json.loads(path.read_text(encoding="utf-8")))
last_progress = progress_rows[-1] if progress_rows else {}
last_phase = last_progress.get("phase_timing_ms") or {}
errors = []
if runner_status != 0:
    errors.append(f"runner_status={runner_status}")
if summary.get("verdict") != "ok_dream7b_bpu_segment_major_load_once_queue_runner":
    errors.append(f"unexpected_runner_verdict={summary.get('verdict')}")
if summary.get("processed_request_count") != job_count * request_count:
    errors.append(f"processed_request_count_mismatch={summary.get('processed_request_count')}")
if summary.get("failed_job_count") != 0:
    errors.append(f"failed_job_count_nonzero={summary.get('failed_job_count')}")
if not summary.get("phase_timing_enabled"):
    errors.append("phase_timing_not_enabled")
payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_segment_major_phase_timing_probe" if not errors else "failed_dream7b_bpu_segment_major_phase_timing_probe",
    "run_dir": str(run_dir),
    "runner_status": runner_status,
    "job_count": job_count,
    "request_count": request_count,
    "top_k": top_k,
    "raw_final": raw_final,
    "processed_request_count": summary.get("processed_request_count"),
    "failed_job_count": summary.get("failed_job_count"),
    "runner_summary_json": str(summary_path),
    "avg_bpu_loading": round(statistics.fmean(samples), 3) if samples else 0.0,
    "avg_nonzero_bpu_loading": round(statistics.fmean(nonzero), 3) if nonzero else 0.0,
    "max_bpu_loading": max(samples) if samples else 0.0,
    "bpu_loading_sample_count": len(samples),
    "nonzero_bpu_loading_sample_count": len(nonzero),
    "monitor_delay_ms": monitor_delay_ms,
    "wall_ms": summary.get("wall_ms"),
    "run_ms": summary.get("run_ms"),
    "total_load_ms": summary.get("total_load_ms"),
    "load_to_run_ratio": summary.get("load_to_run_ratio"),
    "amortized_wall_ms_per_processed_request": summary.get("amortized_wall_ms_per_processed_request"),
    "phase_timing_totals_ms": summary.get("phase_timing_totals_ms") or {},
    "final_segment_progress": last_progress,
    "final_segment_phase_timing_ms": last_phase,
    "final_segment_overhead_ms": round(
        float(last_progress.get("segment_wall_ms") or 0.0) - float(last_progress.get("segment_run_ms") or 0.0),
        3,
    ) if last_progress else None,
    "errors": errors,
}
(run_dir / "phase_timing_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
lines = [
    "# Dream 7B Segment-Major Phase Timing Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- processed_request_count: {payload['processed_request_count']}",
    f"- failed_job_count: {payload['failed_job_count']}",
    f"- raw_final: {payload['raw_final']}",
    f"- avg_bpu_loading: {payload['avg_bpu_loading']}",
    f"- max_bpu_loading: {payload['max_bpu_loading']}",
    f"- load_to_run_ratio: {payload['load_to_run_ratio']}",
    f"- final_segment_overhead_ms: {payload['final_segment_overhead_ms']}",
    f"- final_segment_phase_timing_ms: {json.dumps(last_phase, ensure_ascii=False, sort_keys=True)}",
    "",
    "## Errors",
    "",
]
lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
(run_dir / "phase_timing_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "phase_timing_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
