from __future__ import annotations

from pathlib import Path
from typing import Any

from .recorder import AssistantTraceRecorder, STANDARD_STEPS


def _recorder(report_root: str | Path | None) -> AssistantTraceRecorder:
    root = Path(report_root or "reports")
    return AssistantTraceRecorder(db_path=root / "assistant_trace" / "runtime" / "assistant_trace.db")


def assistant_trace_route_response(
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    report_root: str | Path | None = None,
    personal_root: str | Path | None = None,
) -> tuple[int, dict[str, Any]]:
    _ = personal_root
    normalized = path.rstrip("/") or "/"
    payload = payload or {}
    recorder = _recorder(report_root)
    if method.upper() == "POST" and normalized == "/api/assistant/chat":
        query = str(payload.get("query") or payload.get("message") or "")
        entrypoint = str(payload.get("entrypoint") or "assistant_chat")
        session_id = str(payload.get("session_id") or "default")
        trace = recorder.record_standard_trace(entrypoint=entrypoint, query=query, session_id=session_id)
        return 200, {
            "ok": True,
            "schema": "digua_assistant_chat_v1",
            "trace_id": trace.get("trace", {}).get("trace_id"),
            "answer_redacted": "Trace recorded; hidden chain-of-thought is not saved or displayed.",
            "steps": [step.get("step_name") for step in trace.get("steps") or []],
            "qwen_touched": True,
            "cloud_private_egress": False,
            "raw_path_returned": False,
        }
    if method.upper() == "POST" and normalized == "/api/assistant/trace/record-entrypoint":
        trace = recorder.record_standard_trace(
            entrypoint=str(payload.get("entrypoint") or "unknown"),
            query=str(payload.get("query") or ""),
            session_id=str(payload.get("session_id") or "coverage"),
        )
        return 200, trace
    if method.upper() != "GET":
        return 405, {"ok": False, "error": "method_not_allowed", "raw_path_returned": False}
    if normalized == "/api/assistant/trace/status":
        recent = recorder.list_traces(limit=5)
        return 200, {
            "ok": True,
            "schema": "digua_assistant_trace_status_v1",
            "trace_count_visible": len(recent.get("traces") or []),
            "required_steps": list(STANDARD_STEPS),
            "hidden_chain_of_thought_saved": False,
            "raw_path_returned": False,
            "cloud_private_raw_egress": False,
            "qwen_execution_authority": False,
        }
    if normalized.startswith("/api/assistant/trace/stream/"):
        result = recorder.get_trace(normalized.rsplit("/", 1)[-1])
        result["stream_mode"] = "snapshot"
        return (200 if result.get("ok") else 404), result
    if normalized.startswith("/api/assistant/trace/"):
        result = recorder.get_trace(normalized.rsplit("/", 1)[-1])
        return (200 if result.get("ok") else 404), result
    if normalized == "/api/assistant/traces":
        return 200, recorder.list_traces(session_id=payload.get("session_id"), limit=int(payload.get("limit") or 20))
    return 404, {"ok": False, "error": "unknown_assistant_trace_route", "path": path, "raw_path_returned": False}
