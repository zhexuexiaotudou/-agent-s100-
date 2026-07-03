#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
model_report_root="${DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_MODEL_REPORT_ROOT:-/mnt/nas/openclaw/reports/models}"
forward_probe_cmd="${DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_FORWARD_PROBE_CMD:-dream7b-bpu-selected-pair-forward-path-probe}"
job_count="${DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_COUNT:-3}"
batch_count="${DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_BATCH_COUNT:-16}"
top_k="${DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_TOP_K:-3}"
timeout_sec="${DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_TIMEOUT_SEC:-1800}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

case "$model_report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing model report path outside approved report directories: $model_report_root" >&2
    exit 2
    ;;
esac

if ! command -v "$forward_probe_cmd" >/dev/null 2>&1; then
  echo "Missing deployed command: $forward_probe_cmd" >&2
  exit 4
fi
if ! [[ "$job_count" =~ ^[1-9][0-9]*$ ]] || (( job_count < 2 || job_count > 8 )); then
  echo "DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_COUNT must be an integer from 2 to 8." >&2
  exit 2
fi
if ! [[ "$batch_count" =~ ^[1-9][0-9]*$ ]] || (( batch_count > 16 )); then
  echo "DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_BATCH_COUNT must be an integer from 1 to 16." >&2
  exit 2
fi
if ! [[ "$top_k" =~ ^[0-9]+$ ]]; then
  echo "DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_TOP_K must be a non-negative integer." >&2
  exit 2
