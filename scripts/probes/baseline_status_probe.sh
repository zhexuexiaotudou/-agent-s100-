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
if [[ -f "$workspace/scripts/tool_allowlist.json" ]]; then
  tool_count="$(python3 - "$workspace/scripts/tool_allowlist.json" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as fh:
    data = json.load(fh)
tools = data.get("tools", [])
print(len(tools))
PY
)"
  tool_ids="$(python3 - "$workspace/scripts/tool_allowlist.json" <<'PY'
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

progress_doc_count="$(find "$workspace/docs" -maxdepth 1 -type f -name 'baseline_progress_*.md' 2>/dev/null | wc -l | tr -d ' ')"
probe_report_count="$(count_files "$workspace/logs/probes/*")"
report_count="$(count_files "$workspace/reports/*/*")"
dataset_card_count="$(count_files "$workspace/robot_datasets/*/DATASET_CARD.md")"
image_jsonl_count="$(count_files "$workspace/reports/image-captions/*.jsonl")"
stability_snapshot_count="$(count_files "$workspace/logs/probes/stability_snapshot_*.md")"

latest_stability="$(latest_file "$workspace/logs/probes/stability_snapshot_*.md")"
latest_stability_summary="$(latest_file "$workspace/reports/stability/stability_summary_*.md")"
latest_image_caption="$(latest_file "$workspace/reports/image-captions/image_caption_index_*.md")"
latest_experiment="$(latest_file "$workspace/reports/experiments/experiment_report_*.md")"
latest_security="$(latest_file "$workspace/logs/probes/security_audit_*.md")"
latest_service_policy="$(latest_file "$workspace/logs/probes/service_policy_*.md")"
latest_rosbag_session="$(latest_file "$workspace/logs/probes/rosbag_session_*.md")"
latest_home_assistant="$(latest_file "$workspace/logs/probes/home_assistant_status_*.md")"
latest_control_policy="$(latest_file "$workspace/logs/probes/control_action_policy_*.md")"

github_issue_marker="missing"
github_issue_detail="no remote issue marker"
if [[ -f "$workspace/docs/github_remote_issue.md" ]]; then
  github_issue_url="$(grep -Eo 'https://github.com/[^ ]+/issues/[0-9]+' "$workspace/docs/github_remote_issue.md" | head -1 || true)"
  if [[ -n "$github_issue_url" ]]; then
    github_issue_marker="present"
    github_issue_detail="$github_issue_url"
  else
    github_issue_marker="present"
    github_issue_detail="$workspace/docs/github_remote_issue.md"
  fi
fi

github_pr_marker="missing"
github_pr_detail="no remote PR marker"
if [[ -f "$workspace/docs/github_remote_pr.md" ]]; then
  github_pr_url="$(grep -Eo 'https://github.com/[^ ]+/pull/[0-9]+' "$workspace/docs/github_remote_pr.md" | head -1 || true)"
  github_review_id="$(awk -F': ' '$1 == "review_id" {print $2; exit}' "$workspace/docs/github_remote_pr.md" 2>/dev/null || true)"
  if [[ -n "$github_pr_url" ]]; then
    github_pr_marker="present"
    github_pr_detail="$github_pr_url"
    [[ -n "$github_review_id" ]] && github_pr_detail="$github_pr_detail review_id=$github_review_id"
  else
    github_pr_marker="present"
    github_pr_detail="$workspace/docs/github_remote_pr.md"
  fi
fi

b006_current="GitHub readiness report exists."
b006_gap="Needs real issue, branch, draft PR, and review path."
if [[ "$github_issue_marker" == "present" && "$github_pr_marker" == "present" ]]; then
  b006_current="Remote issue and draft PR markers exist; Codex review evidence is recorded."
  b006_gap="Workflow verified; PR remains draft/unmerged while broader baseline blockers remain."
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
  echo "| Image caption index | ${latest_image_caption:-missing} |"
  echo "| Experiment report | ${latest_experiment:-missing} |"
  echo "| Security audit | ${latest_security:-missing} |"
  echo "| Service policy | ${latest_service_policy:-missing} |"
  echo "| ROS bag session | ${latest_rosbag_session:-missing} |"
  echo "| Home Assistant status | ${latest_home_assistant:-missing} |"
  echo "| Control action policy | ${latest_control_policy:-missing} |"
  echo "| GitHub remote issue | $github_issue_detail |"
  echo "| GitHub remote PR | $github_pr_detail |"
  echo
  echo "## Baseline Status Snapshot"
  echo
  echo "| ID | Current evidence | Remaining gap |"
  echo "| --- | --- | --- |"
  echo "| A-003 | Mount helpers and cifs-utils are prepared. | Needs TS-264C share, account, mount, and reboot validation. |"
  echo "| A-005 | Narrow allowlisted OpenClaw plugin is installed. | Broad exec path still needs platform-level blocking evidence. |"
  echo "| A-006 | Sandbox probe shows runtime unavailable. | Needs sandbox runtime or explicit decision to keep blocked. |"
  echo "| A-007 | Browser smoke works in local workspace. | Needs NAS-backed screenshot/report path. |"
  echo "| A-009 | ROS bag snapshot and session self-test work locally. | Needs NAS-backed captures and longer-session policy. |"
  echo "| A-010 | Timer and summary are running locally. | Needs 7 days of clean samples and NAS-backed output. |"
  echo "| B-002/B-005 | Document index and log diagnosis work locally. | Needs NAS-backed documents/logs. |"
  echo "| B-003 | Metadata caption and JSONL image index work locally. | Needs NAS-backed photos and semantic-caption decision. |"
  echo "| B-006 | $b006_current | $b006_gap |"
  echo "| B-007 | Experiment report works locally. | Needs NAS-backed source reports/datasets. |"
  echo "| B-008 | Home Assistant read-only preflight exists when a status report is present. | Needs HA URL/token and a successful read-only /api/states check. |"
  echo "| B-009 | Low-risk control policy preflight exists when a control policy report is present. | Needs reviewed allowlist, two-step approval path, and execution audit before any control action. |"
  echo "| B-010 | Security audit and service policy reports exist. | Needs final keep/disable/firewall decisions and NAS-backed audit. |"
  echo
  echo "## Next Best Actions"
  echo
  echo "1. Provide TS-264C share/account details so A-003 can be mounted and the NAS-dependent items can be retested."
  echo "2. Keep A-010 timer running until 7 days of stability samples exist."
  echo "3. Decide service policy for NFS/RPC, x11vnc, and iiod from the B-010 report."
  echo "4. Decide whether B-003 should stay metadata-only or add semantic vision captioning."
  echo "5. Provide Home Assistant URL/token only if B-008 should read real device states."
  echo "6. Create and review a disabled B-009 control action policy before implementing any control execution path."
} > "$report"

echo "$report"
