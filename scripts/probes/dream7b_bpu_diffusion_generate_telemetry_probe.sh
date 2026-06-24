#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
prompt="${DREAM7B_BPU_DIFFUSION_GENERATE_TELEMETRY_PROMPT:-hello}"
generate_cmd="${DREAM7B_BPU_DIFFUSION_GENERATE_TELEMETRY_CMD:-dream7b-bpu-diffusion-generate}"
monitor_delay_ms="${DREAM7B_BPU_DIFFUSION_GENERATE_TELEMETRY_MONITOR_DELAY_MS:-100}"
monitor_sample_count="${DREAM7B_BPU_DIFFUSION_GENERATE_TELEMETRY_MONITOR_SAMPLE_COUNT:-900}"
timeout_sec="${DREAM7B_BPU_DIFFUSION_GENERATE_TELEMETRY_TIMEOUT_SEC:-900}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

if ! [[ "$monitor_delay_ms" =~ ^[0-9]+$ ]] || (( monitor_delay_ms < 100 || monitor_delay_ms > 10000 )); then
  echo "DREAM7B_BPU_DIFFUSION_GENERATE_TELEMETRY_MONITOR_DELAY_MS must be an integer from 100 to 10000." >&2
  exit 2
fi
if ! [[ "$monitor_sample_count" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_DIFFUSION_GENERATE_TELEMETRY_MONITOR_SAMPLE_COUNT must be a positive integer." >&2
  exit 2
fi
if ! [[ "$timeout_sec" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_DIFFUSION_GENERATE_TELEMETRY_TIMEOUT_SEC must be a positive integer." >&2
  exit 2
fi

if ! command -v "$generate_cmd" >/dev/null 2>&1; then
  echo "Missing deployed command: $generate_cmd" >&2
  exit 4
fi
if ! command -v hrt_ucp_monitor >/dev/null 2>&1; then
  echo "Missing deployed command: hrt_ucp_monitor" >&2
  exit 4
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_diffusion_generate_telemetry_$stamp"
generation_dir="$run_dir/generation"
mkdir -p "$run_dir" "$generation_dir"
monitor_stdout="$run_dir/hrt_ucp_monitor.stdout"
monitor_stderr="$run_dir/hrt_ucp_monitor.stderr"
generation_stdout="$run_dir/generation.stdout"
generation_stderr="$run_dir/generation.stderr"
somstatus_before="$run_dir/hrut_somstatus_before.txt"
somstatus_after="$run_dir/hrut_somstatus_after.txt"

hrut_somstatus > "$somstatus_before" 2>&1 || true
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
timeout "$timeout_sec" "$generate_cmd" \
  --run-dir "$generation_dir" \
  --prompt "$prompt" > "$generation_stdout" 2> "$generation_stderr"
generation_status="$?"
set -e

cleanup_monitor
trap - EXIT
hrut_somstatus > "$somstatus_after" 2>&1 || true

python3 - \
  "$run_dir" \
  "$generation_dir" \
  "$prompt" \
  "$generate_cmd" \
  "$monitor_delay_ms" \
  "$monitor_sample_count" \
  "$timeout_sec" \
  "$generation_status" <<'PY'
import json
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
generation_dir = Path(sys.argv[2])
prompt = sys.argv[3]
generate_cmd = sys.argv[4]
monitor_delay_ms = int(sys.argv[5])
monitor_sample_count = int(sys.argv[6])
timeout_sec = int(sys.argv[7])
generation_status = int(sys.argv[8])
monitor_stdout = run_dir / "hrt_ucp_monitor.stdout"
monitor_stderr = run_dir / "hrt_ucp_monitor.stderr"
generation_stdout = run_dir / "generation.stdout"
generation_stderr = run_dir / "generation.stderr"
generation_json = generation_dir / "generation.json"
generation_md = generation_dir / "generation.md"
somstatus_before = run_dir / "hrut_somstatus_before.txt"
somstatus_after = run_dir / "hrut_somstatus_after.txt"
errors = []

monitor_text = monitor_stdout.read_text(encoding="utf-8", errors="replace") if monitor_stdout.is_file() else ""
monitor_err = monitor_stderr.read_text(encoding="utf-8", errors="replace") if monitor_stderr.is_file() else ""
generation_err = generation_stderr.read_text(encoding="utf-8", errors="replace") if generation_stderr.is_file() else ""
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
if generation_status != 0:
    errors.append(f"generation command exited with status {generation_status}")

generation = None
if generation_json.is_file():
    generation = json.loads(generation_json.read_text(encoding="utf-8"))
else:
    errors.append(f"missing generation.json: {generation_json}")

history = []
if isinstance(generation, dict):
    history = generation.get("history") or []
    if generation.get("verdict") != "ok_dream7b_bpu_diffusion_generate":
        errors.append(f"unexpected generation verdict: {generation.get('verdict')}")
    if generation.get("forward_cmd") != "dream7b-bpu-fine-forward":
        errors.append(f"unexpected forward_cmd: {generation.get('forward_cmd')}")
    if generation.get("seq_len") != 16:
        errors.append(f"unexpected seq_len: {generation.get('seq_len')}")
    if int(generation.get("executed_step_count") or 0) != len(history):
        errors.append(f"executed_step_count does not match history length: {generation.get('executed_step_count')} vs {len(history)}")
    if int(generation.get("executed_step_count") or 0) < 1:
        errors.append(f"executed_step_count is below 1: {generation.get('executed_step_count')}")
    if generation.get("remaining_mask_positions") != []:
        errors.append(f"remaining_mask_positions is not empty: {generation.get('remaining_mask_positions')}")
    if not generation.get("decoded_final"):
        errors.append("decoded_final is empty")
    if generation.get("boundary") != "bounded_seq16_generation_entrypoint_not_complete_production_text_service":
        errors.append(f"unexpected boundary: {generation.get('boundary')}")
    if generation.get("errors"):
        errors.append(f"generation errors not empty: {generation.get('errors')}")
    for item in history:
        step = item.get("step")
        if item.get("forward_verdict") != "ok_dream7b_segmented_hbm_python_forward":
            errors.append(f"unexpected forward_verdict at step {step}: {item.get('forward_verdict')}")
        if item.get("forward_execution_mode") != "pair_in_process":
            errors.append(f"unexpected forward_execution_mode at step {step}: {item.get('forward_execution_mode')}")
        if item.get("forward_window_execution_mode") != "in-process":
            errors.append(f"unexpected forward_window_execution_mode at step {step}: {item.get('forward_window_execution_mode')}")
        if item.get("forward_child_process_count") != 0:
            errors.append(f"unexpected forward_child_process_count at step {step}: {item.get('forward_child_process_count')}")
        if item.get("forward_final_shape") != [1, 16, 152064]:
            errors.append(f"unexpected forward_final_shape at step {step}: {item.get('forward_final_shape')}")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_diffusion_generate_telemetry_probe" if not errors else "failed_dream7b_bpu_diffusion_generate_telemetry_probe",
    "run_dir": str(run_dir),
    "generation_dir": str(generation_dir),
    "prompt": prompt,
    "generate_cmd": generate_cmd,
    "monitor_delay_ms": monitor_delay_ms,
    "monitor_sample_count": monitor_sample_count,
    "timeout_sec": timeout_sec,
    "generation_status": generation_status,
    "generation_json": str(generation_json),
    "generation_md": str(generation_md),
    "bpu_loading_sample_count": len(bpu_loading_samples),
    "nonzero_bpu_loading_sample_count": nonzero_bpu_loading_sample_count,
    "max_bpu_loading": round(max_bpu_loading, 3),
    "avg_bpu_loading": round(avg_bpu_loading, 3),
    "cma_reserved_used_values": cma_used_values[:10],
    "carveout_used_values": carveout_used_values[:10],
    "monitor_stdout": str(monitor_stdout),
    "monitor_stderr": str(monitor_stderr),
    "monitor_stderr_excerpt": monitor_err[:500],
    "generation_stdout": str(generation_stdout),
    "generation_stderr": str(generation_stderr),
    "generation_stderr_excerpt": generation_err[:500],
    "somstatus_before": str(somstatus_before),
    "somstatus_after": str(somstatus_after),
    "generation_metrics": {
        "verdict": generation.get("verdict") if isinstance(generation, dict) else None,
        "forward_cmd": generation.get("forward_cmd") if isinstance(generation, dict) else None,
        "seq_len": generation.get("seq_len") if isinstance(generation, dict) else None,
        "steps": generation.get("steps") if isinstance(generation, dict) else None,
        "executed_step_count": generation.get("executed_step_count") if isinstance(generation, dict) else None,
        "remaining_mask_positions": generation.get("remaining_mask_positions") if isinstance(generation, dict) else None,
        "decoded_final": generation.get("decoded_final") if isinstance(generation, dict) else None,
        "boundary": generation.get("boundary") if isinstance(generation, dict) else None,
        "history_forward_verdicts": [item.get("forward_verdict") for item in history],
        "history_forward_execution_modes": [item.get("forward_execution_mode") for item in history],
        "history_forward_window_execution_modes": [item.get("forward_window_execution_mode") for item in history],
        "history_forward_child_process_counts": [item.get("forward_child_process_count") for item in history],
        "history_forward_final_shapes": [item.get("forward_final_shape") for item in history],
    },
    "errors": errors,
}
(run_dir / "generation_telemetry_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
error_lines = [f"- {item}" for item in errors] if errors else ["- none"]
lines = [
    "# Dream 7B BPU Diffusion Generate Telemetry Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- run_dir: {payload['run_dir']}",
    f"- generation_dir: {payload['generation_dir']}",
    f"- prompt: {payload['prompt']}",
    f"- generate_cmd: {payload['generate_cmd']}",
    f"- monitor_delay_ms: {payload['monitor_delay_ms']}",
    f"- monitor_sample_count: {payload['monitor_sample_count']}",
    f"- generation_status: {payload['generation_status']}",
    f"- generation_json: {payload['generation_json']}",
    f"- bpu_loading_sample_count: {payload['bpu_loading_sample_count']}",
    f"- nonzero_bpu_loading_sample_count: {payload['nonzero_bpu_loading_sample_count']}",
    f"- max_bpu_loading: {payload['max_bpu_loading']}",
    f"- avg_bpu_loading: {payload['avg_bpu_loading']}",
    f"- generation_verdict: {payload['generation_metrics']['verdict']}",
    f"- executed_step_count: {payload['generation_metrics']['executed_step_count']}",
    f"- remaining_mask_positions: {payload['generation_metrics']['remaining_mask_positions']}",
    "",
    "## Decoded Final",
    "",
    "```text",
    str(payload["generation_metrics"]["decoded_final"] or ""),
    "```",
    "",
    "## Errors",
    "",
    *error_lines,
    "",
]
(run_dir / "generation_telemetry_probe.md").write_text("\n".join(lines), encoding="utf-8")
print(run_dir / "generation_telemetry_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
