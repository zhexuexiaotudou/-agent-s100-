#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
tokens="${2:-1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

if ! command -v dream7b-bpu-fine-forward >/dev/null 2>&1; then
  echo "Missing deployed command: dream7b-bpu-fine-forward" >&2
  exit 4
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_fine_forward_$stamp"
stdout="$run_dir.stdout"
stderr="$run_dir.stderr"

dream7b-bpu-fine-forward \
  --tokens "$tokens" \
  --top-k 5 \
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
if data.get("execution_mode") != "pair_child_process":
    errors.append(f"unexpected execution_mode: {data.get('execution_mode')}")
if data.get("child_window_mode") != "pair":
    errors.append(f"unexpected child_window_mode: {data.get('child_window_mode')}")
if data.get("child_process_count") != 5:
    errors.append(f"unexpected child_process_count: {data.get('child_process_count')}")
if data.get("final_shape") != [1, 16, 152064]:
    errors.append(f"unexpected final_shape: {data.get('final_shape')}")
if len(data.get("segments", [])) != 10:
    errors.append(f"unexpected segment count: {len(data.get('segments', []))}")
if any(item.get("resident_count", 0) > 2 for item in data.get("segments", [])):
    errors.append("resident_count exceeded two-segment window")

payload = {
    "verdict": "ok_dream7b_bpu_fine_forward_probe" if not errors else "failed_dream7b_bpu_fine_forward_probe",
    "summary": str(summary_path),
    "run_dir": str(run_dir),
    "errors": errors,
    "checked": {
        "segment_plan": data.get("segment_plan"),
        "residency_window_size": data.get("residency_window_size"),
        "execution_mode": data.get("execution_mode"),
        "child_window_mode": data.get("child_window_mode"),
        "child_process_count": data.get("child_process_count"),
        "final_shape": data.get("final_shape"),
        "segment_count": len(data.get("segments", [])),
    },
}
(run_dir / "fine_forward_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(run_dir / "fine_forward_probe.md").write_text(
    "\n".join([
        "# Dream 7B BPU Fine Forward Probe",
        "",
        f"- verdict: {payload['verdict']}",
        f"- summary: {payload['summary']}",
        f"- segment_plan: {payload['checked']['segment_plan']}",
        f"- residency_window_size: {payload['checked']['residency_window_size']}",
        f"- execution_mode: {payload['checked']['execution_mode']}",
        f"- child_window_mode: {payload['checked']['child_window_mode']}",
        f"- child_process_count: {payload['checked']['child_process_count']}",
        f"- final_shape: {payload['checked']['final_shape']}",
        f"- segment_count: {payload['checked']['segment_count']}",
        "",
    ]) + "\n",
    encoding="utf-8",
)
print(run_dir / "fine_forward_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
