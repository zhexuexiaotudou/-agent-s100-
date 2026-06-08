#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
forward_cmd="${DREAM7B_BPU_WINDOW3_FORWARD_CMD:-dream7b-bpu-fine-batch-forward}"
timeout_sec="${DREAM7B_BPU_WINDOW3_FORWARD_TIMEOUT_SEC:-240}"
top_k="${DREAM7B_BPU_WINDOW3_FORWARD_TOP_K:-3}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

if ! [[ "$timeout_sec" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_WINDOW3_FORWARD_TIMEOUT_SEC must be a positive integer." >&2
  exit 2
fi
if ! [[ "$top_k" =~ ^[0-9]+$ ]]; then
  echo "DREAM7B_BPU_WINDOW3_FORWARD_TOP_K must be a non-negative integer." >&2
  exit 2
fi
if ! command -v "$forward_cmd" >/dev/null 2>&1; then
  echo "Missing deployed S100P command: $forward_cmd" >&2
  exit 4
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_window3_forward_feasibility_$stamp"
mkdir -p "$run_dir"

python3 - \
  "$run_dir" \
  "$forward_cmd" \
  "$timeout_sec" \
  "$top_k" <<'PY'
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
forward_cmd = sys.argv[2]
timeout_sec = int(sys.argv[3])
top_k = int(sys.argv[4])

forward_dir = run_dir / "forward"
forward_dir.mkdir(parents=True, exist_ok=True)
stdout_path = run_dir / "forward.stdout"
stderr_path = run_dir / "forward.stderr"
returncode_path = run_dir / "forward.returncode"

env = os.environ.copy()
env.update(
    {
        "DREAM7B_BPU_FINE_BATCH_WINDOW_SIZE": "3",
        "DREAM7B_BPU_FINE_BATCH_CHILD_WINDOW_MODE": "pair",
        "DREAM7B_BPU_FINE_BATCH_CHILD_RUNTIME_MODE": "packed",
        "DREAM7B_BPU_FINE_BATCH_WINDOW_EXECUTION_MODE": "window-batch",
    }
)
cmd = [
    forward_cmd,
    "--output-dir",
    str(forward_dir),
    "--seq-len",
    "16",
    "--top-k",
    str(top_k),
]
started = time.monotonic()
timed_out = False
try:
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout_sec, env=env)
    returncode = proc.returncode
    stdout = proc.stdout
    stderr = proc.stderr
except subprocess.TimeoutExpired as exc:
    timed_out = True
    returncode = 124
    stdout = exc.stdout or ""
    stderr = exc.stderr or f"timed out after {timeout_sec} seconds"
wall_ms = round((time.monotonic() - started) * 1000, 3)
stdout_path.write_text(stdout, encoding="utf-8")
stderr_path.write_text(stderr, encoding="utf-8")
returncode_path.write_text(str(returncode) + "\n", encoding="utf-8")

summary_path = forward_dir / "summary.json"
summary = None
if summary_path.is_file():
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

stderr_text = stderr or ""
direct_window3_forward_supported = (
    returncode == 0
    and isinstance(summary, dict)
    and summary.get("verdict") == "ok_dream7b_segmented_hbm_python_forward"
    and summary.get("residency_window_size") == 3
    and summary.get("window_execution_mode") == "window-batch"
)
stderr_contains_memory_alloc_failure = "-400001" in stderr_text and "Memory alloc failed" in stderr_text
expected_window3_failure_observed = returncode != 0 and stderr_contains_memory_alloc_failure
if direct_window3_forward_supported:
    next_optimization_target = "compare window3 forward throughput against the current pair-window production path before changing defaults"
elif expected_window3_failure_observed:
    next_optimization_target = "do not switch production defaults to window3; use selected stable triplet worker or a new HBM split for the next forward-path experiment"
else:
    next_optimization_target = "inspect non-memory-allocation window3 failure before changing production defaults"

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_window3_forward_feasibility_probe",
    "run_dir": str(run_dir),
    "forward_cmd": forward_cmd,
    "forward_dir": str(forward_dir),
    "command": cmd,
    "timeout_sec": timeout_sec,
    "top_k": top_k,
    "returncode": returncode,
    "timed_out": timed_out,
    "wall_ms": wall_ms,
    "stdout": str(stdout_path),
    "stderr": str(stderr_path),
    "summary_json": str(summary_path) if summary_path.is_file() else "",
    "direct_window3_forward_supported": direct_window3_forward_supported,
    "expected_window3_failure_observed": expected_window3_failure_observed,
    "stderr_contains_memory_alloc_failure": stderr_contains_memory_alloc_failure,
    "window_size": 3,
    "child_window_mode": "pair",
    "child_runtime_mode": "packed",
    "window_execution_mode": "window-batch",
    "next_optimization_target": next_optimization_target,
    "errors": [],
}
(run_dir / "window3_forward_feasibility_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

stderr_excerpt = "\n".join(stderr_text.splitlines()[-20:])
lines = [
    "# Dream 7B BPU Window3 Forward Feasibility Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- forward_cmd: {payload['forward_cmd']}",
    f"- returncode: {payload['returncode']}",
    f"- direct_window3_forward_supported: {payload['direct_window3_forward_supported']}",
    f"- expected_window3_failure_observed: {payload['expected_window3_failure_observed']}",
    f"- stderr_contains_memory_alloc_failure: {payload['stderr_contains_memory_alloc_failure']}",
    f"- next_optimization_target: {payload['next_optimization_target']}",
    "",
    "## Stderr Excerpt",
    "",
    "```text",
    stderr_excerpt,
    "```",
    "",
    "## Boundary",
    "",
    "- This probe tests whether the existing `dream7b-bpu-fine-batch-forward` path can directly run packed adjacent three-segment windows.",
    "- A memory-allocation failure means the default pair-window path must stay in place until a selected-triplet worker path or new HBM split is verified.",
]
(run_dir / "window3_forward_feasibility_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "window3_forward_feasibility_probe.md")
PY
