#!/usr/bin/env bash
set -euo pipefail

nas_root="${1:-/mnt/nas/openclaw}"
report_dir="${2:-$nas_root/reports/baseline-status}"

case "$nas_root" in
  /mnt/nas/openclaw|/mnt/nas/openclaw/*|/root/.openclaw/workspace|/root/.openclaw/workspace/*|/tmp/*) ;;
  *)
    echo "Refusing NAS/workspace root outside approved paths: $nas_root" >&2
    exit 2
    ;;
esac

case "$report_dir" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing report directory outside approved paths: $report_dir" >&2
    exit 2
    ;;
esac

mkdir -p "$report_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$report_dir/baseline_acceptance_$stamp.md"
json="$report_dir/baseline_acceptance_$stamp.json"

python3 - "$nas_root" "$report" "$json" <<'PY'
import json
import re
import sys
from datetime import datetime
from pathlib import Path

nas_root = Path(sys.argv[1])
report = Path(sys.argv[2])
json_path = Path(sys.argv[3])


def latest(relative_glob):
    files = sorted(
        nas_root.glob(relative_glob),
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
        reverse=True,
    )
    return files[0] if files else None


def read(path):
    if not path:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def table_value(text, label):
    pattern = re.compile(rf"\|\s*{re.escape(label)}\s*\|\s*([^|]+?)\s*\|")
    match = pattern.search(text)
    return match.group(1).strip() if match else "missing"


def meta_value(text, key):
    pattern = re.compile(rf"^-\s*{re.escape(key)}:\s*(.+)$", re.MULTILINE)
    match = pattern.search(text)
    return match.group(1).strip() if match else "missing"


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def exists(path):
    return path is not None and path.exists()


latest_status = latest("reports/baseline-status/baseline_status_*.md")
latest_gap = latest("reports/baseline-status/baseline_gap_decision_*.md")
latest_teacher = latest("reports/teacher/teacher_baseline_briefing_*.md")
latest_stability = latest("reports/stability/stability_summary_*.md")
latest_overnight_summary = latest("reports/baseline-status/overnight_baseline_*_summary.md")
latest_overnight_status = latest("reports/baseline-status/overnight_baseline_*_status.md")
latest_dream = latest("reports/models/dream7b_readiness_*.md")
latest_dream_smoke = latest("reports/models/dream7b_smoke_*.md")
latest_ha = latest("logs/probes/home_assistant_status_*.md")
latest_control = latest("logs/probes/control_action_policy_*.md")
latest_security = latest("logs/probes/security_audit_*.md")
latest_service_decision = latest("reports/security/service_convergence_decision_*.md")
latest_service_preflight = latest("reports/security/service_execution_preflight_*.md")
latest_document_summary = latest("reports/daily-summary/document_daily_summary_*.md")
latest_document_index = latest("reports/document_index_*.md")
latest_log_diagnosis = latest("logs/probes/log_diagnosis_*.md")
latest_experiment = latest("reports/experiments/experiment_report_*.md")
latest_image_caption = latest("reports/image-captions/image_caption_index_*.md")
latest_vision_readiness = latest("reports/image-captions/vision_caption_readiness_*.md")
latest_dataset_card = latest("robot_datasets/*/DATASET_CARD.md")
latest_browser_smoke = latest("reports/browser-smoke/browser_smoke_*.md")
latest_rosbag_session = latest("logs/probes/rosbag_session_*.md")
latest_rosbag_named = latest("logs/probes/rosbag_named_capture_*.md")

status_text = read(latest_status)
stability_text = read(latest_stability)
overnight_status_text = read(latest_overnight_status)
overnight_summary_text = read(latest_overnight_summary)
dream_text = read(latest_dream)
dream_smoke_text = read(latest_dream_smoke)
ha_text = read(latest_ha)
control_text = read(latest_control)
service_preflight_text = read(latest_service_preflight)

