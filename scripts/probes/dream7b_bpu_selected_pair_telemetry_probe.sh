#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
batch_count="${DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_BATCH_COUNT:-16}"
monitor_delay_ms="${DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_MONITOR_DELAY_MS:-100}"
monitor_sample_count="${DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_MONITOR_SAMPLE_COUNT:-320}"
top_k="${DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_TOP_K:-3}"
timeout_sec="${DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_TIMEOUT_SEC:-480}"
selected_pair_cmd="${DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_FORWARD_CMD:-dream7b-bpu-selected-pair-forward-path-probe}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

if ! [[ "$batch_count" =~ ^[1-9][0-9]*$ ]] || (( batch_count > 16 )); then
  echo "DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_BATCH_COUNT must be an integer from 1 to 16." >&2
  exit 2
fi
if ! [[ "$monitor_delay_ms" =~ ^[0-9]+$ ]] || (( monitor_delay_ms < 100 || monitor_delay_ms > 10000 )); then
  echo "DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_MONITOR_DELAY_MS must be an integer from 100 to 10000." >&2
  exit 2
fi
if ! [[ "$monitor_sample_count" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_MONITOR_SAMPLE_COUNT must be a positive integer." >&2
  exit 2
fi
if ! [[ "$top_k" =~ ^[0-9]+$ ]]; then
  echo "DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_TOP_K must be a non-negative integer." >&2
  exit 2
fi
if ! [[ "$timeout_sec" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_SELECTED_PAIR_TELEMETRY_TIMEOUT_SEC must be a positive integer." >&2
  exit 2
fi
if ! command -v "$selected_pair_cmd" >/dev/null 2>&1; then
  echo "Missing deployed command: $selected_pair_cmd" >&2
  exit 4
fi
if ! command -v hrt_ucp_monitor >/dev/null 2>&1; then
  echo "Missing deployed command: hrt_ucp_monitor" >&2
  exit 4
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_selected_pair_telemetry_$stamp"
mkdir -p "$run_dir"
monitor_stdout="$run_dir/hrt_ucp_monitor.stdout"
monitor_stderr="$run_dir/hrt_ucp_monitor.stderr"
forward_stdout="$run_dir/selected_pair.forward.stdout"
forward_stderr="$run_dir/selected_pair.forward.stderr"
somstatus_before="$run_dir/hrut_somstatus_before.txt"
somstatus_after="$run_dir/hrut_somstatus_after.txt"

hrut_somstatus > "$somstatus_before" 2>&1 || true
hrt_ucp_monitor -b -e bpu -d "$monitor_delay_ms" -n "$monitor_sample_count" > "$monitor_stdout" 2> "$monitor_stderr" &
monitor_pid="$!"

cleanup_monitor() {
  if kill -0 "$monitor_pid" >/dev/null 2>&1; then
    kill "$monitor_pid" >/dev/null 2>&1 || true
    wait "$monitor_pid" >/dev/null 2>&1 || true
  fi
}
trap cleanup_monitor EXIT

sleep 0.3
set +e
DREAM7B_BPU_SELECTED_PAIR_ONLY=1 \
DREAM7B_BPU_SELECTED_PAIR_BATCH_COUNT="$batch_count" \
DREAM7B_BPU_SELECTED_PAIR_TOP_K="$top_k" \
timeout "$timeout_sec" "$selected_pair_cmd" "$report_root" > "$forward_stdout" 2> "$forward_stderr"
forward_status="$?"
set -e
cleanup_monitor
trap - EXIT
hrut_somstatus > "$somstatus_after" 2>&1 || true

python3 - \
  "$run_dir" \
  "$report_root" \
  "$batch_count" \
  "$monitor_delay_ms" \
  "$monitor_sample_count" \
  "$top_k" \
  "$timeout_sec" \
  "$selected_pair_cmd" \
  "$forward_status" <<'PY'
import json
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
report_root = Path(sys.argv[2])
batch_count = int(sys.argv[3])
monitor_delay_ms = int(sys.argv[4])
monitor_sample_count = int(sys.argv[5])
top_k = int(sys.argv[6])
timeout_sec = int(sys.argv[7])
selected_pair_cmd = sys.argv[8]
forward_status = int(sys.argv[9])

monitor_stdout = run_dir / "hrt_ucp_monitor.stdout"
monitor_stderr = run_dir / "hrt_ucp_monitor.stderr"
forward_stdout = run_dir / "selected_pair.forward.stdout"
forward_stderr = run_dir / "selected_pair.forward.stderr"
somstatus_before = run_dir / "hrut_somstatus_before.txt"
somstatus_after = run_dir / "hrut_somstatus_after.txt"

errors = []
warnings = []

def latest_json(pattern):
    paths = [path for path in report_root.glob(pattern) if path.is_file()]
    return max(paths, key=lambda path: path.stat().st_mtime) if paths else None

monitor_text = monitor_stdout.read_text(encoding="utf-8", errors="replace") if monitor_stdout.is_file() else ""
monitor_err = monitor_stderr.read_text(encoding="utf-8", errors="replace") if monitor_stderr.is_file() else ""
bpu_loading_samples = [float(item) for item in re.findall(r"\|\s*BPU0\s+([0-9]+(?:[.][0-9]+)?)\s*\|", monitor_text)]
cma_used_values = re.findall(r"\|\s*cma_reserved\s+\S+\s+(\S+)\s+\S+\s*\|", monitor_text)
carveout_used_values = re.findall(r"\|\s*carveout\s+\S+\s+(\S+)\s+\S+\s*\|", monitor_text)
max_bpu_loading = max(bpu_loading_samples) if bpu_loading_samples else 0.0
avg_bpu_loading = statistics.fmean(bpu_loading_samples) if bpu_loading_samples else 0.0
nonzero_bpu_loading_sample_count = sum(1 for item in bpu_loading_samples if item > 0.0)

if not bpu_loading_samples:
    errors.append("hrt_ucp_monitor produced no BPU0 loading samples")
if max_bpu_loading <= 0.0:
    errors.append(f"max_bpu_loading did not exceed zero: {max_bpu_loading}")
if nonzero_bpu_loading_sample_count <= 0:
    errors.append(f"nonzero_bpu_loading_sample_count did not exceed zero: {nonzero_bpu_loading_sample_count}")
if forward_status != 0:
    errors.append(f"selected pair command exited with status {forward_status}")

stdout_text = forward_stdout.read_text(encoding="utf-8", errors="replace") if forward_stdout.is_file() else ""
selected_report_md = ""
for line in stdout_text.splitlines()[::-1]:
    line = line.strip()
    if line.endswith("selected_pair_forward_path_probe.md"):
        selected_report_md = line
        break
selected_report_json = str(Path(selected_report_md).with_suffix(".json")) if selected_report_md.endswith(".md") else ""
selected_report = {}
selected_json_path = Path(selected_report_json) if selected_report_json else None
if selected_json_path and selected_json_path.is_file():
    selected_report = json.loads(selected_json_path.read_text(encoding="utf-8"))
else:
    errors.append(f"missing selected pair report JSON parsed from stdout: {selected_report_json}")

selected = selected_report.get("selected") if isinstance(selected_report, dict) else {}
comparison = selected_report.get("comparison") if isinstance(selected_report, dict) else {}
if selected_report:
    if selected_report.get("verdict") != "ok_dream7b_bpu_selected_pair_forward_path_probe":
        errors.append(f"unexpected selected pair verdict: {selected_report.get('verdict')}")
    if selected_report.get("selected_only") is not True:
        errors.append(f"selected pair report did not run selected_only mode: {selected_report.get('selected_only')}")
    if selected_report.get("batch_count") != batch_count:
        errors.append(f"unexpected selected pair batch_count: {selected_report.get('batch_count')}")
    if selected.get("selected_pair_covers_all_segments") is not True:
        errors.append(f"selected pair does not cover all segments: {selected.get('selected_pair_covers_all_segments')}")
    if selected.get("final_shapes") != [[1, 16, 152064] for _ in range(batch_count)]:
        errors.append(f"unexpected selected final_shapes: {selected.get('final_shapes')}")
    if comparison.get("baseline_skipped") is not True:
        errors.append(f"selected-only report did not mark comparison.baseline_skipped: {comparison.get('baseline_skipped')}")

default_runtime_path = latest_json("dream7b_bpu_runtime_telemetry_*/runtime_telemetry_probe.json")
default_runtime = {}
if default_runtime_path:
    default_runtime = json.loads(default_runtime_path.read_text(encoding="utf-8"))
else:
    warnings.append("latest default dream7b_bpu_runtime_telemetry report was not found")

default_forward_metrics = default_runtime.get("forward_metrics") if isinstance(default_runtime, dict) else {}
default_avg_bpu_loading = default_runtime.get("avg_bpu_loading") if isinstance(default_runtime, dict) else None
default_max_bpu_loading = default_runtime.get("max_bpu_loading") if isinstance(default_runtime, dict) else None
default_wall_ms = default_forward_metrics.get("wall_ms") if isinstance(default_forward_metrics, dict) else None
selected_wall_ms = selected.get("wall_ms") if isinstance(selected, dict) else None
selected_forward_load_ms = selected.get("forward_load_ms") if isinstance(selected, dict) else None
selected_run_ms = selected.get("run_ms") if isinstance(selected, dict) else None

wall_ms_delta_vs_default_runtime = None
wall_ms_delta_ratio_vs_default_runtime = None
if isinstance(default_wall_ms, (int, float)) and isinstance(selected_wall_ms, (int, float)) and default_wall_ms:
    wall_ms_delta_vs_default_runtime = round(float(default_wall_ms) - float(selected_wall_ms), 3)
    wall_ms_delta_ratio_vs_default_runtime = round(wall_ms_delta_vs_default_runtime / float(default_wall_ms), 6)

avg_bpu_loading_delta_vs_default_runtime = None
if isinstance(default_avg_bpu_loading, (int, float)):
    avg_bpu_loading_delta_vs_default_runtime = round(avg_bpu_loading - float(default_avg_bpu_loading), 3)

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_selected_pair_telemetry_probe" if not errors else "failed_dream7b_bpu_selected_pair_telemetry_probe",
    "run_dir": str(run_dir),
    "report_root": str(report_root),
    "batch_count": batch_count,
    "monitor_delay_ms": monitor_delay_ms,
    "monitor_sample_count": monitor_sample_count,
    "top_k": top_k,
    "timeout_sec": timeout_sec,
    "selected_pair_cmd": selected_pair_cmd,
    "forward_status": forward_status,
    "selected_pair_report_json": selected_report_json,
    "selected_pair_report_md": selected_report_md,
    "selected": {
        "selected_pair": selected.get("selected_pair") if isinstance(selected, dict) else None,
        "selected_segments": selected.get("selected_segments") if isinstance(selected, dict) else None,
        "selected_pair_covers_all_segments": selected.get("selected_pair_covers_all_segments") if isinstance(selected, dict) else None,
        "selected_worker_count": selected.get("selected_worker_count") if isinstance(selected, dict) else None,
        "selected_resident_load_ms": selected.get("selected_resident_load_ms") if isinstance(selected, dict) else None,
        "forward_load_ms": selected_forward_load_ms,
        "selected_total_load_ms": selected.get("selected_total_load_ms") if isinstance(selected, dict) else None,
        "run_ms": selected_run_ms,
        "wall_ms": selected_wall_ms,
        "amortized_wall_ms_per_forward": selected.get("amortized_wall_ms_per_forward") if isinstance(selected, dict) else None,
        "amortized_warm_load_ms_per_forward": selected.get("amortized_warm_load_ms_per_forward") if isinstance(selected, dict) else None,
        "amortized_run_ms_per_forward": selected.get("amortized_run_ms_per_forward") if isinstance(selected, dict) else None,
        "final_shapes": selected.get("final_shapes") if isinstance(selected, dict) else None,
    },
    "bpu_loading_sample_count": len(bpu_loading_samples),
    "nonzero_bpu_loading_sample_count": nonzero_bpu_loading_sample_count,
    "max_bpu_loading": round(max_bpu_loading, 3),
    "avg_bpu_loading": round(avg_bpu_loading, 3),
    "cma_reserved_used_values": cma_used_values[:10],
    "carveout_used_values": carveout_used_values[:10],
    "monitor_stdout": str(monitor_stdout),
    "monitor_stderr": str(monitor_stderr),
    "monitor_stderr_excerpt": monitor_err[:500],
    "forward_stdout": str(forward_stdout),
    "forward_stderr": str(forward_stderr),
    "somstatus_before": str(somstatus_before),
    "somstatus_after": str(somstatus_after),
    "default_runtime_telemetry": {
        "path": str(default_runtime_path) if default_runtime_path else "",
        "verdict": default_runtime.get("verdict") if isinstance(default_runtime, dict) else None,
        "batch_count": default_runtime.get("batch_count") if isinstance(default_runtime, dict) else None,
        "avg_bpu_loading": default_avg_bpu_loading,
        "max_bpu_loading": default_max_bpu_loading,
        "forward_wall_ms": default_wall_ms,
        "forward_load_ms": default_forward_metrics.get("load_ms") if isinstance(default_forward_metrics, dict) else None,
        "forward_run_ms": default_forward_metrics.get("run_ms") if isinstance(default_forward_metrics, dict) else None,
    },
    "comparison_to_default_runtime_telemetry": {
        "wall_ms_delta_vs_default_runtime": wall_ms_delta_vs_default_runtime,
        "wall_ms_delta_ratio_vs_default_runtime": wall_ms_delta_ratio_vs_default_runtime,
        "avg_bpu_loading_delta_vs_default_runtime": avg_bpu_loading_delta_vs_default_runtime,
        "selected_wall_time_improved_vs_default_runtime": (wall_ms_delta_vs_default_runtime is not None and wall_ms_delta_vs_default_runtime > 0),
        "selected_avg_bpu_loading_improved_vs_default_runtime": (avg_bpu_loading_delta_vs_default_runtime is not None and avg_bpu_loading_delta_vs_default_runtime > 0),
    },
    "next_optimization_target": "rerun default runtime telemetry and selected-pair telemetry back-to-back before promoting selected-pair worker path into the default Dream 7B service",
    "warnings": warnings,
    "errors": errors,
}
(run_dir / "selected_pair_telemetry_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Dream 7B BPU Selected Pair Telemetry Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- run_dir: {payload['run_dir']}",
    f"- batch_count: {payload['batch_count']}",
    f"- selected_pair: {payload['selected']['selected_pair']}",
    f"- selected_segments: {payload['selected']['selected_segments']}",
    f"- selected_pair_covers_all_segments: {payload['selected']['selected_pair_covers_all_segments']}",
    f"- selected.wall_ms: {payload['selected']['wall_ms']}",
    f"- selected.forward_load_ms: {payload['selected']['forward_load_ms']}",
    f"- selected.run_ms: {payload['selected']['run_ms']}",
    f"- bpu_loading_sample_count: {payload['bpu_loading_sample_count']}",
    f"- nonzero_bpu_loading_sample_count: {payload['nonzero_bpu_loading_sample_count']}",
    f"- max_bpu_loading: {payload['max_bpu_loading']}",
    f"- avg_bpu_loading: {payload['avg_bpu_loading']}",
    f"- default_runtime_telemetry.path: {payload['default_runtime_telemetry']['path']}",
    f"- comparison.wall_ms_delta_vs_default_runtime: {payload['comparison_to_default_runtime_telemetry']['wall_ms_delta_vs_default_runtime']}",
    f"- comparison.wall_ms_delta_ratio_vs_default_runtime: {payload['comparison_to_default_runtime_telemetry']['wall_ms_delta_ratio_vs_default_runtime']}",
    f"- comparison.avg_bpu_loading_delta_vs_default_runtime: {payload['comparison_to_default_runtime_telemetry']['avg_bpu_loading_delta_vs_default_runtime']}",
    f"- next_optimization_target: {payload['next_optimization_target']}",
    "",
    "## Warnings",
    "",
]
lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- none")
lines.extend(["", "## Errors", ""])
lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
(run_dir / "selected_pair_telemetry_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "selected_pair_telemetry_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
