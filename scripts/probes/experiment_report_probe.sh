#!/usr/bin/env bash
set -euo pipefail

out_dir="${1:-${OPENCLAW_REPORT_DIR:-/root/.openclaw/workspace/reports/experiments}}"
workspace="${OPENCLAW_WORKSPACE_DIR:-/root/.openclaw/workspace}"

case "$out_dir" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $out_dir" >&2
    exit 2
    ;;
esac

case "$workspace" in
  /root/.openclaw/workspace|/mnt/nas/openclaw) ;;
  *)
    echo "Refusing workspace outside approved roots: $workspace" >&2
    exit 2
    ;;
esac

mkdir -p "$out_dir"

timestamp="$(date +%Y%m%d-%H%M%S)"
report="$out_dir/experiment_report_$timestamp.md"

probe_dir="$workspace/logs/probes"
reports_dir="$workspace/reports"
datasets_dir="$workspace/robot_datasets"

if [[ "$workspace" == "/mnt/nas/openclaw" ]]; then
  nas_mode="verified"
else
  nas_mode="fallback"
fi

count_files() {
  local dir="$1"
  local pattern="$2"
  if [[ -d "$dir" ]]; then
    (find "$dir" -type f -name "$pattern" 2>/dev/null || true) | wc -l | tr -d ' '
  else
    echo 0
  fi
}

count_dirs() {
  local dir="$1"
  local pattern="$2"
  if [[ -d "$dir" ]]; then
    (find "$dir" -maxdepth 1 -type d -name "$pattern" 2>/dev/null || true) | wc -l | tr -d ' '
  else
    echo 0
  fi
}

latest_files() {
  local dir="$1"
  local pattern="$2"
  local limit="${3:-5}"
  if [[ -d "$dir" ]]; then
    (find "$dir" -type f -name "$pattern" -printf '%T@ %p\n' 2>/dev/null || true) \
      | sort -nr \
      | head -n "$limit" \
      | cut -d' ' -f2- \
      || true
  fi
}

count_rosbag_datasets() {
  local dir="$1"
  if [[ -d "$dir" ]]; then
    (
      find "$dir" -maxdepth 1 -type d -name 'rosbag_snapshot_*' 2>/dev/null
      find "$dir" -maxdepth 1 -type d -name 'rosbag_session_*' 2>/dev/null
    ) | wc -l | tr -d ' '
  else
    echo 0
  fi
}

extract_field() {
  local file="$1"
  local field="$2"
  if [[ -f "$file" ]]; then
    grep -E "^- ${field}:" "$file" 2>/dev/null | head -1 | sed "s/^- ${field}: //" || true
  fi
}

probe_count="$(count_files "$probe_dir" '*.md')"
experiment_count="$(count_files "$reports_dir/experiments" 'experiment_report_*.md')"
browser_count="$(count_files "$reports_dir/browser-smoke" '*.png')"
document_index_count="$(count_files "$reports_dir" 'document_index_*.md')"
document_summary_count="$(count_files "$reports_dir/daily-summary" 'document_daily_summary_*.md')"
rosbag_count="$(count_rosbag_datasets "$datasets_dir")"
dataset_card_count="$(count_files "$datasets_dir" 'DATASET_CARD.md')"

nas_core_artifacts="no"
if [[ "$nas_mode" == "verified" ]] \
  && (( probe_count > 0 )) \
  && (( browser_count > 0 )) \
  && (( document_index_count > 0 )) \
  && (( document_summary_count > 0 )) \
  && (( rosbag_count > 0 )) \
  && (( dataset_card_count > 0 )); then
  nas_core_artifacts="yes"
fi

