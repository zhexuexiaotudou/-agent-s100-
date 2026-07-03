#!/usr/bin/env bash
set -euo pipefail

workspace="${1:-${OPENCLAW_WORKSPACE_DIR:-/root/.openclaw/workspace}}"
report_dir="${2:-$workspace/reports/review-gates}"

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
report="$report_dir/operator_review_gate_$stamp.md"
json="$report_dir/operator_review_gate_$stamp.json"

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


def read_json(path):
    if not path:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def meta_value(text: str, key: str):
    match = re.search(rf"^-\s*{re.escape(key)}:\s*(.+)$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else "missing"


def table_value(text: str, label: str):
    match = re.search(rf"\|\s*{re.escape(label)}\s*\|\s*([^|]+?)\s*\|", text)
    return match.group(1).strip() if match else "missing"


def rel(path):
    return str(path) if path else None


rosbag_request = latest("reports/rosbag/rosbag_named_capture_request_[0-9]*.json")
rosbag_policy = latest("logs/probes/rosbag_capture_policy_[0-9]*.md")
rosbag_session = latest("logs/probes/rosbag_session_[0-9]*.md")
rosbag_named = latest("logs/probes/rosbag_named_capture_[0-9]*.md")
control_template = latest("reports/control/control_action_template_[0-9]*.json")
control_policy = latest("logs/probes/control_action_policy_[0-9]*.md")
service_decision = latest("reports/security/service_convergence_decision_[0-9]*.md")
service_template = latest("reports/security/service_confirmation_template_[0-9]*.json")
service_preflight = latest("reports/security/service_execution_preflight_[0-9]*.md")

rosbag_data = read_json(rosbag_request)
control_data = read_json(control_template)
service_data = read_json(service_template)
control_policy_text = read_text(control_policy)
service_preflight_text = read_text(service_preflight)

rosbag_template = rosbag_data.get("request_template", {}) if isinstance(rosbag_data.get("request_template"), dict) else {}
rosbag_topics = rosbag_template.get("topics", []) if isinstance(rosbag_template.get("topics", []), list) else []
rosbag_duration = rosbag_template.get("duration_seconds")
rosbag_approval = rosbag_template.get("requires_operator_approval") is True
rosbag_scope_default = bool(
    isinstance(rosbag_template.get("approval_record"), dict)
    and rosbag_template["approval_record"].get("scope_confirmed") is False
)
rosbag_blockers = []
if not rosbag_request:
    rosbag_blockers.append("missing_named_capture_request_template")
if not rosbag_topics:
    rosbag_blockers.append("no_low_risk_topics_in_request")
if not rosbag_approval:
    rosbag_blockers.append("request_must_require_operator_approval")
if not isinstance(rosbag_duration, int) or rosbag_duration <= 0 or rosbag_duration > 300:
    rosbag_blockers.append("duration_must_be_1_to_300_seconds")
if not rosbag_scope_default:
    rosbag_blockers.append("scope_confirmation_must_default_false")
if rosbag_named:
    rosbag_status = "approved_capture_present"
elif not rosbag_blockers:
    rosbag_status = "ready_for_operator_review"
else:
    rosbag_status = "blocked_review_packet_incomplete"

control_template_obj = control_data.get("template", {}) if isinstance(control_data.get("template"), dict) else {}
control_actions = control_template_obj.get("actions", []) if isinstance(control_template_obj.get("actions", []), list) else []
control_blockers = []
if not control_template:
    control_blockers.append("missing_control_action_template")
if not control_policy:
    control_blockers.append("missing_control_policy_preflight")
if not control_actions:
    control_blockers.append("control_template_has_no_actions")
for idx, action in enumerate(control_actions):
    if not isinstance(action, dict):
        control_blockers.append(f"control_action_{idx}_not_object")
        continue
    action_id = action.get("id", f"actions[{idx}]")
    if action.get("enabled") is not False:
        control_blockers.append(f"{action_id}_must_default_disabled")
    if action.get("requires_approval") is not True:
        control_blockers.append(f"{action_id}_must_require_approval")
    if not action.get("confirm_phrase"):
        control_blockers.append(f"{action_id}_missing_confirm_phrase")
    if action.get("mode") not in {"manual-only", "dry-run"}:
        control_blockers.append(f"{action_id}_mode_must_be_manual_or_dry_run")
control_policy_verdict = table_value(control_policy_text, "Verdict")
control_endpoint_called = meta_value(control_policy_text, "control_endpoint_called")
if control_endpoint_called not in {"no", "missing"}:
    control_blockers.append("control_policy_must_not_call_endpoint")
control_status = "ready_for_operator_review" if not control_blockers else "blocked_review_packet_incomplete"

required_confirmations = {
    "gateway_loopback_only",
    "ssh_management_required",
    "nfs_rpc_client_only",
    "x11vnc_unused",
    "iiod_unused_or_firewall",
}
service_template_obj = service_data.get("template", {}) if isinstance(service_data.get("template"), dict) else {}
service_confirmations = service_template_obj.get("confirmations", {}) if isinstance(service_template_obj.get("confirmations"), dict) else {}
service_policy = service_template_obj.get("execution_policy", {}) if isinstance(service_template_obj.get("execution_policy"), dict) else {}
service_blockers = []
if not service_template:
    service_blockers.append("missing_service_confirmation_template")
if not service_decision:
    service_blockers.append("missing_service_convergence_decision_pack")
if not service_preflight:
    service_blockers.append("missing_service_execution_preflight")
missing_confirmation_keys = sorted(required_confirmations - set(service_confirmations))
for key in missing_confirmation_keys:
    service_blockers.append(f"missing_confirmation_key_{key}")
for key in sorted(required_confirmations & set(service_confirmations)):
    if service_confirmations.get(key) is not False:
        service_blockers.append(f"{key}_must_default_false_in_template")
if service_policy.get("mode") != "preflight-only":
    service_blockers.append("service_execution_mode_must_be_preflight_only")
if service_policy.get("service_changes_allowed") is not False:
    service_blockers.append("service_changes_allowed_must_default_false")
if service_policy.get("firewall_changes_allowed") is not False:
    service_blockers.append("firewall_changes_allowed_must_default_false")
if service_policy.get("rollback_required") is not True:
    service_blockers.append("rollback_required_must_default_true")
service_preflight_verdict = meta_value(service_preflight_text, "verdict")
service_status = "ready_for_confirmation_review" if not service_blockers else "blocked_review_packet_incomplete"

packets = [
    {
        "id": "A-009",
        "name": "ROS bag named capture review",
        "status": rosbag_status,
        "blockers": rosbag_blockers,
        "required_operator_step": "Deliberately approve one bounded named capture request before running rosbag_named_capture_probe.",
        "evidence": {
            "request": rel(rosbag_request),
            "policy": rel(rosbag_policy),
            "selftest_session": rel(rosbag_session),
            "approved_named_capture": rel(rosbag_named),
            "topic_count": len(rosbag_topics),
            "duration_seconds": rosbag_duration,
        },
    },
    {
        "id": "B-009",
        "name": "Low-risk control action review",
        "status": control_status,
        "blockers": control_blockers,
        "required_operator_step": "Review real actions, write runtime allowlist deliberately, and keep approval/audit records before execution.",
        "evidence": {
            "template": rel(control_template),
            "policy_preflight": rel(control_policy),
            "policy_verdict": control_policy_verdict,
            "template_action_count": len(control_actions),
        },
    },
    {
        "id": "B-010",
        "name": "Service convergence confirmation review",
        "status": service_status,
        "blockers": service_blockers,
        "required_operator_step": "Fill runtime confirmations deliberately, then rerun preflight before any service or firewall change.",
        "evidence": {
            "decision_pack": rel(service_decision),
            "confirmation_template": rel(service_template),
            "execution_preflight": rel(service_preflight),
            "preflight_verdict": service_preflight_verdict,
        },
    },
]

missing_packets = [packet for packet in packets if packet["status"].startswith("blocked")]
overall = "review_packets_ready" if not missing_packets else "blocked_review_packets_incomplete"

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "mode": "read-only operator review gate; no runtime config writes and no actions executed",
    "workspace": str(workspace),
    "report": str(report),
    "overall": overall,
    "ready_count": len(packets) - len(missing_packets),
    "blocked_count": len(missing_packets),
    "packets": packets,
    "execution_boundary": [
        "does not start rosbag record",
        "does not write runtime allowlists or confirmation configs",
        "does not call Home Assistant or device control endpoints",
        "does not call systemctl, firewall tools, or package managers",
    ],
}

json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

with report.open("w", encoding="utf-8") as out:
    out.write("# Operator Review Gate\n\n")
    out.write(f"- generated_at: {payload['generated_at']}\n")
    out.write("- mode: read-only operator review gate; no runtime config writes and no actions executed\n")
    out.write(f"- workspace: {workspace}\n")
    out.write(f"- report: {report}\n")
    out.write(f"- json: {json_path}\n")
    out.write(f"- overall: {overall}\n")
    out.write(f"- ready_count: {payload['ready_count']}\n")
    out.write(f"- blocked_count: {payload['blocked_count']}\n\n")

    out.write("## Review Packets\n\n")
    out.write("| ID | Status | Required operator step | Blockers |\n")
    out.write("| --- | --- | --- | --- |\n")
    for packet in packets:
        blockers = ", ".join(packet["blockers"]) if packet["blockers"] else "none"
        out.write(
            f"| {packet['id']} | {packet['status']} | "
            f"{packet['required_operator_step']} | {blockers} |\n"
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
