from __future__ import annotations

from pathlib import Path


def archive_metadata(path: str | Path) -> dict:
    p = Path(path)
    return {"archive_type": p.suffix.lower().lstrip(".") or "unknown", "extraction_performed": False, "safe_mode": True}
