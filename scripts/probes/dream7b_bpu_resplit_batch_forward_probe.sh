#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
batch_count="${DREAM7B_BPU_RESPLIT_BATCH_FORWARD_COUNT:-16}"
top_k="${DREAM7B_BPU_RESPLIT_BATCH_FORWARD_TOP_K:-3}"
timeout_sec="${DREAM7B_BPU_RESPLIT_BATCH_FORWARD_TIMEOUT_SEC:-900}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

if ! [[ "$batch_count" =~ ^[1-9][0-9]*$ ]] || (( batch_count > 16 )); then
  echo "DREAM7B_BPU_RESPLIT_BATCH_FORWARD_COUNT must be an integer from 1 to 16." >&2
  exit 2
fi
if ! [[ "$top_k" =~ ^[0-9]+$ ]]; then
  echo "DREAM7B_BPU_RESPLIT_BATCH_FORWARD_TOP_K must be a non-negative integer." >&2
  exit 2
fi
if ! [[ "$timeout_sec" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_RESPLIT_BATCH_FORWARD_TIMEOUT_SEC must be a positive integer." >&2
  exit 2
fi

if ! command -v dream7b-bpu-resplit-batch-forward >/dev/null 2>&1; then
  echo "Missing deployed command: dream7b-bpu-resplit-batch-forward" >&2
  exit 4
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_resplit_batch_forward_$stamp"
mkdir -p "$run_dir"
tokens_batch_json="$run_dir/tokens_batch.json"
stdout="$run_dir.stdout"
stderr="$run_dir.stderr"

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

set +e
timeout "$timeout_sec" dream7b-bpu-resplit-batch-forward \
  --tokens-batch-json "$tokens_batch_json" \
  --top-k "$top_k" \
  --output-dir "$run_dir/forward" > "$stdout" 2> "$stderr"
forward_status="$?"
set -e

python3 - "$run_dir/forward/summary.json" "$run_dir" "$batch_count" "$top_k" "$timeout_sec" "$forward_status" <<'PY'
import json
import sys
from pathlib import Path

summary_path = Path(sys.argv[1])
run_dir = Path(sys.argv[2])
expected_batch_count = int(sys.argv[3])
top_k = int(sys.argv[4])
timeout_sec = int(sys.argv[5])
forward_status = int(sys.argv[6])
errors = []
data = {}

if forward_status != 0:
    errors.append(f"forward command exited with status {forward_status}")
if summary_path.is_file():
    data = json.loads(summary_path.read_text(encoding="utf-8"))
else:
    errors.append(f"missing summary: {summary_path}")

segments = data.get("segments", []) if isinstance(data, dict) else []
final_shapes = data.get("final_shapes", []) if isinstance(data, dict) else []
topk_by_batch = data.get("topk_last_position_by_batch", []) if isinstance(data, dict) else []
segment_sources = sorted({item.get("source") for item in segments})
expected_segment_event_count = expected_batch_count * 14

if data.get("verdict") != "ok_dream7b_segmented_hbm_python_forward":
    errors.append(f"unexpected verdict: {data.get('verdict')}")
if data.get("segment_plan") != "resplit-adjacent":
    errors.append(f"unexpected segment_plan: {data.get('segment_plan')}")
if data.get("residency_window_size") != 2:
    errors.append(f"unexpected residency_window_size: {data.get('residency_window_size')}")
if data.get("execution_mode") != "pair_window_batch":
    errors.append(f"unexpected execution_mode: {data.get('execution_mode')}")
if data.get("window_execution_mode") != "window-batch":
    errors.append(f"unexpected window_execution_mode: {data.get('window_execution_mode')}")
if data.get("child_window_mode") != "pair":
    errors.append(f"unexpected child_window_mode: {data.get('child_window_mode')}")
if data.get("child_runtime_mode") != "packed":
    errors.append(f"unexpected child_runtime_mode: {data.get('child_runtime_mode')}")
if data.get("child_process_count") != 0:
    errors.append(f"unexpected child_process_count: {data.get('child_process_count')}")
if data.get("batch_count") != expected_batch_count:
    errors.append(f"unexpected batch_count: {data.get('batch_count')}")
if data.get("top_k") != top_k:
    errors.append(f"unexpected top_k: {data.get('top_k')}")
if len(final_shapes) != expected_batch_count:
    errors.append(f"unexpected final_shapes length: {len(final_shapes)}")
for shape in final_shapes:
    if shape != [1, 16, 152064]:
        errors.append(f"unexpected final_shape: {shape}")
if len(topk_by_batch) != expected_batch_count:
    errors.append(f"unexpected topk_last_position_by_batch length: {len(topk_by_batch)}")
if len(segments) != expected_segment_event_count:
    errors.append(f"unexpected segment event count: {len(segments)}")
if segment_sources != ["base", "fine", "resplit"]:
    errors.append(f"unexpected segment sources: {segment_sources}")
if any(item.get("resident_count", 0) > 2 for item in segments):
    errors.append("resident_count exceeded two-segment window")
for metric in ("wall_ms", "load_ms", "run_ms", "amortized_wall_ms_per_forward", "amortized_load_ms_per_forward", "amortized_run_ms_per_forward"):
    value = data.get(metric)
    if not isinstance(value, (int, float)) or value <= 0:
        errors.append(f"unexpected {metric}: {value}")

payload = {
    "verdict": "ok_dream7b_bpu_resplit_batch_forward_probe" if not errors else "failed_dream7b_bpu_resplit_batch_forward_probe",
    "summary": str(summary_path),
    "run_dir": str(run_dir),
    "forward_status": forward_status,
    "timeout_sec": timeout_sec,
    "errors": errors,
    "checked": {
        "segment_plan": data.get("segment_plan"),
        "residency_window_size": data.get("residency_window_size"),
        "execution_mode": data.get("execution_mode"),
        "window_execution_mode": data.get("window_execution_mode"),
        "child_window_mode": data.get("child_window_mode"),
        "child_runtime_mode": data.get("child_runtime_mode"),
        "child_process_count": data.get("child_process_count"),
        "batch_count": data.get("batch_count"),
        "top_k": data.get("top_k"),
        "topk_last_position_by_batch_count": len(topk_by_batch),
        "final_shape_count": len(final_shapes),
        "segment_event_count": len(segments),
        "expected_segment_event_count": expected_segment_event_count,
        "segment_sources": segment_sources,
        "hbm_dir": data.get("hbm_dir"),
        "fine_hbm_dir": data.get("fine_hbm_dir"),
        "resplit_hbm_dir": data.get("resplit_hbm_dir"),
        "wall_ms": data.get("wall_ms"),
        "load_ms": data.get("load_ms"),
        "run_ms": data.get("run_ms"),
        "amortized_wall_ms_per_forward": data.get("amortized_wall_ms_per_forward"),
        "amortized_load_ms_per_forward": data.get("amortized_load_ms_per_forward"),
        "amortized_run_ms_per_forward": data.get("amortized_run_ms_per_forward"),
        "load_to_run_ratio": round(float(data.get("load_ms", 0.0)) / float(data.get("run_ms", 1.0)), 6) if data.get("run_ms") else None,
    },
}
(run_dir / "resplit_batch_forward_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(run_dir / "resplit_batch_forward_probe.md").write_text(
    "\n".join([
        "# Dream 7B BPU Resplit Batch Forward Probe",
        "",
        f"- verdict: {payload['verdict']}",
        f"- summary: {payload['summary']}",
        f"- segment_plan: {payload['checked']['segment_plan']}",
        f"- batch_count: {payload['checked']['batch_count']}",
        f"- execution_mode: {payload['checked']['execution_mode']}",
        f"- window_execution_mode: {payload['checked']['window_execution_mode']}",
        f"- child_process_count: {payload['checked']['child_process_count']}",
        f"- final_shape_count: {payload['checked']['final_shape_count']}",
        f"- topk_last_position_by_batch_count: {payload['checked']['topk_last_position_by_batch_count']}",
        f"- segment_event_count: {payload['checked']['segment_event_count']}",
        f"- expected_segment_event_count: {payload['checked']['expected_segment_event_count']}",
        f"- segment_sources: {payload['checked']['segment_sources']}",
        f"- wall_ms: {payload['checked']['wall_ms']}",
        f"- load_ms: {payload['checked']['load_ms']}",
        f"- run_ms: {payload['checked']['run_ms']}",
        f"- amortized_wall_ms_per_forward: {payload['checked']['amortized_wall_ms_per_forward']}",
        f"- amortized_load_ms_per_forward: {payload['checked']['amortized_load_ms_per_forward']}",
        f"- amortized_run_ms_per_forward: {payload['checked']['amortized_run_ms_per_forward']}",
        f"- load_to_run_ratio: {payload['checked']['load_to_run_ratio']}",
        "",
        "## Errors",
        "",
        *([f"- {item}" for item in errors] if errors else ["- none"]),
        "",
    ]) + "\n",
    encoding="utf-8",
)
print(run_dir / "resplit_batch_forward_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
