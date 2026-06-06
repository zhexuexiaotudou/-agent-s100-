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
systemd_telemetry_path, systemd_telemetry = latest_json("dream7b_bpu_batch_queue_systemd_telemetry_*/systemd_telemetry_probe.json")
sustained_path, sustained = latest_json("dream7b_bpu_diffusion_batch_generate_sustained_*/batch_generation_sustained_probe.json")
batch_generate_telemetry_path, batch_generate_telemetry = latest_json("dream7b_bpu_diffusion_batch_generate_telemetry_*/batch_generation_telemetry_probe.json")

if batch_sweep is None:
    errors.append("missing dream7b_bpu_fine_batch_size_sweep_*/batch_size_sweep_probe.json")
if runtime_telemetry is None:
    errors.append("missing dream7b_bpu_runtime_telemetry_*/runtime_telemetry_probe.json")
if systemd_telemetry is None:
    errors.append("missing dream7b_bpu_batch_queue_systemd_telemetry_*/systemd_telemetry_probe.json")
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

if isinstance(systemd_telemetry, dict):
    if systemd_telemetry.get("verdict") != "ok_dream7b_bpu_batch_queue_systemd_telemetry_probe":
        errors.append(f"unexpected systemd telemetry verdict: {systemd_telemetry.get('verdict')}")
    if int(systemd_telemetry.get("processed_request_count") or 0) < min_sustained_total_items:
        errors.append(f"systemd telemetry processed_request_count below {min_sustained_total_items}: {systemd_telemetry.get('processed_request_count')}")
    if float(systemd_telemetry.get("max_bpu_loading") or 0.0) <= 0.0:
        errors.append(f"systemd telemetry max_bpu_loading did not exceed zero: {systemd_telemetry.get('max_bpu_loading')}")

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
telemetry_avgs = [
    float((runtime_telemetry or {}).get("avg_bpu_loading") or 0.0),
    float((systemd_telemetry or {}).get("avg_bpu_loading") or 0.0),
    float((sustained or {}).get("avg_bpu_loading") or 0.0),
    float((batch_generate_telemetry or {}).get("avg_bpu_loading") or 0.0),
]
telemetry_maxes = [
    float((runtime_telemetry or {}).get("max_bpu_loading") or 0.0),
    float((systemd_telemetry or {}).get("max_bpu_loading") or 0.0),
    float((sustained or {}).get("max_bpu_loading") or 0.0),
    float((batch_generate_telemetry or {}).get("max_bpu_loading") or 0.0),
]
max_observed_bpu_loading = max(telemetry_maxes) if telemetry_maxes else 0.0
avg_observed_bpu_loading = statistics.fmean(telemetry_avgs) if telemetry_avgs else 0.0

load_dominated = any(
    ratio is not None and ratio > 1.0
    for ratio in (batch_reference_load_to_run_ratio, runtime_load_to_run_ratio, systemd_load_to_run_ratio)
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
    f"- systemd_load_to_run_ratio: {payload['systemd_telemetry']['load_to_run_ratio']}",
    "",
    "## Evidence",
    "",
    f"- batch_sweep: {payload['batch_scaling_reference']['path']}",
    f"- runtime_telemetry: {payload['runtime_telemetry']['path']}",
    f"- systemd_telemetry: {payload['systemd_telemetry']['path']}",
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
