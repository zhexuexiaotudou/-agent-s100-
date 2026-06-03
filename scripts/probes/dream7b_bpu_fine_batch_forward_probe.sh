#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

if ! command -v dream7b-bpu-fine-batch-forward >/dev/null 2>&1; then
  echo "Missing deployed command: dream7b-bpu-fine-batch-forward" >&2
  exit 4
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_fine_batch_forward_$stamp"
mkdir -p "$run_dir"
tokens_batch_json="$run_dir/tokens_batch.json"
stdout="$run_dir.stdout"
stderr="$run_dir.stderr"

cat > "$tokens_batch_json" <<'JSON'
[
  [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
  [16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1],
  [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116]
]
JSON

dream7b-bpu-fine-batch-forward \
  --tokens-batch-json "$tokens_batch_json" \
  --top-k 3 \
  --output-dir "$run_dir" > "$stdout" 2> "$stderr"

python3 - "$run_dir/summary.json" "$run_dir" <<'PY'
import json
import sys
from pathlib import Path

summary_path = Path(sys.argv[1])
run_dir = Path(sys.argv[2])
data = json.loads(summary_path.read_text(encoding="utf-8"))
errors = []
if data.get("verdict") != "ok_dream7b_segmented_hbm_python_forward":
    errors.append(f"unexpected verdict: {data.get('verdict')}")
if data.get("segment_plan") != "fine-adjacent":
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
if data.get("batch_count") != 3:
    errors.append(f"unexpected batch_count: {data.get('batch_count')}")
expected_shapes = [[1, 16, 152064], [1, 16, 152064], [1, 16, 152064]]
if data.get("final_shapes") != expected_shapes:
    errors.append(f"unexpected final_shapes: {data.get('final_shapes')}")
if len(data.get("segments", [])) != 30:
    errors.append(f"unexpected segment event count: {len(data.get('segments', []))}")
if any(item.get("resident_count", 0) > 2 for item in data.get("segments", [])):
    errors.append("resident_count exceeded two-segment window")
for metric in ("wall_ms", "load_ms", "run_ms", "amortized_wall_ms_per_forward", "amortized_load_ms_per_forward"):
    value = data.get(metric)
    if not isinstance(value, (int, float)) or value <= 0:
        errors.append(f"unexpected {metric}: {value}")

payload = {
    "verdict": "ok_dream7b_bpu_fine_batch_forward_probe" if not errors else "failed_dream7b_bpu_fine_batch_forward_probe",
    "summary": str(summary_path),
    "run_dir": str(run_dir),
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
        "final_shapes": data.get("final_shapes"),
        "segment_event_count": len(data.get("segments", [])),
        "wall_ms": data.get("wall_ms"),
        "load_ms": data.get("load_ms"),
        "run_ms": data.get("run_ms"),
        "amortized_wall_ms_per_forward": data.get("amortized_wall_ms_per_forward"),
        "amortized_load_ms_per_forward": data.get("amortized_load_ms_per_forward"),
    },
}
(run_dir / "fine_batch_forward_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(run_dir / "fine_batch_forward_probe.md").write_text(
    "\n".join([
        "# Dream 7B BPU Fine Batch Forward Probe",
        "",
        f"- verdict: {payload['verdict']}",
        f"- summary: {payload['summary']}",
        f"- segment_plan: {payload['checked']['segment_plan']}",
        f"- residency_window_size: {payload['checked']['residency_window_size']}",
        f"- execution_mode: {payload['checked']['execution_mode']}",
        f"- window_execution_mode: {payload['checked']['window_execution_mode']}",
        f"- child_window_mode: {payload['checked']['child_window_mode']}",
        f"- child_runtime_mode: {payload['checked']['child_runtime_mode']}",
        f"- child_process_count: {payload['checked']['child_process_count']}",
        f"- batch_count: {payload['checked']['batch_count']}",
        f"- wall_ms: {payload['checked']['wall_ms']}",
        f"- load_ms: {payload['checked']['load_ms']}",
        f"- run_ms: {payload['checked']['run_ms']}",
        f"- amortized_wall_ms_per_forward: {payload['checked']['amortized_wall_ms_per_forward']}",
        f"- amortized_load_ms_per_forward: {payload['checked']['amortized_load_ms_per_forward']}",
        f"- final_shapes: {payload['checked']['final_shapes']}",
        f"- segment_event_count: {payload['checked']['segment_event_count']}",
        "",
    ]) + "\n",
    encoding="utf-8",
)
print(run_dir / "fine_batch_forward_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
