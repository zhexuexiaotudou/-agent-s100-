from __future__ import annotations

import json
import re
from typing import Any

from .event_model import redact_private_text


EXPORT_FORBIDDEN_PATTERNS = [
    re.compile(r"/mnt/nas/openclaw/Personal/[^\s,;]+", re.IGNORECASE),
    re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+\\[^\s]+", re.IGNORECASE),
    re.compile(r"\\\\[^\\\s]+\\[^\s]+"),
    re.compile(r"(?i)\bredaction_map\b"),
    re.compile(r"(?i)\bdenied snippet\b"),
]


def sanitize_text(text: Any) -> tuple[str, int]:
    return redact_private_text(text)


def find_export_leaks(payload: Any) -> list[str]:
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks: list[str] = []
    for pattern in EXPORT_FORBIDDEN_PATTERNS:
        leaks.extend(match.group(0) for match in pattern.finditer(text))
    return sorted(set(leaks))


def assert_export_safe(payload: Any) -> None:
    leaks = find_export_leaks(payload)
    if leaks:
        raise ValueError(f"journal export contains private leak markers: {leaks[:3]}")


def export_safety_report(payload: Any) -> dict[str, Any]:
    leaks = find_export_leaks(payload)
    return {
        "ok": not leaks,
        "private_leak_count": len(leaks),
        "redaction_lookup_exported": "redaction_map" in json.dumps(payload, ensure_ascii=False, sort_keys=True).lower(),
        "leak_preview": leaks[:3],
    }
