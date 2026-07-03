#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tool_id="${1:-}"
shift || true

usage() {
  cat <<'EOF'
Usage:
  ai_nas_allowlisted_tool.sh ai_nas_personal_inventory [--bootstrap-demo]
  ai_nas_allowlisted_tool.sh ai_nas_file_search "query"
  ai_nas_allowlisted_tool.sh ai_nas_folder_summary [folder] [question]
  ai_nas_allowlisted_tool.sh ai_nas_duplicate_report
  ai_nas_allowlisted_tool.sh ai_nas_movie_sort_enhanced [--copy]
  ai_nas_allowlisted_tool.sh ai_nas_edge_cloud_router
  ai_nas_allowlisted_tool.sh dream7b_perf_identity

Environment:
  AI_NAS_PERSONAL_ROOT=/mnt/nas/openclaw/Personal
  AI_NAS_REPORT_ROOT=/mnt/nas/openclaw/reports/ai_nas_mvp

Only fixed probe IDs are accepted. This dispatcher never evaluates arbitrary
commands or script paths.
EOF
}

case "$tool_id" in
  ai_nas_personal_inventory)
    exec python3 "$script_dir/ai_nas_personal_inventory_probe.py" "$@"
    ;;
  ai_nas_file_search)
    exec python3 "$script_dir/ai_nas_file_search_probe.py" "$@"
    ;;
  ai_nas_folder_summary)
    exec python3 "$script_dir/ai_nas_folder_summary_probe.py" "$@"
    ;;
  ai_nas_duplicate_report)
    exec python3 "$script_dir/ai_nas_duplicate_report_probe.py" "$@"
    ;;
  ai_nas_movie_sort_enhanced)
    exec python3 "$script_dir/ai_nas_movie_sort_enhanced_probe.py" "$@"
    ;;
  ai_nas_edge_cloud_router)
    exec python3 "$script_dir/ai_nas_edge_cloud_router_probe.py" "$@"
    ;;
  dream7b_perf_identity)
    exec python3 "$script_dir/dream7b_perf_identity_probe.py" "$@"
    ;;
  ""|-h|--help|help)
    usage
    ;;
  *)
    echo "Refusing unknown AI-NAS tool ID: $tool_id" >&2
    usage >&2
    exit 2
    ;;
esac
