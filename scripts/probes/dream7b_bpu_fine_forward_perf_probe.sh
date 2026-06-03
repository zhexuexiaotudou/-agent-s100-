#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
tokens="${2:-1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16}"
base_hbm_dir="${DREAM7B_BPU_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/segments6}"
fine_hbm_dir="${DREAM7B_BPU_FINE_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

case "$base_hbm_dir" in
  /mnt/nas/openclaw/models/dream7b-hbm/segments6|/mnt/nas/openclaw/models/dream7b-hbm/segments6/|/home/sunrise/.cache/openclaw/dream7b-hbm/segments6|/home/sunrise/.cache/openclaw/dream7b-hbm/segments6/) ;;
  *)
    echo "Refusing base HBM path outside approved Dream 7B HBM directories: $base_hbm_dir" >&2
    exit 2
    ;;
esac

case "$fine_hbm_dir" in
  /mnt/nas/openclaw/models/dream7b-hbm/fine-seq16|/mnt/nas/openclaw/models/dream7b-hbm/fine-seq16/|/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16|/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16/) ;;
  *)
    echo "Refusing fine HBM path outside approved Dream 7B HBM directories: $fine_hbm_dir" >&2
    exit 2
    ;;
esac

if ! command -v dream7b-bpu-forward >/dev/null 2>&1; then
  echo "Missing deployed command: dream7b-bpu-forward" >&2
  exit 4
fi

if ! command -v dream7b-bpu-fine-forward >/dev/null 2>&1; then
  echo "Missing deployed command: dream7b-bpu-fine-forward" >&2
  exit 4
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_fine_forward_perf_$stamp"
mkdir -p "$run_dir"

run_case() {
  local label="$1"
  shift
  local out_dir="$run_dir/$label"
  local stdout="$run_dir/$label.stdout"
  local stderr="$run_dir/$label.stderr"
  local start_ns end_ns rc
  start_ns="$(date +%s%N)"
  set +e
  "$@" --tokens "$tokens" --top-k 5 --output-dir "$out_dir" > "$stdout" 2> "$stderr"
  rc=$?
  set -e
  end_ns="$(date +%s%N)"
  python3 - "$label" "$out_dir/summary.json" "$start_ns" "$end_ns" "$rc" "$stdout" "$stderr" <<'PY'
import json
import sys
from pathlib import Path

label, summary_path_text, start_ns, end_ns, rc_text, stdout, stderr = sys.argv[1:8]
summary_path = Path(summary_path_text)
rc = int(rc_text)
wall_ms = (int(end_ns) - int(start_ns)) / 1_000_000.0
if summary_path.exists():
    data = json.loads(summary_path.read_text(encoding="utf-8"))
else:
    data = {}
segments = data.get("segments", [])
load_ms = sum(float(item.get("load_ms", 0.0)) for item in segments)
run_ms = sum(float(item.get("run_ms", 0.0)) for item in segments)
payload = {
    "label": label,
    "returncode": rc,
    "ok": rc == 0 and data.get("verdict") == "ok_dream7b_segmented_hbm_python_forward",
    "summary": str(summary_path) if summary_path.exists() else "",
    "stdout": stdout,
    "stderr": stderr,
    "wall_ms": round(wall_ms, 3),
    "load_ms": round(load_ms, 3),
    "run_ms": round(run_ms, 3),
    "load_to_run_ratio": round(load_ms / run_ms, 3) if run_ms else None,
    "segment_plan": data.get("segment_plan", ""),
    "residency_window_size": data.get("residency_window_size", 0),
    "child_window_mode": data.get("child_window_mode", ""),
    "child_runtime_mode": data.get("child_runtime_mode", ""),
    "execution_mode": data.get("execution_mode", ""),
    "child_process_count": data.get("child_process_count", 0),
    "segment_count": len(segments),
    "final_shape": data.get("final_shape", []),
}
print(json.dumps(payload, ensure_ascii=False))
PY
}

segments6_result="$(run_case segments6 dream7b-bpu-forward --hbm-dir "$base_hbm_dir")"
fine_sliding_result="$(run_case fine_sliding dream7b-bpu-fine-forward --hbm-dir "$base_hbm_dir" --fine-hbm-dir "$fine_hbm_dir" --child-window-mode sliding --child-runtime-mode separate)"
fine_pair_separate_result="$(run_case fine_pair_separate dream7b-bpu-fine-forward --hbm-dir "$base_hbm_dir" --fine-hbm-dir "$fine_hbm_dir" --child-window-mode pair --child-runtime-mode separate)"
fine_pair_packed_result="$(run_case fine_pair_packed dream7b-bpu-fine-forward --hbm-dir "$base_hbm_dir" --fine-hbm-dir "$fine_hbm_dir" --child-window-mode pair --child-runtime-mode packed)"

