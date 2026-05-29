#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/run_allowlisted_tool.sh list
  scripts/run_allowlisted_tool.sh openclaw_status_probe [output_dir]
  scripts/run_allowlisted_tool.sh nas_discovery_probe [output_dir]
  scripts/run_allowlisted_tool.sh ros2_status_probe [output_dir]
  scripts/run_allowlisted_tool.sh sandbox_status_probe [output_dir]
  scripts/run_allowlisted_tool.sh security_audit_probe [output_dir]
  scripts/run_allowlisted_tool.sh service_policy_probe [output_dir]
  scripts/run_allowlisted_tool.sh service_hardening_plan_probe [output_dir]
  scripts/run_allowlisted_tool.sh service_convergence_decision_probe [input_dir] [report_dir]
  scripts/run_allowlisted_tool.sh service_execution_preflight_probe [report_dir] [config_file]
  scripts/run_allowlisted_tool.sh stability_snapshot_probe [output_dir]
  scripts/run_allowlisted_tool.sh stability_summary_probe [input_dir] [report_dir]
  scripts/run_allowlisted_tool.sh image_caption_probe [photos_dir] [report_dir]
  scripts/run_allowlisted_tool.sh vision_caption_readiness_probe [photos_dir] [report_dir]
  scripts/run_allowlisted_tool.sh dream7b_readiness_probe [report_dir]
  scripts/run_allowlisted_tool.sh dream7b_smoke_probe [report_dir] [config_file]
  scripts/run_allowlisted_tool.sh home_assistant_status_probe [output_dir]
  scripts/run_allowlisted_tool.sh control_action_policy_probe [output_dir]
  scripts/run_allowlisted_tool.sh browser_smoke_probe [report_dir]
  scripts/run_allowlisted_tool.sh rosbag_snapshot_probe [dataset_dir] [report_dir]
  scripts/run_allowlisted_tool.sh rosbag_session_probe [dataset_dir] [report_dir]
  scripts/run_allowlisted_tool.sh rosbag_capture_policy_probe [output_dir]
  scripts/run_allowlisted_tool.sh rosbag_named_capture_probe [dataset_dir] [report_dir]
  scripts/run_allowlisted_tool.sh experiment_report_probe [report_dir]
  scripts/run_allowlisted_tool.sh log_diagnose [log_dir] [output_dir]
  scripts/run_allowlisted_tool.sh index_documents [documents_dir] [report_dir]
  scripts/run_allowlisted_tool.sh document_daily_summary_probe [documents_dir] [report_dir]
  scripts/run_allowlisted_tool.sh baseline_status_probe [workspace_dir] [report_dir]
  scripts/run_allowlisted_tool.sh baseline_gap_decision_probe [nas_root] [report_dir]
  scripts/run_allowlisted_tool.sh baseline_acceptance_probe [nas_root] [report_dir]
  scripts/run_allowlisted_tool.sh baseline_acceptance_trend_probe [nas_root] [report_dir]
  scripts/run_allowlisted_tool.sh baseline_evidence_manifest_probe [nas_root] [report_dir]
  scripts/run_allowlisted_tool.sh teacher_baseline_briefing_probe [nas_root] [report_dir]

Only explicitly allowlisted tool IDs can be executed. This script never accepts
arbitrary script paths.
EOF
}

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd "$script_dir/.." && pwd)"

tool_id="${1:-}"
if [[ -z "$tool_id" ]]; then
  usage >&2
  exit 2
fi

case "$tool_id" in
  list)
    cat <<'EOF'
