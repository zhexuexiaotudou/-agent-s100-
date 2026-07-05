from __future__ import annotations

import mimetypes
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .privacy import private_leak_count, redact_text, stable_hash


DOC_EXTS = {".txt", ".md", ".csv", ".json", ".log", ".pdf", ".docx"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm"}
AUDIO_EXTS = {".mp3", ".wav", ".flac", ".m4a"}
CODE_EXTS = {".py", ".js", ".ts", ".html", ".css", ".sh", ".json"}
ARCHIVE_EXTS = {".zip", ".tar", ".gz", ".7z"}


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS multimodal_items(
  item_id TEXT PRIMARY KEY,
  basename TEXT NOT NULL,
  extension TEXT NOT NULL,
  media_type TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  relative_path_hash TEXT NOT NULL,
  content_hash_prefix TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  mtime_epoch REAL NOT NULL,
  text_extract_status TEXT NOT NULL,
  thumbnail_status TEXT NOT NULL,
  ocr_status TEXT NOT NULL,
  embedding_status TEXT NOT NULL,
  raw_path_exported INTEGER NOT NULL DEFAULT 0,
  raw_content_stored INTEGER NOT NULL DEFAULT 0,
  private_leak_count INTEGER NOT NULL DEFAULT 0
);
CREATE VIRTUAL TABLE IF NOT EXISTS multimodal_items_fts USING fts5(item_id UNINDEXED, basename, media_type, extension);
"""


@dataclass(frozen=True)
class MultimodalPolicy:
    thumbnail_enabled: bool = False
    ocr_enabled: bool = False
    embedding_enabled: bool = False
    max_items: int = 500


def classify(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in DOC_EXTS:
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


class MultimodalIndex:
    def __init__(self, db_path: str | Path, *, policy: MultimodalPolicy | None = None) -> None:
        self.db_path = Path(db_path)
        self.policy = policy or MultimodalPolicy()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def migrate(self) -> None:
        conn = self.connect()
        try:
            conn.executescript(SCHEMA_SQL)
            conn.commit()
        finally:
            conn.close()

    def scan(self, root: str | Path) -> dict[str, Any]:
        self.migrate()
        root_path = Path(root)
        counts: dict[str, int] = {"document": 0, "image": 0, "video": 0, "audio": 0, "code": 0, "archive": 0, "other": 0}
        indexed = 0
        skipped = 0
        conn = self.connect()
        try:
            for path in root_path.rglob("*") if root_path.exists() else []:
                if indexed >= self.policy.max_items:
                    skipped += 1
                    continue
                if path.is_symlink() or not path.is_file():
                    continue
                media_type = classify(path)
                try:
                    stat = path.stat()
                    raw = path.read_bytes()[:8192]
                except OSError:
                    skipped += 1
                    continue
                rel = path.relative_to(root_path).as_posix()
                safe_name, name_redactions = redact_text(path.name)
                item_id = "mm_" + stable_hash({"rel": rel, "mtime": stat.st_mtime, "size": stat.st_size}, 20)
                text_extract_status = "extractable" if media_type in {"document", "code"} else "metadata_only"
                thumbnail_status = "pending_disabled" if media_type in {"image", "video"} and not self.policy.thumbnail_enabled else "not_required"
                ocr_status = "pending_disabled" if media_type == "image" and not self.policy.ocr_enabled else "not_required"
                embedding_status = "pending_disabled" if not self.policy.embedding_enabled else "queued_local_only"
                private_count = name_redactions
                conn.execute(
                    """
                    INSERT OR REPLACE INTO multimodal_items(
                      item_id,basename,extension,media_type,mime_type,relative_path_hash,content_hash_prefix,
                      size_bytes,mtime_epoch,text_extract_status,thumbnail_status,ocr_status,embedding_status,
                      raw_path_exported,raw_content_stored,private_leak_count
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        item_id,
                        safe_name,
                        path.suffix.lower(),
                        media_type,
                        mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                        stable_hash(rel, 24),
                        stable_hash(raw.hex(), 16),
                        int(stat.st_size),
                        float(stat.st_mtime),
                        text_extract_status,
                        thumbnail_status,
                        ocr_status,
                        embedding_status,
                        0,
                        0,
                        private_count,
                    ),
                )
                conn.execute("DELETE FROM multimodal_items_fts WHERE item_id=?", (item_id,))
                conn.execute(
                    "INSERT INTO multimodal_items_fts(item_id,basename,media_type,extension) VALUES(?,?,?,?)",
                    (item_id, safe_name, media_type, path.suffix.lower()),
                )
                counts[media_type] = counts.get(media_type, 0) + 1
                indexed += 1
            conn.commit()
        finally:
            conn.close()
        return {
            "ok": indexed > 0 and private_leak_count(counts) == 0,
            "schema": "digua_agent_runtime_multimodal_index_v1",
            "db_path": str(self.db_path),
            "indexed_count": indexed,
            "skipped_count": skipped,
            "counts": counts,
            "feature_flags": {
                "thumbnail_enabled": self.policy.thumbnail_enabled,
                "ocr_enabled": self.policy.ocr_enabled,
                "embedding_enabled": self.policy.embedding_enabled,
            },
            "raw_path_exported": False,
            "raw_content_stored": False,
            "qwen_execution_authority": False,
            "cloud_private_raw_egress": False,
        }

    def status(self) -> dict[str, Any]:
        self.migrate()
        conn = self.connect()
        try:
            rows = conn.execute("SELECT media_type, count(*) AS c FROM multimodal_items GROUP BY media_type").fetchall()
            raw_path_rows = conn.execute("SELECT count(*) FROM multimodal_items WHERE raw_path_exported != 0 OR raw_content_stored != 0").fetchone()[0]
            leaks = conn.execute("SELECT coalesce(sum(private_leak_count), 0) FROM multimodal_items").fetchone()[0]
        finally:
            conn.close()
        counts = {row["media_type"]: row["c"] for row in rows}
        return {
            "ok": raw_path_rows == 0 and leaks == 0,
            "db_path": str(self.db_path),
            "counts": counts,
            "indexed_count": sum(counts.values()),
            "raw_path_rows": raw_path_rows,
            "private_leak_count": leaks,
            "feature_flags": {
                "thumbnail_enabled": self.policy.thumbnail_enabled,
                "ocr_enabled": self.policy.ocr_enabled,
                "embedding_enabled": self.policy.embedding_enabled,
            },
        }

    def search(self, query: str, *, limit: int = 10) -> dict[str, Any]:
        self.migrate()
        terms = " OR ".join(part.replace('"', "") for part in query.split() if part.strip()) or query
        conn = self.connect()
        try:
            try:
                rows = conn.execute(
                    """
                    SELECT i.* FROM multimodal_items_fts f
                    JOIN multimodal_items i ON i.item_id = f.item_id
                    WHERE multimodal_items_fts MATCH ?
                    LIMIT ?
                    """,
                    (terms, limit),
                ).fetchall()
            except sqlite3.DatabaseError:
                rows = conn.execute(
                    "SELECT * FROM multimodal_items WHERE basename LIKE ? OR media_type LIKE ? LIMIT ?",
                    (f"%{query}%", f"%{query}%", limit),
                ).fetchall()
        finally:
            conn.close()
        items = [
            {
                "item_id": row["item_id"],
                "basename": row["basename"],
                "media_type": row["media_type"],
                "extension": row["extension"],
                "relative_path_hash": row["relative_path_hash"],
                "raw_path_exported": False,
            }
            for row in rows
        ]
        return {"ok": True, "query": query, "items": items, "count": len(items)}


