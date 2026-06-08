#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
min_batch_count="${DREAM7B_BPU_UTILIZATION_GAP_MIN_BATCH_COUNT:-16}"
min_sustained_round_count="${DREAM7B_BPU_UTILIZATION_GAP_MIN_SUSTAINED_ROUND_COUNT:-3}"
min_sustained_total_items="${DREAM7B_BPU_UTILIZATION_GAP_MIN_SUSTAINED_TOTAL_ITEMS:-48}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

if ! [[ "$min_batch_count" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_UTILIZATION_GAP_MIN_BATCH_COUNT must be a positive integer." >&2
  exit 2
fi
if ! [[ "$min_sustained_round_count" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_UTILIZATION_GAP_MIN_SUSTAINED_ROUND_COUNT must be a positive integer." >&2
  exit 2
fi
if ! [[ "$min_sustained_total_items" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_UTILIZATION_GAP_MIN_SUSTAINED_TOTAL_ITEMS must be a positive integer." >&2
  exit 2
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_utilization_gap_$stamp"
mkdir -p "$run_dir"

python3 - \
  "$run_dir" \
  "$report_root" \
  "$min_batch_count" \
  "$min_sustained_round_count" \
  "$min_sustained_total_items" <<'PY'
import glob
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
report_root = Path(sys.argv[2])
min_batch_count = int(sys.argv[3])
min_sustained_round_count = int(sys.argv[4])
min_sustained_total_items = int(sys.argv[5])
errors = []
warnings = []


def latest_json(pattern):
    paths = [Path(item) for item in glob.glob(str(report_root / pattern))]
    paths = [item for item in paths if item.is_file()]
    if not paths:
        return None, None
    path = max(paths, key=lambda item: item.stat().st_mtime)
    return path, json.loads(path.read_text(encoding="utf-8"))


def round_float(value):
    if value is None:
        return None
    return round(float(value), 3)


batch_sweep_path, batch_sweep = latest_json("dream7b_bpu_fine_batch_size_sweep_*/batch_size_sweep_probe.json")
runtime_telemetry_path, runtime_telemetry = latest_json("dream7b_bpu_runtime_telemetry_*/runtime_telemetry_probe.json")
selected_pair_telemetry_path, selected_pair_telemetry = latest_json("dream7b_bpu_selected_pair_telemetry_*/selected_pair_telemetry_probe.json")
systemd_telemetry_path, systemd_telemetry = latest_json("dream7b_bpu_batch_queue_systemd_telemetry_*/systemd_telemetry_probe.json")
selected_pair_candidate_service_telemetry_path, selected_pair_candidate_service_telemetry = latest_json("dream7b_bpu_selected_pair_candidate_service_telemetry_*/systemd_telemetry_probe.json")
sustained_path, sustained = latest_json("dream7b_bpu_diffusion_batch_generate_sustained_*/batch_generation_sustained_probe.json")
batch_generate_telemetry_path, batch_generate_telemetry = latest_json("dream7b_bpu_diffusion_batch_generate_telemetry_*/batch_generation_telemetry_probe.json")

if batch_sweep is None:
    errors.append("missing dream7b_bpu_fine_batch_size_sweep_*/batch_size_sweep_probe.json")
if runtime_telemetry is None:
    errors.append("missing dream7b_bpu_runtime_telemetry_*/runtime_telemetry_probe.json")
if selected_pair_telemetry is None:
    errors.append("missing dream7b_bpu_selected_pair_telemetry_*/selected_pair_telemetry_probe.json")
if systemd_telemetry is None:
    errors.append("missing dream7b_bpu_batch_queue_systemd_telemetry_*/systemd_telemetry_probe.json")
if selected_pair_candidate_service_telemetry is None:
    errors.append("missing dream7b_bpu_selected_pair_candidate_service_telemetry_*/systemd_telemetry_probe.json")
if sustained is None:
    errors.append("missing dream7b_bpu_diffusion_batch_generate_sustained_*/batch_generation_sustained_probe.json")
if batch_generate_telemetry is None:
    errors.append("missing dream7b_bpu_diffusion_batch_generate_telemetry_*/batch_generation_telemetry_probe.json")

batch_scaling_reference = None
if isinstance(batch_sweep, dict):
    if batch_sweep.get("verdict") != "ok_dream7b_bpu_fine_batch_size_sweep_probe":
        errors.append(f"unexpected batch sweep verdict: {batch_sweep.get('verdict')}")
    entries = batch_sweep.get("entries") or []
    if entries:
        batch_scaling_reference = max(entries, key=lambda item: int(item.get("batch_count") or 0))
        if int(batch_scaling_reference.get("batch_count") or 0) < min_batch_count:
            warnings.append(
                "batch_size_sweep max batch_count is below "
                f"{min_batch_count}; using runtime/systemd/sustained telemetry as the authoritative batch-{min_batch_count} evidence"
            )
    else:
        errors.append("batch sweep entries are empty")

runtime_forward = (runtime_telemetry or {}).get("forward_metrics") or {}
if isinstance(runtime_telemetry, dict):
    if runtime_telemetry.get("verdict") != "ok_dream7b_bpu_runtime_telemetry_probe":
        errors.append(f"unexpected runtime telemetry verdict: {runtime_telemetry.get('verdict')}")
    if int(runtime_telemetry.get("batch_count") or 0) < min_batch_count:
        errors.append(f"runtime telemetry batch_count below {min_batch_count}: {runtime_telemetry.get('batch_count')}")
    if float(runtime_telemetry.get("max_bpu_loading") or 0.0) <= 0.0:
        errors.append(f"runtime telemetry max_bpu_loading did not exceed zero: {runtime_telemetry.get('max_bpu_loading')}")

selected_pair_selected = (selected_pair_telemetry or {}).get("selected") or {}
selected_pair_comparison = (selected_pair_telemetry or {}).get("comparison_to_default_runtime_telemetry") or {}
if isinstance(selected_pair_telemetry, dict):
    if selected_pair_telemetry.get("verdict") != "ok_dream7b_bpu_selected_pair_telemetry_probe":
        errors.append(f"unexpected selected pair telemetry verdict: {selected_pair_telemetry.get('verdict')}")
    if int(selected_pair_telemetry.get("batch_count") or 0) < min_batch_count:
        errors.append(f"selected pair telemetry batch_count below {min_batch_count}: {selected_pair_telemetry.get('batch_count')}")
    if float(selected_pair_telemetry.get("max_bpu_loading") or 0.0) <= 0.0:
        errors.append(f"selected pair telemetry max_bpu_loading did not exceed zero: {selected_pair_telemetry.get('max_bpu_loading')}")
    if selected_pair_selected.get("selected_pair_covers_all_segments") is not True:
        errors.append(f"selected pair telemetry selected_pair_covers_all_segments is not true: {selected_pair_selected.get('selected_pair_covers_all_segments')}")
    if selected_pair_comparison.get("selected_wall_time_improved_vs_default_runtime") is not True:
        warnings.append("selected pair telemetry did not improve wall time versus the latest default runtime telemetry")

if isinstance(systemd_telemetry, dict):
    if systemd_telemetry.get("verdict") != "ok_dream7b_bpu_batch_queue_systemd_telemetry_probe":
        errors.append(f"unexpected systemd telemetry verdict: {systemd_telemetry.get('verdict')}")
    if int(systemd_telemetry.get("processed_request_count") or 0) < min_sustained_total_items:
        errors.append(f"systemd telemetry processed_request_count below {min_sustained_total_items}: {systemd_telemetry.get('processed_request_count')}")
    if float(systemd_telemetry.get("max_bpu_loading") or 0.0) <= 0.0:
        errors.append(f"systemd telemetry max_bpu_loading did not exceed zero: {systemd_telemetry.get('max_bpu_loading')}")

selected_pair_candidate_service_comparison = (selected_pair_candidate_service_telemetry or {}).get("comparison_to_default_systemd_telemetry") or {}
if isinstance(selected_pair_candidate_service_telemetry, dict):
    if selected_pair_candidate_service_telemetry.get("verdict") != "ok_dream7b_bpu_batch_queue_systemd_telemetry_probe":
        errors.append(f"unexpected selected-pair candidate service telemetry verdict: {selected_pair_candidate_service_telemetry.get('verdict')}")
    if selected_pair_candidate_service_telemetry.get("service_name") != "dream7b-bpu-selected-pair-candidate.service":
        errors.append(f"unexpected selected-pair candidate service_name: {selected_pair_candidate_service_telemetry.get('service_name')}")
    if int(selected_pair_candidate_service_telemetry.get("processed_request_count") or 0) < min_sustained_total_items:
        errors.append(
            "selected-pair candidate service telemetry processed_request_count below "
            f"{min_sustained_total_items}: {selected_pair_candidate_service_telemetry.get('processed_request_count')}"
        )
    if selected_pair_candidate_service_telemetry.get("batch_counts") != [min_batch_count, min_batch_count, min_batch_count]:
        errors.append(f"unexpected selected-pair candidate service batch_counts: {selected_pair_candidate_service_telemetry.get('batch_counts')}")
    if selected_pair_candidate_service_telemetry.get("expected_window_execution_mode") != "selected-pair-resident":
        errors.append(
            "unexpected selected-pair candidate service expected_window_execution_mode: "
            f"{selected_pair_candidate_service_telemetry.get('expected_window_execution_mode')}"
        )
    if selected_pair_candidate_service_telemetry.get("expected_child_process_count") != 2:
        errors.append(f"unexpected selected-pair candidate service expected_child_process_count: {selected_pair_candidate_service_telemetry.get('expected_child_process_count')}")
    if float(selected_pair_candidate_service_telemetry.get("max_bpu_loading") or 0.0) <= 0.0:
        errors.append(
            "selected-pair candidate service telemetry max_bpu_loading did not exceed zero: "
            f"{selected_pair_candidate_service_telemetry.get('max_bpu_loading')}"
        )
    if selected_pair_candidate_service_comparison.get("candidate_wall_time_improved_vs_default_systemd") is not True:
        warnings.append("selected-pair candidate service telemetry did not improve wall time versus default systemd telemetry")
    if selected_pair_candidate_service_comparison.get("candidate_avg_bpu_loading_not_worse_than_default_systemd") is not True:
        warnings.append("selected-pair candidate service telemetry improved wall time but did not improve average BPU loading versus default systemd telemetry")

if isinstance(sustained, dict):
    if sustained.get("verdict") != "ok_dream7b_bpu_diffusion_batch_generate_sustained_probe":
        errors.append(f"unexpected sustained verdict: {sustained.get('verdict')}")
    if int(sustained.get("round_count") or 0) < min_sustained_round_count:
        errors.append(f"sustained round_count below {min_sustained_round_count}: {sustained.get('round_count')}")
    if int(sustained.get("batch_count") or 0) < min_batch_count:
        errors.append(f"sustained batch_count below {min_batch_count}: {sustained.get('batch_count')}")
    if int(sustained.get("actual_total_batch_items") or 0) < min_sustained_total_items:
        errors.append(f"sustained actual_total_batch_items below {min_sustained_total_items}: {sustained.get('actual_total_batch_items')}")
    if float(sustained.get("max_bpu_loading") or 0.0) <= 0.0:
        errors.append(f"sustained max_bpu_loading did not exceed zero: {sustained.get('max_bpu_loading')}")

if isinstance(batch_generate_telemetry, dict):
    if batch_generate_telemetry.get("verdict") != "ok_dream7b_bpu_diffusion_batch_generate_telemetry_probe":
        errors.append(f"unexpected batch generate telemetry verdict: {batch_generate_telemetry.get('verdict')}")
    if int(batch_generate_telemetry.get("batch_count") or 0) < min_batch_count:
        errors.append(f"batch generate telemetry batch_count below {min_batch_count}: {batch_generate_telemetry.get('batch_count')}")
    if float(batch_generate_telemetry.get("max_bpu_loading") or 0.0) <= 0.0:
        errors.append(f"batch generate telemetry max_bpu_loading did not exceed zero: {batch_generate_telemetry.get('max_bpu_loading')}")

batch_reference_amortized_load = float((batch_scaling_reference or {}).get("amortized_load_ms_per_forward") or 0.0)
batch_reference_amortized_run = float((batch_scaling_reference or {}).get("amortized_run_ms_per_forward") or 0.0)
batch_reference_load_to_run_ratio = batch_reference_amortized_load / batch_reference_amortized_run if batch_reference_amortized_run else None
runtime_load = float(runtime_forward.get("load_ms") or 0.0)
runtime_run = float(runtime_forward.get("run_ms") or 0.0)
runtime_load_to_run_ratio = runtime_load / runtime_run if runtime_run else None
runtime_amortized_load = float(runtime_forward.get("amortized_load_ms_per_forward") or 0.0)
runtime_amortized_run = float(runtime_forward.get("amortized_run_ms_per_forward") or 0.0)
systemd_total_load = float((systemd_telemetry or {}).get("total_load_ms") or 0.0)
systemd_total_run = float((systemd_telemetry or {}).get("total_run_ms") or 0.0)
systemd_load_to_run_ratio = systemd_total_load / systemd_total_run if systemd_total_run else None
candidate_service_total_load = float((selected_pair_candidate_service_telemetry or {}).get("total_load_ms") or 0.0)
candidate_service_total_run = float((selected_pair_candidate_service_telemetry or {}).get("total_run_ms") or 0.0)
candidate_service_load_to_run_ratio = candidate_service_total_load / candidate_service_total_run if candidate_service_total_run else None
telemetry_avgs = [
    float((runtime_telemetry or {}).get("avg_bpu_loading") or 0.0),
    float((selected_pair_telemetry or {}).get("avg_bpu_loading") or 0.0),
    float((systemd_telemetry or {}).get("avg_bpu_loading") or 0.0),
    float((selected_pair_candidate_service_telemetry or {}).get("avg_bpu_loading") or 0.0),
    float((sustained or {}).get("avg_bpu_loading") or 0.0),
    float((batch_generate_telemetry or {}).get("avg_bpu_loading") or 0.0),
]
telemetry_maxes = [
    float((runtime_telemetry or {}).get("max_bpu_loading") or 0.0),
    float((selected_pair_telemetry or {}).get("max_bpu_loading") or 0.0),
    float((systemd_telemetry or {}).get("max_bpu_loading") or 0.0),
    float((selected_pair_candidate_service_telemetry or {}).get("max_bpu_loading") or 0.0),
    float((sustained or {}).get("max_bpu_loading") or 0.0),
    float((batch_generate_telemetry or {}).get("max_bpu_loading") or 0.0),
]
max_observed_bpu_loading = max(telemetry_maxes) if telemetry_maxes else 0.0
avg_observed_bpu_loading = statistics.fmean(telemetry_avgs) if telemetry_avgs else 0.0

load_dominated = any(
    ratio is not None and ratio > 1.0
    for ratio in (batch_reference_load_to_run_ratio, runtime_load_to_run_ratio, systemd_load_to_run_ratio, candidate_service_load_to_run_ratio)
)
if max_observed_bpu_loading <= 0.0:
    errors.append(f"max_observed_bpu_loading did not exceed zero: {max_observed_bpu_loading}")
if not load_dominated:
    warnings.append("latest load/run ratios are not load-dominated; update optimization target if this reflects a real improvement")

diagnosis = "hbm_reload_dominated" if load_dominated else "not_hbm_reload_dominated"
next_optimization_target = "reduce per-window HBM reload overhead before expecting sustained 128TOPS-level average utilization" if load_dominated else "re-measure utilization after load/run balance changed"
payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_utilization_gap_probe" if not errors else "failed_dream7b_bpu_utilization_gap_probe",
    "run_dir": str(run_dir),
    "report_root": str(report_root),
    "min_batch_count": min_batch_count,
    "min_sustained_round_count": min_sustained_round_count,
    "min_sustained_total_items": min_sustained_total_items,
    "diagnosis": diagnosis,
    "next_optimization_target": next_optimization_target,
    "max_observed_bpu_loading": round_float(max_observed_bpu_loading),
    "avg_observed_bpu_loading_across_reports": round_float(avg_observed_bpu_loading),
    "telemetry_avg_bpu_loading_values": [round_float(item) for item in telemetry_avgs],
    "telemetry_max_bpu_loading_values": [round_float(item) for item in telemetry_maxes],
    "batch_scaling_reference": {
        "path": str(batch_sweep_path) if batch_sweep_path else None,
        "max_available_batch_count": (batch_scaling_reference or {}).get("batch_count"),
        "amortized_load_ms_per_forward": round_float(batch_reference_amortized_load),
        "amortized_run_ms_per_forward": round_float(batch_reference_amortized_run),
        "load_to_run_ratio": round_float(batch_reference_load_to_run_ratio),
        "load_share": (batch_scaling_reference or {}).get("load_share"),
    },
    "runtime_telemetry": {
        "path": str(runtime_telemetry_path) if runtime_telemetry_path else None,
        "batch_count": (runtime_telemetry or {}).get("batch_count"),
        "max_bpu_loading": (runtime_telemetry or {}).get("max_bpu_loading"),
        "avg_bpu_loading": (runtime_telemetry or {}).get("avg_bpu_loading"),
        "forward_load_ms": round_float(runtime_load),
        "forward_run_ms": round_float(runtime_run),
        "amortized_load_ms_per_forward": round_float(runtime_amortized_load),
        "amortized_run_ms_per_forward": round_float(runtime_amortized_run),
        "load_to_run_ratio": round_float(runtime_load_to_run_ratio),
    },
    "selected_pair_telemetry": {
        "path": str(selected_pair_telemetry_path) if selected_pair_telemetry_path else None,
        "batch_count": (selected_pair_telemetry or {}).get("batch_count"),
        "max_bpu_loading": (selected_pair_telemetry or {}).get("max_bpu_loading"),
        "avg_bpu_loading": (selected_pair_telemetry or {}).get("avg_bpu_loading"),
        "selected_pair": selected_pair_selected.get("selected_pair"),
        "selected_segments": selected_pair_selected.get("selected_segments"),
        "selected_pair_covers_all_segments": selected_pair_selected.get("selected_pair_covers_all_segments"),
        "selected_wall_ms": selected_pair_selected.get("wall_ms"),
        "selected_forward_load_ms": selected_pair_selected.get("forward_load_ms"),
        "selected_run_ms": selected_pair_selected.get("run_ms"),
        "wall_ms_delta_vs_default_runtime": selected_pair_comparison.get("wall_ms_delta_vs_default_runtime"),
        "wall_ms_delta_ratio_vs_default_runtime": selected_pair_comparison.get("wall_ms_delta_ratio_vs_default_runtime"),
        "avg_bpu_loading_delta_vs_default_runtime": selected_pair_comparison.get("avg_bpu_loading_delta_vs_default_runtime"),
        "selected_wall_time_improved_vs_default_runtime": selected_pair_comparison.get("selected_wall_time_improved_vs_default_runtime"),
        "selected_avg_bpu_loading_improved_vs_default_runtime": selected_pair_comparison.get("selected_avg_bpu_loading_improved_vs_default_runtime"),
    },
    "systemd_telemetry": {
        "path": str(systemd_telemetry_path) if systemd_telemetry_path else None,
        "processed_request_count": (systemd_telemetry or {}).get("processed_request_count"),
        "max_bpu_loading": (systemd_telemetry or {}).get("max_bpu_loading"),
        "avg_bpu_loading": (systemd_telemetry or {}).get("avg_bpu_loading"),
        "total_load_ms": round_float(systemd_total_load),
        "total_run_ms": round_float(systemd_total_run),
        "load_to_run_ratio": round_float(systemd_load_to_run_ratio),
        "amortized_load_ms_per_processed_request": (systemd_telemetry or {}).get("amortized_load_ms_per_processed_request"),
        "amortized_run_ms_per_processed_request": (systemd_telemetry or {}).get("amortized_run_ms_per_processed_request"),
    },
    "selected_pair_candidate_service_telemetry": {
        "path": str(selected_pair_candidate_service_telemetry_path) if selected_pair_candidate_service_telemetry_path else None,
        "service_name": (selected_pair_candidate_service_telemetry or {}).get("service_name"),
        "processed_request_count": (selected_pair_candidate_service_telemetry or {}).get("processed_request_count"),
        "batch_counts": (selected_pair_candidate_service_telemetry or {}).get("batch_counts"),
        "expected_forward_command": (selected_pair_candidate_service_telemetry or {}).get("expected_forward_command"),
        "expected_window_execution_mode": (selected_pair_candidate_service_telemetry or {}).get("expected_window_execution_mode"),
        "expected_child_process_count": (selected_pair_candidate_service_telemetry or {}).get("expected_child_process_count"),
        "max_bpu_loading": (selected_pair_candidate_service_telemetry or {}).get("max_bpu_loading"),
        "avg_bpu_loading": (selected_pair_candidate_service_telemetry or {}).get("avg_bpu_loading"),
        "total_load_ms": round_float(candidate_service_total_load),
        "total_run_ms": round_float(candidate_service_total_run),
        "load_to_run_ratio": round_float(candidate_service_load_to_run_ratio),
        "amortized_wall_ms_per_processed_request": (selected_pair_candidate_service_telemetry or {}).get("amortized_wall_ms_per_processed_request"),
        "amortized_load_ms_per_processed_request": (selected_pair_candidate_service_telemetry or {}).get("amortized_load_ms_per_processed_request"),
        "amortized_run_ms_per_processed_request": (selected_pair_candidate_service_telemetry or {}).get("amortized_run_ms_per_processed_request"),
        "comparison_to_default_systemd_telemetry": selected_pair_candidate_service_comparison,
    },
    "sustained_generation": {
        "path": str(sustained_path) if sustained_path else None,
        "round_count": (sustained or {}).get("round_count"),
        "batch_count": (sustained or {}).get("batch_count"),
        "actual_total_batch_items": (sustained or {}).get("actual_total_batch_items"),
        "max_bpu_loading": (sustained or {}).get("max_bpu_loading"),
        "avg_bpu_loading": (sustained or {}).get("avg_bpu_loading"),
        "total_forward_call_count": (sustained or {}).get("total_forward_call_count"),
    },
    "batch_generate_telemetry": {
        "path": str(batch_generate_telemetry_path) if batch_generate_telemetry_path else None,
        "batch_count": (batch_generate_telemetry or {}).get("batch_count"),
        "max_bpu_loading": (batch_generate_telemetry or {}).get("max_bpu_loading"),
        "avg_bpu_loading": (batch_generate_telemetry or {}).get("avg_bpu_loading"),
        "nonzero_bpu_loading_sample_count": (batch_generate_telemetry or {}).get("nonzero_bpu_loading_sample_count"),
    },
    "warnings": warnings,
    "errors": errors,
}
(run_dir / "utilization_gap_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
warning_lines = [f"- {item}" for item in warnings] if warnings else ["- none"]
error_lines = [f"- {item}" for item in errors] if errors else ["- none"]
lines = [
    "# Dream 7B BPU Utilization Gap Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- diagnosis: {payload['diagnosis']}",
    f"- next_optimization_target: {payload['next_optimization_target']}",
    f"- max_observed_bpu_loading: {payload['max_observed_bpu_loading']}",
    f"- avg_observed_bpu_loading_across_reports: {payload['avg_observed_bpu_loading_across_reports']}",
    f"- batch_scaling_reference_load_to_run_ratio: {payload['batch_scaling_reference']['load_to_run_ratio']}",
    f"- runtime_load_to_run_ratio: {payload['runtime_telemetry']['load_to_run_ratio']}",
    f"- selected_pair_telemetry_avg_bpu_loading: {payload['selected_pair_telemetry']['avg_bpu_loading']}",
    f"- selected_pair_telemetry_wall_delta_ratio: {payload['selected_pair_telemetry']['wall_ms_delta_ratio_vs_default_runtime']}",
    f"- systemd_load_to_run_ratio: {payload['systemd_telemetry']['load_to_run_ratio']}",
    f"- selected_pair_candidate_service_load_to_run_ratio: {payload['selected_pair_candidate_service_telemetry']['load_to_run_ratio']}",
    f"- selected_pair_candidate_service_wall_delta_ratio: {payload['selected_pair_candidate_service_telemetry']['comparison_to_default_systemd_telemetry'].get('wall_ms_delta_ratio_vs_default_systemd')}",
    f"- selected_pair_candidate_service_avg_bpu_delta: {payload['selected_pair_candidate_service_telemetry']['comparison_to_default_systemd_telemetry'].get('avg_bpu_loading_delta_vs_default_systemd')}",
    "",
    "## Evidence",
    "",
    f"- batch_sweep: {payload['batch_scaling_reference']['path']}",
    f"- runtime_telemetry: {payload['runtime_telemetry']['path']}",
    f"- selected_pair_telemetry: {payload['selected_pair_telemetry']['path']}",
    f"- systemd_telemetry: {payload['systemd_telemetry']['path']}",
    f"- selected_pair_candidate_service_telemetry: {payload['selected_pair_candidate_service_telemetry']['path']}",
    f"- sustained_generation: {payload['sustained_generation']['path']}",
    f"- batch_generate_telemetry: {payload['batch_generate_telemetry']['path']}",
    "",
    "## Warnings",
    "",
    *warning_lines,
    "",
    "## Errors",
    "",
    *error_lines,
    "",
]
(run_dir / "utilization_gap_probe.md").write_text("\n".join(lines), encoding="utf-8")
print(run_dir / "utilization_gap_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