gateway_status = table_value(status_text, "OpenClaw Gateway")
nas_status = table_value(status_text, "NAS workspace")
allowlisted_count = table_value(status_text, "Allowlisted tool count")
snapshot_count = table_value(stability_text, "Snapshot count")
elapsed_hours = table_value(stability_text, "Elapsed hours")
stability_verdict = table_value(stability_text, "Verdict")
elapsed = to_float(elapsed_hours)
overnight_process = meta_value(overnight_status_text, "process_status")
overnight_failed = meta_value(overnight_status_text, "failed_event_count")
overnight_iterations = meta_value(overnight_status_text, "completed_iterations_observed")
overnight_summary_verdict = meta_value(overnight_summary_text, "verdict")
dream_verdict = meta_value(dream_text, "verdict")
dream_smoke_verdict = meta_value(dream_smoke_text, "verdict")
ha_verdict = table_value(ha_text, "Verdict")
control_verdict = table_value(control_text, "Verdict")
control_enabled = table_value(control_text, "Enabled action count")
control_executed = table_value(control_text, "Executed records")
service_preflight_verdict = meta_value(service_preflight_text, "verdict")


def item(item_id, title, status, evidence, next_action):
    return {
        "id": item_id,
        "title": title,
        "status": status,
        "evidence": evidence,
        "next_action": next_action,
    }


a010_status = "pass" if elapsed is not None and elapsed >= 168 and stability_verdict.startswith("clean") else "collecting"
a010_next = "Generate final 168h stability acceptance summary." if a010_status == "pass" else "Keep stability sampler and overnight runner collecting until 168h."

items = [
    item("A-001", "S100P hardware/system inventory", "pass", "Hardware and runtime inventory is recorded in baseline tracking and status docs.", "Keep current."),
    item("A-002", "OpenClaw Gateway resident service", "pass" if gateway_status in {"active", "active-listening"} else "fail", f"gateway_status={gateway_status}; evidence={latest_status}", "Restore gateway if inactive."),
    item("A-003", "NAS workspace mounted", "pass" if nas_status == "mounted" else "fail", f"nas_status={nas_status}; evidence={latest_status}", "Restore NFS mount and rerun write test."),
    item("A-004", "WebChat/Feishu smoke", "pass", "Feishu gateway message path previously verified and kept in teacher briefing boundary.", "Keep monitoring gateway logs."),
    item("A-005", "Allowlisted tool execution", "pass" if allowlisted_count not in {"missing", "unknown"} else "fail", f"allowlisted_tools={allowlisted_count}; evidence={latest_status}", "Rerun negative test after plugin changes."),
    item("A-006", "Sandbox/runtime isolation", "blocked_runtime", "Docker/Podman/runc runtime remains unavailable on S100P.", "Install sandbox runtime or explicitly drop from baseline v1."),
    item("A-007", "Browser automation smoke", "pass" if exists(latest_browser_smoke) else "missing_evidence", str(latest_browser_smoke or "missing"), "Rerun browser_smoke_probe if evidence is missing."),
    item("A-008", "ROS2 status tool", "pass", "ROS2 status probe has OpenClaw validation evidence in tracking docs.", "Keep as read-only status probe."),
    item("A-009", "ROS bag capture tool", "pass" if exists(latest_rosbag_named) or exists(latest_rosbag_session) else "missing_evidence", f"session={latest_rosbag_session or 'missing'}; named={latest_rosbag_named or 'missing'}", "Use approved named capture policy for real datasets."),
    item("A-010", "7x24 stability", a010_status, f"snapshots={snapshot_count}; elapsed_hours={elapsed_hours}; verdict={stability_verdict}; overnight={overnight_process}/{overnight_summary_verdict}; failed={overnight_failed}; iterations={overnight_iterations}", a010_next),
    item("B-001", "NAS workspace directory spec", "pass" if nas_status == "mounted" else "fail", f"nas_status={nas_status}", "Restore NAS before relying on B-track reports."),
    item("B-002", "Document index and daily summary", "pass" if exists(latest_document_summary) or exists(latest_document_index) else "missing_evidence", f"document_index={latest_document_index or 'missing'}; daily_summary={latest_document_summary or 'missing'}", "Rerun document index/summary when new docs arrive."),
    item("B-003", "Image caption and Dream 7B readiness", "blocked_external_model" if dream_verdict == "blocked_no_model" or dream_smoke_verdict == "blocked_no_config" else "review", f"image_caption={latest_image_caption or 'missing'}; vision={latest_vision_readiness or 'missing'}; dream={dream_verdict}; smoke={dream_smoke_verdict}", "Provide local model files and dream7b_deployment.json, then run bounded smoke."),
    item("B-004", "Robot dataset card", "pass" if exists(latest_dataset_card) else "missing_evidence", str(latest_dataset_card or "missing"), "Generate card beside each real dataset."),
    item("B-005", "Log analysis assistant", "pass" if exists(latest_log_diagnosis) else "missing_evidence", str(latest_log_diagnosis or "missing"), "Rerun log diagnosis after new failures or power cycles."),
    item("B-006", "GitHub/Codex workflow", "pass", "Remote issue, branch, draft PR, and Codex review evidence recorded in tracking docs.", "Keep PR draft until broader baseline blockers are settled."),
    item("B-007", "Weekly/experiment report generation", "pass" if exists(latest_experiment) else "missing_evidence", str(latest_experiment or "missing"), "Regenerate after real operating data accumulates."),
    item("B-008", "Home Assistant read-only state", "blocked_external_config" if ha_verdict == "blocked_no_config" else ("pass" if ha_verdict == "ok_readonly" else "review"), f"ha_verdict={ha_verdict}; evidence={latest_ha or 'missing'}", "Provide HA URL/token; keep read-only."),
    item("B-009", "Low-risk automation control", "blocked_review" if control_enabled == "0" or control_verdict == "policy_ready_no_execution" else "review", f"control_verdict={control_verdict}; enabled={control_enabled}; executed={control_executed}; evidence={latest_control or 'missing'}", "Add reviewed real actions and approval audit before execution."),
    item("B-010", "Security audit and service convergence", "blocked_confirmations" if service_preflight_verdict == "blocked_no_confirmations" else ("pass" if service_preflight_verdict == "ready_for_manual_execution_review" else "review"), f"security={latest_security or 'missing'}; decision={latest_service_decision or 'missing'}; preflight={service_preflight_verdict}", "Fill service convergence confirmations before any service/firewall change."),
]

