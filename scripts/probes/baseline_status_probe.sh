#!/usr/bin/env bash
set -euo pipefail

workspace="${1:-/root/.openclaw/workspace}"
report_dir="${2:-/root/.openclaw/workspace/reports/baseline-status}"

case "$workspace" in
  /root/.openclaw/workspace|/root/.openclaw/workspace/*|/mnt/nas/openclaw|/mnt/nas/openclaw/*) ;;
  *)
    echo "Refusing workspace outside approved baseline directories: $workspace" >&2
    exit 2
    ;;
esac

case "$report_dir" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_dir" >&2
    exit 2
    ;;
esac

mkdir -p "$report_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$report_dir/baseline_status_$stamp.md"

count_files() {
  local pattern="$1"
  find "$workspace" -path "$pattern" -type f 2>/dev/null | wc -l | tr -d ' '
}

latest_file() {
  local pattern="$1"
  find "$workspace" -path "$pattern" -type f -printf '%T@ %p\n' 2>/dev/null \
    | sort -nr \
    | awk 'NR==1 {$1=""; sub(/^ /, ""); print}'
}

tool_count="unknown"
tool_ids=""
tool_allowlist="$workspace/scripts/tool_allowlist.json"
if [[ ! -f "$tool_allowlist" && -f /root/.openclaw/workspace/scripts/tool_allowlist.json ]]; then
  tool_allowlist="/root/.openclaw/workspace/scripts/tool_allowlist.json"
fi
if [[ -f "$tool_allowlist" ]]; then
  tool_count="$(python3 - "$tool_allowlist" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as fh:
    data = json.load(fh)
tools = data.get("tools", [])
print(len(tools))
PY
)"
  tool_ids="$(python3 - "$tool_allowlist" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as fh:
    data = json.load(fh)
for tool in data.get("tools", []):
    print(tool.get("id", "unknown"))
PY
)"
fi

gateway_status="unknown"
if systemctl is-active --quiet openclaw-gateway.service 2>/dev/null; then
  gateway_status="active"
elif ss -ltnp 2>/dev/null | grep -qE '127\.0\.0\.1:18789|\[::1\]:18789'; then
  gateway_status="active-listening"
else
  gateway_status="inactive"
fi

timer_status="unknown"
if systemctl list-unit-files openclaw-stability-sampler.timer --no-legend 2>/dev/null | grep -q openclaw-stability-sampler.timer; then
  timer_status="$(systemctl is-active openclaw-stability-sampler.timer 2>/dev/null || true)"
else
  timer_status="not_installed"
fi

nas_status="not_mounted"
if mountpoint -q /mnt/nas/openclaw 2>/dev/null; then
  nas_status="mounted"
elif [[ -d /mnt/nas/openclaw ]]; then
  nas_status="directory_exists_not_mounted"
fi

progress_docs_dir="$workspace/docs"
if [[ ! -d "$progress_docs_dir" && -d /root/.openclaw/workspace/docs ]]; then
  progress_docs_dir="/root/.openclaw/workspace/docs"
fi
progress_doc_count="$(find "$progress_docs_dir" -maxdepth 1 -type f -name 'baseline_progress_*.md' 2>/dev/null | wc -l | tr -d ' ')"
probe_report_count="$(count_files "$workspace/logs/probes/*")"
report_count="$(count_files "$workspace/reports/*/*")"
dataset_card_count="$(count_files "$workspace/robot_datasets/*/DATASET_CARD.md")"
image_jsonl_count="$(count_files "$workspace/reports/image-captions/*.jsonl")"
stability_snapshot_count="$(count_files "$workspace/logs/probes/stability_snapshot_*.md")"

latest_document_index="$(latest_file "$workspace/reports/document_index_*.md")"
latest_browser_smoke="$(latest_file "$workspace/reports/browser-smoke/browser_smoke_*.md")"
latest_log_diagnosis="$(latest_file "$workspace/logs/probes/log_diagnosis_*.md")"
latest_stability="$(latest_file "$workspace/logs/probes/stability_snapshot_*.md")"
latest_stability_summary="$(latest_file "$workspace/reports/stability/stability_summary_*.md")"
latest_image_caption="$(latest_file "$workspace/reports/image-captions/image_caption_index_*.md")"
latest_experiment="$(latest_file "$workspace/reports/experiments/experiment_report_*.md")"
latest_security="$(latest_file "$workspace/logs/probes/security_audit_*.md")"
latest_service_policy="$(latest_file "$workspace/logs/probes/service_policy_*.md")"
latest_rosbag_session="$(latest_file "$workspace/logs/probes/rosbag_session_*.md")"
latest_dataset_card="$(latest_file "$workspace/robot_datasets/*/DATASET_CARD.md")"
latest_home_assistant="$(latest_file "$workspace/logs/probes/home_assistant_status_*.md")"
latest_control_policy="$(latest_file "$workspace/logs/probes/control_action_policy_*.md")"

