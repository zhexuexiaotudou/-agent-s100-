#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
forward_cmd="${DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_FORWARD_CMD:-dream7b-bpu-selected-pair-batch-forward}"
batch_count="${DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_BATCH_COUNT:-16}"
top_k="${DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_TOP_K:-3}"
timeout_sec="${DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_TIMEOUT_SEC:-900}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac
if ! [[ "$batch_count" =~ ^[1-9][0-9]*$ ]] || (( batch_count > 16 )); then
  echo "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_BATCH_COUNT must be an integer from 1 to 16." >&2
  exit 2
fi
if ! [[ "$top_k" =~ ^[0-9]+$ ]]; then
  echo "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_TOP_K must be a non-negative integer." >&2
  exit 2
fi
if ! [[ "$timeout_sec" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_TIMEOUT_SEC must be a positive integer." >&2
  exit 2
fi
if ! command -v "$forward_cmd" >/dev/null 2>&1; then
  echo "Missing deployed command: $forward_cmd" >&2
  exit 4
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_selected_pair_candidate_forward_$stamp"
mkdir -p "$run_dir"
tokens_batch_json="$run_dir/tokens_batch.json"
forward_dir="$run_dir/forward"
stdout_path="$run_dir/forward.stdout"
stderr_path="$run_dir/forward.stderr"

python3 - "$tokens_batch_json" "$batch_count" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
batch_count = int(sys.argv[2])
seq_len = 16
rows = []
for batch_index in range(batch_count):
    base = (batch_index + 1) * 100
    rows.append([base + offset for offset in range(1, seq_len + 1)])
path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

set +e
timeout "$timeout_sec" "$forward_cmd" \
  --tokens-batch-json "$tokens_batch_json" \
  --top-k "$top_k" \
  --output-dir "$forward_dir" > "$stdout_path" 2> "$stderr_path"
forward_status="$?"
set -e

python3 - \
  "$run_dir" \
  "$forward_cmd" \
  "$batch_count" \
  "$top_k" \
  "$timeout_sec" \
  "$tokens_batch_json" \
  "$forward_dir" \
  "$stdout_path" \
  "$stderr_path" \
  "$forward_status" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
forward_cmd = sys.argv[2]
batch_count = int(sys.argv[3])
top_k = int(sys.argv[4])
timeout_sec = int(sys.argv[5])
tokens_batch_json = Path(sys.argv[6])
forward_dir = Path(sys.argv[7])
stdout_path = Path(sys.argv[8])
stderr_path = Path(sys.argv[9])
forward_status = int(sys.argv[10])

errors = []
warnings = []
summary_path = forward_dir / "summary.json"
summary = {}
if forward_status != 0:
    errors.append(f"selected pair candidate forward exited with status {forward_status}")
if summary_path.is_file():
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
else:
    errors.append(f"missing selected pair candidate summary: {summary_path}")

expected_shapes = [[1, 16, 152064] for _ in range(batch_count)]
if summary:
    if summary.get("verdict") != "ok_dream7b_segmented_hbm_python_forward":
        errors.append(f"unexpected forward verdict: {summary.get('verdict')}")
    if summary.get("selected_pair_candidate") is not True:
        errors.append(f"selected_pair_candidate is not true: {summary.get('selected_pair_candidate')}")
    if summary.get("execution_mode") != "pair_window_batch":
        errors.append(f"unexpected execution_mode: {summary.get('execution_mode')}")
    if summary.get("window_execution_mode") != "selected-pair-resident":
        errors.append(f"unexpected window_execution_mode: {summary.get('window_execution_mode')}")
    if int(summary.get("batch_count") or 0) != batch_count:
        errors.append(f"unexpected batch_count: {summary.get('batch_count')}")
    if summary.get("selected_pair") != [1, 8]:
        errors.append(f"unexpected selected_pair: {summary.get('selected_pair')}")
    if summary.get("selected_segments") != ["seg02_04", "seg24_26"]:
        errors.append(f"unexpected selected_segments: {summary.get('selected_segments')}")
    if summary.get("selected_pair_covers_all_segments") is not True:
        errors.append(f"selected_pair_covers_all_segments is not true: {summary.get('selected_pair_covers_all_segments')}")
    if summary.get("final_shapes") != expected_shapes:
        errors.append(f"unexpected final_shapes: {summary.get('final_shapes')}")
    if not summary.get("source_probe_json"):
        errors.append("summary missing source_probe_json")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_selected_pair_candidate_forward_probe" if not errors else "failed_dream7b_bpu_selected_pair_candidate_forward_probe",
    "run_dir": str(run_dir),
    "forward_cmd": forward_cmd,
    "batch_count": batch_count,
    "top_k": top_k,
    "timeout_sec": timeout_sec,
    "tokens_batch_json": str(tokens_batch_json),
    "forward_dir": str(forward_dir),
    "forward_status": forward_status,
    "summary_json": str(summary_path) if summary_path.is_file() else "",
    "summary_verdict": summary.get("verdict"),
    "selected_pair_candidate": summary.get("selected_pair_candidate"),
    "execution_mode": summary.get("execution_mode"),
    "window_execution_mode": summary.get("window_execution_mode"),
    "child_process_count": summary.get("child_process_count"),
    "selected_pair": summary.get("selected_pair"),
    "selected_segments": summary.get("selected_segments"),
    "selected_pair_covers_all_segments": summary.get("selected_pair_covers_all_segments"),
    "load_ms": summary.get("load_ms"),
    "warm_load_ms": summary.get("warm_load_ms"),
    "run_ms": summary.get("run_ms"),
    "wall_ms": summary.get("wall_ms"),
    "amortized_wall_ms_per_forward": summary.get("amortized_wall_ms_per_forward"),
    "source_probe_json": summary.get("source_probe_json"),
    "stdout": str(stdout_path),
    "stderr": str(stderr_path),
    "next_optimization_target": "wire this selected-pair candidate forward command into a guarded service candidate and re-run deployment acceptance before replacing the current default service path",
    "warnings": warnings,
    "errors": errors,
}
(run_dir / "selected_pair_candidate_forward_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Dream 7B BPU Selected Pair Candidate Forward Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- run_dir: {payload['run_dir']}",
    f"- forward_cmd: {payload['forward_cmd']}",
    f"- batch_count: {payload['batch_count']}",
    f"- summary_json: {payload['summary_json']}",
    f"- selected_pair_candidate: {payload['selected_pair_candidate']}",
    f"- selected_pair: {payload['selected_pair']}",
    f"- selected_segments: {payload['selected_segments']}",
    f"- selected_pair_covers_all_segments: {payload['selected_pair_covers_all_segments']}",
    f"- wall_ms: {payload['wall_ms']}",
    f"- warm_load_ms: {payload['warm_load_ms']}",
    f"- next_optimization_target: {payload['next_optimization_target']}",
    "",
    "## Warnings",
    "",
]
lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- none")
lines.extend(["", "## Errors", ""])
lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
(run_dir / "selected_pair_candidate_forward_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "selected_pair_candidate_forward_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
