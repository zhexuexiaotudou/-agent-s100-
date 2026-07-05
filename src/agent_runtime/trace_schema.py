from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .privacy import private_leak_count, stable_hash


REQUIRED_SPANS = {
    "context_pack.compile",
    "memory.lookup",
    "multimodal_index.lookup",
    "rag.retrieve",
    "safety.redact",
}


def utc_stamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _now_ns() -> int:
    return time.time_ns()


@dataclass
class TraceRecorder:
    trace_id: str = field(default_factory=lambda: "trc_" + uuid.uuid4().hex[:24])
    spans: list[dict[str, Any]] = field(default_factory=list)

    def span(
        self,
        name: str,
        *,
        status: str = "ok",
        attributes: dict[str, Any] | None = None,
        parent_span_id: str | None = None,
        duration_ms: float | None = None,
    ) -> dict[str, Any]:
        start_ns = _now_ns()
        if duration_ms is None:
            end_ns = start_ns + 1_000_000
            duration_ms = 1.0
        else:
            end_ns = start_ns + int(duration_ms * 1_000_000)
        span = {
            "trace_id": self.trace_id,
            "span_id": "spn_" + uuid.uuid4().hex[:16],
            "parent_span_id": parent_span_id,
            "name": name,
            "start_time_unix_nano": start_ns,
            "end_time_unix_nano": end_ns,
            "duration_ms": round(float(duration_ms), 3),
            "status": status,
            "attributes": attributes or {},
        }
        self.spans.append(span)
        return span

    def record_required_skeleton(self) -> None:
        for index, name in enumerate(sorted(REQUIRED_SPANS), start=1):
            self.span(name, attributes={"sequence": index, "agent_runtime": True})

    def to_record(self, *, request_id: str, attributes: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {
            "schema": "digua_agent_runtime_trace_v1",
            "trace_id": self.trace_id,
            "request_id": request_id,
            "generated_at": utc_stamp(),
            "spans": self.spans,
            "attributes": {
                "qwen_execution_authority": False,
                "cloud_private_raw_egress": False,
                **(attributes or {}),
            },
        }
        payload["private_leak_count"] = private_leak_count(payload)
        payload["trace_hash"] = stable_hash(payload, 32)
        return payload

    @staticmethod
    def append_jsonl(path: str | Path, record: dict[str, Any]) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def validate_trace_record(record: dict[str, Any]) -> dict[str, Any]:
    span_names = {str(span.get("name")) for span in record.get("spans") or []}
    missing = sorted(REQUIRED_SPANS - span_names)
    durations_ok = all(float(span.get("duration_ms") or 0) >= 0 for span in record.get("spans") or [])
    leak_count = private_leak_count(record)
    return {
        "ok": not missing and durations_ok and leak_count == 0,
        "missing_required_spans": missing,
        "durations_ok": durations_ok,
        "private_leak_count": leak_count,
    }
