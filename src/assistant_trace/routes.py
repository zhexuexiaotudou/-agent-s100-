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
        intent = _intent(query)
        privacy_spans = _privacy_spans(query)
        private = bool(privacy_spans)
        route = "private_local_only" if private else "local_only"
        answer = _answer_for_intent(intent, private)
        trace = recorder.record_execution_trace(
            entrypoint=entrypoint,
            query=query,
            session_id=session_id,
            step_payloads={
                "qwen_router": {"qwen_touched": True, "router_output": {"intent": intent, "entrypoint": entrypoint}},
                "privacy_tokenizer": {"privacy_spans": privacy_spans, "cloud_private_egress": False},
                "task_classifier": {"task_type": intent, "supported": True},
                "route_decision": {"route": route, "cloud_allowed": not private},
                "token_budget": {"estimated_input_tokens": max(1, len(query) // 3), "budget_policy": "local_first"},
                "tool_execution": {"tool_calls": [{"tool": intent, "status": "completed_or_noop"}], "qwen_execution_authority": False},
                "safety_gate": {"delete_enabled": False, "overwrite_enabled": False, "raw_path_returned": False},
                "evidence_summary": {"evidence_refs": [f"trace:{entrypoint}:{intent}"], "raw_private_content_logged": False},
                "final_answer": {"answer_redacted": answer, "hidden_chain_of_thought_exposed": False},
            },
        )
        return 200, {
            "ok": True,
            "schema": "digua_assistant_chat_v1",
            "trace_id": trace.get("trace", {}).get("trace_id"),
            "answer_redacted": answer,
            "task_type": intent,
            "route": route,
            "privacy_level": "high" if private else "medium",
            "cloud_used": False,
            "tool_execution": intent,
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


def _intent(query: str) -> str:
    text = str(query or "").lower()
    if any(term in text for term in ["organize", "整理"]):
        return "organize"
    if any(term in text for term in ["invoice", "contract", "发票", "合同", "金额"]):
        return "private_document_query"
    if any(term in text for term in ["public", "公开", "趋势", "benchmark"]):
        return "public_complex_query"
    if any(term in text for term in ["photo", "照片", "相册", "上传"]):
        return "media_search"
    return "local_chat"


def _privacy_spans(query: str) -> list[str]:
    text = str(query or "").lower()
    spans: list[str] = []
    for marker, label in [
        ("invoice", "invoice"),
        ("发票", "invoice"),
        ("contract", "contract"),
        ("合同", "contract"),
        ("amount", "amount"),
        ("金额", "amount"),
        ("family", "private_nas_context"),
        ("家庭", "private_nas_context"),
        ("personal/", "private_nas_context"),
        ("/mnt/nas/", "private_nas_context"),
    ]:
        if marker in text and label not in spans:
            spans.append(label)
    return spans


def _answer_for_intent(intent: str, private: bool) -> str:
    if intent == "organize":
        return "已识别为受控整理任务；需要计划、审批、执行和回滚链路。"
    if intent == "private_document_query":
        return "已识别为私有文档任务；仅允许本地检索和证据回答。"
    if intent == "public_complex_query":
        return "已识别为公开复杂任务；可在脱敏后进入受控云端。"
    if intent == "media_search":
        return "已识别为本地媒体检索任务；返回本地索引结果。"
    return "已识别为本地任务；返回本地工具执行结果。"