{
  echo "# OpenClaw S100P Experiment Report"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- workspace: $workspace"
  echo "- nas_backed_mode: $nas_mode"
  echo "- output: $report"
  echo
  echo "## Summary"
  echo
  echo "| Artifact | Count |"
  echo "| --- | ---: |"
  echo "| Probe reports | $probe_count |"
  echo "| Experiment reports | $experiment_count |"
  echo "| Browser smoke screenshots | $browser_count |"
  echo "| Document indexes | $document_index_count |"
  echo "| Document daily summaries | $document_summary_count |"
  echo "| ROS bag datasets | $rosbag_count |"
  echo "| Dataset cards | $dataset_card_count |"
  echo
  echo "## Latest Probe Reports"
  echo
  latest_files "$probe_dir" '*.md' 10 | while read -r file; do
    [[ -n "$file" ]] || continue
    verdict="$(extract_field "$file" verdict)"
    echo "- \`$file\`${verdict:+ verdict=$verdict}"
  done
  echo
  echo "## Latest Dataset Cards"
  echo
  latest_files "$datasets_dir" 'DATASET_CARD.md' 10 | while read -r file; do
    [[ -n "$file" ]] || continue
    dataset_id="$(extract_field "$file" dataset_id)"
    topics="$(extract_field "$file" topics)"
    verdict="$(extract_field "$file" verdict)"
    echo "- \`$file\`${dataset_id:+ dataset_id=$dataset_id}${topics:+ topics=\"$topics\"}${verdict:+ verdict=$verdict}"
  done
  echo
  echo "## Latest Browser Smoke"
  echo
  latest_files "$reports_dir/browser-smoke" 'browser_smoke_*.md' 5 | while read -r file; do
    [[ -n "$file" ]] || continue
    marker="$(extract_field "$file" visible_marker)"
    screenshot_status="$(extract_field "$file" screenshot_status)"
    verdict="$(extract_field "$file" verdict)"
    echo "- \`$file\`${marker:+ visible_marker=$marker}${screenshot_status:+ screenshot_status=$screenshot_status}${verdict:+ verdict=$verdict}"
  done
  echo
  echo "## Latest Document Indexes"
  echo
  latest_files "$reports_dir" 'document_index_*.md' 5 | while read -r file; do
    [[ -n "$file" ]] || continue
    indexed="$(extract_field "$file" indexed_files)"
    echo "- \`$file\`${indexed:+ indexed_files=$indexed}"
  done
  echo
  echo "## Latest Document Daily Summaries"
  echo
  latest_files "$reports_dir/daily-summary" 'document_daily_summary_*.md' 5 | while read -r file; do
    [[ -n "$file" ]] || continue
    total="$(extract_field "$file" "Total documents")"
    modified="$(extract_field "$file" "Modified last 24h")"
    echo "- \`$file\`${total:+ total_documents=$total}${modified:+ modified_last_24h=$modified}"
  done
  echo
  echo "## Current Blockers"
  echo
  if [[ "$nas_core_artifacts" == "yes" ]]; then
    echo "- NAS-backed core report artifacts are present: logs/probes, document index, document daily summary, browser screenshot, ROS bag session, and dataset card."
  elif [[ "$nas_mode" == "verified" ]]; then
    echo "- NAS-backed report generation is verified; remaining acceptance needs richer NAS artifacts from B-002, A-007, A-009, and B-004."
  else
    echo "- NAS-backed acceptance is pending until /mnt/nas/openclaw is mounted and this probe is rerun with OPENCLAW_WORKSPACE_DIR=/mnt/nas/openclaw."
  fi
  echo "- A-005 broad exec remains unverified until non-allowlisted command execution is blocked."
  echo "- A-006 sandbox isolation is blocked until Docker/Podman/runc runtime is installed or the item is dropped from baseline."
  echo
  echo "## Suggested Next Actions"
  echo
  if [[ "$nas_core_artifacts" == "yes" ]]; then
    echo "1. Replace smoke artifacts with real weekly operating data, then rerun this report as the weekly baseline summary."
  elif [[ "$nas_mode" == "verified" ]]; then
    echo "1. Populate the NAS workspace with document indexes, browser screenshots, ROS bag sessions, and dataset cards, then rerun this report."
  else
    echo "1. Mount TS-264C workspace and rerun B-002/B-005/B-007/A-007/A-009 against NAS paths."
  fi
  echo "2. Decide whether A-006 needs Docker/Podman on S100P or should be excluded from the first baseline."
  echo "3. Extend ROS bag capture from bounded snapshot to explicit start/stop with NAS output."
} > "$report"

echo "$report"
