from __future__ import annotations

import json
import re
from typing import Any


RAW_PATH_RE = re.compile(r"([A-Za-z]:\\|/mnt/nas/|/home/|/root/)")
PRIVATE_MARKERS = ("password", "token", "secret", "credential", "api_key")


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(marker in lowered for marker in PRIVATE_MARKERS):
                out[str(key)] = "[redacted]"
            else:
                out[str(key)] = redact(item)
        return out
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return RAW_PATH_RE.sub("[redacted-path]", value)[:2000]
    return value


def has_raw_path(value: Any) -> bool:
    return bool(RAW_PATH_RE.search(json.dumps(value, ensure_ascii=False)))