fi
if ! [[ "$timeout_sec" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_SELECTED_PAIR_CROSS_JOB_TIMEOUT_SEC must be a positive integer." >&2
  exit 2
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_selected_pair_cross_job_reuse_$stamp"
forward_report_root="$run_dir/selected_pair_forward_reports"
mkdir -p "$run_dir" "$forward_report_root"

triplet_json="$(
  python3 - "$model_report_root" <<'PY'
import glob
import sys
from pathlib import Path

root = Path(sys.argv[1])
paths = [
    Path(item)
    for item in glob.glob(str(root / "dream7b_bpu_single_segment_triplet_residency_*/single_segment_triplet_residency_probe.json"))
]
paths = [item for item in paths if item.is_file()]
if not paths:
    raise SystemExit("missing dream7b_bpu_single_segment_triplet_residency_*/single_segment_triplet_residency_probe.json")
print(max(paths, key=lambda item: item.stat().st_mtime))
PY
)"

forward_stdout="$run_dir/selected_pair_forward.stdout"
forward_stderr="$run_dir/selected_pair_forward.stderr"
set +e
DREAM7B_BPU_SELECTED_PAIR_ONLY=1 \
DREAM7B_BPU_SELECTED_PAIR_TRIPLET_JSON="$triplet_json" \
DREAM7B_BPU_SELECTED_PAIR_JOB_COUNT="$job_count" \
DREAM7B_BPU_SELECTED_PAIR_BATCH_COUNT="$batch_count" \
DREAM7B_BPU_SELECTED_PAIR_TOP_K="$top_k" \
DREAM7B_BPU_SELECTED_PAIR_TIMEOUT_SEC="$timeout_sec" \
  "$forward_probe_cmd" "$forward_report_root" > "$forward_stdout" 2> "$forward_stderr"
forward_status="$?"
set -e

python3 - \
  "$run_dir" \
  "$model_report_root" \
  "$forward_stdout" \
  "$forward_stderr" \
  "$forward_status" \
  "$job_count" \
  "$batch_count" \
  "$top_k" \
  "$timeout_sec" <<'PY'
import glob
import json
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
model_report_root = Path(sys.argv[2])
forward_stdout = Path(sys.argv[3])
forward_stderr = Path(sys.argv[4])
forward_status = int(sys.argv[5])
job_count = int(sys.argv[6])
batch_count = int(sys.argv[7])
top_k = int(sys.argv[8])
timeout_sec = int(sys.argv[9])

errors = []
warnings = []


def latest_json(pattern):
    paths = [Path(item) for item in glob.glob(str(model_report_root / pattern))]
    paths = [item for item in paths if item.is_file()]
    if not paths:
        return None, {}
    path = max(paths, key=lambda item: item.stat().st_mtime)
    return path, json.loads(path.read_text(encoding="utf-8"))


def round_float(value):
    if value is None:
        return None
    return round(float(value), 3)


def ratio_delta(reference, candidate):
    if reference in (None, 0) or candidate is None:
        return None
    return round((float(reference) - float(candidate)) / float(reference), 6)


forward_md = ""
for line in forward_stdout.read_text(encoding="utf-8", errors="replace").splitlines()[::-1]:
    line = line.strip()
    if line.endswith("selected_pair_forward_path_probe.md"):
        forward_md = line
        break

forward_probe = {}
selected_summary = {}
forward_json = None
selected_summary_path = None
if forward_status != 0:
    errors.append(f"selected-pair forward path probe returned {forward_status}")
if not forward_md:
    errors.append(f"could not parse selected_pair_forward_path_probe.md from {forward_stdout}")
else:
    forward_json = Path(forward_md).with_suffix(".json")
    if not forward_json.is_file():
        errors.append(f"missing selected pair forward JSON: {forward_json}")
    else:
        forward_probe = json.loads(forward_json.read_text(encoding="utf-8"))
        selected_summary_path = Path(forward_probe.get("selected_summary_json") or "")
        if selected_summary_path.is_file():
            selected_summary = json.loads(selected_summary_path.read_text(encoding="utf-8"))
        else:
            errors.append(f"missing selected summary JSON: {selected_summary_path}")

candidate_path, candidate = latest_json("dream7b_bpu_selected_pair_candidate_service_telemetry_*/systemd_telemetry_probe.json")
if not candidate_path:
    errors.append("missing dream7b_bpu_selected_pair_candidate_service_telemetry_*/systemd_telemetry_probe.json")

selected = forward_probe.get("selected") or {}
processed_forward_count = int(selected.get("processed_forward_count") or selected_summary.get("processed_forward_count") or 0)
expected_processed_forward_count = job_count * batch_count
selected_final_shapes_by_job = selected.get("final_shapes_by_job") or selected_summary.get("final_shapes_by_job") or []
expected_final_shapes_by_job = [[[1, 16, 152064] for _ in range(batch_count)] for _ in range(job_count)]

if forward_probe.get("verdict") != "ok_dream7b_bpu_selected_pair_forward_path_probe":
    errors.append(f"unexpected selected-pair forward verdict: {forward_probe.get('verdict')}")
if forward_probe.get("selected_only") is not True:
    errors.append(f"selected-pair forward selected_only is not true: {forward_probe.get('selected_only')}")
if int(forward_probe.get("job_count") or 0) != job_count:
    errors.append(f"unexpected selected-pair forward job_count: {forward_probe.get('job_count')}")
if int(forward_probe.get("batch_count") or 0) != batch_count:
    errors.append(f"unexpected selected-pair forward batch_count: {forward_probe.get('batch_count')}")
if processed_forward_count != expected_processed_forward_count:
    errors.append(f"unexpected processed_forward_count: {processed_forward_count}")
if selected.get("selected_pair_covers_all_segments") is not True:
    errors.append(f"selected_pair_covers_all_segments is not true: {selected.get('selected_pair_covers_all_segments')}")
if int(selected.get("selected_worker_count") or 0) != 2:
    errors.append(f"unexpected selected_worker_count: {selected.get('selected_worker_count')}")
if selected_final_shapes_by_job != expected_final_shapes_by_job:
    errors.append("selected final_shapes_by_job did not match expected [job][batch] seq16 logits shapes")

candidate_processed = int(candidate.get("processed_request_count") or 0)
candidate_batch_counts = candidate.get("batch_counts") or []
if candidate:
    if candidate.get("verdict") != "ok_dream7b_bpu_batch_queue_systemd_telemetry_probe":
        errors.append(f"unexpected candidate service telemetry verdict: {candidate.get('verdict')}")
    if candidate.get("service_name") != "dream7b-bpu-selected-pair-candidate.service":
        errors.append(f"unexpected candidate service_name: {candidate.get('service_name')}")
    if candidate_processed < expected_processed_forward_count:
        errors.append(f"candidate service processed_request_count below {expected_processed_forward_count}: {candidate_processed}")
    if candidate_batch_counts[:job_count] != [batch_count for _ in range(job_count)]:
        errors.append(f"unexpected candidate batch_counts: {candidate_batch_counts}")
    if candidate.get("expected_window_execution_mode") != "selected-pair-resident":
        errors.append(f"unexpected candidate expected_window_execution_mode: {candidate.get('expected_window_execution_mode')}")
    if candidate.get("expected_child_process_count") != 2:
        errors.append(f"unexpected candidate expected_child_process_count: {candidate.get('expected_child_process_count')}")

cross_wall = selected.get("amortized_wall_ms_per_forward")
cross_load = selected.get("amortized_total_load_ms_per_forward")
cross_run = selected.get("amortized_run_ms_per_forward")
candidate_wall = candidate.get("amortized_wall_ms_per_processed_request")
candidate_load = candidate.get("amortized_load_ms_per_processed_request")
candidate_run = candidate.get("amortized_run_ms_per_processed_request")
wall_delta_ratio = ratio_delta(candidate_wall, cross_wall)
load_delta_ratio = ratio_delta(candidate_load, cross_load)
run_delta_ratio = ratio_delta(candidate_run, cross_run)
cross_wall_improved = wall_delta_ratio is not None and wall_delta_ratio > 0
cross_load_improved = load_delta_ratio is not None and load_delta_ratio > 0
resident_load_once_amortized = None
if processed_forward_count:
    resident_load_once_amortized = round_float(float(selected.get("selected_resident_load_ms") or 0.0) / processed_forward_count)

if not cross_wall_improved:
    warnings.append("cross-job selected-pair reuse did not improve amortized wall time versus selected-pair candidate service telemetry")
if not cross_load_improved:
    warnings.append("cross-job selected-pair reuse did not improve amortized load time versus selected-pair candidate service telemetry")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_selected_pair_cross_job_reuse_probe" if not errors else "failed_dream7b_bpu_selected_pair_cross_job_reuse_probe",
    "run_dir": str(run_dir),
    "model_report_root": str(model_report_root),
    "forward_probe_cmd": "dream7b-bpu-selected-pair-forward-path-probe",
    "forward_status": forward_status,
    "forward_stdout": str(forward_stdout),
    "forward_stderr": str(forward_stderr),
    "selected_pair_forward_path_probe_json": str(forward_json) if forward_json else "",
    "selected_pair_forward_summary_json": str(selected_summary_path) if selected_summary_path else "",
    "candidate_service_telemetry_path": str(candidate_path) if candidate_path else "",
    "job_count": job_count,
    "batch_count": batch_count,
    "processed_forward_count": processed_forward_count,
    "top_k": top_k,
    "timeout_sec": timeout_sec,
    "selected_pair": selected.get("selected_pair"),
    "selected_segments": selected.get("selected_segments"),
    "selected_pair_covers_all_segments": selected.get("selected_pair_covers_all_segments"),
    "selected_worker_count": selected.get("selected_worker_count"),
    "selected_resident_load_ms": selected.get("selected_resident_load_ms"),
    "resident_load_once_amortized_ms_per_forward": resident_load_once_amortized,
    "cross_job_metrics": {
        "selected_total_load_ms": selected.get("selected_total_load_ms"),
        "run_ms": selected.get("run_ms"),
        "wall_ms": selected.get("wall_ms"),
        "amortized_wall_ms_per_forward": cross_wall,
        "amortized_total_load_ms_per_forward": cross_load,
        "amortized_run_ms_per_forward": cross_run,
    },
    "candidate_service_metrics": {
        "processed_request_count": candidate.get("processed_request_count"),
        "batch_counts": candidate.get("batch_counts"),
        "total_wall_ms": candidate.get("total_wall_ms"),
        "total_load_ms": candidate.get("total_load_ms"),
        "total_run_ms": candidate.get("total_run_ms"),
        "amortized_wall_ms_per_processed_request": candidate_wall,
        "amortized_load_ms_per_processed_request": candidate_load,
        "amortized_run_ms_per_processed_request": candidate_run,
        "avg_bpu_loading": candidate.get("avg_bpu_loading"),
        "max_bpu_loading": candidate.get("max_bpu_loading"),
    },
    "comparison_to_selected_pair_candidate_service": {
        "wall_ms_delta_ratio": wall_delta_ratio,
        "load_ms_delta_ratio": load_delta_ratio,
        "run_ms_delta_ratio": run_delta_ratio,
        "cross_job_wall_time_improved": cross_wall_improved,
        "cross_job_load_time_improved": cross_load_improved,
        "candidate_service_reloads_selected_pair_per_batch": True,
        "cross_job_reuses_selected_pair_workers_once": True,
    },
    "next_optimization_target": (
        "promote a long-lived selected-pair queue runner prototype that keeps the selected-pair workers alive across jobs"
        if cross_wall_improved and cross_load_improved
        else "do not promote cross-job selected-pair reuse until telemetry shows amortized wall/load improvement"
    ),
    "warnings": warnings,
    "errors": errors,
}

