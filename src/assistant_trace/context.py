from __future__ import annotations

import hashlib
from typing import Any

from .recorder import AssistantTraceRecorder


class AssistantTraceContext:
    def __init__(
        self,
        recorder: AssistantTraceRecorder,
        *,
        entrypoint: str,
        query: str = "",
        session_id: str = "demo",
        request: dict[str, Any] | None = None,
    ) -> None:
        self.recorder = recorder
        self.entrypoint = entrypoint
        self.session_id = session_id
        self.query = query
        base_request = {
            "query_hash": hashlib.sha256(query.encode("utf-8", errors="replace")).hexdigest(),
            "payload_source": "real_execution_context",
            "synthetic_trace": False,
            "product_demo_allowed": True,
        }
        if request:
            base_request.update(request)
        self.trace_id = recorder.create_trace(entrypoint=entrypoint, session_id=session_id, request=base_request)

    def step_started(self, step_name: str, payload: dict[str, Any] | None = None) -> None:
        self.recorder.add_step(self.trace_id, step_name, self._payload({"event": "started", **(payload or {})}), status="started")

    def step_completed(self, step_name: str, payload: dict[str, Any] | None = None) -> None:
        self.recorder.add_step(self.trace_id, step_name, self._payload(payload or {}), status="ok")

    def record_router_decision(self, payload: dict[str, Any]) -> None:
        self.step_completed("qwen_router", payload)

    def record_privacy_spans(self, payload: dict[str, Any]) -> None:
        self.step_completed("privacy_tokenizer", payload)

    def record_task_classifier(self, payload: dict[str, Any]) -> None:
        self.step_completed("task_classifier", payload)

    def record_route_decision(self, payload: dict[str, Any]) -> None:
        self.step_completed("route_decision", payload)

    def record_token_budget(self, payload: dict[str, Any]) -> None:
        self.step_completed("token_budget", payload)

    def record_tool_call(self, tool_id: str, input_redacted: dict[str, Any], output_summary: dict[str, Any]) -> None:
        self.step_completed(
            "tool_execution",
            {
                "tool": tool_id,
                "input_redacted": input_redacted,
                "output_summary": output_summary,
                "qwen_execution_authority": False,
            },
        )

    def record_safety_gate(self, payload: dict[str, Any]) -> None:
        self.step_completed("safety_gate", payload)

    def record_evidence(self, payload: dict[str, Any]) -> None:
        self.step_completed("evidence_summary", payload)

    def finish(self, answer_summary: dict[str, Any]) -> None:
        self.recorder.finish(self.trace_id, status="completed", answer=self._payload(answer_summary))

    @staticmethod
    def _payload(payload: dict[str, Any]) -> dict[str, Any]:
        out = dict(payload)
        out.setdefault("payload_source", "real_execution_context")
        out.setdefault("synthetic_trace", False)
        out.setdefault("product_demo_allowed", True)
        return out
