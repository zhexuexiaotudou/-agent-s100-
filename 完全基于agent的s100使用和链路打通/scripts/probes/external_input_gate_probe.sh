#!/usr/bin/env bash
set -euo pipefail

workspace="${1:-${OPENCLAW_WORKSPACE_DIR:-/root/.openclaw/workspace}}"
report_dir="${2:-$workspace/reports/external-inputs}"

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
report="$report_dir/external_input_gate_$stamp.md"
json="$report_dir/external_input_gate_$stamp.json"

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


dream_readiness = latest("reports/models/dream7b_readiness_[0-9]*.md")
dream_template_json = latest("reports/models/dream7b_config_template_[0-9]*.json")
dream_template_md = latest("reports/models/dream7b_config_template_[0-9]*.md")
dream_smoke = latest("reports/models/dream7b_smoke_[0-9]*.md")
ha_template_json = latest("reports/home-assistant/home_assistant_config_template_[0-9]*.json")
ha_template_md = latest("reports/home-assistant/home_assistant_config_template_[0-9]*.md")
ha_status = latest("logs/probes/home_assistant_status_[0-9]*.md")

dream_readiness_text = read_text(dream_readiness)
dream_smoke_text = read_text(dream_smoke)
ha_status_text = read_text(ha_status)
dream_template = read_json(dream_template_json)
ha_template = read_json(ha_template_json)

dream_verdict = meta_value(dream_readiness_text, "verdict")
dream_runtime = table_value(dream_readiness_text, "Runtime summary")
dream_model_files = table_value(dream_readiness_text, "Candidate model-like files")
dream_smoke_verdict = meta_value(dream_smoke_text, "verdict")
dream_target = dream_template.get("target_runtime_config", "missing") if isinstance(dream_template, dict) else "missing"
dream_contract = dream_template.get("read_only_contract", []) if isinstance(dream_template.get("read_only_contract", []), list) else []

dream_blockers = []
if not dream_readiness:
    dream_blockers.append("missing_dream7b_readiness")
if not dream_template_json or not dream_template_md:
    dream_blockers.append("missing_dream7b_config_template")
if not dream_smoke:
    dream_blockers.append("missing_dream7b_smoke_gate")
if dream_target != "/root/.openclaw/workspace/config/dream7b_deployment.json":
    dream_blockers.append("unexpected_dream7b_target_config")
if "does not download model files" not in dream_contract:
    dream_blockers.append("template_must_state_no_model_download")
if dream_verdict == "candidate_runtime_and_model_present" and dream_smoke_verdict == "ok_smoke":
    dream_status = "external_input_satisfied"
elif not dream_blockers:
    dream_status = "waiting_for_model_files_and_runtime_config"
else:
    dream_status = "blocked_external_input_packet_incomplete"

ha_verdict = table_value(ha_status_text, "Verdict")
ha_url_configured = table_value(ha_status_text, "URL configured")
ha_token_configured = table_value(ha_status_text, "Token configured")
ha_target = ha_template.get("target_runtime_config", "missing") if isinstance(ha_template, dict) else "missing"
ha_allowed = ha_template.get("readonly_api_contract", []) if isinstance(ha_template.get("readonly_api_contract", []), list) else []
ha_forbidden = ha_template.get("forbidden_api_contract", []) if isinstance(ha_template.get("forbidden_api_contract", []), list) else []

ha_blockers = []
if not ha_template_json or not ha_template_md:
    ha_blockers.append("missing_home_assistant_config_template")
if not ha_status:
    ha_blockers.append("missing_home_assistant_status_probe")
if ha_target != "/root/.openclaw/workspace/config/home_assistant.env":
    ha_blockers.append("unexpected_home_assistant_target_config")
if "GET /api/" not in ha_allowed or "GET /api/states" not in ha_allowed:
    ha_blockers.append("template_must_allow_only_readonly_gets")
if "POST /api/services/*" not in ha_forbidden:
    ha_blockers.append("template_must_forbid_service_posts")
if ha_verdict == "ok_readonly":
    ha_status_value = "external_input_satisfied"
elif not ha_blockers:
    ha_status_value = "waiting_for_home_assistant_env"
else:
    ha_status_value = "blocked_external_input_packet_incomplete"

packets = [
    {
        "id": "B-003",
        "name": "Dream 7B / local DLM external input gate",
        "status": dream_status,
        "blockers": dream_blockers,
        "required_external_input": "Install or mount approved local model files and deliberately write dream7b_deployment.json, then run bounded smoke.",
        "evidence": {
            "readiness": rel(dream_readiness),
            "readiness_verdict": dream_verdict,
            "runtime_summary": dream_runtime,
            "candidate_model_files": dream_model_files,
            "config_template": rel(dream_template_md),
            "smoke_gate": rel(dream_smoke),
            "smoke_verdict": dream_smoke_verdict,
        },
    },
    {
        "id": "B-008",
        "name": "Home Assistant read-only external input gate",
        "status": ha_status_value,
        "blockers": ha_blockers,
        "required_external_input": "Deliberately write HOME_ASSISTANT_URL and a long-lived token to the approved env file, then rerun read-only status.",
        "evidence": {
            "config_template": rel(ha_template_md),
            "status_probe": rel(ha_status),
            "status_verdict": ha_verdict,
            "url_configured": ha_url_configured,
            "token_configured": ha_token_configured,
        },
    },
]

incomplete = [packet for packet in packets if packet["status"].startswith("blocked")]
overall = "external_input_packets_ready" if not incomplete else "blocked_external_input_packets_incomplete"
payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "mode": "read-only external input gate; no credentials, model downloads, or API control calls",
    "workspace": str(workspace),
    "report": str(report),
    "overall": overall,
    "ready_count": len(packets) - len(incomplete),
    "blocked_count": len(incomplete),
    "packets": packets,
    "execution_boundary": [
        "does not write Home Assistant credentials",
        "does not download, copy, or install model files",
        "does not write Dream 7B runtime config",
        "does not call Home Assistant service/control endpoints",
        "does not run model inference",
    ],
}

json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

with report.open("w", encoding="utf-8") as out:
    out.write("# External Input Gate\n\n")
    out.write(f"- generated_at: {payload['generated_at']}\n")
    out.write("- mode: read-only external input gate; no credentials, model downloads, or API control calls\n")
    out.write(f"- workspace: {workspace}\n")
    out.write(f"- report: {report}\n")
    out.write(f"- json: {json_path}\n")
    out.write(f"- overall: {overall}\n")
    out.write(f"- ready_count: {payload['ready_count']}\n")
    out.write(f"- blocked_count: {payload['blocked_count']}\n\n")

    out.write("## External Input Packets\n\n")
    out.write("| ID | Status | Required external input | Blockers |\n")
    out.write("| --- | --- | --- | --- |\n")
    for packet in packets:
        blockers = ", ".join(packet["blockers"]) if packet["blockers"] else "none"
        out.write(
            f"| {packet['id']} | {packet['status']} | "
            f"{packet['required_external_input']} | {blockers} |\n"
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
