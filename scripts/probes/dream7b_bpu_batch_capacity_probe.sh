#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
counts_text="${DREAM7B_BPU_BATCH_CAPACITY_COUNTS:-8 12 16}"
timeout_sec="${DREAM7B_BPU_BATCH_CAPACITY_TIMEOUT_SEC:-900}"
top_k="${DREAM7B_BPU_BATCH_CAPACITY_TOP_K:-3}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

if ! [[ "$timeout_sec" =~ ^[0-9]+$ ]] || (( timeout_sec < 1 )); then
  echo "DREAM7B_BPU_BATCH_CAPACITY_TIMEOUT_SEC must be a positive integer." >&2
  exit 2
fi
if ! [[ "$top_k" =~ ^[0-9]+$ ]]; then
  echo "DREAM7B_BPU_BATCH_CAPACITY_TOP_K must be a non-negative integer." >&2
  exit 2
fi

read -r -a counts <<< "$counts_text"
if (( ${#counts[@]} < 2 )); then
  echo "DREAM7B_BPU_BATCH_CAPACITY_COUNTS must contain at least two integer counts." >&2
  exit 2
fi
for count in "${counts[@]}"; do
  if ! [[ "$count" =~ ^[1-9][0-9]*$ ]] || (( count > 16 )); then
    echo "DREAM7B_BPU_BATCH_CAPACITY_COUNTS values must be integers from 1 to 16: $count" >&2
    exit 2
  fi
done

if ! command -v dream7b-bpu-fine-batch-forward >/dev/null 2>&1; then
  echo "Missing deployed command: dream7b-bpu-fine-batch-forward" >&2
  exit 4
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_batch_capacity_$stamp"
mkdir -p "$run_dir"

for count in "${counts[@]}"; do
  batch_dir="$run_dir/batch_${count}"
  mkdir -p "$batch_dir"
  tokens_batch_json="$batch_dir/tokens_batch.json"
  python3 - "$tokens_batch_json" "$count" <<'PY'
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
  timeout "$timeout_sec" dream7b-bpu-fine-batch-forward \
    --tokens-batch-json "$tokens_batch_json" \
    --top-k "$top_k" \
    --output-dir "$batch_dir/forward" > "$batch_dir/forward.stdout" 2> "$batch_dir/forward.stderr"
  status="$?"
  set -e
  printf '%s\n' "$status" > "$batch_dir/forward.status"
done

python3 - "$run_dir" "$counts_text" "$timeout_sec" "$top_k" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
counts = [int(item) for item in sys.argv[2].split()]
timeout_sec = int(sys.argv[3])
top_k = int(sys.argv[4])
errors = []
entries = []
passing_counts = []
for count in counts:
    batch_dir = run_dir / f"batch_{count}"
    summary_path = batch_dir / "forward/summary.json"
    status_path = batch_dir / "forward.status"
    stderr_path = batch_dir / "forward.stderr"
    status = int(status_path.read_text(encoding="utf-8").strip()) if status_path.is_file() else -1
    entry = {
        "batch_count": count,
        "status": status,
        "summary": str(summary_path),
        "stderr": str(stderr_path),
    }
    if status != 0:
        entry["ok"] = False
        entry["stderr_excerpt"] = stderr_path.read_text(encoding="utf-8", errors="replace")[-1000:] if stderr_path.is_file() else ""
        errors.append(f"batch_count={count} exited with status {status}")
        entries.append(entry)
        continue
    if not summary_path.is_file():
        entry["ok"] = False
        errors.append(f"missing summary.json for batch_count={count}: {summary_path}")
        entries.append(entry)
        continue
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    final_shapes = data.get("final_shapes") or []
    entry.update(
        {
            "ok": data.get("verdict") == "ok_dream7b_segmented_hbm_python_forward",
            "verdict": data.get("verdict"),
            "segment_plan": data.get("segment_plan"),
            "residency_window_size": data.get("residency_window_size"),
            "execution_mode": data.get("execution_mode"),
            "window_execution_mode": data.get("window_execution_mode"),
            "child_process_count": data.get("child_process_count"),
            "reported_batch_count": data.get("batch_count"),
            "final_shape_count": len(final_shapes),
            "wall_ms": round(float(data.get("wall_ms") or 0.0), 3),
            "load_ms": round(float(data.get("load_ms") or 0.0), 3),
            "run_ms": round(float(data.get("run_ms") or 0.0), 3),
            "amortized_wall_ms_per_forward": round(float(data.get("amortized_wall_ms_per_forward") or 0.0), 3),
            "amortized_load_ms_per_forward": round(float(data.get("amortized_load_ms_per_forward") or 0.0), 3),
            "amortized_run_ms_per_forward": round(float(data.get("amortized_run_ms_per_forward") or 0.0), 3),
        }
    )
    if entry["verdict"] != "ok_dream7b_segmented_hbm_python_forward":
        errors.append(f"unexpected verdict for batch_count={count}: {entry['verdict']}")
    if entry["segment_plan"] != "fine-adjacent":
        errors.append(f"unexpected segment_plan for batch_count={count}: {entry['segment_plan']}")
    if entry["residency_window_size"] != 2:
        errors.append(f"unexpected residency_window_size for batch_count={count}: {entry['residency_window_size']}")
    if entry["execution_mode"] != "pair_window_batch":
        errors.append(f"unexpected execution_mode for batch_count={count}: {entry['execution_mode']}")
    if entry["window_execution_mode"] != "window-batch":
        errors.append(f"unexpected window_execution_mode for batch_count={count}: {entry['window_execution_mode']}")
    if entry["child_process_count"] != 0:
        errors.append(f"unexpected child_process_count for batch_count={count}: {entry['child_process_count']}")
    if entry["reported_batch_count"] != count:
        errors.append(f"unexpected reported batch_count for batch_count={count}: {entry['reported_batch_count']}")
    if entry["final_shape_count"] != count:
        errors.append(f"unexpected final_shape_count for batch_count={count}: {entry['final_shape_count']}")
    for shape in final_shapes:
        if shape != [1, 16, 152064]:
            errors.append(f"unexpected final_shape for batch_count={count}: {shape}")
    if entry["ok"]:
        passing_counts.append(count)
    entries.append(entry)

by_count = {item["batch_count"]: item for item in entries if item.get("ok")}
if counts[0] in by_count and counts[-1] in by_count:
    first = by_count[counts[0]]["amortized_wall_ms_per_forward"]
    last = by_count[counts[-1]]["amortized_wall_ms_per_forward"]
    if first <= last:
        errors.append(f"amortized wall did not improve from batch_count={counts[0]} to batch_count={counts[-1]}: {first} <= {last}")

max_passing_count = max(passing_counts) if passing_counts else 0
payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_batch_capacity_probe" if not errors else "failed_dream7b_bpu_batch_capacity_probe",
    "run_dir": str(run_dir),
    "counts": counts,
    "max_passing_count": max_passing_count,
    "timeout_sec": timeout_sec,
    "top_k": top_k,
    "entries": entries,
    "errors": errors,
}
(run_dir / "batch_capacity_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
error_lines = [f"- {item}" for item in errors] if errors else ["- none"]
lines = [
    "# Dream 7B BPU Batch Capacity Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- run_dir: {payload['run_dir']}",
    f"- counts: {payload['counts']}",
    f"- max_passing_count: {payload['max_passing_count']}",
    f"- timeout_sec: {payload['timeout_sec']}",
    f"- top_k: {payload['top_k']}",
    "",
    "## Results",
    "",
    "| batch_count | ok | status | wall_ms | load_ms | run_ms | amortized_wall_ms_per_forward | amortized_load_ms_per_forward | amortized_run_ms_per_forward |",
    "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
]
for item in entries:
    lines.append(
        f"| {item['batch_count']} | {item.get('ok')} | {item['status']} | {item.get('wall_ms', '')} | {item.get('load_ms', '')} | {item.get('run_ms', '')} | {item.get('amortized_wall_ms_per_forward', '')} | {item.get('amortized_load_ms_per_forward', '')} | {item.get('amortized_run_ms_per_forward', '')} |"
    )
lines.extend([
    "",
    "## Errors",
    "",
    *error_lines,
    "",
    "## Boundary",
    "",
    "- This probe tests independent seq16 token batches through `dream7b-bpu-fine-batch-forward`.",
    "- It does not change the service default until a separate systemd queue probe is updated and rerun.",
    "- It does not prove single-request Dream diffusion latency improvement.",
    "",
])
(run_dir / "batch_capacity_probe.md").write_text("\n".join(lines), encoding="utf-8")
print(run_dir / "batch_capacity_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