github_marker_dir="$workspace/docs"
if [[ ! -d "$github_marker_dir" && -d /root/.openclaw/workspace/docs ]]; then
  github_marker_dir="/root/.openclaw/workspace/docs"
fi

github_issue_marker="missing"
github_issue_detail="no remote issue marker"
if [[ -f "$github_marker_dir/github_remote_issue.md" ]]; then
  github_issue_url="$(grep -Eo 'https://github.com/[^ ]+/issues/[0-9]+' "$github_marker_dir/github_remote_issue.md" | head -1 || true)"
  if [[ -n "$github_issue_url" ]]; then
    github_issue_marker="present"
    github_issue_detail="$github_issue_url"
  else
    github_issue_marker="present"
    github_issue_detail="$github_marker_dir/github_remote_issue.md"
  fi
fi

github_pr_marker="missing"
github_pr_detail="no remote PR marker"
if [[ -f "$github_marker_dir/github_remote_pr.md" ]]; then
  github_pr_url="$(grep -Eo 'https://github.com/[^ ]+/pull/[0-9]+' "$github_marker_dir/github_remote_pr.md" | head -1 || true)"
  github_review_id="$(awk -F': ' '$1 == "review_id" {print $2; exit}' "$github_marker_dir/github_remote_pr.md" 2>/dev/null || true)"
  if [[ -n "$github_pr_url" ]]; then
    github_pr_marker="present"
    github_pr_detail="$github_pr_url"
    [[ -n "$github_review_id" ]] && github_pr_detail="$github_pr_detail review_id=$github_review_id"
  else
    github_pr_marker="present"
    github_pr_detail="$github_marker_dir/github_remote_pr.md"
  fi
fi

b006_current="GitHub readiness report exists."
b006_gap="Needs real issue, branch, draft PR, and review path."
if [[ "$github_issue_marker" == "present" && "$github_pr_marker" == "present" ]]; then
  b006_current="Remote issue and draft PR markers exist; Codex review evidence is recorded."
  b006_gap="Workflow verified; PR remains draft/unmerged while broader baseline blockers remain."
fi

a003_current="NAS workspace is not mounted."
a003_gap="Mount and reboot validation are required."
if [[ "$nas_status" == "mounted" ]]; then
  a003_current="/mnt/nas/openclaw is mounted and available for NAS-backed artifacts."
  a003_gap="Verified by persistent NFS evidence; keep monitoring after power cycles."
fi

a007_current="No NAS-backed browser smoke report found."
a007_gap="Run browser_smoke_probe to NAS."
if [[ -n "$latest_browser_smoke" ]]; then
  a007_current="NAS-backed browser smoke report exists: $latest_browser_smoke."
  a007_gap="Verified for smoke screenshot; replace with real browser tasks if needed."
fi

a009_current="No NAS-backed ROS bag session found."
a009_gap="Run rosbag_session_probe to NAS and decide longer-session policy."
if [[ -n "$latest_rosbag_session" ]]; then
  a009_current="NAS-backed ROS bag session exists: $latest_rosbag_session."
  a009_gap="Bounded self-test verified; longer named capture policy remains."
fi

a010_current="No NAS-backed stability snapshot found."
a010_gap="Collect 7 days of clean snapshots."
if [[ -n "$latest_stability_summary" ]]; then
  a010_current="NAS-backed stability summary exists: $latest_stability_summary."
  a010_gap="Still needs 168 hours of clean samples."
fi

b002_current="No NAS-backed document index found."
b002_gap="Run document index and add daily summary."
if [[ -n "$latest_document_index" ]]; then
  b002_current="NAS-backed document index exists: $latest_document_index."
  b002_gap="Daily summary remains pending."
fi

b003_current="No NAS-backed image caption index found."
b003_gap="Run image caption index and decide semantic captioning."
if [[ -n "$latest_image_caption" ]]; then
  b003_current="NAS-backed image metadata caption index exists: $latest_image_caption."
  b003_gap="Semantic vision caption remains pending or needs to be scoped out."
fi

b004_current="No NAS-backed dataset card found."
b004_gap="Generate dataset card beside each robot dataset."
if [[ -n "$latest_dataset_card" ]]; then
  b004_current="NAS-backed dataset card exists: $latest_dataset_card."
  b004_gap="Verified for ROS bag session smoke dataset."
fi

b005_current="No NAS-backed log diagnosis found."
b005_gap="Run log_diagnose against NAS logs."
if [[ -n "$latest_log_diagnosis" ]]; then
  b005_current="NAS-backed log diagnosis exists: $latest_log_diagnosis."
  b005_gap="Verified for current link-check and gateway logs."
fi

