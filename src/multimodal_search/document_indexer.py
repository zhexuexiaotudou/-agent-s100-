from __future__ import annotations

from pathlib import Path


TEXT_EXTS = {".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".py", ".js", ".ts", ".css", ".html", ".sh"}


def extract_text(path: str | Path, *, max_chars: int = 12000) -> str:
    p = Path(path)
    if p.suffix.lower() not in TEXT_EXTS:
        return ""
    try:
        return p.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except Exception:
        return ""


def chunk_text(text: str, *, chunk_size: int = 900) -> list[str]:
    clean = " ".join((text or "").split())
    if not clean:
        return []
    return [clean[index : index + chunk_size] for index in range(0, len(clean), chunk_size)]