def seed_multimodal_fixture(root: str | Path) -> Path:
    base = Path(root)
    base.mkdir(parents=True, exist_ok=True)
    for index in range(12):
        (base / "Documents").mkdir(exist_ok=True)
        (base / "Documents" / f"runtime_policy_{index}.md").write_text(
            f"Agent Runtime document {index}. OpenClaw gateway, FTS-first RAG, evidence refs, dispatcher-only copy.\n",
            encoding="utf-8",
        )
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"0" * 128
    for index in range(10):
        (base / "Photos").mkdir(exist_ok=True)
        (base / "Photos" / f"image_runtime_{index}.png").write_bytes(png_bytes + bytes([index]))
    for index in range(3):
        (base / "Movies").mkdir(exist_ok=True)
        (base / "Movies" / f"runtime_clip_{index}.mp4").write_bytes(b"mp4" + os.urandom(32))
        (base / "Audio").mkdir(exist_ok=True)
        (base / "Audio" / f"runtime_audio_{index}.mp3").write_bytes(b"mp3" + os.urandom(32))
    (base / "Code").mkdir(exist_ok=True)
    (base / "Code" / "agent_runtime_probe.py").write_text("print('agent runtime fixture')\n", encoding="utf-8")
    (base / "Archives").mkdir(exist_ok=True)
    (base / "Archives" / "runtime_bundle.zip").write_bytes(b"PK\x03\x04" + os.urandom(32))
    now = time.time()
    for path in base.rglob("*"):
        if path.is_file():
            os.utime(path, (now, now))
    return base
