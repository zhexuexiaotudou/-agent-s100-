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
report="$report_dir/baseline_gap_decision_$stamp.md"

python3 - "$nas_root" "$report" <<'PY'
import re
import sys
from datetime import datetime
from pathlib import Path

nas_root = Path(sys.argv[1])
report = Path(sys.argv[2])

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

def float_value(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

latest_stability = latest("reports/stability/stability_summary_*.md")
latest_baseline = latest("reports/baseline-status/baseline_status_*.md")
latest_overnight_status = latest("reports/baseline-status/overnight_baseline_*_status.md")
latest_overnight_summary = latest("reports/baseline-status/overnight_baseline_*_summary.md")
latest_dream = latest("reports/models/dream7b_readiness_*.md")
latest_ha = latest("logs/probes/home_assistant_status_*.md")
latest_control = latest("logs/probes/control_action_policy_*.md")
latest_service_decision = latest("reports/security/service_convergence_decision_*.md")
latest_security = latest("logs/probes/security_audit_*.md")

stability_text = read(latest_stability)
baseline_text = read(latest_baseline)
overnight_status_text = read(latest_overnight_status)
overnight_summary_text = read(latest_overnight_summary)
dream_text = read(latest_dream)
ha_text = read(latest_ha)
control_text = read(latest_control)
service_text = read(latest_service_decision)

snapshot_count = table_value(stability_text, "Snapshot count")
elapsed_hours = table_value(stability_text, "Elapsed hours")
stability_verdict = table_value(stability_text, "Verdict")
gateway_status = table_value(baseline_text, "OpenClaw Gateway")
nas_status = table_value(baseline_text, "NAS workspace")
allowlisted_count = table_value(baseline_text, "Allowlisted tool count")

overnight_process = meta_value(overnight_status_text, "process_status")
overnight_failed = meta_value(overnight_status_text, "failed_event_count")
overnight_iterations = meta_value(overnight_status_text, "completed_iterations_observed")
overnight_next = meta_value(overnight_status_text, "next_iteration_after")
overnight_summary_verdict = meta_value(overnight_summary_text, "verdict")

dream_verdict = meta_value(dream_text, "verdict")
dream_runtime = table_value(dream_text, "Runtime summary")
dream_model_count = table_value(dream_text, "Candidate model-like files")
dream_memory = table_value(dream_text, "Memory total GiB")

ha_verdict = table_value(ha_text, "Verdict")
ha_url = table_value(ha_text, "URL configured")
ha_token = table_value(ha_text, "Token configured")
ha_entities = table_value(ha_text, "Entity count")

control_verdict = table_value(control_text, "Verdict")
control_actions = table_value(control_text, "Action count")
control_enabled = table_value(control_text, "Enabled action count")
control_executed = table_value(control_text, "Executed records")

elapsed = float_value(elapsed_hours)
if elapsed is None:
    a010_decision = "review_missing_elapsed"
elif elapsed >= 168 and stability_verdict == "clean_168h":
    a010_decision = "ready_for_acceptance_review"
elif elapsed >= 168:
    a010_decision = "review_168h_summary"
else:
    a010_decision = "continue_collecting"

if dream_verdict == "candidate_runtime_and_model_present":
    b003_decision = "run_bounded_local_inference_smoke"
elif dream_verdict == "blocked_no_model":
    b003_decision = "external_model_files_required"
elif dream_verdict == "blocked_no_runtime":
    b003_decision = "runtime_install_required"
else:
    b003_decision = "review_dream_readiness"

if ha_verdict == "ok_readonly":
    b008_decision = "readonly_state_verified"
elif ha_verdict == "blocked_no_config":
    b008_decision = "external_ha_url_token_required"
elif ha_verdict in {"blocked_auth", "blocked_connectivity"}:
    b008_decision = "fix_ha_connectivity_or_auth"
else:
    b008_decision = "rerun_ha_preflight"

if control_verdict == "policy_ready_no_execution" and control_enabled == "0":
    b009_decision = "external_reviewed_action_required"
elif control_verdict == "policy_ready_no_execution":
    b009_decision = "review_enabled_actions_before_execution"
else:
    b009_decision = "fix_control_policy"

b010_decision = "operator_service_confirmation_required" if latest_service_decision else "rerun_service_decision_pack"

automation_safe = [
    ("A-010", "continue sampler and overnight runner; refresh summaries", a010_decision),
    ("B-005/B-007", "rerun log diagnosis and experiment report after new real data arrives", "safe_when_data_exists"),
    ("B-010", "rerun security audit and service decision pack read-only", "safe_readonly"),
]

external_inputs = [
    ("B-003", "Dream 7B/model files or explicit decision to keep local DLM out of baseline v1", b003_decision),
    ("B-008", "Home Assistant URL and long-lived token", b008_decision),
    ("B-009", "reviewed low-risk action allowlist plus approval wording", b009_decision),
    ("B-010", "operator confirmation for NFS/RPC, x11vnc, and iiod decisions", b010_decision),
]

report.parent.mkdir(parents=True, exist_ok=True)
with report.open("w", encoding="utf-8") as out:
    out.write("# Baseline Gap Decision Report\n\n")
    out.write(f"- generated_at: {datetime.now().astimezone().isoformat()}\n")
    out.write(f"- mode: read-only decision summary; no system changes executed\n")
    out.write(f"- nas_root: {nas_root}\n")
    out.write(f"- report: {report}\n\n")

    out.write("## Current Evidence\n\n")
    out.write("| Area | Latest evidence | Key status |\n| --- | --- | --- |\n")
    out.write(f"| A-010 stability | {latest_stability or 'missing'} | snapshots={snapshot_count}; elapsed_hours={elapsed_hours}; verdict={stability_verdict} |\n")
    out.write(f"| Overnight runner | {latest_overnight_status or 'missing'} | process={overnight_process}; iterations={overnight_iterations}; failed={overnight_failed}; next={overnight_next}; last_summary={overnight_summary_verdict} |\n")
    out.write(f"| Baseline roll-up | {latest_baseline or 'missing'} | gateway={gateway_status}; NAS={nas_status}; allowlisted_tools={allowlisted_count} |\n")
    out.write(f"| Dream 7B readiness | {latest_dream or 'missing'} | verdict={dream_verdict}; runtime={dream_runtime}; model_files={dream_model_count}; memory={dream_memory} GiB |\n")
    out.write(f"| Home Assistant | {latest_ha or 'missing'} | verdict={ha_verdict}; URL={ha_url}; token={ha_token}; entities={ha_entities} |\n")
    out.write(f"| Control policy | {latest_control or 'missing'} | verdict={control_verdict}; actions={control_actions}; enabled={control_enabled}; executed={control_executed} |\n")
    out.write(f"| Service convergence | {latest_service_decision or 'missing'} | decision_pack={'present' if latest_service_decision else 'missing'} |\n")
    out.write(f"| Security audit | {latest_security or 'missing'} | audit={'present' if latest_security else 'missing'} |\n\n")

    out.write("## Automation-Safe Next Actions\n\n")
    out.write("| ID | Action | Classification |\n| --- | --- | --- |\n")
    for item_id, action, classification in automation_safe:
        out.write(f"| {item_id} | {action} | {classification} |\n")

    out.write("\n## External Inputs Or Decisions Required\n\n")
    out.write("| ID | Required input or decision | Classification |\n| --- | --- | --- |\n")
    for item_id, required, classification in external_inputs:
        out.write(f"| {item_id} | {required} | {classification} |\n")

    out.write("\n## Practical Next Workflow\n\n")
    out.write("1. Keep A-010 collection running until at least 168 elapsed hours.\n")
    out.write("2. Treat Dream 7B as not deployed until model files are mounted or installed and a bounded local inference smoke test passes.\n")
    out.write("3. Keep B-008 read-only until Home Assistant URL/token are provided.\n")
    out.write("4. Keep B-009 execution disabled until a reviewed action and explicit approval audit exist.\n")
    out.write("5. Do not disable services or change firewall rules until B-010 operator confirmations are complete.\n")

PY

echo "$report"
