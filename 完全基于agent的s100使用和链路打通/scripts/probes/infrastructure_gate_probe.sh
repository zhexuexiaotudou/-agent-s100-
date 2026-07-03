#!/usr/bin/env bash
set -euo pipefail

workspace="${1:-${OPENCLAW_WORKSPACE_DIR:-/root/.openclaw/workspace}}"
report_dir="${2:-$workspace/reports/infrastructure}"

case "$workspace" in
  /tmp/*|/mnt/nas/openclaw|/mnt/nas/openclaw/*|/root/.openclaw/workspace|/root/.openclaw/workspace/*) ;;
  *)
    echo "Refusing workspace outside approved baseline directories: $workspace" >&2
    exit 2
    ;;
esac

case "$report_dir" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing report directory outside approved report directories: $report_dir" >&2
    exit 2
    ;;
esac

mkdir -p "$report_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$report_dir/infrastructure_gate_$stamp.md"
json="$report_dir/infrastructure_gate_$stamp.json"

python3 - "$workspace" "$report" "$json" <<'PY'
import json
import re
import sys
from datetime import datetime
from pathlib import Path

workspace = Path(sys.argv[1])
report = Path(sys.argv[2])
json_path = Path(sys.argv[3])


def latest(pattern: str):
    files = sorted(
        workspace.glob(pattern),
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
        reverse=True,
    )
    return files[0] if files else None


def read_text(path):
    if not path:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def meta_value(text: str, key: str):
    match = re.search(rf"^-\s*{re.escape(key)}:\s*(.+)$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else "missing"


def table_value(text: str, label: str):
    match = re.search(rf"\|\s*{re.escape(label)}\s*\|\s*([^|]+?)\s*\|", text)
    return match.group(1).strip() if match else "missing"


def rel(path):
    return str(path) if path else None


def has_evidence(path):
    return path is not None and path.exists()


nas_link = latest("logs/probes/nas_link_blocker_[0-9]*.md")
baseline_status = latest("reports/baseline-status/baseline_status_[0-9]*.md")
sandbox_status = latest("logs/probes/sandbox_status_[0-9]*.md")
sandbox_smoke = latest("logs/probes/sandbox_isolation_smoke_[0-9]*.md")

nas_text = read_text(nas_link)
status_text = read_text(baseline_status)
sandbox_text = read_text(sandbox_status)
smoke_text = read_text(sandbox_smoke)

nas_verdict = meta_value(nas_text, "verdict")
nas_mount = table_value(nas_text, "Mount status")
nas_ping = table_value(nas_text, "Ping status")
nas_neighbor = table_value(nas_text, "Neighbor state")
nas_workspace = table_value(status_text, "NAS workspace")

sandbox_runtime_available = meta_value(sandbox_text, "runtime_available")
sandbox_runtime_choice = meta_value(sandbox_text, "runtime_choice")
sandbox_isolation_verdict = meta_value(sandbox_text, "isolation_verdict")
smoke_verdict = meta_value(smoke_text, "verdict")

nas_blockers = []
if not has_evidence(nas_link):
    nas_blockers.append("missing_nas_link_blocker_probe")
if not has_evidence(baseline_status):
    nas_blockers.append("missing_baseline_status_probe")

nas_values = {nas_verdict, nas_mount, nas_ping, nas_neighbor, nas_workspace}
if nas_workspace == "mounted" or nas_mount == "mounted":
    nas_status = "infrastructure_satisfied"
elif nas_blockers:
    nas_status = "blocked_infrastructure_packet_incomplete"
elif nas_ping in {"ok", "reachable"} or nas_neighbor in {"REACHABLE", "STALE", "DELAY", "PROBE"}:
    nas_status = "waiting_for_mount_validation"
elif any(value in {"missing", "unknown", "unreachable", "failed", "not-mounted", "not_mounted"} for value in nas_values):
    nas_status = "waiting_for_nas_link_repair"
else:
    nas_status = "waiting_for_nas_link_repair"

sandbox_blockers = []
if not has_evidence(sandbox_status):
    sandbox_blockers.append("missing_sandbox_status_probe")
if sandbox_runtime_available == "yes" and not has_evidence(sandbox_smoke):
    sandbox_blockers.append("missing_sandbox_isolation_smoke")

if smoke_verdict == "ok_isolated" or sandbox_isolation_verdict in {"pass", "ok"}:
    sandbox_status_value = "infrastructure_satisfied"
elif sandbox_blockers:
    sandbox_status_value = "blocked_infrastructure_packet_incomplete"
elif sandbox_runtime_available == "yes":
    sandbox_status_value = "waiting_for_isolation_smoke"
else:
    sandbox_status_value = "waiting_for_runtime_install_or_scope_decision"

packets = [
    {
        "id": "A-003",
        "name": "NAS workspace mount infrastructure gate",
        "status": nas_status,
        "blockers": nas_blockers,
        "required_infrastructure_action": "Repair NAS L2/IP reachability if needed, then validate mount and write probe deliberately.",
        "evidence": {
            "nas_link_blocker": rel(nas_link),
            "baseline_status": rel(baseline_status),
            "nas_verdict": nas_verdict,
            "mount_status": nas_mount,
            "ping_status": nas_ping,
            "neighbor_state": nas_neighbor,
            "nas_workspace": nas_workspace,
        },
    },
    {
        "id": "A-006",
        "name": "Container runtime and sandbox isolation gate",
        "status": sandbox_status_value,
        "blockers": sandbox_blockers,
        "required_infrastructure_action": "Install or explicitly scope a container runtime, then run bounded isolation smoke with an existing local image.",
        "evidence": {
            "sandbox_status": rel(sandbox_status),
            "sandbox_smoke": rel(sandbox_smoke),
            "runtime_available": sandbox_runtime_available,
            "runtime_choice": sandbox_runtime_choice,
            "isolation_verdict": sandbox_isolation_verdict,
            "smoke_verdict": smoke_verdict,
        },
    },
    {
        "id": "B-001",
        "name": "NAS workspace directory infrastructure gate",
        "status": nas_status,
        "blockers": nas_blockers,
        "required_infrastructure_action": "Use the same NAS mount validation as A-003 before relying on NAS-backed B-track reports.",
        "evidence": {
            "nas_link_blocker": rel(nas_link),
            "baseline_status": rel(baseline_status),
            "nas_verdict": nas_verdict,
            "mount_status": nas_mount,
            "ping_status": nas_ping,
            "neighbor_state": nas_neighbor,
            "nas_workspace": nas_workspace,
        },
    },
]

incomplete = [packet for packet in packets if packet["status"].startswith("blocked")]
overall = "infrastructure_packets_ready" if not incomplete else "blocked_infrastructure_packets_incomplete"
payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "mode": "read-only infrastructure gate; no mount, network, runtime install, service, or firewall changes",
    "workspace": str(workspace),
    "report": str(report),
    "overall": overall,
    "ready_count": len(packets) - len(incomplete),
    "blocked_count": len(incomplete),
    "packets": packets,
    "execution_boundary": [
        "does not use NAS credentials or log in to NAS",
        "does not mount or unmount filesystems",
        "does not change network routes, interfaces, or firewall rules",
        "does not install packages, runtimes, or container images",
        "does not start, stop, enable, or disable services",
    ],
}

json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

with report.open("w", encoding="utf-8") as out:
    out.write("# Infrastructure Gate\n\n")
    out.write(f"- generated_at: {payload['generated_at']}\n")
    out.write("- mode: read-only infrastructure gate; no mount, network, runtime install, service, or firewall changes\n")
    out.write(f"- workspace: {workspace}\n")
    out.write(f"- report: {report}\n")
    out.write(f"- json: {json_path}\n")
    out.write(f"- overall: {overall}\n")
    out.write(f"- ready_count: {payload['ready_count']}\n")
    out.write(f"- blocked_count: {payload['blocked_count']}\n\n")

    out.write("## Infrastructure Packets\n\n")
    out.write("| ID | Status | Required infrastructure action | Blockers |\n")
    out.write("| --- | --- | --- | --- |\n")
    for packet in packets:
        blockers = ", ".join(packet["blockers"]) if packet["blockers"] else "none"
        out.write(
            f"| {packet['id']} | {packet['status']} | "
            f"{packet['required_infrastructure_action']} | {blockers} |\n"
        )

    out.write("\n## Evidence\n\n")
    for packet in packets:
        out.write(f"### {packet['id']} {packet['name']}\n\n")
        out.write("| Evidence | Value |\n| --- | --- |\n")
        for key, value in packet["evidence"].items():
            out.write(f"| {key} | {value if value is not None else 'missing'} |\n")
        out.write("\n")

    out.write("## Execution Boundary\n\n")
    for boundary in payload["execution_boundary"]:
        out.write(f"- {boundary}\n")

print(report)
PY
