from __future__ import annotations

import hashlib
import mimetypes
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DOCUMENT_EXTS = {".pdf", ".docx", ".txt", ".md", ".xlsx", ".pptx", ".csv"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".flac"}
CODE_EXTS = {".py", ".js", ".ts", ".json", ".yaml", ".yml", ".md", ".css", ".html", ".sh"}
ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".tar", ".gz"}
PRIVATE_MARKERS = ("password", "token", "credential", "secret", "api_key", "private")


@dataclass(frozen=True)
class ScannedAsset:
    asset_id: str
    root: Path
    path: Path
    modality: str
    file_type: str
    title_redacted: str
    path_hash: str
    parent_hash: str
    size_bytes: int
    mtime: int
    sha256: str
    mime_type: str


def hash_text(value: str, length: int = 24) -> str:
    return hashlib.sha256(value.encode("utf-8", "surrogateescape")).hexdigest()[:length]


def hash_path(path: Path, root: Path) -> str:
    return hash_text(path.resolve().relative_to(root.resolve()).as_posix(), 32)


def redact_title(name: str) -> str:
    redacted = name
    lower = name.lower()
    for marker in PRIVATE_MARKERS:
        if marker in lower:
            redacted = redacted.replace(marker, "[redacted]")
            redacted = redacted.replace(marker.upper(), "[REDACTED]")
    return redacted[:160]


def classify_file_modality(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in DOCUMENT_EXTS:
        return "document"
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    if ext in AUDIO_EXTS:
        return "audio"
    if ext in CODE_EXTS:
        return "code"
    if ext in ARCHIVE_EXTS:
        return "archive"
    return "other"


def calculate_file_sha256_limited_or_full(path: Path, *, max_bytes: int = 4 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        remaining = max_bytes
        while remaining > 0:
            chunk = handle.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            digest.update(chunk)
            remaining -= len(chunk)
    return digest.hexdigest()


def scan_nas_sources(root_allowlist: Iterable[str | Path], *, max_files: int = 5000) -> list[ScannedAsset]:
    assets: list[ScannedAsset] = []
    for raw_root in root_allowlist:
        root = Path(raw_root)
        if not root.exists():
            continue
        root_base = root.parent if root.is_file() else root
        paths = [root] if root.is_file() else root.rglob("*")
        for path in paths:
            if len(assets) >= max_files:
                return assets
            if path.is_symlink() or not path.is_file():
                continue
            try:
                resolved = path.resolve()
                resolved.relative_to(root_base.resolve())
                stat = path.stat()
            except Exception:
                continue
            modality = classify_file_modality(path)
            rel = resolved.relative_to(root_base.resolve()).as_posix()
            p_hash = hash_text(rel, 32)
            assets.append(
                ScannedAsset(
                    asset_id="mm_" + hash_text(f"{rel}:{stat.st_size}:{int(stat.st_mtime)}", 24),
                    root=root_base,
                    path=path,
                    modality=modality,
                    file_type=path.suffix.lower().lstrip(".") or "unknown",
                    title_redacted=redact_title(path.name),
                    path_hash=p_hash,
                    parent_hash=hash_text(str(Path(rel).parent), 24),
                    size_bytes=int(stat.st_size),
                    mtime=int(stat.st_mtime or time.time()),
                    sha256=calculate_file_sha256_limited_or_full(path),
                    mime_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                )
            )
    return assets