(run_dir / "selected_pair_cross_job_reuse_probe.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
lines = [
    "# Dream 7B BPU Selected Pair Cross-Job Reuse Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- job_count: {payload['job_count']}",
    f"- batch_count: {payload['batch_count']}",
    f"- processed_forward_count: {payload['processed_forward_count']}",
    f"- selected_pair: {payload['selected_pair']}",
    f"- selected_segments: {payload['selected_segments']}",
    f"- selected_resident_load_ms: {payload['selected_resident_load_ms']}",
    f"- resident_load_once_amortized_ms_per_forward: {payload['resident_load_once_amortized_ms_per_forward']}",
    f"- cross_job.amortized_wall_ms_per_forward: {payload['cross_job_metrics']['amortized_wall_ms_per_forward']}",
    f"- candidate_service.amortized_wall_ms_per_processed_request: {payload['candidate_service_metrics']['amortized_wall_ms_per_processed_request']}",
    f"- comparison.wall_ms_delta_ratio: {payload['comparison_to_selected_pair_candidate_service']['wall_ms_delta_ratio']}",
    f"- comparison.load_ms_delta_ratio: {payload['comparison_to_selected_pair_candidate_service']['load_ms_delta_ratio']}",
    f"- next_optimization_target: {payload['next_optimization_target']}",
    "",
    "## Warnings",
    "",
]
lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- none")
lines.extend(["", "## Errors", ""])
lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
(run_dir / "selected_pair_cross_job_reuse_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "selected_pair_cross_job_reuse_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
