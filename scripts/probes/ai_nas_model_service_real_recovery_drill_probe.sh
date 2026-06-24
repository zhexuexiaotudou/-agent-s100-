#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ $# -gt 0 && "${1:-}" != --* ]]; then
  manifest_json="${1:-}"
  approval_phrase="${2:-}"
  execute_flag="${3:-}"
  args=(--manifest-json "$manifest_json")
  if [[ -n "$approval_phrase" ]]; then
    args+=(--approval-phrase "$approval_phrase")
  fi
  if [[ "$execute_flag" == "--execute" ]]; then
    args+=(--execute)
  fi
  exec python3 "$script_dir/ai_nas_model_service_real_recovery_drill_probe.py" "${args[@]}"
fi
exec python3 "$script_dir/ai_nas_model_service_real_recovery_drill_probe.py" "$@"
