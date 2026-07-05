from __future__ import annotations

from pathlib import Path
from typing import Any

from src.agent_runtime.service import AgentRuntimeService


def _service(report_root: str | Path | None, personal_root: str | Path | None) -> AgentRuntimeService:
    return AgentRuntimeService(report_root=report_root, personal_root=personal_root)


def agent_runtime_route_response(
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    report_root: str | Path | None = None,
    personal_root: str | Path | None = None,
) -> tuple[int, dict[str, Any]]:
    payload = payload or {}
    normalized = path.rstrip("/") or "/"
    service = _service(report_root, personal_root)
    if normalized == "/api/agent-runtime/status":
        return 200, service.status()
    if normalized == "/api/agent-runtime/tool-manifest":
        return 200, service.tool_manifest()
    if normalized == "/api/agent-runtime/memory/stats":
        return 200, service.memory_stats()
    if normalized == "/api/agent-runtime/multimodal-index/status":
        return 200, service.multimodal_status()
    if normalized == "/api/agent-runtime/eval/status":
        result = service.eval_status()
        return (200 if result.get("ok") else 404), result
    if method.upper() != "POST":
        return 405, {"ok": False, "error": "method_not_allowed", "path": path}
    if normalized == "/api/agent-runtime/context-pack":
        result = service.context_pack(payload)
        return (200 if result.get("ok") else 400), result
    if normalized == "/api/agent-runtime/memory/record":
        result = service.memory_record(payload)
        return (200 if result.get("ok") else 400), result
    if normalized == "/api/agent-runtime/multimodal-index/scan":
        result = service.scan_multimodal(payload)
        return (200 if result.get("ok") else 400), result
    if normalized == "/api/agent-runtime/rag/query":
        result = service.rag_query(payload)
        return (200 if result.get("ok") else 400), result
    return 404, {"ok": False, "error": "unknown_agent_runtime_route", "path": path}