python3 - "$run_dir" "$segments6_result" "$fine_sliding_result" "$fine_pair_separate_result" "$fine_pair_packed_result" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
results = [json.loads(item) for item in sys.argv[2:6]]
by_label = {item["label"]: item for item in results}
errors = []
for item in results:
    if not item["ok"]:
        errors.append(f"{item['label']} failed")
    if item["final_shape"] != [1, 16, 152064]:
        errors.append(f"{item['label']} unexpected final_shape={item['final_shape']}")
if by_label["fine_pair_packed"]["execution_mode"] != "pair_child_process":
    errors.append("fine_pair_packed did not use pair_child_process")
if by_label["fine_pair_packed"]["child_process_count"] != 5:
    errors.append(f"fine_pair_packed child_process_count={by_label['fine_pair_packed']['child_process_count']}")
if by_label["fine_pair_packed"]["child_runtime_mode"] != "packed":
    errors.append(f"fine_pair_packed child_runtime_mode={by_label['fine_pair_packed']['child_runtime_mode']}")
if by_label["fine_pair_separate"]["child_runtime_mode"] != "separate":
    errors.append(f"fine_pair_separate child_runtime_mode={by_label['fine_pair_separate']['child_runtime_mode']}")
if by_label["fine_sliding"]["child_process_count"] not in (0, 10):
    errors.append(f"fine_sliding child_process_count={by_label['fine_sliding']['child_process_count']}")

sliding_load = by_label["fine_sliding"]["load_ms"]
pair_load = by_label["fine_pair_packed"]["load_ms"]
sliding_wall = by_label["fine_sliding"]["wall_ms"]
pair_wall = by_label["fine_pair_packed"]["wall_ms"]
separate_pair_load = by_label["fine_pair_separate"]["load_ms"]
separate_pair_wall = by_label["fine_pair_separate"]["wall_ms"]
payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_fine_forward_perf_probe" if not errors else "failed_dream7b_bpu_fine_forward_perf_probe",
    "run_dir": str(run_dir),
    "errors": errors,
    "results": results,
    "pair_vs_sliding": {
        "child_process_reduction": by_label["fine_sliding"]["child_process_count"] - by_label["fine_pair_packed"]["child_process_count"],
        "load_ms_delta": round(sliding_load - pair_load, 3),
        "load_speedup": round(sliding_load / pair_load, 3) if pair_load else None,
        "wall_ms_delta": round(sliding_wall - pair_wall, 3),
        "wall_speedup": round(sliding_wall / pair_wall, 3) if pair_wall else None,
    },
    "packed_vs_separate_pair": {
        "load_ms_delta": round(separate_pair_load - pair_load, 3),
        "load_speedup": round(separate_pair_load / pair_load, 3) if pair_load else None,
        "wall_ms_delta": round(separate_pair_wall - pair_wall, 3),
        "wall_speedup": round(separate_pair_wall / pair_wall, 3) if pair_wall else None,
    },
    "notes": [
        "This is a regression/performance probe over fixed seq16 token input.",
        "It compares the deployed six-segment forward, fine sliding-child forward, separate pair-child forward, and packed pair-child forward.",
        "Pair-child is expected to keep the two-segment residency invariant while reducing child process count.",
        "Packed pair-child uses one HB_HBMRuntime constructed from both resident HBM files.",
    ],
}
(run_dir / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Dream 7B BPU Fine Forward Performance Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- run_dir: {payload['run_dir']}",
    f"- pair_vs_sliding_child_process_reduction: {payload['pair_vs_sliding']['child_process_reduction']}",
    f"- pair_vs_sliding_load_speedup: {payload['pair_vs_sliding']['load_speedup']}",
    f"- pair_vs_sliding_wall_speedup: {payload['pair_vs_sliding']['wall_speedup']}",
    f"- packed_vs_separate_pair_load_speedup: {payload['packed_vs_separate_pair']['load_speedup']}",
    f"- packed_vs_separate_pair_wall_speedup: {payload['packed_vs_separate_pair']['wall_speedup']}",
    "",
    "## Results",
    "",
    "| Case | OK | Exec mode | Child mode | Runtime mode | Child count | Segments | Wall ms | Load ms | Run ms |",
    "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
]
for item in results:
    lines.append(
        f"| {item['label']} | {item['ok']} | {item['execution_mode']} | {item['child_window_mode']} | {item['child_runtime_mode']} | "
        f"{item['child_process_count']} | {item['segment_count']} | {item['wall_ms']:.3f} | {item['load_ms']:.3f} | {item['run_ms']:.3f} |"
    )
lines.extend([
    "",
    "## Boundary",
    "",
    "- This measures one seq16 forward per mode; use repeated runs before treating small timing deltas as stable.",
    "- It is a regression gate for the current S100P deployment path, not a full throughput benchmark.",
])
(run_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "summary.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
