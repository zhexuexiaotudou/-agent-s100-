#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
tokens="${2:-1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16}"
repeat_count="${3:-3}"
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

if ! [[ "$repeat_count" =~ ^[1-9][0-9]*$ ]]; then
  echo "repeat_count must be a positive integer: $repeat_count" >&2
  exit 2
fi

if (( repeat_count > 10 )); then
  echo "repeat_count must be <= 10 for this bounded probe: $repeat_count" >&2
  exit 2
fi

if ! command -v dream7b-bpu-fine-forward >/dev/null 2>&1; then
  echo "Missing deployed command: dream7b-bpu-fine-forward" >&2
  exit 4
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_fine_forward_repeat_$stamp"
mkdir -p "$run_dir"

results_jsonl="$run_dir/results.jsonl"
: > "$results_jsonl"

for index in $(seq 1 "$repeat_count"); do
  label="$(printf 'run_%02d' "$index")"
  out_dir="$run_dir/$label"
  stdout="$run_dir/$label.stdout"
  stderr="$run_dir/$label.stderr"
  start_ns="$(date +%s%N)"
  set +e
  dream7b-bpu-fine-forward \
    --hbm-dir "$base_hbm_dir" \
    --fine-hbm-dir "$fine_hbm_dir" \
    --child-window-mode pair \
    --child-runtime-mode packed \
    --window-execution-mode in-process \
    --tokens "$tokens" \
    --top-k 5 \
    --output-dir "$out_dir" > "$stdout" 2> "$stderr"
  rc=$?
  set -e
  end_ns="$(date +%s%N)"
  python3 - "$label" "$out_dir/summary.json" "$start_ns" "$end_ns" "$rc" "$stdout" "$stderr" >> "$results_jsonl" <<'PY'
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
payload = {
    "label": label,
    "returncode": rc,
    "ok": rc == 0 and data.get("verdict") == "ok_dream7b_segmented_hbm_python_forward",
    "summary": str(summary_path) if summary_path.exists() else "",
    "stdout": stdout,
    "stderr": stderr,
    "wall_ms": round(wall_ms, 3),
    "load_ms": round(sum(float(item.get("load_ms", 0.0)) for item in segments), 3),
    "run_ms": round(sum(float(item.get("run_ms", 0.0)) for item in segments), 3),
    "segment_plan": data.get("segment_plan", ""),
    "residency_window_size": data.get("residency_window_size", 0),
    "child_window_mode": data.get("child_window_mode", ""),
    "child_runtime_mode": data.get("child_runtime_mode", ""),
    "window_execution_mode": data.get("window_execution_mode", ""),
    "execution_mode": data.get("execution_mode", ""),
    "child_process_count": data.get("child_process_count", 0),
    "segment_count": len(segments),
    "final_shape": data.get("final_shape", []),
}
print(json.dumps(payload, ensure_ascii=False))
PY
done

python3 - "$run_dir" "$results_jsonl" "$repeat_count" <<'PY'
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
results_path = Path(sys.argv[2])
repeat_count = int(sys.argv[3])
results = [json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines() if line.strip()]
errors = []
if len(results) != repeat_count:
    errors.append(f"expected {repeat_count} results, got {len(results)}")
for item in results:
    if not item["ok"]:
        errors.append(f"{item['label']} failed")
    if item["segment_plan"] != "fine-adjacent":
        errors.append(f"{item['label']} segment_plan={item['segment_plan']}")
    if item["residency_window_size"] != 2:
        errors.append(f"{item['label']} residency_window_size={item['residency_window_size']}")
    if item["child_window_mode"] != "pair":
        errors.append(f"{item['label']} child_window_mode={item['child_window_mode']}")
    if item["child_runtime_mode"] != "packed":
        errors.append(f"{item['label']} child_runtime_mode={item['child_runtime_mode']}")
    if item["window_execution_mode"] != "in-process":
        errors.append(f"{item['label']} window_execution_mode={item['window_execution_mode']}")
    if item["execution_mode"] != "pair_in_process":
        errors.append(f"{item['label']} execution_mode={item['execution_mode']}")
    if item["child_process_count"] != 0:
        errors.append(f"{item['label']} child_process_count={item['child_process_count']}")
    if item["segment_count"] != 10:
        errors.append(f"{item['label']} segment_count={item['segment_count']}")
    if item["final_shape"] != [1, 16, 152064]:
        errors.append(f"{item['label']} final_shape={item['final_shape']}")

def median(values):
    return round(float(statistics.median(values)), 3) if values else 0.0

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_fine_forward_repeat_probe" if not errors else "failed_dream7b_bpu_fine_forward_repeat_probe",
    "run_dir": str(run_dir),
    "repeat_count": repeat_count,
    "errors": errors,
    "median_wall_ms": median([item["wall_ms"] for item in results]),
    "median_load_ms": median([item["load_ms"] for item in results]),
    "median_run_ms": median([item["run_ms"] for item in results]),
    "results": results,
}
(run_dir / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Dream 7B BPU Fine Forward Repeat Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- run_dir: {payload['run_dir']}",
    f"- repeat_count: {payload['repeat_count']}",
    f"- median_wall_ms: {payload['median_wall_ms']}",
    f"- median_load_ms: {payload['median_load_ms']}",
    f"- median_run_ms: {payload['median_run_ms']}",
    "",
    "## Results",
    "",
    "| Run | OK | Exec mode | Window exec | Child count | Segments | Wall ms | Load ms | Run ms |",
    "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
]
for item in results:
    lines.append(
        f"| {item['label']} | {item['ok']} | {item['execution_mode']} | {item['window_execution_mode']} | "
        f"{item['child_process_count']} | {item['segment_count']} | {item['wall_ms']:.3f} | {item['load_ms']:.3f} | {item['run_ms']:.3f} |"
    )
lines.extend([
    "",
    "## Boundary",
    "",
    "- This is a bounded repeated-run stability probe over fixed seq16 token input.",
    "- It proves repeated default fine-forward execution, not production prompt throughput.",
])
(run_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "summary.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
