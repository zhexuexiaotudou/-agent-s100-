from __future__ import annotations

from pathlib import Path


def audio_metadata(path: str | Path) -> dict:
    p = Path(path)
    return {"duration_sec": None, "codec": p.suffix.lower().lstrip(".") or "unknown", "metadata_mode": "metadata_only"}
