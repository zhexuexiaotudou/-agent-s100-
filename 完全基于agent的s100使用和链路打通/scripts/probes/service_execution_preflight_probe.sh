#!/usr/bin/env bash
set -euo pipefail

out_dir="${1:-/mnt/nas/openclaw/reports/security}"
config_file="${2:-/root/.openclaw/workspace/config/service_convergence_confirmations.json}"

case "$out_dir" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $out_dir" >&2
    exit 2
    ;;
esac

case "$config_file" in
  /root/.openclaw/workspace/config/service_convergence_confirmations.json|/mnt/nas/openclaw/config/service_convergence_confirmations.json|/tmp/service_convergence_confirmations.json) ;;
  *)
    echo "Refusing confirmation config outside approved paths: $config_file" >&2
    exit 2
    ;;
esac

mkdir -p "$out_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$out_dir/service_execution_preflight_$stamp.md"

listener_snapshot="$(ss -ltnp 2>/dev/null || true)"
running_services="$(systemctl --no-pager --plain --type=service --state=running 2>/dev/null || true)"

python3 - "$config_file" "$report" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

config_path = Path(sys.argv[1])
report_path = Path(sys.argv[2])

required = [
    "gateway_loopback_only",
    "ssh_management_required",
    "nfs_rpc_client_only",
    "x11vnc_unused",
    "iiod_unused_or_firewall",
]

status = {
    "config_status": "missing",
    "policy_state": "missing",
    "operator_name": "",
    "confirmed_at": "",
    "mode": "missing",
    "service_changes_allowed": False,
    "firewall_changes_allowed": False,
    "rollback_required": False,
    "confirmations": {key: False for key in required},
    "errors": [],
}

if config_path.exists():
    status["config_status"] = "present"
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        status["policy_state"] = str(data.get("policy_state", "missing"))
        operator = data.get("operator", {}) if isinstance(data.get("operator", {}), dict) else {}
        policy = data.get("execution_policy", {}) if isinstance(data.get("execution_policy", {}), dict) else {}
        confirmations = data.get("confirmations", {}) if isinstance(data.get("confirmations", {}), dict) else {}
        status["operator_name"] = str(operator.get("name", ""))
        status["confirmed_at"] = str(operator.get("confirmed_at", ""))
        status["mode"] = str(policy.get("mode", "missing"))
        status["service_changes_allowed"] = policy.get("service_changes_allowed") is True
        status["firewall_changes_allowed"] = policy.get("firewall_changes_allowed") is True
        status["rollback_required"] = policy.get("rollback_required") is True
        for key in required:
            status["confirmations"][key] = confirmations.get(key) is True
        if data.get("version") != 1:
            status["errors"].append("version must be 1")
        if status["policy_state"] not in {"reviewed", "confirmed"}:
            status["errors"].append("policy_state must be reviewed or confirmed")
        if status["mode"] != "preflight-only":
            status["errors"].append("mode must remain preflight-only in this probe")
        if not status["rollback_required"]:
            status["errors"].append("rollback_required must be true")
    except Exception as exc:
        status["errors"].append(f"invalid JSON: {exc}")

missing = [key for key, value in status["confirmations"].items() if not value]
if status["config_status"] == "missing":
    verdict = "blocked_no_confirmations"
elif status["errors"]:
    verdict = "blocked_invalid_confirmations"
elif missing:
    verdict = "blocked_incomplete_confirmations"
elif status["service_changes_allowed"] or status["firewall_changes_allowed"]:
    verdict = "blocked_execution_flags_set"
else:
    verdict = "ready_for_manual_execution_review"

with report_path.open("w", encoding="utf-8") as out:
    out.write("# B-010 Service Execution Preflight\n\n")
    out.write(f"- generated_at: {datetime.now().astimezone().isoformat()}\n")
    out.write("- mode: read-only preflight; no service or firewall changes executed\n")
    out.write(f"- report: {report_path}\n")
    out.write(f"- confirmation_config: {config_path}\n")
    out.write(f"- verdict: {verdict}\n\n")

    out.write("## Confirmation Config\n\n")
    out.write("| Check | Value |\n| --- | --- |\n")
    out.write(f"| Config status | {status['config_status']} |\n")
    out.write(f"| Policy state | {status['policy_state']} |\n")
    out.write(f"| Operator name present | {'yes' if status['operator_name'] else 'no'} |\n")
    out.write(f"| Confirmed at present | {'yes' if status['confirmed_at'] else 'no'} |\n")
    out.write(f"| Execution mode | {status['mode']} |\n")
    out.write(f"| Service changes allowed flag | {str(status['service_changes_allowed']).lower()} |\n")
    out.write(f"| Firewall changes allowed flag | {str(status['firewall_changes_allowed']).lower()} |\n")
    out.write(f"| Rollback required | {str(status['rollback_required']).lower()} |\n")
    out.write(f"| Missing confirmations | {', '.join(missing) if missing else 'none'} |\n")
    out.write(f"| Config errors | {'; '.join(status['errors']) if status['errors'] else 'none'} |\n\n")

    out.write("## Required Confirmations\n\n")
    out.write("| Confirmation | Value |\n| --- | --- |\n")
    for key in required:
        out.write(f"| {key} | {str(status['confirmations'][key]).lower()} |\n")

    out.write("\n## Execution Boundary\n\n")
    out.write("- This probe never calls `systemctl disable`, `systemctl stop`, firewall tools, or package managers.\n")
    out.write("- `ready_for_manual_execution_review` means the confirmation gate is complete enough to review commands manually.\n")
    out.write("- It is not itself approval to execute service or firewall changes.\n")

    out.write("\n## Candidate Manual Commands After Review\n\n")
    out.write("```bash\n")
    out.write("# Only after confirmations are reviewed outside this probe.\n")
    out.write("sudo systemctl disable --now nfs-server nfs-mountd rpcbind rpc-statd rpc-statd-notify || true\n")
    out.write("sudo systemctl disable --now x11vnc || true\n")
    out.write("sudo systemctl disable --now iiod || true\n")
    out.write("```\n")

    out.write("\n## Rollback Commands Required For Any Manual Execution\n\n")
    out.write("```bash\n")
    out.write("sudo systemctl enable --now nfs-server nfs-mountd rpcbind rpc-statd rpc-statd-notify || true\n")
    out.write("sudo systemctl enable --now x11vnc || true\n")
    out.write("sudo systemctl enable --now iiod || true\n")
    out.write("```\n")

PY

{
  echo
  echo "## Current Listener Snapshot"
  echo
  echo '```text'
  printf '%s\n' "$listener_snapshot"
  echo '```'
  echo
  echo "## Current Relevant Services"
  echo
  echo '```text'
  printf '%s\n' "$running_services" | grep -Ei 'openclaw|ssh|nfs|rpc|x11vnc|iiod' || true
  echo '```'
} >> "$report"

echo "$report"
