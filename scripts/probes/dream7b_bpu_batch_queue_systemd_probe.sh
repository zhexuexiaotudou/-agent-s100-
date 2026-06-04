#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
service_name="${2:-dream7b-bpu-batch-queue.service}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_batch_queue_systemd_$stamp"
mkdir -p "$run_dir"

service_status="$(systemctl is-active "$service_name" 2>/dev/null || true)"
service_enabled="$(systemctl is-enabled "$service_name" 2>/dev/null || true)"
unit_path="$(systemctl show "$service_name" -p FragmentPath --value 2>/dev/null || true)"
exec_start="$(systemctl show "$service_name" -p ExecStart --value 2>/dev/null || true)"
systemctl --no-pager --full status "$service_name" > "$run_dir/systemctl_status.txt" 2>&1 || true

python3 - "$run_dir" "$service_name" "$service_status" "$service_enabled" "$unit_path" "$exec_start" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
service_name = sys.argv[2]
service_status = sys.argv[3]
service_enabled = sys.argv[4]
unit_path = sys.argv[5]
exec_start = sys.argv[6]
errors = []
if service_status != "active":
    errors.append(f"unexpected service_status: {service_status}")
if service_enabled != "enabled":
    errors.append(f"unexpected service_enabled: {service_enabled}")
if not unit_path.endswith("/dream7b-bpu-batch-queue.service"):
    errors.append(f"unexpected unit_path: {unit_path}")
for text in ("dream7b-bpu-batch-queue-service", "/mnt/nas/openclaw/queues/dream7b-bpu", "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd", "/run/lock/dream7b_bpu_batch_queue_runner.lock", "--drain-all"):
    if text not in exec_start:
        errors.append(f"ExecStart missing {text}: {exec_start}")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_batch_queue_systemd_probe" if not errors else "failed_dream7b_bpu_batch_queue_systemd_probe",
    "service_name": service_name,
    "service_status": service_status,
    "service_enabled": service_enabled,
    "unit_path": unit_path,
    "exec_start": exec_start,
    "drain_all_required": True,
    "errors": errors,
}
error_lines = [f"- {item}" for item in errors] if errors else ["- none"]
(run_dir / "systemd_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(run_dir / "systemd_probe.md").write_text(
    "\n".join([
        "# Dream 7B BPU Batch Queue Systemd Probe",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- service_name: {payload['service_name']}",
        f"- service_status: {payload['service_status']}",
        f"- service_enabled: {payload['service_enabled']}",
        f"- unit_path: {payload['unit_path']}",
        f"- exec_start: {payload['exec_start']}",
        f"- drain_all_required: {payload['drain_all_required']}",
        "",
        "## Errors",
        "",
        *error_lines,
        "",
    ]) + "\n",
    encoding="utf-8",
)
print(run_dir / "systemd_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
