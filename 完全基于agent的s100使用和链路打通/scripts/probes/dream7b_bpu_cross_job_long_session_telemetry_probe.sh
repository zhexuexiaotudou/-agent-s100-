#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
queue_dir="${2:-/tmp/dream7b-bpu-cross-job-long-session}"
job_count="${DREAM7B_BPU_LONG_SESSION_JOB_COUNT:-18}"
job_count_limit="${DREAM7B_BPU_LONG_SESSION_JOB_COUNT_LIMIT:-24}"
request_count="${DREAM7B_BPU_LONG_SESSION_REQUEST_COUNT:-16}"
timeout_sec="${DREAM7B_BPU_LONG_SESSION_TIMEOUT_SEC:-5400}"
monitor_delay_ms="${DREAM7B_BPU_LONG_SESSION_MONITOR_DELAY_MS:-100}"
monitor_sample_count="${DREAM7B_BPU_LONG_SESSION_MONITOR_SAMPLE_COUNT:-8000}"
base_probe="${DREAM7B_BPU_LONG_SESSION_BASE_PROBE:-scripts/probes/dream7b_bpu_selected_pair_cross_job_queue_telemetry_probe.sh}"
forward_probe_cmd="${DREAM7B_BPU_LONG_SESSION_FORWARD_PROBE_CMD:-bash scripts/probes/dream7b_bpu_selected_pair_forward_path_probe.sh}"

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

if ! [[ "$job_count" =~ ^[1-9][0-9]*$ ]] || (( job_count < 13 || job_count > 32 )); then
  echo "DREAM7B_BPU_LONG_SESSION_JOB_COUNT must be an integer from 13 to 32." >&2
  exit 2
fi
if ! [[ "$job_count_limit" =~ ^[1-9][0-9]*$ ]] || (( job_count_limit < job_count || job_count_limit > 32 )); then
  echo "DREAM7B_BPU_LONG_SESSION_JOB_COUNT_LIMIT must be an integer from job_count to 32." >&2
  exit 2
fi
if ! [[ "$request_count" =~ ^[1-9][0-9]*$ ]] || (( request_count < 1 || request_count > 16 )); then
  echo "DREAM7B_BPU_LONG_SESSION_REQUEST_COUNT must be an integer from 1 to 16." >&2
  exit 2
