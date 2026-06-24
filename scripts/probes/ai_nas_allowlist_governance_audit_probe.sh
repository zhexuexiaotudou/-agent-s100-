#!/usr/bin/env sh
set -eu
script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec python3 "$script_dir/ai_nas_allowlist_governance_audit_probe.py" "$@"
