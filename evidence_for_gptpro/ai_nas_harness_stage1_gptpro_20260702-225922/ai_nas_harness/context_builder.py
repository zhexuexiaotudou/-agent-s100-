from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .config_io import load_json_yaml, repo_root, resolve_repo_path


DEFAULT_REGISTRY_PATH = repo_root() / "config" / "workspace_registry.yaml"


GLOBAL_SYSTEM_PROMPT = """You are the AI-NAS Workspace Harness shadow layer.
Do not replace OpenClaw, Qwen, or the AI-NAS allowlist dispatcher.
Never expose tools outside the selected workspace.
Never route private NAS content to cloud.
Destructive or recovery actions require explicit human approval.
Dream7B and ports 18888/18889 are outside the foreground product path."""


def _tool_schema(tool: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(tool, str):
        return {
            "name": tool,
            "description": f"AI-NAS allowlisted dispatcher tool: {tool}",
            "input_schema": {"type": "object", "additionalProperties": True},
        }
    tool_id = str(tool.get("tool_id") or tool.get("name") or "").strip()
    if not tool_id:
        raise ValueError("tool dict must include tool_id or name")
    return {
        "name": tool_id,
        "description": str(tool.get("description") or f"AI-NAS allowlisted dispatcher tool: {tool_id}"),
        "input_schema": tool.get("input_schema") or {"type": "object", "additionalProperties": True},
    }


def _history_block(recent_history: list[dict[str, Any]] | list[str]) -> str:
    items: list[str] = []
    for item in recent_history[-8:]:
        if isinstance(item, str):
            items.append(item[:800])
        elif isinstance(item, dict):
            role = str(item.get("role") or "event")
            content = str(item.get("content") or item.get("summary") or "")[:800]
            if content:
                items.append(f"{role}: {content}")
    return "\n".join(items)


def _memory_block(scoped_memory: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for item in scoped_memory[:12]:
        memory_type = str(item.get("memory_type") or item.get("type") or "case")
        scope = str(item.get("scope") or "global")
        privacy = str(item.get("privacy_level") or "none")
        text = str(item.get("content") or item.get("summary") or "")[:600]
        if text:
            lines.append(f"- [{memory_type} scope={scope} privacy={privacy}] {text}")
    return "\n".join(lines)


def build_context(
    user_request: str,
    workspace_id: str,
    recent_history: list[dict[str, Any]] | list[str],
    scoped_memory: list[dict[str, Any]],
    allowed_tools: list[str] | list[dict[str, Any]],
    *,
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
) -> dict[str, Any]:
    registry = load_json_yaml(registry_path)
    workspaces = registry.get("workspaces") or {}
    if workspace_id not in workspaces:
        raise KeyError(f"unknown_workspace:{workspace_id}")
    workspace = workspaces[workspace_id]
    prompt_path = resolve_repo_path(workspace["prompt_file"])
    workspace_prompt = prompt_path.read_text(encoding="utf-8")

    unique_tools: list[str] = []
    tool_schemas = []
    for raw_tool in allowed_tools:
        schema = _tool_schema(raw_tool)
        name = schema["name"]
        if name not in unique_tools:
            unique_tools.append(name)
            tool_schemas.append(schema)

    payload = {
        "system_prompt": GLOBAL_SYSTEM_PROMPT,
        "workspace_prompt": workspace_prompt,
        "tool_schemas": tool_schemas,
        "memory_block": _memory_block(scoped_memory),
        "history_block": _history_block(recent_history),
        "workspace_id": workspace_id,
        "user_request_preview": user_request[:1000],
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["context_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    payload["context_size_chars"] = {
        "system_prompt": len(payload["system_prompt"]),
        "workspace_prompt": len(payload["workspace_prompt"]),
        "tool_schemas": len(json.dumps(tool_schemas, ensure_ascii=False, sort_keys=True)),
        "memory_block": len(payload["memory_block"]),
        "history_block": len(payload["history_block"]),
        "total": len(canonical),
    }
    payload["exposed_tool_ids"] = unique_tools
    return payload


def estimate_baseline_context_size(all_tool_ids: list[str], recent_history: list[dict[str, Any]] | list[str]) -> int:
    baseline = {
        "system_prompt": GLOBAL_SYSTEM_PROMPT,
        "tools": [_tool_schema(tool_id) for tool_id in all_tool_ids],
        "history": _history_block(recent_history),
        "note": "Baseline estimate assumes the old pattern where all allowlisted tools are visible.",
    }
    return len(json.dumps(baseline, ensure_ascii=False, sort_keys=True))

