#!/usr/bin/env bash
set -euo pipefail

base_url="${1:-http://127.0.0.1:8765}"
out_dir="${2:-reports/agent_runtime_live_status}"
mkdir -p "$out_dir"

curl -fsS "$base_url/api/harness/status" >"$out_dir/harness_status.json"
curl -fsS "$base_url/api/agent-runtime/status" >"$out_dir/agent_runtime_status.json"
curl -fsS "$base_url/api/agent-runtime/tool-manifest" >"$out_dir/agent_runtime_tool_manifest.json"
curl -fsS "$base_url/api/agent-runtime/memory/stats" >"$out_dir/agent_runtime_memory_stats.json"
curl -fsS "$base_url/api/agent-runtime/multimodal-index/status" >"$out_dir/agent_runtime_multimodal_status.json"

python3 - "$out_dir" <<'PY'
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
status = json.loads((out / "agent_runtime_status.json").read_text(encoding="utf-8"))
manifest = json.loads((out / "agent_runtime_tool_manifest.json").read_text(encoding="utf-8"))
payload = {
    "ok": bool(status.get("ok")) and bool(manifest.get("ok")),
    "status_ok": bool(status.get("ok")),
    "manifest_ok": bool(manifest.get("ok")),
    "qwen_execution_authority": status.get("qwen_execution_authority"),
    "cloud_private_raw_egress": status.get("cloud_private_raw_egress"),
    "public_mcp_exposed": status.get("public_mcp_exposed"),
}
(out / "agent_runtime_live_status_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload, ensure_ascii=False))
sys.exit(0 if payload["ok"] else 1)
PY