openclaw_status_probe  Read-only OpenClaw/network/NAS status probe
nas_discovery_probe  Read-only passive NAS/network discovery for A-003
log_diagnose           Read-only log error summary report
index_documents        Read-only document index report
document_daily_summary_probe  Read-only deterministic daily document summary
ros2_status_probe      Read-only ROS2/TROS node/topic/service status report
sandbox_status_probe   Read-only Docker/Podman/sandbox capability status report
security_audit_probe   Read-only OpenClaw/S100P security baseline audit report
service_policy_probe   Read-only service keep/disable/firewall policy plan
service_hardening_plan_probe  Read-only dry-run hardening command plan
service_convergence_decision_probe  Read-only B-010 service convergence decision pack
service_execution_preflight_probe  Read-only B-010 service execution confirmation gate
stability_snapshot_probe  Read-only uptime/resource/log snapshot for A-010
stability_summary_probe  Read-only aggregate summary for A-010 stability snapshots
image_caption_probe  Read-only image metadata caption and JSONL index for B-003
vision_caption_readiness_probe  Read-only local semantic vision caption readiness for B-003
dream7b_readiness_probe  Read-only Dream 7B / local DLM deployment readiness
dream7b_smoke_probe  Bounded local Dream 7B smoke test, only when explicit config and local model files exist
home_assistant_status_probe  Read-only Home Assistant API status preflight for B-008
control_action_policy_probe  Read-only low-risk control policy and audit preflight for B-009
browser_smoke_probe    Headless Chromium local page screenshot smoke test
rosbag_snapshot_probe  Bounded ROS bag snapshot for low-risk topics
rosbag_session_probe   Start/status/stop ROS bag self-test for low-risk topics
rosbag_capture_policy_probe  Read-only named ROS bag capture policy and topic classification
rosbag_named_capture_probe  Operator-approved bounded named ROS bag capture
experiment_report_probe  Generate a Markdown summary from workspace reports and datasets
baseline_status_probe  Read-only roll-up status report for the two baseline tracks
baseline_gap_decision_probe  Read-only remaining-gap and next-decision report
baseline_acceptance_probe  Read-only pass/collecting/blocked acceptance gate for all baseline IDs
baseline_acceptance_trend_probe  Read-only trend report across baseline acceptance snapshots
baseline_evidence_manifest_probe  Read-only SHA256 manifest for current baseline evidence files
teacher_baseline_briefing_probe  Read-only teacher-facing briefing package for the two baseline tracks
EOF
    exit 0
    ;;
  openclaw_status_probe)
    shift
    tool_path="$repo_dir/scripts/probes/openclaw_status_probe.sh"
    max_args=1
    ;;
  nas_discovery_probe)
    shift
    tool_path="$repo_dir/scripts/probes/nas_discovery_probe.sh"
    max_args=1
    ;;
  log_diagnose)
    shift
    tool_path="$repo_dir/scripts/probes/log_diagnose.sh"
    max_args=2
    ;;
  index_documents)
    shift
    tool_path="$repo_dir/scripts/probes/index_documents.sh"
    max_args=2
    ;;
  document_daily_summary_probe)
    shift
    tool_path="$repo_dir/scripts/probes/document_daily_summary_probe.sh"
    max_args=2
    ;;
  ros2_status_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ros2_status_probe.sh"
    max_args=1
    ;;
  sandbox_status_probe)
    shift
    tool_path="$repo_dir/scripts/probes/sandbox_status_probe.sh"
    max_args=1
    ;;
  security_audit_probe)
    shift
    tool_path="$repo_dir/scripts/probes/security_audit_probe.sh"
    max_args=1
    ;;
  service_policy_probe)
    shift
    tool_path="$repo_dir/scripts/probes/service_policy_probe.sh"
    max_args=1
    ;;
  service_hardening_plan_probe)
    shift
    tool_path="$repo_dir/scripts/probes/service_hardening_plan_probe.sh"
    max_args=1
    ;;
  service_convergence_decision_probe)
    shift
    tool_path="$repo_dir/scripts/probes/service_convergence_decision_probe.sh"
    max_args=2
    ;;
  service_execution_preflight_probe)
    shift
    tool_path="$repo_dir/scripts/probes/service_execution_preflight_probe.sh"
    max_args=2
    ;;
  stability_snapshot_probe)
    shift
    tool_path="$repo_dir/scripts/probes/stability_snapshot_probe.sh"
    max_args=1
    ;;
  stability_summary_probe)
    shift
    tool_path="$repo_dir/scripts/probes/stability_summary_probe.sh"
    max_args=2
    ;;
  image_caption_probe)
    shift
    tool_path="$repo_dir/scripts/probes/image_caption_probe.sh"
    max_args=2
    ;;
  vision_caption_readiness_probe)
    shift
    tool_path="$repo_dir/scripts/probes/vision_caption_readiness_probe.sh"
    max_args=2
    ;;
  dream7b_readiness_probe)
    shift
    tool_path="$repo_dir/scripts/probes/dream7b_readiness_probe.sh"
    max_args=1
    ;;
  dream7b_smoke_probe)
    shift
    tool_path="$repo_dir/scripts/probes/dream7b_smoke_probe.sh"
    max_args=2
    ;;
  home_assistant_status_probe)
    shift
    tool_path="$repo_dir/scripts/probes/home_assistant_status_probe.sh"
    max_args=1
    ;;
  control_action_policy_probe)
    shift
    tool_path="$repo_dir/scripts/probes/control_action_policy_probe.sh"
    max_args=1
    ;;
  browser_smoke_probe)
    shift
    tool_path="$repo_dir/scripts/probes/browser_smoke_probe.sh"
    max_args=1
    ;;
  rosbag_snapshot_probe)
    shift
    tool_path="$repo_dir/scripts/probes/rosbag_snapshot_probe.sh"
    max_args=2
    ;;
  rosbag_session_probe)
    shift
    tool_path="$repo_dir/scripts/probes/rosbag_session_probe.sh"
    max_args=2
    ;;
  rosbag_capture_policy_probe)
    shift
    tool_path="$repo_dir/scripts/probes/rosbag_capture_policy_probe.sh"
    max_args=1
    ;;
  rosbag_named_capture_probe)
    shift
    tool_path="$repo_dir/scripts/probes/rosbag_named_capture_probe.sh"
    max_args=2
    ;;
  experiment_report_probe)
    shift
    tool_path="$repo_dir/scripts/probes/experiment_report_probe.sh"
    max_args=1
    ;;
  baseline_status_probe)
    shift
    tool_path="$repo_dir/scripts/probes/baseline_status_probe.sh"
    max_args=2
    ;;
  baseline_gap_decision_probe)
    shift
    tool_path="$repo_dir/scripts/probes/baseline_gap_decision_probe.sh"
    max_args=2
    ;;
  baseline_acceptance_probe)
    shift
    tool_path="$repo_dir/scripts/probes/baseline_acceptance_probe.sh"
    max_args=2
    ;;
  baseline_acceptance_trend_probe)
    shift
    tool_path="$repo_dir/scripts/probes/baseline_acceptance_trend_probe.sh"
    max_args=2
    ;;
  baseline_evidence_manifest_probe)
    shift
    tool_path="$repo_dir/scripts/probes/baseline_evidence_manifest_probe.sh"
    max_args=2
    ;;
  teacher_baseline_briefing_probe)
    shift
    tool_path="$repo_dir/scripts/probes/teacher_baseline_briefing_probe.sh"
    max_args=2
    ;;
  -h|--help|help)
    usage
    exit 0
    ;;
  *)
    echo "Tool is not allowlisted: $tool_id" >&2
    exit 3
    ;;
