from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_TOOL_IDS = {
    "agent_runtime.context_pack.compile",
    "agent_runtime.memory.record",
    "agent_runtime.memory.lookup",
    "agent_runtime.multimodal_index.scan",
    "agent_runtime.multimodal_index.search",
    "agent_runtime.rag.query",
    "agent_runtime.rag.evaluate",
    "harness.copy.preview",
    "harness.copy.dry_run",
    "harness.copy.confirm",
    "harness.copy.execute",
    "harness.copy.rollback",
}


def load_manifest(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_internal_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    tools = manifest.get("tools") if isinstance(manifest.get("tools"), list) else []
    tool_ids = {str(tool.get("tool_id")) for tool in tools}
    missing = sorted(REQUIRED_TOOL_IDS - tool_ids)
    public_mcp_exposed = bool(manifest.get("public_mcp_exposed"))
    qwen_tool_execution = bool(manifest.get("qwen_tool_execution_authority"))
    mutating = [tool for tool in tools if tool.get("mutates_state")]
    mutating_not_dispatcher_only = [tool.get("tool_id") for tool in mutating if not tool.get("dispatcher_only")]
    cloud_raw = bool(manifest.get("cloud_private_raw_egress_allowed"))
    return {
        "ok": not missing and not public_mcp_exposed and not qwen_tool_execution and not mutating_not_dispatcher_only and not cloud_raw,
        "missing_tool_ids": missing,
        "tool_count": len(tools),
        "public_mcp_exposed": public_mcp_exposed,
        "qwen_tool_execution_authority": qwen_tool_execution,
        "mutating_not_dispatcher_only": mutating_not_dispatcher_only,
        "cloud_private_raw_egress_allowed": cloud_raw,
    }
