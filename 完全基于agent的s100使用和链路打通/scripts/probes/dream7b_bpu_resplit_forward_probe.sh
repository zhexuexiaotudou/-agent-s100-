#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
tokens="${2:-1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16}"
expected_base_hbm_dir="${DREAM7B_BPU_RESPLIT_FORWARD_EXPECTED_BASE_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/segments6}"
expected_fine_hbm_dir="${DREAM7B_BPU_RESPLIT_FORWARD_EXPECTED_FINE_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16}"
expected_resplit_hbm_dir="${DREAM7B_BPU_RESPLIT_FORWARD_EXPECTED_RESPLIT_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/resplit-seq16}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

if ! command -v dream7b-bpu-resplit-forward >/dev/null 2>&1; then
  echo "Missing deployed command: dream7b-bpu-resplit-forward" >&2
  exit 4
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_resplit_forward_$stamp"
stdout="$run_dir.stdout"
stderr="$run_dir.stderr"

dream7b-bpu-resplit-forward \
  --tokens "$tokens" \
  --top-k 5 \
  --output-dir "$run_dir" > "$stdout" 2> "$stderr"

python3 - \
  "$run_dir/summary.json" \
  "$run_dir" \
  "$stdout" \
  "$stderr" \
  "$expected_base_hbm_dir" \
  "$expected_fine_hbm_dir" \
  "$expected_resplit_hbm_dir" <<'PY'
import json
import sys
from pathlib import Path

summary_path = Path(sys.argv[1])
run_dir = Path(sys.argv[2])
stdout_path = Path(sys.argv[3])
stderr_path = Path(sys.argv[4])
expected_base_hbm_dir = sys.argv[5]
expected_fine_hbm_dir = sys.argv[6]
expected_resplit_hbm_dir = sys.argv[7]

data = json.loads(summary_path.read_text(encoding="utf-8"))
segments = data.get("segments", [])
sources = sorted({item.get("source") for item in segments})
errors = []

if data.get("verdict") != "ok_dream7b_segmented_hbm_python_forward":
    errors.append(f"unexpected summary verdict: {data.get('verdict')}")
if data.get("segment_plan") != "resplit-adjacent":
    errors.append(f"unexpected segment_plan: {data.get('segment_plan')}")
if data.get("residency_window_size") != 2:
    errors.append(f"unexpected residency_window_size: {data.get('residency_window_size')}")
if data.get("execution_mode") != "pair_in_process":
    errors.append(f"unexpected execution_mode: {data.get('execution_mode')}")
if data.get("window_execution_mode") != "in-process":
    errors.append(f"unexpected window_execution_mode: {data.get('window_execution_mode')}")
if data.get("child_window_mode") != "pair":
    errors.append(f"unexpected child_window_mode: {data.get('child_window_mode')}")
if data.get("child_runtime_mode") != "packed":
    errors.append(f"unexpected child_runtime_mode: {data.get('child_runtime_mode')}")
if data.get("child_process_count") != 0:
    errors.append(f"unexpected child_process_count: {data.get('child_process_count')}")
if data.get("hbm_dir") != expected_base_hbm_dir:
    errors.append(f"unexpected hbm_dir: {data.get('hbm_dir')}")
if data.get("fine_hbm_dir") != expected_fine_hbm_dir:
    errors.append(f"unexpected fine_hbm_dir: {data.get('fine_hbm_dir')}")
if data.get("resplit_hbm_dir") != expected_resplit_hbm_dir:
    errors.append(f"unexpected resplit_hbm_dir: {data.get('resplit_hbm_dir')}")
if data.get("batch_count") != 1:
    errors.append(f"unexpected batch_count: {data.get('batch_count')}")
if data.get("top_k", 0) < 1:
    errors.append(f"unexpected top_k: {data.get('top_k')}")
if not data.get("topk_last_position"):
    errors.append("topk_last_position is empty")
if data.get("final_shape") != [1, 16, 152064]:
    errors.append(f"unexpected final_shape: {data.get('final_shape')}")
