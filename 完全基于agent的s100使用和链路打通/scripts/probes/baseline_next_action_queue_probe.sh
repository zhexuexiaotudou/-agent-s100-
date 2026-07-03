#!/usr/bin/env bash
set -euo pipefail

workspace="${1:-${OPENCLAW_WORKSPACE_DIR:-/root/.openclaw/workspace}}"
report_dir="${2:-$workspace/reports/baseline-status}"
audit_decision="${3:-${OPENCLAW_AUDIT_DECISION:-continue-non-nas-readonly-only}}"
audit_decision="${audit_decision%$'\r'}"

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

case "$audit_decision" in
  continue|continue-non-nas-readonly-only|continue-nas-backed-baseline|hold-blocked-items) ;;
  *)
    echo "Refusing unknown audit decision: $audit_decision" >&2
    exit 2
    ;;
esac

mkdir -p "$report_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$report_dir/baseline_next_action_queue_$stamp.md"
json="$report_dir/baseline_next_action_queue_$stamp.json"

python3 - "$workspace" "$report" "$json" "$audit_decision" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

workspace = Path(sys.argv[1])
report = Path(sys.argv[2])
json_path = Path(sys.argv[3])
audit_decision = sys.argv[4]


def latest(pattern: str):
    files = sorted(
        workspace.glob(pattern),
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
        reverse=True,
    )
    return files[0] if files else None


def load_json(path):
    if not path:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def latest_text(pattern: str):
    path = latest(pattern)
    if not path:
        return None, ""
    try:
        return path, path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return path, ""


def meta_value(text: str, key: str):
    import re
    match = re.search(rf"^-\s*{re.escape(key)}:\s*(.+)$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else "missing"


def lane_for(item):
    item_id = item.get("id", "")
    status = item.get("status", "")
    next_action = item.get("next_action", "")

    if status == "pass":
        return "done"
    if status == "collecting":
        return "collecting"
    if item_id in infrastructure_ready_ids:
        return "ready_for_infrastructure_action"
    if item_id in {"A-003", "B-001"} or "NAS L2/IP" in next_action or "NAS" in next_action and status == "fail":
        return "blocked_external_link"
    if status == "blocked_runtime":
        return "blocked_external_runtime"
    if item_id in external_input_ready_ids:
        return "ready_for_external_input"
    if status in {"blocked_external_model", "blocked_external_config"}:
        return "blocked_external_input"
    if item_id in review_packet_ready_ids:
        return "ready_for_operator_decision"
    if status in {"blocked_review", "blocked_confirmations", "review"}:
        return "needs_operator_review"
    if status == "missing_evidence":
        return "ready_for_readonly_probe"
    if status == "fail":
        return "blocked_failure_review"
    if status.startswith("blocked"):
        return "blocked_review"
    return "needs_triage"


def allowed_now(lane):
    if audit_decision == "continue-nas-backed-baseline":
        return lane in {"ready_for_readonly_probe", "collecting"}
    if audit_decision == "continue-non-nas-readonly-only":
        return lane in {"ready_for_readonly_probe", "collecting"}
    if audit_decision == "continue":
        return lane in {"ready_for_readonly_probe", "collecting"}
    return False


review_gate_path, review_gate_text = latest_text("reports/review-gates/operator_review_gate_[0-9]*.md")
review_gate_overall = meta_value(review_gate_text, "overall")
review_packet_ready_ids = set()
if review_gate_overall == "review_packets_ready":
    review_packet_ready_ids.update({"A-009", "B-009", "B-010"})

external_input_gate_path, external_input_gate_text = latest_text("reports/external-inputs/external_input_gate_[0-9]*.md")
external_input_gate_overall = meta_value(external_input_gate_text, "overall")
external_input_ready_ids = set()
if external_input_gate_overall == "external_input_packets_ready":
    external_input_ready_ids.update({"B-003", "B-008"})

infrastructure_gate_path, infrastructure_gate_text = latest_text("reports/infrastructure/infrastructure_gate_[0-9]*.md")
infrastructure_gate_overall = meta_value(infrastructure_gate_text, "overall")
infrastructure_ready_ids = set()
if infrastructure_gate_overall == "infrastructure_packets_ready":
    infrastructure_ready_ids.update({"A-003", "A-006", "B-001"})

acceptance_json = latest("reports/baseline-status/baseline_acceptance_[0-9]*.json")
acceptance = load_json(acceptance_json)
items = acceptance.get("items", [])

queue = []
for item in items:
    lane = lane_for(item)
    queue.append(
        {
            "id": item.get("id"),
            "title": item.get("title"),
            "status": item.get("status"),
            "lane": lane,
            "allowed_now": allowed_now(lane),
            "evidence": item.get("evidence"),
            "next_action": item.get("next_action"),
        }
    )

lane_counts = {}
for entry in queue:
    lane_counts[entry["lane"]] = lane_counts.get(entry["lane"], 0) + 1

safe_now = [entry for entry in queue if entry["allowed_now"]]
blocked = [entry for entry in queue if entry["lane"].startswith("blocked")]
reviews = [entry for entry in queue if entry["lane"] == "needs_operator_review"]
ready_operator_decisions = [entry for entry in queue if entry["lane"] == "ready_for_operator_decision"]
ready_external_inputs = [entry for entry in queue if entry["lane"] == "ready_for_external_input"]
ready_infrastructure_actions = [entry for entry in queue if entry["lane"] == "ready_for_infrastructure_action"]

if audit_decision == "continue-non-nas-readonly-only":
    route = (
        "Continue only local/S100P read-only evidence refresh. Do not mount NAS, "
        "write credentials, run control actions, install runtimes, or change services."
    )
elif audit_decision == "continue-nas-backed-baseline":
    route = "NAS-backed baseline refresh is allowed after mount and write validation."
elif audit_decision == "hold-blocked-items":
    route = "Hold baseline-changing work until audit blockers are cleared."
else:
    route = "Continue only actions that match the current audit findings."

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "mode": "read-only next action queue; no system changes executed",
    "workspace": str(workspace),
    "report": str(report),
    "audit_decision": audit_decision,
    "acceptance_json": str(acceptance_json) if acceptance_json else None,
    "overall": acceptance.get("overall", "unknown"),
    "route": route,
    "lane_counts": lane_counts,
    "safe_now_count": len(safe_now),
    "blocked_count": len(blocked),
    "review_count": len(reviews),
    "ready_operator_decision_count": len(ready_operator_decisions),
    "ready_external_input_count": len(ready_external_inputs),
    "ready_infrastructure_action_count": len(ready_infrastructure_actions),
    "operator_review_gate": str(review_gate_path) if review_gate_path else None,
    "operator_review_gate_overall": review_gate_overall,
    "external_input_gate": str(external_input_gate_path) if external_input_gate_path else None,
    "external_input_gate_overall": external_input_gate_overall,
    "infrastructure_gate": str(infrastructure_gate_path) if infrastructure_gate_path else None,
    "infrastructure_gate_overall": infrastructure_gate_overall,
    "queue": queue,
}

