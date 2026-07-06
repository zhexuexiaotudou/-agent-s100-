from __future__ import annotations

from pathlib import Path
from typing import Any

from .recorder import AssistantTraceRecorder


def record_entrypoint_trace(
    *,
    report_root: str | Path,
    entrypoint: str,
    query: str = "",
    session_id: str = "global",
) -> dict[str, Any]:
    recorder = AssistantTraceRecorder(db_path=Path(report_root) / "assistant_trace" / "runtime" / "assistant_trace.db")
    return recorder.record_standard_trace(entrypoint=entrypoint, query=query, session_id=session_id)
