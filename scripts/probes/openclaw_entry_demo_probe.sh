#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/teacher-demos/openclaw-entry}"

case "$report_root" in
  ""|"/"|"/tmp"|"/mnt"|"/mnt/nas"|"/mnt/nas/openclaw"|"/root"|"/root/.openclaw"|"/root/.openclaw/workspace") ;;
  /tmp/*|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports/*) safe_report_root=1 ;;
  *)
    echo "Refusing report root outside approved demo report directories: $report_root" >&2
    exit 2
    ;;
esac

if [[ "${safe_report_root:-0}" != "1" ]]; then
  echo "Refusing unsafe report root: $report_root" >&2
  exit 2
fi

stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/openclaw_entry_demo_$stamp"
captures_dir="$run_dir/captures"
mkdir -p "$captures_dir"

capture() {
  local name="$1"
  shift
  local out="$captures_dir/$name.txt"
  if "$@" >"$out" 2>&1; then
    printf 'ok:%s' "$out"
  else
    local rc=$?
    printf 'failed:%s:%s' "$rc" "$out"
  fi
}

hostname_capture="$(capture hostname hostname)"
kernel_capture="$(capture uname uname -a)"
identity_capture="$(capture id id)"
ip_capture="$(capture ip_addr ip -br addr)"
route_capture="$(capture ip_route ip route)"
nas_findmnt_capture="$(capture nas_findmnt findmnt /mnt/nas/openclaw)"
nas_mount_capture="$(capture nas_mount sh -c "mount | grep ' /mnt/nas/openclaw '")"
service_capture="$(capture openclaw_gateway_status systemctl --user --no-pager --full status openclaw-gateway)"
service_active_capture="$(capture openclaw_gateway_active systemctl --user is-active openclaw-gateway)"
root_service_capture="$(capture openclaw_gateway_root_status sudo -n env XDG_RUNTIME_DIR=/run/user/0 systemctl --user --no-pager --full status openclaw-gateway)"
root_service_active_capture="$(capture openclaw_gateway_root_active sudo -n env XDG_RUNTIME_DIR=/run/user/0 systemctl --user is-active openclaw-gateway)"
port_capture="$(capture port_18789 sh -c "ss -ltnp 2>/dev/null | grep ':18789 '")"

nas_mounted="false"
if findmnt /mnt/nas/openclaw >/dev/null 2>&1; then
  nas_mounted="true"
fi

nas_writable="false"
if [[ -w /mnt/nas/openclaw ]]; then
  nas_writable="true"
fi

status_probe_report=""
status_probe_status="skipped"
status_probe_script="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/openclaw_status_probe.sh"
if [[ -x "$status_probe_script" || -f "$status_probe_script" ]]; then
  if [[ -w /mnt/nas/openclaw/logs/probes ]]; then
    status_out_dir="/mnt/nas/openclaw/logs/probes"
  else
    status_out_dir="/tmp/openclaw-entry-demo-status"
  fi
  mkdir -p "$status_out_dir"
  status_probe_stdout="$captures_dir/openclaw_status_probe_stdout.txt"
  status_probe_stderr="$captures_dir/openclaw_status_probe_stderr.txt"
  if bash "$status_probe_script" "$status_out_dir" >"$status_probe_stdout" 2>"$status_probe_stderr"; then
    status_probe_status="ok"
    status_probe_report="$(tail -n 1 "$status_probe_stdout" || true)"
  else
    status_probe_status="failed"
  fi
fi

json="$run_dir/openclaw_entry_demo.json"
md="$run_dir/openclaw_entry_demo.md"

export OPENCLAW_ENTRY_DEMO_RUN_DIR="$run_dir"
export OPENCLAW_ENTRY_DEMO_REPORT_ROOT="$report_root"
export OPENCLAW_ENTRY_DEMO_STAMP="$stamp"
export OPENCLAW_ENTRY_DEMO_HOSTNAME_CAPTURE="$hostname_capture"
export OPENCLAW_ENTRY_DEMO_KERNEL_CAPTURE="$kernel_capture"
export OPENCLAW_ENTRY_DEMO_IDENTITY_CAPTURE="$identity_capture"
export OPENCLAW_ENTRY_DEMO_IP_CAPTURE="$ip_capture"
export OPENCLAW_ENTRY_DEMO_ROUTE_CAPTURE="$route_capture"
export OPENCLAW_ENTRY_DEMO_NAS_FINDMNT_CAPTURE="$nas_findmnt_capture"
export OPENCLAW_ENTRY_DEMO_NAS_MOUNT_CAPTURE="$nas_mount_capture"
export OPENCLAW_ENTRY_DEMO_SERVICE_CAPTURE="$service_capture"
export OPENCLAW_ENTRY_DEMO_SERVICE_ACTIVE_CAPTURE="$service_active_capture"
export OPENCLAW_ENTRY_DEMO_ROOT_SERVICE_CAPTURE="$root_service_capture"
export OPENCLAW_ENTRY_DEMO_ROOT_SERVICE_ACTIVE_CAPTURE="$root_service_active_capture"
export OPENCLAW_ENTRY_DEMO_PORT_CAPTURE="$port_capture"
export OPENCLAW_ENTRY_DEMO_NAS_MOUNTED="$nas_mounted"
export OPENCLAW_ENTRY_DEMO_NAS_WRITABLE="$nas_writable"
export OPENCLAW_ENTRY_DEMO_STATUS_PROBE_STATUS="$status_probe_status"
export OPENCLAW_ENTRY_DEMO_STATUS_PROBE_REPORT="$status_probe_report"

python3 - "$json" "$md" <<'PY'
import json
import os
import platform
from datetime import datetime
from pathlib import Path

json_path = Path(os.sys.argv[1])
md_path = Path(os.sys.argv[2])

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_openclaw_entry_demo_probe",
    "demo_id": "openclaw_entry_demo",
    "host": platform.node(),
    "report_root": os.environ["OPENCLAW_ENTRY_DEMO_REPORT_ROOT"],
    "run_dir": os.environ["OPENCLAW_ENTRY_DEMO_RUN_DIR"],
    "claims": {
        "openclaw_runs_on_s100p": "validated_by_openclaw_gateway_status_and_port_capture",
        "pc_high_privilege_required": "not_required_by_demo_procedure",
        "pc_unsafe_writes": "not_required_by_demo_procedure",
        "persistence": "nas_report_root_when_/mnt/nas/openclaw_is_mounted_and_writable",
    },
    "safety_boundary": {
        "system_changes": "no",
        "service_changes": "no",
        "firewall_changes": "no",
        "pc_writes": "no",
        "nas_writes": "bounded_reports_only",
        "secret_capture": "no",
    },
    "recording_script": [
        "Show the PC side using only the normal browser or chat entry, without elevated Windows tools.",
        "Ask OpenClaw to run scripts/run_allowlisted_tool.sh openclaw_entry_demo_probe.",
        "Show the S100P report path under /mnt/nas/openclaw/reports/teacher-demos/openclaw-entry when NAS is mounted.",
        "Open openclaw_entry_demo.md and show gateway status, port capture, and NAS persistence evidence.",
    ],
    "captures": {
        "hostname": os.environ["OPENCLAW_ENTRY_DEMO_HOSTNAME_CAPTURE"],
        "kernel": os.environ["OPENCLAW_ENTRY_DEMO_KERNEL_CAPTURE"],
        "identity": os.environ["OPENCLAW_ENTRY_DEMO_IDENTITY_CAPTURE"],
        "ip_addr": os.environ["OPENCLAW_ENTRY_DEMO_IP_CAPTURE"],
        "ip_route": os.environ["OPENCLAW_ENTRY_DEMO_ROUTE_CAPTURE"],
        "nas_findmnt": os.environ["OPENCLAW_ENTRY_DEMO_NAS_FINDMNT_CAPTURE"],
        "nas_mount": os.environ["OPENCLAW_ENTRY_DEMO_NAS_MOUNT_CAPTURE"],
        "openclaw_gateway_status": os.environ["OPENCLAW_ENTRY_DEMO_SERVICE_CAPTURE"],
        "openclaw_gateway_active": os.environ["OPENCLAW_ENTRY_DEMO_SERVICE_ACTIVE_CAPTURE"],
        "openclaw_gateway_root_status": os.environ["OPENCLAW_ENTRY_DEMO_ROOT_SERVICE_CAPTURE"],
        "openclaw_gateway_root_active": os.environ["OPENCLAW_ENTRY_DEMO_ROOT_SERVICE_ACTIVE_CAPTURE"],
        "port_18789": os.environ["OPENCLAW_ENTRY_DEMO_PORT_CAPTURE"],
    },
    "nas": {
        "mountpoint": "/mnt/nas/openclaw",
        "mounted": os.environ["OPENCLAW_ENTRY_DEMO_NAS_MOUNTED"] == "true",
        "writable": os.environ["OPENCLAW_ENTRY_DEMO_NAS_WRITABLE"] == "true",
    },
    "openclaw_status_probe": {
        "status": os.environ["OPENCLAW_ENTRY_DEMO_STATUS_PROBE_STATUS"],
        "report": os.environ["OPENCLAW_ENTRY_DEMO_STATUS_PROBE_REPORT"],
    },
}

json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# OpenClaw Entry Demo Evidence",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- run_dir: `{payload['run_dir']}`",
    f"- nas_mounted: `{payload['nas']['mounted']}`",
    f"- nas_writable: `{payload['nas']['writable']}`",
    f"- openclaw_status_probe.status: `{payload['openclaw_status_probe']['status']}`",
    f"- openclaw_status_probe.report: `{payload['openclaw_status_probe']['report']}`",
    "",
    "## Demo Claims",
    "",
]
for key, value in payload["claims"].items():
    lines.append(f"- `{key}`: `{value}`")
lines.extend(["", "## Safety Boundary", ""])
for key, value in payload["safety_boundary"].items():
    lines.append(f"- `{key}`: `{value}`")
lines.extend(["", "## Recording Script", ""])
for index, item in enumerate(payload["recording_script"], 1):
    lines.append(f"{index}. {item}")
lines.extend(["", "## Capture Files", ""])
for key, value in payload["captures"].items():
    lines.append(f"- `{key}`: `{value}`")
md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

echo "$md"