json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

with report.open("w", encoding="utf-8") as out:
    out.write("# Baseline Next Action Queue\n\n")
    out.write(f"- generated_at: {payload['generated_at']}\n")
    out.write("- mode: read-only next action queue; no system changes executed\n")
    out.write(f"- audit_decision: {audit_decision}\n")
    out.write(f"- acceptance_json: {payload['acceptance_json'] or 'missing'}\n")
    out.write(f"- operator_review_gate: {payload['operator_review_gate'] or 'missing'}\n")
    out.write(f"- operator_review_gate_overall: {payload['operator_review_gate_overall']}\n")
    out.write(f"- external_input_gate: {payload['external_input_gate'] or 'missing'}\n")
    out.write(f"- external_input_gate_overall: {payload['external_input_gate_overall']}\n")
    out.write(f"- infrastructure_gate: {payload['infrastructure_gate'] or 'missing'}\n")
    out.write(f"- infrastructure_gate_overall: {payload['infrastructure_gate_overall']}\n")
    out.write(f"- overall: {payload['overall']}\n")
    out.write(f"- route: {route}\n\n")

    out.write("## Lane Counts\n\n")
    out.write("| Lane | Count |\n| --- | ---: |\n")
    for lane, count in sorted(lane_counts.items()):
        out.write(f"| {lane} | {count} |\n")

    out.write("\n## Safe Now\n\n")
    if safe_now:
        out.write("| ID | Status | Next action |\n| --- | --- | --- |\n")
        for entry in safe_now:
            out.write(f"| {entry['id']} | {entry['status']} | {entry['next_action']} |\n")
    else:
        out.write("No additional baseline-changing actions are safe under the current audit lane.\n")

    out.write("\n## Ready For Operator Decision\n\n")
    if ready_operator_decisions:
        out.write("| ID | Status | Decision needed |\n| --- | --- | --- |\n")
        for entry in ready_operator_decisions:
            out.write(f"| {entry['id']} | {entry['status']} | {entry['next_action']} |\n")
    else:
        out.write("No operator decision packets are ready.\n")

    out.write("\n## Ready For External Input\n\n")
    if ready_external_inputs:
        out.write("| ID | Status | External input needed |\n| --- | --- | --- |\n")
        for entry in ready_external_inputs:
            out.write(f"| {entry['id']} | {entry['status']} | {entry['next_action']} |\n")
    else:
        out.write("No external input packets are ready.\n")

    out.write("\n## Ready For Infrastructure Action\n\n")
    if ready_infrastructure_actions:
        out.write("| ID | Status | Infrastructure action needed |\n| --- | --- | --- |\n")
        for entry in ready_infrastructure_actions:
            out.write(f"| {entry['id']} | {entry['status']} | {entry['next_action']} |\n")
    else:
        out.write("No infrastructure action packets are ready.\n")

    out.write("\n## Blocked Or Waiting\n\n")
    waiting = [entry for entry in queue if not entry["allowed_now"] and entry["lane"] != "done"]
    if waiting:
        out.write("| ID | Lane | Status | Required action |\n| --- | --- | --- | --- |\n")
        for entry in waiting:
            out.write(f"| {entry['id']} | {entry['lane']} | {entry['status']} | {entry['next_action']} |\n")
    else:
        out.write("No blocked or waiting items.\n")

print(report)
PY
