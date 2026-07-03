#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
telemetry_json="${DREAM7B_BPU_50PCT_CANDIDATE_TELEMETRY_JSON:-}"
deployment_acceptance_json="${DREAM7B_BPU_50PCT_CANDIDATE_DEPLOYMENT_ACCEPTANCE_JSON:-}"
default_deployable_json="${DREAM7B_BPU_50PCT_CANDIDATE_DEFAULT_DEPLOYABLE_JSON:-}"
min_avg_bpu="${DREAM7B_BPU_50PCT_CANDIDATE_MIN_AVG_BPU:-50.0}"
min_processed="${DREAM7B_BPU_50PCT_CANDIDATE_MIN_PROCESSED:-192}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_50pct_candidate_acceptance_$stamp"
mkdir -p "$run_dir"

python3 - \
  "$run_dir" \
  "$report_root" \
  "$telemetry_json" \
  "$deployment_acceptance_json" \
  "$default_deployable_json" \
  "$min_avg_bpu" \
  "$min_processed" <<'PY'
import glob
import json
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
report_root = Path(sys.argv[2])
telemetry_json = sys.argv[3]
deployment_acceptance_json = sys.argv[4]
default_deployable_json = sys.argv[5]
min_avg_bpu = float(sys.argv[6])
min_processed = int(sys.argv[7])


def latest(pattern: str) -> Path:
    paths = sorted(Path(item) for item in glob.glob(pattern) if Path(item).is_file())
    if not paths:
        raise FileNotFoundError(pattern)
    return paths[-1]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


if telemetry_json:
    telemetry_path = Path(telemetry_json)
else:
    telemetry_path = latest(str(report_root / "dream7b_bpu_selected_pair_cross_job_queue_telemetry_*" / "cross_job_queue_telemetry_probe.json"))

if deployment_acceptance_json:
    deployment_path = Path(deployment_acceptance_json)
else:
    deployment_path = latest(str(report_root / "dream7b_bpu_deployment_acceptance_*" / "deployment_acceptance_probe.json"))

if default_deployable_json:
    default_path = Path(default_deployable_json)
else:
    default_path = latest(str(report_root / "dream7b_bpu_default_deployable_acceptance_*" / "default_deployable_acceptance_probe.json"))

telemetry = load(telemetry_path)
deployment = load(deployment_path)
default_deployable = load(default_path)

errors = []
warnings = []

processed = int(telemetry.get("processed_request_count") or 0)
failed = int(telemetry.get("failed_job_count") or 0)
avg_bpu = float(telemetry.get("avg_bpu_loading") or 0.0)
load_to_run = telemetry.get("load_to_run_ratio")
job_count = int(telemetry.get("job_count") or 0)
request_count = int(telemetry.get("request_count") or 0)

if telemetry.get("verdict") != "ok_dream7b_bpu_selected_pair_cross_job_queue_telemetry_probe":
    errors.append(f"unexpected telemetry verdict: {telemetry.get('verdict')}")
if processed < min_processed:
    errors.append(f"processed_request_count below target: {processed} < {min_processed}")
if failed != 0:
    errors.append(f"failed_job_count is nonzero: {failed}")
if avg_bpu < min_avg_bpu:
    errors.append(f"avg_bpu_loading below target: {avg_bpu} < {min_avg_bpu}")
if deployment.get("verdict") != "ok_dream7b_bpu_deployment_acceptance_probe":
    errors.append(f"unexpected deployment acceptance verdict: {deployment.get('verdict')}")
if int(deployment.get("passed_check_count") or 0) != int(deployment.get("check_count") or -1):
    errors.append(
        f"deployment acceptance did not pass all checks: "
        f"{deployment.get('passed_check_count')} / {deployment.get('check_count')}"
    )

default_ready = bool(default_deployable.get("default_deployable_ready"))
default_status = default_deployable.get("default_deployable_status")
candidate_only = not default_ready and default_status == "blocked_candidate_only"
if default_ready:
    rollback_status = "default_ready"
elif candidate_only:
    rollback_status = "rollback_safe_candidate_only"
else:
    rollback_status = f"default_status_{default_status}"
    warnings.append(f"default deployable status is neither ready nor known candidate-only: {default_status}")

candidate_command = (
    "DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_JOB_COUNT=2 "
    "DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_REQUEST_COUNT=192 "
    "DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_REQUEST_COUNT_LIMIT=256 "
    "DREAM7B_BPU_CROSS_JOB_QUEUE_TELEMETRY_FORWARD_PROBE_CMD='bash scripts/probes/dream7b_bpu_selected_pair_forward_path_probe.sh' "
    "bash scripts/probes/dream7b_bpu_selected_pair_cross_job_queue_telemetry_probe.sh /mnt/nas/openclaw/reports/models"
)

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_50pct_candidate_acceptance_probe" if not errors else "failed_dream7b_bpu_50pct_candidate_acceptance_probe",
    "run_dir": str(run_dir),
    "telemetry_json": str(telemetry_path),
    "deployment_acceptance_json": str(deployment_path),
    "default_deployable_json": str(default_path),
    "candidate_command": candidate_command,
    "candidate_scope": "selected-pair cross-job queue telemetry candidate; default service not replaced",
    "rollback_status": rollback_status,
    "default_service_replaced": False,
    "min_avg_bpu": min_avg_bpu,
    "min_processed": min_processed,
    "job_count": job_count,
    "request_count": request_count,
    "processed_request_count": processed,
    "failed_job_count": failed,
    "avg_bpu_loading": avg_bpu,
    "max_bpu_loading": telemetry.get("max_bpu_loading"),
    "load_to_run_ratio": load_to_run,
    "amortized_wall_ms_per_processed_request": telemetry.get("amortized_wall_ms_per_processed_request"),
    "deployment_acceptance_verdict": deployment.get("verdict"),
    "deployment_acceptance_check_count": deployment.get("check_count"),
    "deployment_acceptance_passed_check_count": deployment.get("passed_check_count"),
    "default_deployable_ready": default_ready,
    "default_deployable_status": default_status,
    "warnings": warnings,
    "errors": errors,
}
(run_dir / "50pct_candidate_acceptance_probe.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
lines = [
    "# Dream 7B 50 Percent Candidate Acceptance Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- telemetry_json: {payload['telemetry_json']}",
    f"- processed_request_count: {processed}",
    f"- failed_job_count: {failed}",
    f"- avg_bpu_loading: {avg_bpu}",
    f"- load_to_run_ratio: {load_to_run}",
    f"- rollback_status: {rollback_status}",
    f"- default_service_replaced: {payload['default_service_replaced']}",
    f"- deployment_acceptance: {payload['deployment_acceptance_passed_check_count']} / {payload['deployment_acceptance_check_count']}",
    "",
    "## Errors",
    "",
]
lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
lines.extend(["", "## Warnings", ""])
lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- none")
(run_dir / "50pct_candidate_acceptance_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "50pct_candidate_acceptance_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