fi
if ! [[ "$timeout_sec" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_LONG_SESSION_TIMEOUT_SEC must be a positive integer." >&2
  exit 2
fi
if ! [[ "$monitor_delay_ms" =~ ^[0-9]+$ ]] || (( monitor_delay_ms < 100 || monitor_delay_ms > 10000 )); then
  echo "DREAM7B_BPU_LONG_SESSION_MONITOR_DELAY_MS must be an integer from 100 to 10000." >&2
  exit 2
fi
if ! [[ "$monitor_sample_count" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_LONG_SESSION_MONITOR_SAMPLE_COUNT must be a positive integer." >&2
  exit 2
fi
if [[ ! -f "$base_probe" ]]; then
  echo "Missing base telemetry probe: $base_probe" >&2
  exit 4
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_cross_job_long_session_telemetry_$stamp"
mkdir -p "$run_dir"

base_stdout="$run_dir/base_probe.stdout"
base_stderr="$run_dir/base_probe.stderr"

set +e
DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_JOB_COUNT="$job_count" \
DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_JOB_COUNT_LIMIT="$job_count_limit" \
DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_REQUEST_COUNT="$request_count" \
DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_TIMEOUT_SEC="$timeout_sec" \
DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_MONITOR_DELAY_MS="$monitor_delay_ms" \
DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_MONITOR_SAMPLE_COUNT="$monitor_sample_count" \
DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_FORWARD_PROBE_CMD="$forward_probe_cmd" \
bash "$base_probe" "$report_root" "$queue_dir" > "$base_stdout" 2> "$base_stderr"
base_status="$?"
set -e

python3 - \
  "$run_dir" \
  "$report_root" \
  "$base_stdout" \
  "$base_stderr" \
  "$base_status" \
  "$job_count" \
  "$request_count" <<'PY'
import glob
import json
import re
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
report_root = Path(sys.argv[2])
base_stdout = Path(sys.argv[3])
base_stderr = Path(sys.argv[4])
base_status = int(sys.argv[5])
job_count = int(sys.argv[6])
request_count = int(sys.argv[7])


def latest_json(pattern):
    paths = [Path(item) for item in glob.glob(str(report_root / pattern))]
    paths = [item for item in paths if item.is_file()]
    if not paths:
        return None, {}
    path = max(paths, key=lambda item: item.stat().st_mtime)
    return path, json.loads(path.read_text(encoding="utf-8"))


def ratio_delta(new, old):
    if new is None or old in (None, 0):
        return None
    return round(float(old) - float(new), 6)


stdout_text = base_stdout.read_text(encoding="utf-8", errors="replace")
base_report_path = None
for raw in reversed(stdout_text.splitlines()):
    line = raw.strip()
    if line.endswith("cross_job_queue_telemetry_probe.md"):
        base_report_path = Path(line).with_suffix(".json")
        break

errors = []
warnings = []
if base_status != 0:
    errors.append(f"base telemetry probe returned {base_status}")
if base_report_path is None or not base_report_path.is_file():
    errors.append("could not locate base cross-job telemetry JSON from stdout")
    current = {}
else:
    current = json.loads(base_report_path.read_text(encoding="utf-8"))
    if current.get("verdict") != "ok_dream7b_bpu_selected_pair_cross_job_queue_telemetry_probe":
        errors.append(f"unexpected base telemetry verdict: {current.get('verdict')}")

default_path, default = latest_json("dream7b_bpu_cross_job_default_service_telemetry_*/default_service_telemetry_probe.json")
candidate_path, candidate = latest_json("dream7b_bpu_selected_pair_cross_job_queue_telemetry_*/cross_job_queue_telemetry_probe.json")
gap_path, gap = latest_json("dream7b_bpu_utilization_gap_*/utilization_gap_probe.json")

processed = int(current.get("processed_request_count") or 0)
failed_raw = current.get("failed_job_count")
failed = int(failed_raw) if failed_raw is not None else -1
avg_bpu = current.get("avg_bpu_loading")
load_ratio = current.get("load_to_run_ratio")
wall = current.get("amortized_wall_ms_per_processed_request")

phase1 = {
    "processed_request_count_ge_192": processed >= 192,
    "failed_job_count_zero": failed == 0,
    "avg_bpu_loading_ge_15": avg_bpu is not None and float(avg_bpu) >= 15.0,
    "load_to_run_ratio_le_7": load_ratio is not None and float(load_ratio) <= 7.0,
}
phase1["passed"] = all(phase1.values())

comparison = {
    "default_report": str(default_path) if default_path else "",
    "default_avg_bpu_loading": default.get("avg_bpu_loading"),
    "default_load_to_run_ratio": default.get("load_to_run_ratio"),
    "default_wall_ms_per_request": default.get("amortized_wall_ms_per_processed_request"),
    "candidate_report": str(candidate_path) if candidate_path else "",
    "candidate_avg_bpu_loading": candidate.get("avg_bpu_loading"),
    "candidate_load_to_run_ratio": candidate.get("load_to_run_ratio"),
    "candidate_wall_ms_per_request": candidate.get("amortized_wall_ms_per_processed_request"),
    "avg_bpu_delta_vs_default": round(float(avg_bpu) - float(default.get("avg_bpu_loading")), 6) if avg_bpu is not None and default.get("avg_bpu_loading") is not None else None,
    "load_to_run_delta_vs_default": ratio_delta(load_ratio, default.get("load_to_run_ratio")),
    "wall_ms_delta_vs_default": ratio_delta(wall, default.get("amortized_wall_ms_per_processed_request")),
    "avg_bpu_delta_vs_latest_candidate": round(float(avg_bpu) - float(candidate.get("avg_bpu_loading")), 6) if avg_bpu is not None and candidate.get("avg_bpu_loading") is not None else None,
    "load_to_run_delta_vs_latest_candidate": ratio_delta(load_ratio, candidate.get("load_to_run_ratio")),
    "wall_ms_delta_vs_latest_candidate": ratio_delta(wall, candidate.get("amortized_wall_ms_per_processed_request")),
}

decision = "phase1_pass" if phase1["passed"] else "long_session_candidate_only"
if not errors and not phase1["passed"]:
    warnings.append("long session did not pass Phase 1 sustained-utilization gate")
if (gap.get("diagnosis") or "") == "hbm_reload_dominated":
    warnings.append("latest utilization diagnosis remains hbm_reload_dominated")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_cross_job_long_session_telemetry_probe" if not errors else "failed_dream7b_bpu_cross_job_long_session_telemetry_probe",
    "decision": decision,
    "run_dir": str(run_dir),
    "base_probe_json": str(base_report_path) if base_report_path else "",
    "job_count": job_count,
    "request_count": request_count,
    "processed_request_count": current.get("processed_request_count"),
    "failed_job_count": current.get("failed_job_count"),
    "avg_bpu_loading": avg_bpu,
    "max_bpu_loading": current.get("max_bpu_loading"),
    "load_to_run_ratio": load_ratio,
    "amortized_wall_ms_per_processed_request": wall,
    "phase1_gate": phase1,
    "comparison": comparison,
    "latest_utilization_gap": str(gap_path) if gap_path else "",
    "latest_utilization_diagnosis": gap.get("diagnosis"),
    "base_stdout": str(base_stdout),
    "base_stderr": str(base_stderr),
    "base_stderr_excerpt": base_stderr.read_text(encoding="utf-8", errors="replace")[:1000],
    "warnings": warnings,
    "errors": errors,
}
(run_dir / "long_session_telemetry_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
lines = [
    "# Dream 7B Cross-Job Long-Session Telemetry Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- decision: {payload['decision']}",
    f"- processed_request_count: {payload['processed_request_count']}",
    f"- failed_job_count: {payload['failed_job_count']}",
    f"- avg_bpu_loading: {payload['avg_bpu_loading']}",
    f"- load_to_run_ratio: {payload['load_to_run_ratio']}",
    f"- amortized_wall_ms_per_processed_request: {payload['amortized_wall_ms_per_processed_request']}",
    f"- phase1_passed: {payload['phase1_gate']['passed']}",
    "",
    "## Errors",
    "",
]
lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
lines.extend(["", "## Warnings", ""])
lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- none")
(run_dir / "long_session_telemetry_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "long_session_telemetry_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