if data.get("final_dtype") != "float32":
    errors.append(f"unexpected final_dtype: {data.get('final_dtype')}")
if len(segments) != 14:
    errors.append(f"unexpected segment event count: {len(segments)}")
if sources != ["base", "fine", "resplit"]:
    errors.append(f"unexpected segment sources: {sources}")
if any(item.get("resident_count", 0) > 2 for item in segments):
    errors.append("resident_count exceeded two-segment window")
for metric in ("wall_ms", "load_ms", "run_ms", "amortized_wall_ms_per_forward", "amortized_load_ms_per_forward", "amortized_run_ms_per_forward"):
    value = data.get(metric)
    if not isinstance(value, (int, float)) or value <= 0:
        errors.append(f"unexpected {metric}: {value}")

payload = {
    "verdict": "ok_dream7b_bpu_resplit_forward_probe" if not errors else "failed_dream7b_bpu_resplit_forward_probe",
    "summary": str(summary_path),
    "run_dir": str(run_dir),
    "stdout": str(stdout_path),
    "stderr": str(stderr_path),
    "errors": errors,
    "checked": {
        "segment_plan": data.get("segment_plan"),
        "residency_window_size": data.get("residency_window_size"),
        "execution_mode": data.get("execution_mode"),
        "window_execution_mode": data.get("window_execution_mode"),
        "child_window_mode": data.get("child_window_mode"),
        "child_runtime_mode": data.get("child_runtime_mode"),
        "child_process_count": data.get("child_process_count"),
        "hbm_dir": data.get("hbm_dir"),
        "fine_hbm_dir": data.get("fine_hbm_dir"),
        "resplit_hbm_dir": data.get("resplit_hbm_dir"),
        "batch_count": data.get("batch_count"),
        "top_k": data.get("top_k"),
        "topk_last_position": data.get("topk_last_position"),
        "final_shape": data.get("final_shape"),
        "final_dtype": data.get("final_dtype"),
        "segment_event_count": len(segments),
        "segment_sources": sources,
        "wall_ms": data.get("wall_ms"),
        "load_ms": data.get("load_ms"),
        "run_ms": data.get("run_ms"),
        "amortized_wall_ms_per_forward": data.get("amortized_wall_ms_per_forward"),
        "amortized_load_ms_per_forward": data.get("amortized_load_ms_per_forward"),
        "amortized_run_ms_per_forward": data.get("amortized_run_ms_per_forward"),
    },
}
(run_dir / "resplit_forward_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(run_dir / "resplit_forward_probe.md").write_text(
    "\n".join([
        "# Dream 7B BPU Resplit Forward Probe",
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
        f"- hbm_dir: {payload['checked']['hbm_dir']}",
        f"- fine_hbm_dir: {payload['checked']['fine_hbm_dir']}",
        f"- resplit_hbm_dir: {payload['checked']['resplit_hbm_dir']}",
        f"- batch_count: {payload['checked']['batch_count']}",
        f"- top_k: {payload['checked']['top_k']}",
        f"- topk_last_position: {payload['checked']['topk_last_position']}",
        f"- final_shape: {payload['checked']['final_shape']}",
        f"- final_dtype: {payload['checked']['final_dtype']}",
        f"- segment_event_count: {payload['checked']['segment_event_count']}",
        f"- segment_sources: {payload['checked']['segment_sources']}",
        f"- wall_ms: {payload['checked']['wall_ms']}",
        f"- load_ms: {payload['checked']['load_ms']}",
        f"- run_ms: {payload['checked']['run_ms']}",
        f"- amortized_wall_ms_per_forward: {payload['checked']['amortized_wall_ms_per_forward']}",
        f"- amortized_load_ms_per_forward: {payload['checked']['amortized_load_ms_per_forward']}",
        f"- amortized_run_ms_per_forward: {payload['checked']['amortized_run_ms_per_forward']}",
        "",
        "## Errors",
        "",
        *([f"- {item}" for item in errors] if errors else ["- none"]),
        "",
    ]) + "\n",
    encoding="utf-8",
)
print(run_dir / "resplit_forward_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