esac

if [[ ! -f "$tool_path" ]]; then
  echo "Allowlisted tool is missing: $tool_path" >&2
  exit 4
fi

if [[ $# -gt "$max_args" ]]; then
  echo "Too many arguments for $tool_id" >&2
  exit 2
fi

if [[ "$tool_id" == "openclaw_status_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing output path outside approved probe directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "nas_discovery_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing output path outside approved probe directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "ros2_status_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing output path outside approved probe directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "sandbox_status_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing output path outside approved probe directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "security_audit_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing output path outside approved probe directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "service_policy_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing output path outside approved probe directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "service_hardening_plan_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing output path outside approved probe directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "service_convergence_decision_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing input path outside approved probe directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "service_execution_preflight_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/root/.openclaw/workspace/config/service_convergence_confirmations.json|/mnt/nas/openclaw/config/service_convergence_confirmations.json|/tmp/service_convergence_confirmations.json) ;;
    *)
      echo "Refusing confirmation config outside approved paths: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "stability_snapshot_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing output path outside approved probe directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "stability_summary_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing input path outside approved stability snapshot directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "image_caption_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/photos|/mnt/nas/openclaw/photos/*|/root/.openclaw/workspace/photos|/root/.openclaw/workspace/photos/*) ;;
    *)
      echo "Refusing input path outside approved photo directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "vision_caption_readiness_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/photos|/mnt/nas/openclaw/photos/*|/root/.openclaw/workspace/photos|/root/.openclaw/workspace/photos/*) ;;
    *)
      echo "Refusing input path outside approved photo directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "dream7b_readiness_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "dream7b_smoke_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/root/.openclaw/workspace/config/dream7b_deployment.json|/mnt/nas/openclaw/config/dream7b_deployment.json|/tmp/dream7b_deployment.json) ;;
    *)
      echo "Refusing Dream 7B config outside approved paths: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "home_assistant_status_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing output path outside approved probe directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "control_action_policy_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing output path outside approved probe directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "browser_smoke_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "rosbag_snapshot_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/robot_datasets|/mnt/nas/openclaw/robot_datasets/*|/root/.openclaw/workspace/robot_datasets|/root/.openclaw/workspace/robot_datasets/*) ;;
    *)
      echo "Refusing dataset path outside approved robot dataset directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing report path outside approved probe directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "rosbag_session_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/robot_datasets|/mnt/nas/openclaw/robot_datasets/*|/root/.openclaw/workspace/robot_datasets|/root/.openclaw/workspace/robot_datasets/*) ;;
    *)
      echo "Refusing dataset path outside approved robot dataset directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing report path outside approved probe directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "rosbag_capture_policy_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing output path outside approved probe directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "rosbag_named_capture_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/robot_datasets|/mnt/nas/openclaw/robot_datasets/*|/root/.openclaw/workspace/robot_datasets|/root/.openclaw/workspace/robot_datasets/*) ;;
    *)
      echo "Refusing dataset path outside approved robot dataset directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing report path outside approved probe directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "experiment_report_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "log_diagnose" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/*|/root/.openclaw/workspace/logs|/root/.openclaw/workspace/logs/*) ;;
    *)
      echo "Refusing log path outside approved directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing output path outside approved probe directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "index_documents" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/documents|/mnt/nas/openclaw/documents/*|/root/.openclaw/workspace/documents|/root/.openclaw/workspace/documents/*) ;;
    *)
      echo "Refusing input path outside approved document directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "baseline_status_probe" ]]; then
  case "${1:-}" in
    ""|/root/.openclaw/workspace|/root/.openclaw/workspace/*|/mnt/nas/openclaw|/mnt/nas/openclaw/*) ;;
    *)
      echo "Refusing workspace outside approved baseline directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "baseline_gap_decision_probe" ]]; then
  case "${1:-}" in
    ""|/root/.openclaw/workspace|/root/.openclaw/workspace/*|/mnt/nas/openclaw|/mnt/nas/openclaw/*|/tmp/*) ;;
    *)
      echo "Refusing NAS/workspace root outside approved baseline directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "baseline_acceptance_probe" ]]; then
  case "${1:-}" in
    ""|/root/.openclaw/workspace|/root/.openclaw/workspace/*|/mnt/nas/openclaw|/mnt/nas/openclaw/*|/tmp/*) ;;
    *)
      echo "Refusing NAS/workspace root outside approved baseline directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "baseline_acceptance_trend_probe" ]]; then
  case "${1:-}" in
    ""|/root/.openclaw/workspace|/root/.openclaw/workspace/*|/mnt/nas/openclaw|/mnt/nas/openclaw/*|/tmp/*) ;;
    *)
      echo "Refusing NAS/workspace root outside approved baseline directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "baseline_evidence_manifest_probe" ]]; then
  case "${1:-}" in
    ""|/root/.openclaw/workspace|/root/.openclaw/workspace/*|/mnt/nas/openclaw|/mnt/nas/openclaw/*|/tmp/*) ;;
    *)
      echo "Refusing NAS/workspace root outside approved baseline directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "teacher_baseline_briefing_probe" ]]; then
  case "${1:-}" in
    ""|/root/.openclaw/workspace|/root/.openclaw/workspace/*|/mnt/nas/openclaw|/mnt/nas/openclaw/*|/tmp/*) ;;
    *)
      echo "Refusing NAS/workspace root outside approved baseline directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "document_daily_summary_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/documents|/mnt/nas/openclaw/documents/*|/root/.openclaw/workspace/documents|/root/.openclaw/workspace/documents/*) ;;
    *)
      echo "Refusing input path outside approved document directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

exec bash "$tool_path" "$@"
