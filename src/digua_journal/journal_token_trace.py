from __future__ import annotations

import uuid
from typing import Any

from .event_model import utc_now
from .journal_privacy_guard import export_safety_report

try:
    from tools.token_budget.qwen_token_counter import QwenTokenCounter
except Exception:  # pragma: no cover - optional runtime dependency
    QwenTokenCounter = None  # type: ignore[assignment]


class JournalTokenTracer:
    def __init__(self) -> None:
        self.counter = QwenTokenCounter() if QwenTokenCounter else None

    def count(self, text: Any) -> int:
        value = "" if text is None else str(text)
        if not value:
            return 0
        if self.counter:
            return int(self.counter.count_text_tokens(value))
        return max(1, (len(value) + 3) // 4)

    def make_trace(self, *, prompt: str, evidence: str, output: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        safety = export_safety_report({"prompt": prompt, "evidence": evidence, "output": output})
        return {
            "trace_id": "jtrace_" + uuid.uuid4().hex[:20],
            "created_at": utc_now(),
            "route": "local_qwen_summary",
            "cloud_allowed": False,
            "prompt_tokens": self.count(prompt),
            "evidence_tokens": self.count(evidence),
            "output_tokens": self.count(output),
            "redaction_count": int((metadata or {}).get("redaction_count", 0)),
            "private_leak_count": safety["private_leak_count"],
            "metadata": {
                "cloud_generation_enabled": False,
                "redaction_lookup_exported": False,
                "qwen_execution_authority": False,
                **(metadata or {}),
            },
        }
