#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
hbm_python="${DREAM7B_TRUE_BATCH_HBM_PYTHON:-/mnt/nas/openclaw/runtimes/hbm-runtime-venv/bin/python}"
probe_py="${DREAM7B_TRUE_BATCH_PROBE_PY:-/mnt/nas/openclaw/scripts/probes/dream7b_true_batch_runtime_chain_probe.py}"
hbm_root="${DREAM7B_TRUE_BATCH_HBM_ROOT:-/mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b2}"
batch_size="${DREAM7B_TRUE_BATCH_SIZE:-2}"
seq_len="${DREAM7B_TRUE_BATCH_SEQ_LEN:-16}"
vocab_size="${DREAM7B_TRUE_BATCH_VOCAB_SIZE:-152064}"
repeat="${DREAM7B_TRUE_BATCH_REPEAT:-64}"
monitor_delay_ms="${DREAM7B_TRUE_BATCH_MONITOR_DELAY_MS:-100}"
monitor_sample_count="${DREAM7B_TRUE_BATCH_MONITOR_SAMPLE_COUNT:-2400}"

case "$report_root" in
  /mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/tmp/*) ;;
  *) echo "Refusing report path outside approved report directories: $report_root" >&2; exit 2 ;;
esac
if [[ ! -x "$hbm_python" ]]; then
  echo "Missing executable HBM runtime Python: $hbm_python" >&2
  exit 2
fi
if [[ ! -f "$probe_py" ]]; then
  echo "Missing true-batch runtime probe: $probe_py" >&2
  exit 2
fi
if ! command -v hrt_ucp_monitor >/dev/null 2>&1; then
  echo "Missing hrt_ucp_monitor" >&2
  exit 2
fi

stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_true_batch_runtime_telemetry_${stamp}_b${batch_size}"
mkdir -p "$run_dir"

monitor_stdout="$run_dir/hrt_ucp_monitor.stdout"
monitor_stderr="$run_dir/hrt_ucp_monitor.stderr"
runner_stdout="$run_dir/runtime_chain.stdout"
runner_stderr="$run_dir/runtime_chain.stderr"

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
"$hbm_python" "$probe_py" \
  --hbm-root "$hbm_root" \
  --report-root "$run_dir" \
  --batch-size "$batch_size" \
  --seq-len "$seq_len" \
  --repeat "$repeat" \
  > "$runner_stdout" 2> "$runner_stderr"
runner_status="$?"
set -e

cleanup_monitor
trap - EXIT

python3 - "$run_dir" "$runner_status" "$repeat" "$monitor_delay_ms" "$batch_size" "$seq_len" "$vocab_size" <<'PY'
import json
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
runner_status = int(sys.argv[2])
repeat = int(sys.argv[3])
monitor_delay_ms = int(sys.argv[4])
batch_size = int(sys.argv[5])
seq_len = int(sys.argv[6])
vocab_size = int(sys.argv[7])
monitor_text = (run_dir / "hrt_ucp_monitor.stdout").read_text(encoding="utf-8", errors="replace")
samples = [float(item) for item in re.findall(r"\|\s*BPU0\s+([0-9]+(?:[.][0-9]+)?)\s*\|", monitor_text)]
nonzero = [item for item in samples if item > 0.0]
chain_reports = sorted(run_dir.glob("dream7b_true_batch_runtime_chain_*_b*/true_batch_runtime_chain.json"))
chain = json.loads(chain_reports[-1].read_text(encoding="utf-8")) if chain_reports else {}
errors = []
if runner_status != 0:
    errors.append(f"runner_status={runner_status}")
if not samples:
    errors.append("no_bpu_monitor_samples")
if chain.get("verdict") != "ok_dream7b_true_batch_runtime_chain":
    errors.append(f"chain_verdict={chain.get('verdict')}")
expected_final_shape = [batch_size, seq_len, vocab_size]
if chain.get("final_shape") != expected_final_shape:
    errors.append(f"final_shape={chain.get('final_shape')}")
payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_true_batch_runtime_telemetry" if not errors else "failed_dream7b_true_batch_runtime_telemetry",
    "run_dir": str(run_dir),
    "runner_status": runner_status,
    "repeat": repeat,
    "expected_final_shape": expected_final_shape,
    "monitor_delay_ms": monitor_delay_ms,
    "bpu_loading_sample_count": len(samples),
    "nonzero_bpu_loading_sample_count": len(nonzero),
    "avg_bpu_loading": round(statistics.fmean(samples), 3) if samples else 0.0,
    "avg_nonzero_bpu_loading": round(statistics.fmean(nonzero), 3) if nonzero else 0.0,
    "max_bpu_loading": max(samples) if samples else 0.0,
    "chain_report": str(chain_reports[-1]) if chain_reports else None,
    "chain_total_load_ms": chain.get("total_load_ms"),
    "chain_total_run_ms": chain.get("total_run_ms"),
    "chain_wall_ms": chain.get("wall_ms"),
    "chain_segment_count_executed": chain.get("segment_count_executed"),
    "chain_final_shape": chain.get("final_shape"),
    "errors": errors,
}
(run_dir / "true_batch_runtime_telemetry.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
lines = [
    "# Dream7B True Batch Runtime Telemetry",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- repeat: {payload['repeat']}",
    f"- avg_bpu_loading: {payload['avg_bpu_loading']}",
    f"- avg_nonzero_bpu_loading: {payload['avg_nonzero_bpu_loading']}",
    f"- max_bpu_loading: {payload['max_bpu_loading']}",
    f"- chain_total_run_ms: {payload['chain_total_run_ms']}",
    f"- chain_wall_ms: {payload['chain_wall_ms']}",
    f"- chain_final_shape: {payload['chain_final_shape']}",
    "",
    "## Errors",
    "",
]
lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
(run_dir / "true_batch_runtime_telemetry.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "true_batch_runtime_telemetry.json")
print(run_dir / "true_batch_runtime_telemetry.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
