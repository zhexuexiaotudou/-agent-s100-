#!/usr/bin/env bash
set -euo pipefail

workspace="${OPENCLAW_WORKSPACE:-/root/.openclaw/workspace}"
nas_root="${OPENCLAW_NAS_ROOT:-/mnt/nas/openclaw}"
duration_hours="${OVERNIGHT_BASELINE_HOURS:-10}"
interval_seconds="${OVERNIGHT_BASELINE_INTERVAL_SECONDS:-1800}"

case "$workspace" in
  /root/.openclaw/workspace|/root/.openclaw/workspace/*) ;;
  *)
    echo "Refusing workspace outside /root/.openclaw/workspace: $workspace" >&2
    exit 2
    ;;
esac

case "$nas_root" in
  /mnt/nas/openclaw|/mnt/nas/openclaw/*) ;;
  *)
    echo "Refusing NAS root outside /mnt/nas/openclaw: $nas_root" >&2
    exit 2
    ;;
esac

case "$duration_hours" in
  ''|*[!0-9]*) echo "OVERNIGHT_BASELINE_HOURS must be an integer" >&2; exit 2 ;;
esac

case "$interval_seconds" in
  ''|*[!0-9]*) echo "OVERNIGHT_BASELINE_INTERVAL_SECONDS must be an integer" >&2; exit 2 ;;
esac

if (( duration_hours < 1 || duration_hours > 24 )); then
  echo "OVERNIGHT_BASELINE_HOURS must be between 1 and 24" >&2
  exit 2
fi

if (( interval_seconds < 300 || interval_seconds > 7200 )); then
  echo "OVERNIGHT_BASELINE_INTERVAL_SECONDS must be between 300 and 7200" >&2
  exit 2
fi

runner="$workspace/scripts/run_allowlisted_tool.sh"
if [[ ! -x "$runner" ]]; then
  echo "Allowlist runner is missing or not executable: $runner" >&2
  exit 4
fi

summary_helper="$workspace/scripts/summarize_overnight_baseline_runner.sh"

if ! mountpoint -q "$nas_root" 2>/dev/null; then
  echo "NAS root is not mounted: $nas_root" >&2
  exit 5
fi

started_stamp="$(date +%Y%m%d-%H%M%S)"
out_dir="$nas_root/logs/overnight"
mkdir -p "$out_dir" "$nas_root/logs/probes" "$nas_root/reports/stability" "$nas_root/reports/baseline-status" "$nas_root/reports/security" "$nas_root/reports/teacher"
jsonl="$out_dir/overnight_baseline_$started_stamp.jsonl"
report="$out_dir/overnight_baseline_$started_stamp.md"
pid_file="$out_dir/overnight_baseline_$started_stamp.pid"

echo "$$" > "$pid_file"

end_epoch=$(( $(date +%s) + duration_hours * 3600 ))
iteration=0

json_escape() {
  python3 -c 'import json,sys; print(json.dumps(sys.stdin.read())[1:-1])'
}

log_event() {
  local level="$1"
  local action="$2"
  local status="$3"
  local detail="$4"
  local escaped
  escaped="$(printf '%s' "$detail" | json_escape)"
  printf '{"time":"%s","iteration":%s,"level":"%s","action":"%s","status":"%s","detail":"%s"}\n' \
    "$(date -Is)" "$iteration" "$level" "$action" "$status" "$escaped" >> "$jsonl"
}

run_tool() {
  local action="$1"
  shift
  local output
  local status="ok"
  set +e
  output="$("$runner" "$@" 2>&1)"
  local rc=$?
  set -e
  if [[ "$rc" -ne 0 ]]; then
    status="failed_rc_$rc"
  fi
  log_event "info" "$action" "$status" "$output"
  printf '%s\n' "$output"
}

run_helper() {
  local action="$1"
  shift
  local output
  local status="ok"
  set +e
  output="$("$@" 2>&1)"
  local rc=$?
  set -e
  if [[ "$rc" -ne 0 ]]; then
    status="failed_rc_$rc"
  fi
  log_event "info" "$action" "$status" "$output"
  printf '%s\n' "$output"
}

{
  echo "# Overnight Baseline Runner"
  echo
  echo "- started_at: $(date -Is)"
  echo "- pid: $$"
  echo "- workspace: $workspace"
  echo "- nas_root: $nas_root"
  echo "- duration_hours: $duration_hours"
  echo "- interval_seconds: $interval_seconds"
  echo "- jsonl: $jsonl"
  echo "- pid_file: $pid_file"
  echo "- mode: read-only probes and reports"
  echo
  echo "## Initial Status"
  echo
  echo '```text'
  echo "starting"
  echo '```'
} > "$report"

log_event "info" "runner_start" "ok" "pid=$$ duration_hours=$duration_hours interval_seconds=$interval_seconds"

while (( $(date +%s) < end_epoch )); do
  iteration=$((iteration + 1))
  log_event "info" "iteration_start" "ok" "iteration=$iteration"

  run_tool "stability_snapshot" stability_snapshot_probe "$nas_root/logs/probes" >/dev/null || true
  run_tool "stability_summary" stability_summary_probe "$nas_root/logs/probes" "$nas_root/reports/stability" >/dev/null || true
  run_tool "baseline_status" baseline_status_probe "$nas_root" "$nas_root/reports/baseline-status" >/dev/null || true
  run_tool "baseline_gap_decision" baseline_gap_decision_probe "$nas_root" "$nas_root/reports/baseline-status" >/dev/null || true
  run_tool "baseline_acceptance" baseline_acceptance_probe "$nas_root" "$nas_root/reports/baseline-status" >/dev/null || true
  run_tool "baseline_acceptance_trend" baseline_acceptance_trend_probe "$nas_root" "$nas_root/reports/baseline-status" >/dev/null || true
  run_tool "baseline_evidence_manifest" baseline_evidence_manifest_probe "$nas_root" "$nas_root/reports/baseline-status" >/dev/null || true
  run_tool "teacher_baseline_briefing" teacher_baseline_briefing_probe "$nas_root" "$nas_root/reports/teacher" >/dev/null || true

  if (( iteration == 1 || iteration % 4 == 0 )); then
    run_tool "openclaw_status" openclaw_status_probe "$nas_root/logs/probes" >/dev/null || true
    run_tool "security_audit" security_audit_probe "$nas_root/logs/probes" >/dev/null || true
    run_tool "service_convergence_decision" service_convergence_decision_probe "$nas_root/logs/probes" "$nas_root/reports/security" >/dev/null || true
    run_tool "service_execution_preflight" service_execution_preflight_probe "$nas_root/reports/security" >/dev/null || true
  fi

  log_event "info" "iteration_end" "ok" "iteration=$iteration"

  if (( $(date +%s) + interval_seconds >= end_epoch )); then
    break
  fi
  sleep "$interval_seconds"
done

latest_stability="$(find "$nas_root/reports/stability" -type f -name 'stability_summary_*.md' -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1 {$1=""; sub(/^ /, ""); print}')"
latest_baseline="$(find "$nas_root/reports/baseline-status" -type f -name 'baseline_status_*.md' -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1 {$1=""; sub(/^ /, ""); print}')"
latest_gap="$(find "$nas_root/reports/baseline-status" -type f -name 'baseline_gap_decision_*.md' -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1 {$1=""; sub(/^ /, ""); print}')"
latest_acceptance="$(find "$nas_root/reports/baseline-status" -type f -name 'baseline_acceptance_[0-9]*.md' -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1 {$1=""; sub(/^ /, ""); print}')"
latest_acceptance_trend="$(find "$nas_root/reports/baseline-status" -type f -name 'baseline_acceptance_trend_*.md' -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1 {$1=""; sub(/^ /, ""); print}')"
latest_manifest="$(find "$nas_root/reports/baseline-status" -type f -name 'baseline_evidence_manifest_*.md' -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1 {$1=""; sub(/^ /, ""); print}')"
latest_teacher="$(find "$nas_root/reports/teacher" -type f -name 'teacher_baseline_briefing_*.md' -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1 {$1=""; sub(/^ /, ""); print}')"
latest_convergence="$(find "$nas_root/reports/security" -type f -name 'service_convergence_decision_*.md' -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1 {$1=""; sub(/^ /, ""); print}')"

{
  echo
  echo "## Final Status"
  echo
  echo "- finished_at: $(date -Is)"
  echo "- iterations: $iteration"
  echo "- latest_stability_summary: ${latest_stability:-missing}"
  echo "- latest_baseline_status: ${latest_baseline:-missing}"
  echo "- latest_baseline_gap_decision: ${latest_gap:-missing}"
  echo "- latest_baseline_acceptance: ${latest_acceptance:-missing}"
  echo "- latest_baseline_acceptance_trend: ${latest_acceptance_trend:-missing}"
  echo "- latest_baseline_evidence_manifest: ${latest_manifest:-missing}"
  echo "- latest_teacher_baseline_briefing: ${latest_teacher:-missing}"
  echo "- latest_service_convergence_decision: ${latest_convergence:-missing}"
  echo "- jsonl: $jsonl"
} >> "$report"

log_event "info" "runner_finish" "ok" "iterations=$iteration latest_stability=${latest_stability:-missing} latest_baseline=${latest_baseline:-missing} latest_gap=${latest_gap:-missing} latest_acceptance=${latest_acceptance:-missing} latest_acceptance_trend=${latest_acceptance_trend:-missing} latest_manifest=${latest_manifest:-missing} latest_teacher=${latest_teacher:-missing} latest_convergence=${latest_convergence:-missing}"

if [[ -x "$summary_helper" ]]; then
  run_helper "overnight_summary" "$summary_helper" "$out_dir" "$nas_root/reports/baseline-status" "$nas_root" >/dev/null || true
else
  log_event "warn" "overnight_summary" "missing_helper" "$summary_helper"
fi

echo "$report"
