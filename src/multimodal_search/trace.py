from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any


def new_trace_id() -> str:
    return "mm_trace_" + uuid.uuid4().hex[:16]


class TraceWriter:
    def __init__(self, trace_path: str | Path) -> None:
        self.trace_path = Path(trace_path)
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: dict[str, Any]) -> None:
        payload = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **event}
        with self.trace_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
