#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
config="${1:-$repo_root/configs/agent_runtime_feature_flags.json}"
backup="$config.bak.$(date +%Y%m%d-%H%M%S)"
cp "$config" "$backup"

python3 - "$config" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
for key in [
    "agent_runtime_enabled",
    "context_pack_enabled",
    "memory_manager_enabled",
    "multimodal_index_enabled",
    "rag_enabled",
    "rag_eval_enabled",
    "default_service_routes_enabled",
]:
    payload[key] = False
payload["public_mcp_enabled"] = False
payload["qwen_tool_execution_enabled"] = False
payload["cloud_private_raw_egress_enabled"] = False
payload["destructive_actions_enabled"] = False
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

echo "disabled agent runtime feature flags; backup=$backup"
