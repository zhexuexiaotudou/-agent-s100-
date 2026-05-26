#!/usr/bin/env bash
set -euo pipefail

input_dir="${1:-/root/.openclaw/workspace/logs/probes}"
report_dir="${2:-/root/.openclaw/workspace/reports/stability}"

case "$input_dir" in
  /tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
  *)
    echo "Refusing input path outside approved stability snapshot directories: $input_dir" >&2
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
report="$report_dir/stability_summary_$stamp.md"

trim() {
  sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//'
}

field_value() {
  local file="$1"
  local field="$2"
  grep -m1 "| $field |" "$file" 2>/dev/null \
    | awk -F'|' '{print $3}' \
    | trim || true
}

metadata_value() {
  local file="$1"
  local field="$2"
  grep -m1 "^- $field:" "$file" 2>/dev/null \
    | sed -E "s/^- $field:[[:space:]]*//" \
    | trim || true
}

to_epoch() {
  local value="$1"
  if [[ -z "$value" ]]; then
    echo 0
    return
  fi
  date -d "$value" +%s 2>/dev/null || echo 0
}

mapfile -t snapshots < <(find "$input_dir" -maxdepth 1 -type f -name 'stability_snapshot_*.md' 2>/dev/null | sort)
sample_count="${#snapshots[@]}"

first_file=""
last_file=""
first_generated=""
last_generated=""
first_epoch=0
last_epoch=0
elapsed_hours="0.0"
max_reboots=0
max_oom=0
max_gateway_errors=0
gateway_statuses=""
nas_statuses=""

if (( sample_count > 0 )); then
  first_file="${snapshots[0]}"
  last_file="${snapshots[$((sample_count - 1))]}"
  first_generated="$(metadata_value "$first_file" "generated_at")"
  last_generated="$(metadata_value "$last_file" "generated_at")"
  first_epoch="$(to_epoch "$first_generated")"
  last_epoch="$(to_epoch "$last_generated")"
  if (( first_epoch > 0 && last_epoch >= first_epoch )); then
    elapsed_hours="$(awk -v a="$first_epoch" -v b="$last_epoch" 'BEGIN { printf "%.2f", (b - a) / 3600 }')"
  fi

  for snapshot in "${snapshots[@]}"; do
    reboots="$(field_value "$snapshot" "Reboot records visible")"
    oom="$(field_value "$snapshot" "Kernel OOM matches in last 24h")"
    gateway_errors="$(field_value "$snapshot" "Gateway error-like log matches in last 24h")"
    gateway_status="$(field_value "$snapshot" "Gateway status")"
    nas_status="$(field_value "$snapshot" "NAS workspace")"

    [[ "$reboots" =~ ^[0-9]+$ ]] || reboots=0
    [[ "$oom" =~ ^[0-9]+$ ]] || oom=0
    [[ "$gateway_errors" =~ ^[0-9]+$ ]] || gateway_errors=0

    (( reboots > max_reboots )) && max_reboots="$reboots"
    (( oom > max_oom )) && max_oom="$oom"
    (( gateway_errors > max_gateway_errors )) && max_gateway_errors="$gateway_errors"
    gateway_statuses+="${gateway_status:-unknown}"$'\n'
    nas_statuses+="${nas_status:-unknown}"$'\n'
  done
fi

verdict="collecting"
if (( sample_count == 0 )); then
  verdict="no_samples"
elif (( max_oom > 0 || max_gateway_errors > 0 )); then
  verdict="warn"
elif (( first_epoch > 0 && last_epoch - first_epoch >= 604800 )); then
  verdict="candidate_7day_pass"
fi

{
  echo "# S100P Stability Summary"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- input_dir: $input_dir"
  echo "- report: $report"
  echo "- mode: aggregate existing stability snapshots"
  echo
  echo "## Summary"
  echo
  echo "| Check | Value |"
  echo "| --- | --- |"
  echo "| Snapshot count | $sample_count |"
  echo "| First snapshot | ${first_generated:-n/a} |"
  echo "| Last snapshot | ${last_generated:-n/a} |"
  echo "| Elapsed hours | $elapsed_hours |"
  echo "| Max reboot records visible | $max_reboots |"
  echo "| Max kernel OOM matches in last 24h | $max_oom |"
  echo "| Max Gateway error-like matches in last 24h | $max_gateway_errors |"
  echo "| Verdict | $verdict |"
  echo
  echo "## Observed Gateway Statuses"
  echo
  echo '```text'
  if [[ -n "$gateway_statuses" ]]; then
    printf '%s' "$gateway_statuses" | sort | uniq -c
  else
    echo "none"
  fi
  echo '```'
  echo
  echo "## Observed NAS Statuses"
  echo
  echo '```text'
  if [[ -n "$nas_statuses" ]]; then
    printf '%s' "$nas_statuses" | sort | uniq -c
  else
    echo "none"
  fi
  echo '```'
  echo
  echo "## Latest Snapshot"
  echo
  if [[ -n "$last_file" ]]; then
    echo "- path: $last_file"
    echo
    echo '```text'
    sed -n '1,45p' "$last_file"
    echo '```'
  else
    echo "No stability snapshots found."
  fi
  echo
  echo "## A-010 Acceptance"
  echo
  echo "- This report summarizes existing snapshot evidence."
  echo "- A-010 is not a verified 7x24 pass until elapsed hours is at least 168 and the trend remains clean."
  echo "- NAS-backed acceptance additionally requires summaries under /mnt/nas/openclaw/reports after A-003 is mounted."
} > "$report"

echo "$report"
