#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
min_target_avg_bpu="${DREAM7B_BPU_BACKLOG_SWEEP_MIN_TARGET_AVG_BPU:-70.0}"
target_90_load_to_run_ratio="${DREAM7B_BPU_BACKLOG_SWEEP_TARGET_90_LOAD_TO_RUN_RATIO:-0.15}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing report path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_50pct_service_backlog_sweep_summary_$stamp"
mkdir -p "$run_dir"

python3 - "$run_dir" "$report_root" "$min_target_avg_bpu" "$target_90_load_to_run_ratio" <<'PY'
import glob
import json
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
report_root = Path(sys.argv[2])
min_target_avg_bpu = float(sys.argv[3])
target_90_load_to_run_ratio = float(sys.argv[4])

reports = []
for raw in glob.glob(str(report_root / "dream7b_bpu_50pct_candidate_service_telemetry_*" / "50pct_candidate_service_telemetry_probe.json")):
    path = Path(raw)
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("verdict") != "ok_dream7b_bpu_50pct_candidate_service_telemetry_probe":
        continue
    if data.get("service_name") != "dream7b-bpu-selected-pair-cross-job-candidate-50pct.service":
        continue
    reports.append((path, data))

latest_by_job_count = {}
for path, data in reports:
    job_count = int(data.get("job_count") or 0)
    if job_count <= 0:
        continue
    previous = latest_by_job_count.get(job_count)
    if previous is None or path.stat().st_mtime > previous[0].stat().st_mtime:
        latest_by_job_count[job_count] = (path, data)

rows = []
for job_count in sorted(latest_by_job_count):
    path, data = latest_by_job_count[job_count]
    rows.append(
        {
            "job_count": job_count,
            "request_count": data.get("request_count"),
            "processed_request_count": data.get("processed_request_count"),
            "failed_job_count": data.get("failed_job_count"),
            "avg_bpu_loading": data.get("avg_bpu_loading"),
            "max_bpu_loading": data.get("max_bpu_loading"),
            "load_to_run_ratio": data.get("load_to_run_ratio"),
            "amortized_wall_ms_per_processed_request": data.get("amortized_wall_ms_per_processed_request"),
            "report_json": str(path),
            "report_md": str(path.with_suffix(".md")),
        }
    )

errors = []
warnings = []
required_counts = {2, 4, 8, 12}
missing = sorted(required_counts.difference(latest_by_job_count))
if missing:
    errors.append(f"missing backlog telemetry for job_count: {missing}")
for row in rows:
    if int(row.get("failed_job_count") or 0) != 0:
        errors.append(f"job_count={row['job_count']} has failed_job_count={row.get('failed_job_count')}")

best = max(rows, key=lambda item: float(item.get("avg_bpu_loading") or 0.0), default={})
best_avg = float(best.get("avg_bpu_loading") or 0.0)
best_ratio = float(best.get("load_to_run_ratio") or 999.0)
last_two = rows[-2:] if len(rows) >= 2 else rows
plateau_delta = None
if len(last_two) == 2:
    plateau_delta = round(float(last_two[-1].get("avg_bpu_loading") or 0.0) - float(last_two[-2].get("avg_bpu_loading") or 0.0), 6)

if best_avg < min_target_avg_bpu:
    warnings.append(f"backlog-only service path remains below {min_target_avg_bpu}% avg BPU")
if best_ratio > target_90_load_to_run_ratio:
    warnings.append(f"best load_to_run_ratio {best_ratio} remains above target {target_90_load_to_run_ratio}")

decision = "backlog_plateau_below_70_percent"
if best_avg >= min_target_avg_bpu:
    decision = "backlog_progress_candidate"
if best_ratio <= target_90_load_to_run_ratio:
    decision = "backlog_meets_90pct_ratio_gate"

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_50pct_service_backlog_sweep_summary_probe" if not errors else "failed_dream7b_bpu_50pct_service_backlog_sweep_summary_probe",
    "decision": decision,
    "run_dir": str(run_dir),
    "target_min_avg_bpu": min_target_avg_bpu,
    "target_90_load_to_run_ratio": target_90_load_to_run_ratio,
    "best_job_count": best.get("job_count"),
    "best_avg_bpu_loading": best.get("avg_bpu_loading"),
    "best_load_to_run_ratio": best.get("load_to_run_ratio"),
    "best_report_json": best.get("report_json"),
    "plateau_delta_avg_bpu_last_two_job_counts": plateau_delta,
    "rows": rows,
    "next_actions": [
        "do not expect backlog depth alone to reach 70-80 percent average BPU",
        "implement true producer/consumer prefetch so CPU job preparation overlaps BPU execution",
        "investigate resident segment topology beyond selected pair and reduce remaining load_to_run_ratio",
        "prepare vendor support package for Dream adapter, HBM layout, and runtime memory pool work because load_to_run_ratio remains far above 0.15",
    ],
    "warnings": warnings,
    "errors": errors,
}
(run_dir / "50pct_service_backlog_sweep_summary_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Dream 7B 50 Percent Service Backlog Sweep Summary",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- decision: {payload['decision']}",
    f"- best_job_count: {payload['best_job_count']}",
    f"- best_avg_bpu_loading: {payload['best_avg_bpu_loading']}",
    f"- best_load_to_run_ratio: {payload['best_load_to_run_ratio']}",
    f"- plateau_delta_avg_bpu_last_two_job_counts: {payload['plateau_delta_avg_bpu_last_two_job_counts']}",
    "",
    "## Sweep",
    "",
]
for row in rows:
    lines.append(
        f"- job_count={row['job_count']}: processed={row['processed_request_count']}, "
        f"failed={row['failed_job_count']}, avg_bpu={row['avg_bpu_loading']}, "
        f"load_to_run={row['load_to_run_ratio']}, wall_ms_per_request={row['amortized_wall_ms_per_processed_request']}"
    )
lines.extend(["", "## Next Actions", ""])
for item in payload["next_actions"]:
    lines.append(f"- {item}")
lines.extend(["", "## Errors", ""])
lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
lines.extend(["", "## Warnings", ""])
lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- none")
(run_dir / "50pct_service_backlog_sweep_summary_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "50pct_service_backlog_sweep_summary_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
