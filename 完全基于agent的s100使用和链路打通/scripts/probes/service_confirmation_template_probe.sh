#!/usr/bin/env bash
set -euo pipefail

report_dir="${1:-/mnt/nas/openclaw/reports/security}"

case "$report_dir" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_dir" >&2
    exit 2
    ;;
esac

mkdir -p "$report_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$report_dir/service_confirmation_template_$stamp.md"
json="$report_dir/service_confirmation_template_$stamp.json"

listener_snapshot="$(ss -ltnp 2>/dev/null || true)"
running_services="$(systemctl --no-pager --plain --type=service --state=running 2>/dev/null || true)"

has_listener() {
  local pattern="$1"
  printf '%s\n' "$listener_snapshot" | grep -Eiq "$pattern" && echo yes || echo no
}

has_service() {
  local pattern="$1"
  printf '%s\n' "$running_services" | grep -Eiq "$pattern" && echo yes || echo no
}

gateway_loopback="no"
if printf '%s\n' "$listener_snapshot" | grep -Eq '127\.0\.0\.1:18789|\[::1\]:18789'; then
  gateway_loopback="yes"
fi

ssh_present="$(has_service '^ssh\.service| ssh\.service')"
nfs_rpc_present="$(has_service 'nfs|rpcbind|rpc-statd|rpc-statd-notify|nfs-mountd')"
x11vnc_present="$(has_service 'x11vnc')"
vnc_listening="$(has_listener '(:5900|x11vnc)')"
iiod_present="$(has_service 'iiod')"
iiod_listening="$(has_listener '(:30431|iiod)')"

python3 - "$json" "$stamp" "$gateway_loopback" "$ssh_present" "$nfs_rpc_present" "$x11vnc_present" "$vnc_listening" "$iiod_present" "$iiod_listening" <<'PY'
import json
import sys
from datetime import datetime

(
    json_path,
    stamp,
    gateway_loopback,
    ssh_present,
    nfs_rpc_present,
    x11vnc_present,
    vnc_listening,
    iiod_present,
    iiod_listening,
) = sys.argv[1:]

payload = {
    "version": 1,
    "generated_at": datetime.now().astimezone().isoformat(),
    "stamp": stamp,
    "mode": "read-only template artifact; not an execution config",
    "target_runtime_config": "/root/.openclaw/workspace/config/service_convergence_confirmations.json",
    "signals": {
        "gateway_loopback": gateway_loopback,
        "ssh_present": ssh_present,
        "nfs_rpc_present": nfs_rpc_present,
        "x11vnc_present": x11vnc_present,
        "vnc_listening": vnc_listening,
        "iiod_present": iiod_present,
        "iiod_listening": iiod_listening,
    },
    "template": {
        "version": 1,
        "policy_state": "draft_template",
        "description": "Draft B-010 confirmation config. Copy only after review; set each confirmation deliberately.",
        "confirmations": {
            "gateway_loopback_only": False,
            "ssh_management_required": False,
            "nfs_rpc_client_only": False,
            "x11vnc_unused": False,
            "iiod_unused_or_firewall": False,
        },
        "operator": {
            "name": "",
            "confirmed_at": "",
            "notes": "Do not use this draft as approval. Fill after reviewing the current service decision pack.",
        },
        "execution_policy": {
            "mode": "preflight-only",
            "service_changes_allowed": False,
            "firewall_changes_allowed": False,
            "rollback_required": True,
        },
    },
}

with open(json_path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
PY

{
  echo "# B-010 Service Confirmation Template"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- mode: read-only template artifact; not an execution config"
  echo "- report: $report"
  echo "- json: $json"
  echo "- target_runtime_config: /root/.openclaw/workspace/config/service_convergence_confirmations.json"
  echo
  echo "## Current Signals"
  echo
  echo "| Signal | Value |"
  echo "| --- | --- |"
  echo "| gateway_loopback | $gateway_loopback |"
  echo "| ssh_present | $ssh_present |"
  echo "| nfs_rpc_present | $nfs_rpc_present |"
  echo "| x11vnc_present | $x11vnc_present |"
  echo "| vnc_listening | $vnc_listening |"
  echo "| iiod_present | $iiod_present |"
  echo "| iiod_listening | $iiod_listening |"
  echo
  echo "## Required Confirmations"
  echo
  echo "| Confirmation | Default | Reason |"
  echo "| --- | --- | --- |"
  echo "| gateway_loopback_only | false | Confirm Gateway is loopback-only in the latest security audit. |"
  echo "| ssh_management_required | false | Confirm SSH is required for board administration before any service narrowing. |"
  echo "| nfs_rpc_client_only | false | Confirm S100P is not exporting NFS shares to other hosts. |"
  echo "| x11vnc_unused | false | Confirm no VNC desktop workflow is required. |"
  echo "| iiod_unused_or_firewall | false | Confirm IIO hardware tooling does not need public listener exposure. |"
  echo
  echo "## Draft Runtime Config"
  echo
  echo "This is intentionally not written to the runtime config path."
  echo
  echo '```json'
  python3 - "$json" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as fh:
    print(json.dumps(json.load(fh)["template"], ensure_ascii=False, indent=2))
PY
  echo '```'
  echo
  echo "## Boundary"
  echo
  echo "- This probe does not call systemctl, firewall tools, package managers, or copy files into config."
  echo "- B-010 remains blocked until the runtime confirmation config is deliberately reviewed and filled."
  echo "- Even a complete confirmation config only moves the gate to manual execution review; it does not execute changes."
} > "$report"

echo "$report"
