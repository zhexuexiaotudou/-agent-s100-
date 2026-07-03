#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
batch_count="${DREAM7B_BPU_TELEMETRY_BATCH_COUNT:-16}"
monitor_delay_ms="${DREAM7B_BPU_TELEMETRY_MONITOR_DELAY_MS:-100}"
monitor_sample_count="${DREAM7B_BPU_TELEMETRY_MONITOR_SAMPLE_COUNT:-320}"
top_k="${DREAM7B_BPU_TELEMETRY_TOP_K:-3}"
timeout_sec="${DREAM7B_BPU_TELEMETRY_TIMEOUT_SEC:-480}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

if ! [[ "$batch_count" =~ ^[1-9][0-9]*$ ]] || (( batch_count > 16 )); then
  echo "DREAM7B_BPU_TELEMETRY_BATCH_COUNT must be an integer from 1 to 16." >&2
  exit 2
fi
if ! [[ "$monitor_delay_ms" =~ ^[0-9]+$ ]] || (( monitor_delay_ms < 100 || monitor_delay_ms > 10000 )); then
  echo "DREAM7B_BPU_TELEMETRY_MONITOR_DELAY_MS must be an integer from 100 to 10000." >&2
  exit 2
fi
if ! [[ "$monitor_sample_count" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_TELEMETRY_MONITOR_SAMPLE_COUNT must be a positive integer." >&2
  exit 2
fi
if ! [[ "$top_k" =~ ^[0-9]+$ ]]; then
  echo "DREAM7B_BPU_TELEMETRY_TOP_K must be a non-negative integer." >&2
  exit 2
fi
if ! [[ "$timeout_sec" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_TELEMETRY_TIMEOUT_SEC must be a positive integer." >&2
  exit 2
fi

if ! command -v dream7b-bpu-fine-batch-forward >/dev/null 2>&1; then
  echo "Missing deployed command: dream7b-bpu-fine-batch-forward" >&2
  exit 4
fi
if ! command -v hrt_ucp_monitor >/dev/null 2>&1; then
  echo "Missing deployed command: hrt_ucp_monitor" >&2
  exit 4
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_runtime_telemetry_$stamp"
mkdir -p "$run_dir"
tokens_batch_json="$run_dir/tokens_batch.json"
monitor_stdout="$run_dir/hrt_ucp_monitor.stdout"
monitor_stderr="$run_dir/hrt_ucp_monitor.stderr"
forward_stdout="$run_dir/forward.stdout"
forward_stderr="$run_dir/forward.stderr"
somstatus_before="$run_dir/hrut_somstatus_before.txt"
somstatus_after="$run_dir/hrut_somstatus_after.txt"

python3 - "$tokens_batch_json" "$batch_count" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
count = int(sys.argv[2])
rows = []
for index in range(count):
    base = (index + 1) * 100
    rows.append([base + offset for offset in range(1, 17)])
path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

hrut_somstatus > "$somstatus_before" 2>&1 || true
hrt_ucp_monitor -b -e bpu -d "$monitor_delay_ms" -n "$monitor_sample_count" > "$monitor_stdout" 2> "$monitor_stderr" &
monitor_pid="$!"
sleep 0.3
set +e
timeout "$timeout_sec" dream7b-bpu-fine-batch-forward \
  --tokens-batch-json "$tokens_batch_json" \
  --top-k "$top_k" \
  --output-dir "$run_dir/forward" > "$forward_stdout" 2> "$forward_stderr"
forward_status="$?"
set -e
hrut_somstatus > "$somstatus_after" 2>&1 || true

if kill -0 "$monitor_pid" >/dev/null 2>&1; then
  wait "$monitor_pid" || true
fi

python3 - \
  "$run_dir" \
  "$batch_count" \
  "$monitor_delay_ms" \
  "$monitor_sample_count" \
  "$top_k" \
  "$timeout_sec" \
  "$forward_status" <<'PY'
import json
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
batch_count = int(sys.argv[2])
monitor_delay_ms = int(sys.argv[3])
monitor_sample_count = int(sys.argv[4])
top_k = int(sys.argv[5])
timeout_sec = int(sys.argv[6])
forward_status = int(sys.argv[7])
monitor_stdout = run_dir / "hrt_ucp_monitor.stdout"
monitor_stderr = run_dir / "hrt_ucp_monitor.stderr"
summary_path = run_dir / "forward/summary.json"
somstatus_before = run_dir / "hrut_somstatus_before.txt"
somstatus_after = run_dir / "hrut_somstatus_after.txt"
errors = []

monitor_text = monitor_stdout.read_text(encoding="utf-8", errors="replace") if monitor_stdout.is_file() else ""
monitor_err = monitor_stderr.read_text(encoding="utf-8", errors="replace") if monitor_stderr.is_file() else ""
bpu_loading_samples = [float(item) for item in re.findall(r"\|\s*BPU0\s+([0-9]+(?:[.][0-9]+)?)\s*\|", monitor_text)]
cma_used_values = re.findall(r"\|\s*cma_reserved\s+\S+\s+(\S+)\s+\S+\s*\|", monitor_text)
carveout_used_values = re.findall(r"\|\s*carveout\s+\S+\s+(\S+)\s+\S+\s*\|", monitor_text)
if not bpu_loading_samples:
    errors.append("hrt_ucp_monitor produced no BPU0 loading samples")
max_bpu_loading = max(bpu_loading_samples) if bpu_loading_samples else 0.0
avg_bpu_loading = statistics.fmean(bpu_loading_samples) if bpu_loading_samples else 0.0
nonzero_bpu_loading_sample_count = sum(1 for item in bpu_loading_samples if item > 0.0)

forward = None
if summary_path.is_file():
    forward = json.loads(summary_path.read_text(encoding="utf-8"))
else:
    errors.append(f"missing forward summary: {summary_path}")

if forward_status != 0:
    errors.append(f"forward command exited with status {forward_status}")
if isinstance(forward, dict):
    if forward.get("verdict") != "ok_dream7b_segmented_hbm_python_forward":
        errors.append(f"unexpected forward verdict: {forward.get('verdict')}")
    if forward.get("batch_count") != batch_count:
        errors.append(f"unexpected batch_count: {forward.get('batch_count')}")
    if forward.get("execution_mode") != "pair_window_batch":
        errors.append(f"unexpected execution_mode: {forward.get('execution_mode')}")
    if forward.get("window_execution_mode") != "window-batch":
        errors.append(f"unexpected window_execution_mode: {forward.get('window_execution_mode')}")
    if forward.get("child_process_count") != 0:
        errors.append(f"unexpected child_process_count: {forward.get('child_process_count')}")
    final_shapes = forward.get("final_shapes") or []
    if len(final_shapes) != batch_count:
        errors.append(f"unexpected final_shapes length: {len(final_shapes)}")
    for shape in final_shapes:
        if shape != [1, 16, 152064]:
            errors.append(f"unexpected final_shape: {shape}")
else:
    final_shapes = []

if max_bpu_loading <= 0.0:
    errors.append(f"max_bpu_loading did not exceed zero: {max_bpu_loading}")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_runtime_telemetry_probe" if not errors else "failed_dream7b_bpu_runtime_telemetry_probe",
    "run_dir": str(run_dir),
    "batch_count": batch_count,
    "monitor_delay_ms": monitor_delay_ms,
    "monitor_sample_count": monitor_sample_count,
    "top_k": top_k,
    "timeout_sec": timeout_sec,
    "forward_status": forward_status,
    "forward_summary": str(summary_path),
    "bpu_loading_sample_count": len(bpu_loading_samples),
    "nonzero_bpu_loading_sample_count": nonzero_bpu_loading_sample_count,
    "max_bpu_loading": round(max_bpu_loading, 3),
    "avg_bpu_loading": round(avg_bpu_loading, 3),
    "cma_reserved_used_values": cma_used_values[:10],
    "carveout_used_values": carveout_used_values[:10],
    "monitor_stdout": str(monitor_stdout),
    "monitor_stderr": str(monitor_stderr),
    "monitor_stderr_excerpt": monitor_err[:500],
    "somstatus_before": str(somstatus_before),
    "somstatus_after": str(somstatus_after),
    "forward_metrics": {
        "verdict": forward.get("verdict") if isinstance(forward, dict) else None,
        "execution_mode": forward.get("execution_mode") if isinstance(forward, dict) else None,
        "window_execution_mode": forward.get("window_execution_mode") if isinstance(forward, dict) else None,
        "child_process_count": forward.get("child_process_count") if isinstance(forward, dict) else None,
        "wall_ms": forward.get("wall_ms") if isinstance(forward, dict) else None,
        "load_ms": forward.get("load_ms") if isinstance(forward, dict) else None,
        "run_ms": forward.get("run_ms") if isinstance(forward, dict) else None,
        "amortized_wall_ms_per_forward": forward.get("amortized_wall_ms_per_forward") if isinstance(forward, dict) else None,
        "amortized_load_ms_per_forward": forward.get("amortized_load_ms_per_forward") if isinstance(forward, dict) else None,
        "amortized_run_ms_per_forward": forward.get("amortized_run_ms_per_forward") if isinstance(forward, dict) else None,
        "final_shapes": final_shapes,
    },
    "errors": errors,
}
(run_dir / "runtime_telemetry_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
error_lines = [f"- {item}" for item in errors] if errors else ["- none"]
lines = [
    "# Dream 7B BPU Runtime Telemetry Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- run_dir: {payload['run_dir']}",
    f"- batch_count: {payload['batch_count']}",
    f"- monitor_delay_ms: {payload['monitor_delay_ms']}",
    f"- monitor_sample_count: {payload['monitor_sample_count']}",
    f"- bpu_loading_sample_count: {payload['bpu_loading_sample_count']}",
    f"- nonzero_bpu_loading_sample_count: {payload['nonzero_bpu_loading_sample_count']}",
    f"- max_bpu_loading: {payload['max_bpu_loading']}",
    f"- avg_bpu_loading: {payload['avg_bpu_loading']}",
    f"- forward_summary: {payload['forward_summary']}",
    f"- forward_wall_ms: {payload['forward_metrics']['wall_ms']}",
    f"- forward_load_ms: {payload['forward_metrics']['load_ms']}",
    f"- forward_run_ms: {payload['forward_metrics']['run_ms']}",
    f"- amortized_wall_ms_per_forward: {payload['forward_metrics']['amortized_wall_ms_per_forward']}",
    f"- amortized_load_ms_per_forward: {payload['forward_metrics']['amortized_load_ms_per_forward']}",
    f"- amortized_run_ms_per_forward: {payload['forward_metrics']['amortized_run_ms_per_forward']}",
    f"- final_shapes: {payload['forward_metrics']['final_shapes']}",
    "",
    "## Errors",
    "",
    *error_lines,
    "",
]
(run_dir / "runtime_telemetry_probe.md").write_text("\n".join(lines), encoding="utf-8")
print(run_dir / "runtime_telemetry_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