status_counts = {}
for entry in items:
    status_counts[entry["status"]] = status_counts.get(entry["status"], 0) + 1

blocking = [entry for entry in items if entry["status"].startswith("blocked") or entry["status"] in {"fail", "missing_evidence", "collecting", "review"}]
overall = "ready" if not blocking else "not_ready"

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "mode": "read-only acceptance gate; no system changes executed",
    "nas_root": str(nas_root),
    "report": str(report),
    "overall": overall,
    "status_counts": status_counts,
    "evidence": {
        "baseline_status": str(latest_status) if latest_status else None,
        "baseline_gap": str(latest_gap) if latest_gap else None,
        "teacher_briefing": str(latest_teacher) if latest_teacher else None,
        "stability": str(latest_stability) if latest_stability else None,
        "overnight_summary": str(latest_overnight_summary) if latest_overnight_summary else None,
    },
    "items": items,
}

json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

with report.open("w", encoding="utf-8") as out:
    out.write("# Baseline Acceptance Gate\n\n")
    out.write(f"- generated_at: {payload['generated_at']}\n")
    out.write("- mode: read-only acceptance gate; no system changes executed\n")
    out.write(f"- nas_root: {nas_root}\n")
    out.write(f"- report: {report}\n")
    out.write(f"- json: {json_path}\n")
    out.write(f"- overall: {overall}\n\n")

    out.write("## Status Counts\n\n")
    out.write("| Status | Count |\n| --- | --- |\n")
    for status, count in sorted(status_counts.items()):
        out.write(f"| {status} | {count} |\n")

    out.write("\n## Gate Matrix\n\n")
    out.write("| ID | Title | Status | Evidence | Next action |\n| --- | --- | --- | --- | --- |\n")
    for entry in items:
        evidence = entry["evidence"].replace("|", "\\|")
        next_action = entry["next_action"].replace("|", "\\|")
        out.write(f"| {entry['id']} | {entry['title']} | {entry['status']} | {evidence} | {next_action} |\n")

    out.write("\n## Not Ready Reasons\n\n")
    if blocking:
        out.write("| ID | Status | Required action |\n| --- | --- | --- |\n")
        for entry in blocking:
            next_action = entry["next_action"].replace("|", "\\|")
            out.write(f"| {entry['id']} | {entry['status']} | {next_action} |\n")
    else:
        out.write("All tracked gates are ready.\n")

    out.write("\n## Evidence Roots\n\n")
    out.write("| Evidence | Path |\n| --- | --- |\n")
    for key, value in payload["evidence"].items():
        out.write(f"| {key} | {value or 'missing'} |\n")

print(report)
PY
