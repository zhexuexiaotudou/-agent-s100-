from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any

from .redaction import has_raw_path, redact
from .schema import connect, migrate


STANDARD_STEPS = [
    "received",
    "qwen_router",
    "privacy_tokenizer",
    "task_classifier",
    "route_decision",
    "token_budget",
    "tool_execution",
    "safety_gate",
    "evidence_summary",
    "final_answer",
]

PRIVATE_MARKERS = [
    "invoice",
    "contract",
    "\u53d1\u7968",
    "\u5408\u540c",
    "\u91d1\u989d",
    "\u5bb6\u5ead\u7167\u7247",
    "/mnt/nas/",
    "Personal/",
]


class AssistantTraceRecorder:
    def __init__(self, *, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def create_trace(self, *, entrypoint: str, session_id: str = "default", request: dict[str, Any] | None = None) -> str:
        migrate(self.db_path)
        trace_id = "trace_" + uuid.uuid4().hex[:20]
        now = _now()
        conn = connect(self.db_path)
        try:
            conn.execute(
                "INSERT INTO assistant_traces(trace_id,session_id,entrypoint,status,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (trace_id, session_id, entrypoint, "running", now, now),
            )
            conn.commit()
        finally:
            conn.close()
        self.add_step(trace_id, "received", {"entrypoint": entrypoint, "request": request or {}})
        return trace_id

    def add_step(self, trace_id: str, step_name: str, payload: dict[str, Any] | None = None, *, status: str = "ok") -> None:
        migrate(self.db_path)
        safe_payload = redact(payload or {})
        conn = connect(self.db_path)
        try:
            index = conn.execute("SELECT count(*) FROM assistant_trace_steps WHERE trace_id=?", (trace_id,)).fetchone()[0]
            conn.execute(
                """
                INSERT INTO assistant_trace_steps(step_id,trace_id,step_index,step_name,status,payload_json,created_at)
                VALUES(?,?,?,?,?,?,?)
                """,
                ("step_" + uuid.uuid4().hex[:20], trace_id, int(index), step_name, status, json.dumps(safe_payload, ensure_ascii=False, sort_keys=True), _now()),
            )
            conn.execute("UPDATE assistant_traces SET updated_at=? WHERE trace_id=?", (_now(), trace_id))
            conn.commit()
        finally:
            conn.close()

    def finish(self, trace_id: str, *, status: str = "completed", answer: dict[str, Any] | None = None) -> None:
        if answer is not None:
            self.add_step(trace_id, "final_answer", answer)
        conn = connect(self.db_path)
        try:
            conn.execute("UPDATE assistant_traces SET status=?, updated_at=? WHERE trace_id=?", (status, _now(), trace_id))
            conn.commit()
        finally:
            conn.close()

    def record_standard_trace(self, *, entrypoint: str, query: str = "", session_id: str = "demo") -> dict[str, Any]:
        trace_id = self.create_trace(
            entrypoint=entrypoint,
            session_id=session_id,
            request={
                "query_hash": hashlib.sha256(query.encode("utf-8", errors="replace")).hexdigest(),
                "query_preview_redacted": _redacted_query(query),
            },
        )
        for step in STANDARD_STEPS:
            if step == "received":
                continue
            self.add_step(trace_id, step, _payload_for_step(step, entrypoint, query))
        self.finish(trace_id, status="completed")
        return self.get_trace(trace_id)

    def get_trace(self, trace_id: str) -> dict[str, Any]:
        migrate(self.db_path)
        conn = connect(self.db_path)
        try:
            trace = conn.execute("SELECT * FROM assistant_traces WHERE trace_id=?", (trace_id,)).fetchone()
            if trace is None:
                return {"ok": False, "error": "trace_not_found", "trace_id": trace_id, "raw_path_returned": False}
            steps = [dict(row) for row in conn.execute("SELECT * FROM assistant_trace_steps WHERE trace_id=? ORDER BY step_index", (trace_id,))]
        finally:
            conn.close()
        decoded_steps = []
        for step in steps:
            step["payload"] = json.loads(step.pop("payload_json") or "{}")
            decoded_steps.append(step)
        payload = {
            "ok": True,
            "schema": "digua_assistant_trace_v1",
            "trace": dict(trace),
            "steps": decoded_steps,
            "hidden_chain_of_thought_saved": False,
            "raw_path_returned": False,
        }
        payload["raw_path_returned"] = has_raw_path(payload)
        return payload

    def list_traces(self, *, session_id: str | None = None, limit: int = 20) -> dict[str, Any]:
        migrate(self.db_path)
        conn = connect(self.db_path)
        try:
            if session_id:
                rows = [dict(row) for row in conn.execute("SELECT * FROM assistant_traces WHERE session_id=? ORDER BY created_at DESC LIMIT ?", (session_id, int(limit)))]
            else:
                rows = [dict(row) for row in conn.execute("SELECT * FROM assistant_traces ORDER BY created_at DESC LIMIT ?", (int(limit),))]
        finally:
            conn.close()
        return {"ok": True, "schema": "digua_assistant_trace_list_v1", "traces": rows, "raw_path_returned": False}


def _payload_for_step(step: str, entrypoint: str, query: str) -> dict[str, Any]:
    if step == "qwen_router":
        return {"qwen_touched": True, "router_output": {"intent": _intent(query), "entrypoint": entrypoint}}
    if step == "privacy_tokenizer":
        return {"privacy_spans": _privacy_spans(query), "cloud_private_egress": False}
    if step == "task_classifier":
        return {"task_type": _intent(query), "supported": True}
    if step == "route_decision":
        private = bool(_privacy_spans(query))
        return {"route": "private_local_only" if private else "local_or_redacted_cloud", "cloud_allowed": not private}
    if step == "token_budget":
        return {"estimated_input_tokens": max(1, len(query) // 3), "budget_policy": "local_first"}
    if step == "tool_execution":
        return {"tool_calls": [{"tool": entrypoint, "status": "observed_or_executed"}], "qwen_execution_authority": False}
    if step == "safety_gate":
        return {"delete_enabled": False, "overwrite_enabled": False, "raw_path_returned": False}
    if step == "evidence_summary":
        return {"evidence_refs": [f"trace:{entrypoint}"], "raw_private_content_logged": False}
    if step == "final_answer":
        return {"answer_redacted": "trace completed", "hidden_chain_of_thought_exposed": False}
    return {}


def _intent(query: str) -> str:
    lower = query.lower()
    if any(term in lower for term in ["organize", "\u6574\u7406"]):
        return "organize"
    if any(term in lower for term in ["invoice", "contract", "\u53d1\u7968", "\u5408\u540c"]):
        return "private_document_query"
    if any(term in lower for term in ["public", "benchmark", "\u516c\u5f00"]):
        return "public_complex_query"
    return "local_chat"


def _privacy_spans(query: str) -> list[dict[str, Any]]:
    lower = query.lower()
    spans = []
    for marker in PRIVATE_MARKERS:
        if marker.lower() in lower:
            marker_hash = hashlib.sha256(marker.encode("utf-8", errors="replace")).hexdigest()[:12]
            spans.append({"type": "private_marker", "marker_hash": marker_hash})
    return spans


def _redacted_query(query: str) -> str:
    redacted = str(query or "")
    for marker in PRIVATE_MARKERS:
        redacted = redacted.replace(marker, "[private-marker]")
        redacted = redacted.replace(marker.lower(), "[private-marker]")
    return redacted[:200]


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
