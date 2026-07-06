from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .naming_policy import normalize_rel


SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".mp3",
    ".wav",
    ".m4a",
    ".pdf",
    ".docx",
    ".txt",
    ".md",
    ".csv",
    ".xlsx",
    ".pptx",
}


def collect_source_files(personal_root: Path, source_root: str, *, limit: int, source_rel_paths: Iterable[str] | None = None) -> list[Path]:
    if source_rel_paths:
        files: list[Path] = []
        for rel in source_rel_paths:
            normalized = normalize_rel(rel)
            path = personal_root / normalized
            if path.exists() and path.is_file() and not path.is_symlink():
                files.append(path)
            if len(files) >= limit:
                break
        return files
    root = personal_root / normalize_rel(source_root)
    if not root.exists():
        return []
    out: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        out.append(path)
        if len(out) >= limit:
            break
    return out
