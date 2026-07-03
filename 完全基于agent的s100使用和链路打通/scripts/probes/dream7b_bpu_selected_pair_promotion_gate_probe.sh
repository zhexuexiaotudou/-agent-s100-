#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
min_batch_count="${DREAM7B_BPU_SELECTED_PAIR_PROMOTION_MIN_BATCH_COUNT:-16}"
min_wall_delta_ratio="${DREAM7B_BPU_SELECTED_PAIR_PROMOTION_MIN_WALL_DELTA_RATIO:-0.05}"
min_avg_bpu_delta="${DREAM7B_BPU_SELECTED_PAIR_PROMOTION_MIN_AVG_BPU_DELTA:-1.0}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

if ! [[ "$min_batch_count" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_SELECTED_PAIR_PROMOTION_MIN_BATCH_COUNT must be a positive integer." >&2
  exit 2
fi
if ! [[ "$min_wall_delta_ratio" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "DREAM7B_BPU_SELECTED_PAIR_PROMOTION_MIN_WALL_DELTA_RATIO must be a non-negative number." >&2
  exit 2
fi
if ! [[ "$min_avg_bpu_delta" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "DREAM7B_BPU_SELECTED_PAIR_PROMOTION_MIN_AVG_BPU_DELTA must be a non-negative number." >&2
  exit 2
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_selected_pair_promotion_gate_$stamp"
mkdir -p "$run_dir"

python3 - \
  "$run_dir" \
  "$report_root" \
  "$min_batch_count" \
  "$min_wall_delta_ratio" \
  "$min_avg_bpu_delta" <<'PY'
import glob
import json
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
report_root = Path(sys.argv[2])
min_batch_count = int(sys.argv[3])
min_wall_delta_ratio = float(sys.argv[4])
min_avg_bpu_delta = float(sys.argv[5])

errors = []
warnings = []
checks = []


def latest_json(pattern):
    paths = [Path(item) for item in glob.glob(str(report_root / pattern))]
    paths = [item for item in paths if item.is_file()]
    if not paths:
        return None, None
    path = max(paths, key=lambda item: item.stat().st_mtime)
    return path, json.loads(path.read_text(encoding="utf-8"))


def add_check(name, path, ok, details):
    row = {
        "name": name,
        "ok": bool(ok),
        "path": str(path) if path else "",
        "details": details,
    }
    checks.append(row)
    if not ok:
        errors.append(f"{name} failed: {details}")


selected_path, selected_report = latest_json("dream7b_bpu_selected_pair_telemetry_*/selected_pair_telemetry_probe.json")
if selected_report is None:
    add_check("selected_pair_telemetry", selected_path, False, {"reason": "missing selected_pair_telemetry_probe.json"})
else:
    selected = selected_report.get("selected") or {}
    comparison = selected_report.get("comparison_to_default_runtime_telemetry") or {}
    ok = (
        selected_report.get("verdict") == "ok_dream7b_bpu_selected_pair_telemetry_probe"
        and int(selected_report.get("batch_count") or 0) >= min_batch_count
        and selected.get("selected_pair_covers_all_segments") is True
        and selected.get("selected_pair") == [1, 8]
        and selected.get("selected_segments") == ["seg02_04", "seg24_26"]
        and comparison.get("selected_wall_time_improved_vs_default_runtime") is True
        and comparison.get("selected_avg_bpu_loading_improved_vs_default_runtime") is True
        and float(comparison.get("wall_ms_delta_ratio_vs_default_runtime") or 0.0) >= min_wall_delta_ratio
        and float(comparison.get("avg_bpu_loading_delta_vs_default_runtime") or 0.0) >= min_avg_bpu_delta
        and not selected_report.get("errors")
    )
    add_check(
        "selected_pair_telemetry",
        selected_path,
        ok,
        {
            "verdict": selected_report.get("verdict"),
            "batch_count": selected_report.get("batch_count"),
            "selected_pair": selected.get("selected_pair"),
            "selected_segments": selected.get("selected_segments"),
            "selected_pair_covers_all_segments": selected.get("selected_pair_covers_all_segments"),
            "max_bpu_loading": selected_report.get("max_bpu_loading"),
            "avg_bpu_loading": selected_report.get("avg_bpu_loading"),
            "wall_ms_delta_ratio_vs_default_runtime": comparison.get("wall_ms_delta_ratio_vs_default_runtime"),
            "avg_bpu_loading_delta_vs_default_runtime": comparison.get("avg_bpu_loading_delta_vs_default_runtime"),
            "selected_wall_time_improved_vs_default_runtime": comparison.get("selected_wall_time_improved_vs_default_runtime"),
            "selected_avg_bpu_loading_improved_vs_default_runtime": comparison.get("selected_avg_bpu_loading_improved_vs_default_runtime"),
        },
    )

utilization_path, utilization = latest_json("dream7b_bpu_utilization_gap_*/utilization_gap_probe.json")
if utilization is None:
    add_check("utilization_gap", utilization_path, False, {"reason": "missing utilization_gap_probe.json"})
else:
    selected_pair_telemetry = utilization.get("selected_pair_telemetry") or {}
    ok = (
        utilization.get("verdict") == "ok_dream7b_bpu_utilization_gap_probe"
        and utilization.get("diagnosis") == "hbm_reload_dominated"
        and float(utilization.get("max_observed_bpu_loading") or 0.0) >= 100.0
        and selected_pair_telemetry.get("selected_wall_time_improved_vs_default_runtime") is True
        and selected_pair_telemetry.get("selected_avg_bpu_loading_improved_vs_default_runtime") is True
        and str(selected_pair_telemetry.get("path") or "") == str(selected_path)
        and not utilization.get("errors")
    )
    add_check(
        "utilization_gap",
        utilization_path,
        ok,
        {
            "verdict": utilization.get("verdict"),
            "diagnosis": utilization.get("diagnosis"),
            "max_observed_bpu_loading": utilization.get("max_observed_bpu_loading"),
            "avg_observed_bpu_loading_across_reports": utilization.get("avg_observed_bpu_loading_across_reports"),
            "selected_pair_telemetry_path": selected_pair_telemetry.get("path"),
        },
    )

acceptance_path, acceptance = latest_json("dream7b_bpu_deployment_acceptance_*/deployment_acceptance_probe.json")
if acceptance is None:
    add_check("deployment_acceptance", acceptance_path, False, {"reason": "missing deployment_acceptance_probe.json"})
else:
    acceptance_checks = acceptance.get("checks") or []
    selected_pair_acceptance = next(
        (item for item in acceptance_checks if isinstance(item, dict) and item.get("name") == "selected_pair_telemetry"),
        {},
    )
    utilization_acceptance = next(
        (item for item in acceptance_checks if isinstance(item, dict) and item.get("name") == "utilization_gap"),
        {},
    )
    ok = (
        acceptance.get("verdict") == "ok_dream7b_bpu_deployment_acceptance_probe"
        and acceptance.get("check_count") == acceptance.get("passed_check_count")
        and selected_pair_acceptance.get("ok") is True
        and utilization_acceptance.get("ok") is True
        and str(selected_pair_acceptance.get("path") or "") == str(selected_path)
        and str(utilization_acceptance.get("path") or "") == str(utilization_path)
        and not acceptance.get("errors")
    )
    add_check(
        "deployment_acceptance",
        acceptance_path,
        ok,
        {
            "verdict": acceptance.get("verdict"),
            "check_count": acceptance.get("check_count"),
            "passed_check_count": acceptance.get("passed_check_count"),
            "selected_pair_telemetry_ok": selected_pair_acceptance.get("ok"),
            "utilization_gap_ok": utilization_acceptance.get("ok"),
        },
    )

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_selected_pair_promotion_gate_probe" if not errors else "failed_dream7b_bpu_selected_pair_promotion_gate_probe",
    "run_dir": str(run_dir),
    "report_root": str(report_root),
    "min_batch_count": min_batch_count,
    "min_wall_delta_ratio": min_wall_delta_ratio,
    "min_avg_bpu_delta": min_avg_bpu_delta,
    "selected_pair_telemetry_path": str(selected_path) if selected_path else "",
    "utilization_gap_path": str(utilization_path) if utilization_path else "",
    "deployment_acceptance_path": str(acceptance_path) if acceptance_path else "",
    "promotion_ready_for_guarded_default_service_candidate": not errors,
    "default_service_already_promoted": False,
    "checks": checks,
    "next_optimization_target": "implement a guarded selected-pair default-service candidate and re-run deployment acceptance before replacing the current default Dream 7B service path",
    "warnings": warnings,
    "errors": errors,
}

(run_dir / "selected_pair_promotion_gate_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Dream 7B BPU Selected Pair Promotion Gate Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- run_dir: {payload['run_dir']}",
    f"- min_batch_count: {payload['min_batch_count']}",
    f"- min_wall_delta_ratio: {payload['min_wall_delta_ratio']}",
    f"- min_avg_bpu_delta: {payload['min_avg_bpu_delta']}",
    f"- selected_pair_telemetry_path: {payload['selected_pair_telemetry_path']}",
    f"- utilization_gap_path: {payload['utilization_gap_path']}",
    f"- deployment_acceptance_path: {payload['deployment_acceptance_path']}",
    f"- promotion_ready_for_guarded_default_service_candidate: {payload['promotion_ready_for_guarded_default_service_candidate']}",
    f"- default_service_already_promoted: {payload['default_service_already_promoted']}",
    f"- next_optimization_target: {payload['next_optimization_target']}",
    "",
    "## Checks",
    "",
]
for check in checks:
    lines.append(f"- {check['name']}: ok={check['ok']} path={check['path']}")
lines.extend(["", "## Warnings", ""])
lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- none")
lines.extend(["", "## Errors", ""])
lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
(run_dir / "selected_pair_promotion_gate_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "selected_pair_promotion_gate_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
