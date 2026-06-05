#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
tokens="${2:-1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16}"
repeat_count="${DREAM7B_BPU_FINE_FORWARD_LONG_REPEAT_COUNT:-6}"
max_wall_spread_ratio="${DREAM7B_BPU_FINE_FORWARD_LONG_REPEAT_MAX_WALL_SPREAD_RATIO:-0}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

if ! [[ "$repeat_count" =~ ^[1-9][0-9]*$ ]] || (( repeat_count < 4 || repeat_count > 10 )); then
  echo "DREAM7B_BPU_FINE_FORWARD_LONG_REPEAT_COUNT must be an integer from 4 to 10." >&2
  exit 2
fi

if ! [[ "$max_wall_spread_ratio" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "DREAM7B_BPU_FINE_FORWARD_LONG_REPEAT_MAX_WALL_SPREAD_RATIO must be a non-negative number." >&2
  exit 2
fi

if ! command -v dream7b-bpu-fine-forward-repeat-probe >/dev/null 2>&1; then
  echo "Missing deployed command: dream7b-bpu-fine-forward-repeat-probe" >&2
  exit 4
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_fine_forward_long_repeat_$stamp"
repeat_root="$run_dir/repeat"
mkdir -p "$repeat_root"

repeat_stdout="$run_dir/repeat.stdout"
repeat_stderr="$run_dir/repeat.stderr"
set +e
dream7b-bpu-fine-forward-repeat-probe "$repeat_root" "$tokens" "$repeat_count" > "$repeat_stdout" 2> "$repeat_stderr"
repeat_status="$?"
set -e

repeat_summary_md="$(tail -n 1 "$repeat_stdout" | tr -d '\r' || true)"
repeat_summary_json="${repeat_summary_md%/summary.md}/summary.json"

python3 - \
  "$run_dir" \
  "$repeat_root" \
  "$repeat_count" \
  "$max_wall_spread_ratio" \
  "$repeat_status" \
  "$repeat_stdout" \
  "$repeat_stderr" \
  "$repeat_summary_md" \
  "$repeat_summary_json" <<'PY'
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
repeat_root = Path(sys.argv[2])
repeat_count = int(sys.argv[3])
max_wall_spread_ratio = float(sys.argv[4])
repeat_status = int(sys.argv[5])
repeat_stdout = Path(sys.argv[6])
repeat_stderr = Path(sys.argv[7])
repeat_summary_md = sys.argv[8]
repeat_summary_json = Path(sys.argv[9])
errors = []
warnings = []

summary = None
if repeat_status != 0:
    errors.append(f"repeat probe exited with status {repeat_status}")
if repeat_summary_json.is_file():
    summary = json.loads(repeat_summary_json.read_text(encoding="utf-8"))
else:
    errors.append(f"missing repeat summary JSON: {repeat_summary_json}")

results = summary.get("results", []) if isinstance(summary, dict) else []
wall_values = [float(item.get("wall_ms") or 0.0) for item in results]
load_values = [float(item.get("load_ms") or 0.0) for item in results]
run_values = [float(item.get("run_ms") or 0.0) for item in results]
failure_count = sum(1 for item in results if not item.get("ok"))
wall_min_ms = min(wall_values) if wall_values else 0.0
wall_max_ms = max(wall_values) if wall_values else 0.0
wall_median_ms = statistics.median(wall_values) if wall_values else 0.0
wall_spread_ratio = ((wall_max_ms - wall_min_ms) / wall_median_ms) if wall_median_ms else 0.0

if isinstance(summary, dict):
    if summary.get("verdict") != "ok_dream7b_bpu_fine_forward_repeat_probe":
        errors.append(f"unexpected repeat verdict: {summary.get('verdict')}")
    if summary.get("repeat_count") != repeat_count:
        errors.append(f"unexpected repeat_count: {summary.get('repeat_count')}")
    if len(results) != repeat_count:
        errors.append(f"unexpected result count: {len(results)}")
for item in results:
    label = item.get("label")
    if item.get("execution_mode") != "pair_in_process":
        errors.append(f"{label} execution_mode={item.get('execution_mode')}")
    if item.get("window_execution_mode") != "in-process":
        errors.append(f"{label} window_execution_mode={item.get('window_execution_mode')}")
    if item.get("child_process_count") != 0:
        errors.append(f"{label} child_process_count={item.get('child_process_count')}")
    if item.get("segment_count") != 10:
        errors.append(f"{label} segment_count={item.get('segment_count')}")
    if item.get("final_shape") != [1, 16, 152064]:
        errors.append(f"{label} final_shape={item.get('final_shape')}")
if failure_count:
    errors.append(f"failure_count={failure_count}")
if max_wall_spread_ratio > 0 and wall_spread_ratio > max_wall_spread_ratio:
    errors.append(f"wall_spread_ratio {wall_spread_ratio:.6f} exceeds limit {max_wall_spread_ratio:.6f}")
elif max_wall_spread_ratio == 0 and wall_spread_ratio > 0:
    warnings.append("wall_spread_ratio recorded but not gated because DREAM7B_BPU_FINE_FORWARD_LONG_REPEAT_MAX_WALL_SPREAD_RATIO is 0")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_fine_forward_long_repeat_probe" if not errors else "failed_dream7b_bpu_fine_forward_long_repeat_probe",
    "run_dir": str(run_dir),
    "repeat_root": str(repeat_root),
    "repeat_count": repeat_count,
    "repeat_status": repeat_status,
    "repeat_stdout": str(repeat_stdout),
    "repeat_stderr": str(repeat_stderr),
    "repeat_summary_md": repeat_summary_md,
    "repeat_summary_json": str(repeat_summary_json),
    "failure_count": failure_count,
    "median_wall_ms": round(float(statistics.median(wall_values)), 3) if wall_values else 0.0,
    "median_load_ms": round(float(statistics.median(load_values)), 3) if load_values else 0.0,
    "median_run_ms": round(float(statistics.median(run_values)), 3) if run_values else 0.0,
    "min_wall_ms": round(wall_min_ms, 3),
    "max_wall_ms": round(wall_max_ms, 3),
    "wall_spread_ratio": round(wall_spread_ratio, 6),
    "max_wall_spread_ratio": max_wall_spread_ratio,
    "results": results,
    "warnings": warnings,
    "errors": errors,
}
(run_dir / "long_repeat_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
warning_lines = [f"- {item}" for item in warnings] if warnings else ["- none"]
error_lines = [f"- {item}" for item in errors] if errors else ["- none"]
result_lines = [
    f"| {item.get('label')} | {item.get('ok')} | {item.get('execution_mode')} | {item.get('window_execution_mode')} | {item.get('child_process_count')} | {item.get('wall_ms')} | {item.get('load_ms')} | {item.get('run_ms')} |"
    for item in results
]
(run_dir / "long_repeat_probe.md").write_text(
    "\n".join([
        "# Dream 7B BPU Fine Forward Long Repeat Probe",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- run_dir: {payload['run_dir']}",
        f"- repeat_count: {payload['repeat_count']}",
        f"- repeat_status: {payload['repeat_status']}",
        f"- repeat_summary_md: {payload['repeat_summary_md']}",
        f"- repeat_summary_json: {payload['repeat_summary_json']}",
        f"- failure_count: {payload['failure_count']}",
        f"- median_wall_ms: {payload['median_wall_ms']}",
        f"- median_load_ms: {payload['median_load_ms']}",
        f"- median_run_ms: {payload['median_run_ms']}",
        f"- min_wall_ms: {payload['min_wall_ms']}",
        f"- max_wall_ms: {payload['max_wall_ms']}",
        f"- wall_spread_ratio: {payload['wall_spread_ratio']}",
        f"- max_wall_spread_ratio: {payload['max_wall_spread_ratio']}",
        "",
        "## Results",
        "",
        "| run | ok | execution_mode | window_execution_mode | child_process_count | wall_ms | load_ms | run_ms |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: |",
        *result_lines,
        "",
        "## Warnings",
        "",
        *warning_lines,
        "",
        "## Errors",
        "",
        *error_lines,
        "",
    ]) + "\n",
    encoding="utf-8",
)
print(run_dir / "long_repeat_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
