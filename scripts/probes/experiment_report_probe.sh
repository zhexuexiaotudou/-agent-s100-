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

extract_field() {
  local file="$1"
  local field="$2"
  if [[ -f "$file" ]]; then
    grep -E "^- ${field}:" "$file" 2>/dev/null | head -1 | sed "s/^- ${field}: //" || true
  fi
}

{
  echo "# OpenClaw S100P Experiment Report"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- workspace: $workspace"
  echo "- output: $report"
  echo
  echo "## Summary"
  echo
  echo "| Artifact | Count |"
  echo "| --- | ---: |"
  echo "| Probe reports | $(count_files "$probe_dir" '*.md') |"
  echo "| Experiment reports | $(count_files "$reports_dir/experiments" 'experiment_report_*.md') |"
  echo "| Browser smoke screenshots | $(count_files "$reports_dir/browser-smoke" '*.png') |"
  echo "| Document indexes | $(count_files "$reports_dir" 'document_index_*.md') |"
  echo "| ROS bag datasets | $(count_dirs "$datasets_dir" 'rosbag_snapshot_*') |"
  echo "| Dataset cards | $(count_files "$datasets_dir" 'DATASET_CARD.md') |"
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
  echo "## Current Blockers"
  echo
  echo "- NAS-backed acceptance is pending until /mnt/nas/openclaw is mounted."
  echo "- A-005 broad exec remains unverified until non-allowlisted command execution is blocked."
  echo "- A-006 sandbox isolation is blocked until Docker/Podman/runc runtime is installed or the item is dropped from baseline."
  echo
  echo "## Suggested Next Actions"
  echo
  echo "1. Mount TS-264C workspace and rerun B-002/B-005/B-007/A-007/A-009 against NAS paths."
  echo "2. Decide whether A-006 needs Docker/Podman on S100P or should be excluded from the first baseline."
  echo "3. Extend ROS bag capture from bounded snapshot to explicit start/stop after NAS output is available."
} > "$report"

echo "$report"
