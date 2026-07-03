#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
venv="${DREAM7B_BPU_PHASE1_PREFLIGHT_VENV:-/mnt/nas/openclaw/runtimes/hbm-runtime-venv}"
forward_script="${DREAM7B_BPU_PHASE1_PREFLIGHT_FORWARD_SCRIPT:-/mnt/nas/openclaw/tmp/cross_job_queue_repo/scripts/probes/dream7b_segmented_hbm_python_forward.py}"
base_hbm_dir="${DREAM7B_BPU_HBM_DIR:-/mnt/nas/openclaw/models/dream7b-hbm/segments6}"
fine_hbm_dir="${DREAM7B_BPU_FINE_HBM_DIR:-/mnt/nas/openclaw/models/dream7b-hbm/fine-seq16}"
resplit_hbm_dir="${DREAM7B_BPU_RESPLIT_HBM_DIR:-/mnt/nas/openclaw/models/dream7b-hbm/resplit-seq16}"
topwindow_hbm_dir="${DREAM7B_BPU_TOPWINDOW_HBM_DIR:-/mnt/nas/openclaw/models/dream7b-hbm/resplit-topwindow-seq16}"
phase1_hbm_dir="${DREAM7B_BPU_PHASE1_HBM_DIR:-/mnt/nas/openclaw/models/dream7b-hbm/phase1-topload-seq16}"
expected_missing="${DREAM7B_BPU_PHASE1_PREFLIGHT_EXPECTED_MISSING:-seg02_03 seg03_04 seg04_05 seg05_07}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

for dir_var in base_hbm_dir fine_hbm_dir resplit_hbm_dir topwindow_hbm_dir phase1_hbm_dir; do
  dir="${!dir_var}"
  case "$dir" in
    /mnt/nas/openclaw/models/dream7b-hbm|/mnt/nas/openclaw/models/dream7b-hbm/*|/home/sunrise/.cache/openclaw/dream7b-hbm|/home/sunrise/.cache/openclaw/dream7b-hbm/*) ;;
    *)
      echo "Refusing $dir_var outside approved Dream 7B HBM directories: $dir" >&2
      exit 2
      ;;
  esac
done

if [[ ! -x "$venv/bin/python" ]]; then
  echo "Missing Dream 7B BPU runtime venv: $venv" >&2
  exit 4
fi
if [[ ! -f "$forward_script" ]]; then
  echo "Missing Dream 7B forward script: $forward_script" >&2
  exit 4
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_phase1_segment_plan_preflight_$stamp"
mkdir -p "$run_dir"

stdout_path="$run_dir/dry_run.stdout"
stderr_path="$run_dir/dry_run.stderr"
set +e
"$venv/bin/python" "$forward_script" \
  --segment-plan phase1-topload-adjacent \
  --hbm-dir "$base_hbm_dir" \
  --fine-hbm-dir "$fine_hbm_dir" \
  --resplit-hbm-dir "$resplit_hbm_dir" \
  --topwindow-hbm-dir "$topwindow_hbm_dir" \
  --phase1-hbm-dir "$phase1_hbm_dir" \
  --output-dir "$run_dir/dry_run" \
  --dry-run-segments > "$stdout_path" 2> "$stderr_path"
dry_run_status="$?"
set -e

python3 - \
  "$run_dir" \
  "$report_root" \
  "$venv" \
  "$forward_script" \
  "$base_hbm_dir" \
  "$fine_hbm_dir" \
  "$resplit_hbm_dir" \
  "$topwindow_hbm_dir" \
  "$phase1_hbm_dir" \
  "$expected_missing" \
  "$dry_run_status" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
report_root = Path(sys.argv[2])
venv = Path(sys.argv[3])
forward_script = Path(sys.argv[4])
base_hbm_dir = Path(sys.argv[5])
fine_hbm_dir = Path(sys.argv[6])
resplit_hbm_dir = Path(sys.argv[7])
topwindow_hbm_dir = Path(sys.argv[8])
phase1_hbm_dir = Path(sys.argv[9])
expected_missing = sorted(item for item in sys.argv[10].split() if item)
dry_run_status = int(sys.argv[11])

dry_run_path = run_dir / "dry_run/segment_plan_preflight.json"
stdout_path = run_dir / "dry_run.stdout"
stderr_path = run_dir / "dry_run.stderr"
errors = []
warnings = []
dry_run = {}
if dry_run_status != 0:
    errors.append(f"dry-run forward exited with status {dry_run_status}")
if not dry_run_path.is_file():
    errors.append(f"missing dry-run preflight json: {dry_run_path}")
else:
    dry_run = json.loads(dry_run_path.read_text(encoding="utf-8"))

missing_segments = sorted(item.get("segment") for item in dry_run.get("missing_segments", []))
unexpected_missing = sorted(set(missing_segments) - set(expected_missing))
unexpected_present = sorted(set(expected_missing) - set(missing_segments))
if unexpected_missing:
    errors.append(f"unexpected missing segments: {unexpected_missing}")
if unexpected_present:
    warnings.append(f"expected phase1 segments already present: {unexpected_present}")
if dry_run and dry_run.get("segment_count") != 20:
    errors.append(f"unexpected phase1 segment_count: {dry_run.get('segment_count')}")
if dry_run and dry_run.get("segment_plan") != "phase1-topload-adjacent":
    errors.append(f"unexpected segment_plan: {dry_run.get('segment_plan')}")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_phase1_segment_plan_preflight_probe" if not errors else "failed_dream7b_bpu_phase1_segment_plan_preflight_probe",
    "run_dir": str(run_dir),
    "report_root": str(report_root),
    "venv": str(venv),
    "forward_script": str(forward_script),
    "base_hbm_dir": str(base_hbm_dir),
    "fine_hbm_dir": str(fine_hbm_dir),
    "resplit_hbm_dir": str(resplit_hbm_dir),
    "topwindow_hbm_dir": str(topwindow_hbm_dir),
    "phase1_hbm_dir": str(phase1_hbm_dir),
    "dry_run_status": dry_run_status,
    "dry_run_json": str(dry_run_path),
    "dry_run_stdout": str(stdout_path),
    "dry_run_stderr": str(stderr_path),
    "segment_plan": dry_run.get("segment_plan"),
    "segment_count": dry_run.get("segment_count"),
    "missing_segment_count": dry_run.get("missing_segment_count"),
    "expected_missing_segments": expected_missing,
    "missing_segments": missing_segments,
    "unexpected_missing_segments": unexpected_missing,
    "unexpected_present_segments": unexpected_present,
    "phase1_ready_to_run": dry_run.get("missing_segment_count") == 0 and not errors,
    "warnings": warnings,
    "errors": errors,
}
(run_dir / "phase1_segment_plan_preflight_probe.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
lines = [
    "# Dream 7B Phase 1 Segment Plan Preflight",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- segment_plan: {payload['segment_plan']}",
    f"- segment_count: {payload['segment_count']}",
    f"- missing_segment_count: {payload['missing_segment_count']}",
    f"- missing_segments: {payload['missing_segments']}",
    f"- phase1_ready_to_run: {payload['phase1_ready_to_run']}",
    "",
    "## Warnings",
    "",
]
lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- none")
lines.extend(["", "## Errors", ""])
lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
(run_dir / "phase1_segment_plan_preflight_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "phase1_segment_plan_preflight_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