b007_current="No NAS-backed experiment report found."
b007_gap="Generate report from NAS logs and datasets."
if [[ -n "$latest_experiment" ]]; then
  b007_current="NAS-backed experiment report exists: $latest_experiment."
  b007_gap="Verified for smoke baseline; replace with real weekly operating data."
fi

b010_current="No NAS-backed security audit found."
b010_gap="Run security audit to NAS and decide service policy."
if [[ -n "$latest_security" ]]; then
  b010_current="NAS-backed security audit exists: $latest_security."
  b010_gap="Service keep/disable/firewall decisions remain."
fi

{
  echo "# OpenClaw + NAS Baseline Status"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- workspace: $workspace"
  echo "- report: $report"
  echo "- mode: read-only baseline evidence summary"
  echo
  echo "## Current System"
  echo
  echo "| Check | Value |"
  echo "| --- | --- |"
  echo "| OpenClaw Gateway | $gateway_status |"
  echo "| Stability sampler timer | $timer_status |"
  echo "| NAS workspace | $nas_status |"
  echo "| Allowlisted tool count | $tool_count |"
  echo "| Progress docs | $progress_doc_count |"
  echo "| Probe reports | $probe_report_count |"
  echo "| Workspace reports | $report_count |"
  echo "| Dataset cards | $dataset_card_count |"
  echo "| Image caption JSONL indexes | $image_jsonl_count |"
  echo "| Stability snapshots | $stability_snapshot_count |"
  echo
  echo "## Allowlisted Tools"
  echo
  echo '```text'
  if [[ -n "$tool_ids" ]]; then
    printf '%s\n' "$tool_ids"
  else
    echo "unknown"
  fi
  echo '```'
  echo
  echo "## Latest Evidence Files"
  echo
  echo "| Area | Latest file |"
  echo "| --- | --- |"
  echo "| Stability snapshot | ${latest_stability:-missing} |"
  echo "| Stability summary | ${latest_stability_summary:-missing} |"
  echo "| Document index | ${latest_document_index:-missing} |"
  echo "| Browser smoke | ${latest_browser_smoke:-missing} |"
  echo "| Log diagnosis | ${latest_log_diagnosis:-missing} |"
  echo "| Image caption index | ${latest_image_caption:-missing} |"
  echo "| Experiment report | ${latest_experiment:-missing} |"
  echo "| Security audit | ${latest_security:-missing} |"
  echo "| Service policy | ${latest_service_policy:-missing} |"
  echo "| ROS bag session | ${latest_rosbag_session:-missing} |"
  echo "| Dataset card | ${latest_dataset_card:-missing} |"
  echo "| Home Assistant status | ${latest_home_assistant:-missing} |"
  echo "| Control action policy | ${latest_control_policy:-missing} |"
  echo "| GitHub remote issue | $github_issue_detail |"
  echo "| GitHub remote PR | $github_pr_detail |"
  echo
  echo "## Baseline Status Snapshot"
  echo
  echo "| ID | Current evidence | Remaining gap |"
  echo "| --- | --- | --- |"
  echo "| A-003 | $a003_current | $a003_gap |"
  echo "| A-005 | Narrow allowlisted OpenClaw plugin is installed. | Broad exec path still needs platform-level blocking evidence. |"
  echo "| A-006 | Sandbox probe shows runtime unavailable. | Needs sandbox runtime or explicit decision to keep blocked. |"
  echo "| A-007 | $a007_current | $a007_gap |"
  echo "| A-009 | $a009_current | $a009_gap |"
  echo "| A-010 | $a010_current | $a010_gap |"
  echo "| B-002 | $b002_current | $b002_gap |"
  echo "| B-003 | $b003_current | $b003_gap |"
  echo "| B-004 | $b004_current | $b004_gap |"
  echo "| B-005 | $b005_current | $b005_gap |"
  echo "| B-006 | $b006_current | $b006_gap |"
  echo "| B-007 | $b007_current | $b007_gap |"
  echo "| B-008 | Home Assistant read-only preflight exists when a status report is present. | Needs HA URL/token and a successful read-only /api/states check. |"
  echo "| B-009 | Low-risk control policy preflight exists when a control policy report is present. | Needs reviewed allowlist, two-step approval path, and execution audit before any control action. |"
  echo "| B-010 | $b010_current | $b010_gap |"
  echo
  echo "## Next Best Actions"
  echo
  echo "1. Keep A-010 timer running until 7 days of stability samples exist."
  echo "2. Replace smoke NAS artifacts with real weekly operating data, then rerun the report stack."
  echo "3. Decide service policy for NFS/RPC, x11vnc, and iiod from the B-010 report."
  echo "4. Decide whether B-003 should stay metadata-only or add semantic vision captioning."
  echo "5. Provide Home Assistant URL/token only if B-008 should read real device states."
  echo "6. Create and review a disabled B-009 control action policy before implementing any control execution path."
} > "$report"

echo "$report"
