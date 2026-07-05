from __future__ import annotations

import hashlib
import json
import re
from typing import Any


PRIVATE_PATTERNS = [
    re.compile(r"/mnt/nas/openclaw/Personal/[^\s,;\"']+", re.IGNORECASE),
    re.compile(r"\\\\[^\\\s]+\\[^\s,;\"']+"),
    re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+\\[^\s,;\"']+", re.IGNORECASE),
    re.compile(r"(?i)\bredaction_map\b"),
    re.compile(r"(?i)\bsecret[_-]?key\b"),
    re.compile(r"(?i)\bapi[_-]?key\b"),
    re.compile(r"(?i)\bpassword\b"),
]


def stable_hash(value: Any, length: int = 16) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:length]


def redact_text(value: Any) -> tuple[str, int]:
    text = "" if value is None else str(value)
    count = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return f"<PRIVATE_HASH:{stable_hash(match.group(0), 12)}>"

    for pattern in PRIVATE_PATTERNS:
        text = pattern.sub(replace, text)
    return text, count


def redact_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    redactions = 0

    def walk(value: Any, key: str = "") -> Any:
        nonlocal redactions
        if key.lower() in {"raw_content", "raw_path", "full_path", "redaction_map", "secret", "password"}:
            redactions += 1
            return "<OMITTED_PRIVATE_FIELD>"
        if isinstance(value, dict):
            return {str(k): walk(v, str(k)) for k, v in value.items()}
        if isinstance(value, list):
            return [walk(v, key) for v in value]
        if isinstance(value, str):
            safe, count = redact_text(value)
            redactions += count
            return safe
        return value

    return walk(payload), redactions


def private_leak_count(payload: Any) -> int:
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return sum(len(pattern.findall(text)) for pattern in PRIVATE_PATTERNS)


def estimate_tokens(text: Any) -> int:
    value = "" if text is None else str(text)
    return max(1, (len(value.encode("utf-8", errors="replace")) + 3) // 4)
