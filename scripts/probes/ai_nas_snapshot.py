#!/usr/bin/env python3
"""AI-NAS Snapshot, Trash, and Version Recovery layer.

Provides:
- TrashManager: intercepts deletes, moves files to .trash/ instead of unlinking
- VersionTracker: saves old versions before overwrites in .versions/
- SnapshotManager: creates point-in-time directory snapshots in .snapshots/
- Recovery: restore single files or entire directories from trash/versions/snapshots
"""
from __future__ import annotations
import hashlib, json, os, shutil, sqlite3, time
from datetime import datetime, timedelta, timezone
from pathlib import Path

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _parse_iso(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)

def _now_compact() -> str:
    return time.strftime("%Y%m%d-%H%M%S")

def _now_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")

def _init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript("""
        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS trash_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_path TEXT NOT NULL,
            trash_path TEXT NOT NULL,
            username TEXT NOT NULL DEFAULT '',
            size_bytes INTEGER NOT NULL DEFAULT 0,
            sha256 TEXT,
            deleted_at TEXT NOT NULL,
            restored_at TEXT,
            expires_at TEXT
        );
        CREATE TABLE IF NOT EXISTS file_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_path TEXT NOT NULL,
            version_path TEXT NOT NULL,
            version_number INTEGER NOT NULL,
            size_bytes INTEGER NOT NULL DEFAULT 0,
            sha256 TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            path TEXT NOT NULL,
            source_path TEXT NOT NULL DEFAULT '',
            file_count INTEGER NOT NULL DEFAULT 0,
            total_size_bytes INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            creator TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS snapshot_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
            relative_path TEXT NOT NULL,
            size_bytes INTEGER,
            sha256 TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_trash_original ON trash_entries(original_path);
        CREATE INDEX IF NOT EXISTS idx_trash_deleted ON trash_entries(deleted_at);
        CREATE INDEX IF NOT EXISTS idx_versions_path ON file_versions(original_path);
        CREATE INDEX IF NOT EXISTS idx_snapshot_files_snap ON snapshot_files(snapshot_id);
    """)
    try:
        con.execute("ALTER TABLE trash_entries ADD COLUMN expires_at TEXT")
    except sqlite3.OperationalError:
        pass
    con.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('schema_version','1')")
    con.commit(); con.close()


class SnapshotStore:
    """Thread-safe trash/version/snapshot manager backed by SQLite + filesystem."""

    def __init__(self, personal_root: Path, db_path: Path | None = None) -> None:
        self.personal_root = personal_root.resolve(strict=False)
        self.db_path = db_path or (personal_root / ".snapshots" / "recovery.db")
        self.trash_root = personal_root / ".trash"
        self.versions_root = personal_root / ".versions"
        self.snapshots_root = personal_root / ".snapshots"
        self.trash_root.mkdir(parents=True, exist_ok=True)
        self.versions_root.mkdir(parents=True, exist_ok=True)
        self.snapshots_root.mkdir(parents=True, exist_ok=True)
        _init_db(self.db_path)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.db_path))
        con.execute("PRAGMA foreign_keys=ON")
        con.row_factory = sqlite3.Row
        return con

    def _relative_to_personal_root(self, file_path: Path) -> str:
        try:
            return file_path.resolve(strict=False).relative_to(self.personal_root).as_posix()
        except ValueError:
            return file_path.name

    # ── Trash ──────────────────────────────────────────────

    def trash_file(self, file_path: Path, username: str = "") -> dict:
        """Move a file to the trash instead of deleting it permanently."""
        if not file_path.exists() or not file_path.is_file():
            return {"ok": False, "error": "file_not_found"}
        size = file_path.stat().st_size
        rel = self._relative_to_personal_root(file_path)
        ts = _now_timestamp()
        trash_name = f"{ts}_{file_path.name}"
        trash_path = self.trash_root / trash_name
        expires_at = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        shutil.move(str(file_path), str(trash_path))
        sha = self._hash_file(trash_path)
        con = self._connect()
        try:
            con.execute(
                "INSERT INTO trash_entries(original_path, trash_path, username, size_bytes, sha256, deleted_at, expires_at) VALUES(?,?,?,?,?,?,?)",
                (rel, trash_name, username, size, sha, _now_iso(), expires_at),
            )
            con.commit()
            eid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
            return {"ok": True, "trash_id": eid, "original_path": rel, "trash_name": trash_name, "size_bytes": size, "expires_at": expires_at}
        finally:
            con.close()

    def list_trash(self, username: str = "") -> list[dict]:
        con = self._connect()
        try:
            if username:
                rows = con.execute(
                    "SELECT id, original_path, trash_path, username, size_bytes, sha256, deleted_at, restored_at, expires_at FROM trash_entries WHERE restored_at IS NULL AND username=? ORDER BY deleted_at DESC",
                    (username,),
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT id, original_path, trash_path, username, size_bytes, sha256, deleted_at, restored_at, expires_at FROM trash_entries WHERE restored_at IS NULL ORDER BY deleted_at DESC"
                ).fetchall()
            return [dict(row) for row in rows]
        finally:
            con.close()

    def restore_from_trash(self, trash_id: int) -> dict:
        con = self._connect()
        try:
            row = con.execute(
                "SELECT id, original_path, trash_path, restored_at FROM trash_entries WHERE id=? AND restored_at IS NULL",
                (trash_id,),
            ).fetchone()
            if not row:
                return {"ok": False, "error": "trash_entry_not_found_or_already_restored"}
            trash_file = self.trash_root / row["trash_path"]
            if not trash_file.exists():
                return {"ok": False, "error": "trash_file_missing_from_disk"}
            original = self.personal_root / row["original_path"]
            original.parent.mkdir(parents=True, exist_ok=True)
            if original.exists():
                return {"ok": False, "error": "original_path_already_exists"}
            shutil.move(str(trash_file), str(original))
            con.execute("UPDATE trash_entries SET restored_at=? WHERE id=?", (_now_iso(), trash_id))
            con.commit()
            return {"ok": True, "restored_to": row["original_path"]}
        finally:
            con.close()

    def empty_trash(self, username: str = "") -> dict:
        con = self._connect()
        try:
            if username:
                rows = con.execute(
                    "SELECT id, trash_path FROM trash_entries WHERE restored_at IS NULL AND username=?",
                    (username,),
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT id, trash_path FROM trash_entries WHERE restored_at IS NULL"
                ).fetchall()
            count = 0
            for row in rows:
                fp = self.trash_root / row["trash_path"]
                if fp.exists():
                    fp.unlink()
                con.execute("UPDATE trash_entries SET restored_at=? WHERE id=?", (_now_iso(), row["id"]))
                count += 1
            con.commit()
            return {"ok": True, "emptied": count}
        finally:
            con.close()

    def cleanup_expired_trash(self, retention_days: int = 30, *, now: datetime | None = None) -> dict:
        """Permanently remove unrestored trash entries older than the retention window."""
        try:
            days = max(1, min(int(retention_days), 365))
        except (TypeError, ValueError):
            days = 30
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        cutoff = current - timedelta(days=days)
        cutoff_iso = cutoff.isoformat()
        con = self._connect()
        try:
            rows = con.execute(
                """
                SELECT id, trash_path, deleted_at, expires_at
                FROM trash_entries
                WHERE restored_at IS NULL
                  AND (
                    (expires_at IS NOT NULL AND expires_at <= ?)
                    OR (expires_at IS NULL AND deleted_at <= ?)
                  )
                """,
                (current.isoformat(), cutoff_iso),
            ).fetchall()
            removed = 0
            missing = 0
            for row in rows:
                fp = self.trash_root / row["trash_path"]
                if fp.exists():
                    fp.unlink()
                    removed += 1
                else:
                    missing += 1
                con.execute("UPDATE trash_entries SET restored_at=? WHERE id=?", (current.isoformat(), row["id"]))
            con.commit()
            return {
                "ok": True,
                "removed": removed,
                "missing": missing,
                "retention_days": days,
                "cutoff": cutoff_iso,
            }
        finally:
            con.close()

    # ── Versioning ─────────────────────────────────────────

    def save_version(self, file_path: Path) -> dict:
        """Save the current version of a file before it gets overwritten."""
        if not file_path.exists() or not file_path.is_file():
            return {"ok": False, "error": "file_not_found"}
        rel = self._relative_to_personal_root(file_path)
        ts = _now_timestamp()
        version_name = f"{ts}_{file_path.name}"
        version_subdir = self.versions_root / rel
        version_subdir.parent.mkdir(parents=True, exist_ok=True)
        version_path = self.versions_root / f"{rel}.v{ts}"
        version_path.parent.mkdir(parents=True, exist_ok=True)
        size = file_path.stat().st_size
        shutil.copy2(str(file_path), str(version_path))
        sha = self._hash_file(version_path)
        con = self._connect()
        try:
            existing = con.execute(
                "SELECT COALESCE(MAX(version_number), 0) + 1 FROM file_versions WHERE original_path=?",
                (rel,),
            ).fetchone()[0]
            con.execute(
                "INSERT INTO file_versions(original_path, version_path, version_number, size_bytes, sha256, created_at) VALUES(?,?,?,?,?,?)",
                (rel, str(version_path.relative_to(self.personal_root)) if self._is_under(version_path, self.personal_root) else str(version_path), existing, size, sha, _now_iso()),
            )
            con.commit()
            vid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
            return {"ok": True, "version_id": vid, "version_number": existing, "original_path": rel, "size_bytes": size}
        finally:
            con.close()

    def list_versions(self, relative_path: str) -> list[dict]:
        con = self._connect()
        try:
            rows = con.execute(
                "SELECT id, original_path, version_path, version_number, size_bytes, sha256, created_at FROM file_versions WHERE original_path=? ORDER BY version_number DESC",
                (relative_path,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            con.close()

    def restore_version(self, version_id: int) -> dict:
        con = self._connect()
        try:
            row = con.execute(
                "SELECT id, original_path, version_path, version_number FROM file_versions WHERE id=?",
                (version_id,),
            ).fetchone()
            if not row:
                return {"ok": False, "error": "version_not_found"}
            vp = row["version_path"]
            version_file = self.personal_root / vp if not Path(vp).is_absolute() else Path(vp)
            if not version_file.exists():
                version_file = self.versions_root / f"{row['original_path']}.v{row['version_number']}"
                for f in Path(self.versions_root).glob(f"{row['original_path']}.v*"):
                    version_file = f; break
            if not version_file.exists():
                return {"ok": False, "error": "version_file_missing_from_disk"}
            original = self.personal_root / row["original_path"]
            original.parent.mkdir(parents=True, exist_ok=True)
            if original.exists():
                self.save_version(original)
            shutil.copy2(str(version_file), str(original))
            return {"ok": True, "restored_to": row["original_path"], "version_number": row["version_number"]}
        finally:
            con.close()

    # ── Snapshots ──────────────────────────────────────────

    def create_snapshot(self, name: str, source_path: str = "", creator: str = "") -> dict:
        """Create a point-in-time snapshot of a directory."""
        if not name or "/" in name or "\\" in name:
            return {"ok": False, "error": "invalid_snapshot_name"}
        source = self.personal_root / source_path if source_path else self.personal_root
        if not source.exists():
            return {"ok": False, "error": "source_path_not_found"}
        snap_dir = self.snapshots_root / name
        if snap_dir.exists():
            return {"ok": False, "error": "snapshot_already_exists"}
        snap_dir.mkdir(parents=True, exist_ok=True)
        file_count = 0; total_size = 0
        con = self._connect()
        try:
            con.execute(
                "INSERT INTO snapshots(name, path, source_path, file_count, total_size_bytes, created_at, creator) VALUES(?,?,?,?,?,?,?)",
                (name, str(snap_dir.relative_to(self.personal_root)) if self._is_under(snap_dir, self.personal_root) else str(snap_dir), source_path, 0, 0, _now_iso(), creator),
            )
            snap_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
            for f in source.rglob("*"):
                if f.is_file():
                    try:
                        rel = f.relative_to(source).as_posix()
                    except ValueError:
                        rel = f.name
                    dest = snap_dir / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(f), str(dest))
                    sz = f.stat().st_size
                    file_count += 1; total_size += sz
                    con.execute(
                        "INSERT INTO snapshot_files(snapshot_id, relative_path, size_bytes, sha256) VALUES(?,?,?,?)",
                        (snap_id, rel, sz, self._hash_file(dest)),
                    )
            con.execute(
                "UPDATE snapshots SET file_count=?, total_size_bytes=? WHERE id=?",
                (file_count, total_size, snap_id),
            )
            con.commit()
            return {"ok": True, "snapshot": {"id": snap_id, "name": name, "file_count": file_count, "total_size": total_size}}
        finally:
            con.close()

    def list_snapshots(self) -> list[dict]:
        con = self._connect()
        try:
            rows = con.execute(
                "SELECT id, name, path, source_path, file_count, total_size_bytes, created_at, creator FROM snapshots ORDER BY created_at DESC"
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            con.close()

    def browse_snapshot(self, snapshot_name: str, relative_path: str = "") -> dict:
        con = self._connect()
        try:
            row = con.execute("SELECT id, name, path FROM snapshots WHERE name=?", (snapshot_name,)).fetchone()
            if not row:
                return {"ok": False, "error": "snapshot_not_found"}
            snap_dir = self.snapshots_root / snapshot_name / relative_path
            if not snap_dir.exists():
                return {"ok": False, "error": "path_not_in_snapshot"}
            files = con.execute(
                "SELECT relative_path, size_bytes, sha256 FROM snapshot_files WHERE snapshot_id=? AND relative_path LIKE ?",
                (row["id"], (relative_path + "/" if relative_path else "") + "%"),
            ).fetchall()
            return {"ok": True, "snapshot": row["name"], "path": relative_path or "/", "files": [dict(f) for f in files]}
        finally:
            con.close()

    def restore_from_snapshot(self, snapshot_name: str, relative_path: str, target: str = "") -> dict:
        """Restore a file or directory from a snapshot."""
        con = self._connect()
        try:
            row = con.execute("SELECT id, name, path FROM snapshots WHERE name=?", (snapshot_name,)).fetchone()
            if not row:
                return {"ok": False, "error": "snapshot_not_found"}
            snap_file = self.snapshots_root / snapshot_name / relative_path
            if not snap_file.exists():
                return {"ok": False, "error": "file_not_in_snapshot"}
            if target:
                target_path = self.personal_root / target
            else:
                target_path = self.personal_root / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            if target_path.exists() and target_path.is_file():
                self.save_version(target_path)
            if snap_file.is_dir():
                shutil.copytree(str(snap_file), str(target_path), dirs_exist_ok=True)
                return {"ok": True, "restored_to": str(target_path.relative_to(self.personal_root)), "type": "directory"}
            else:
                shutil.copy2(str(snap_file), str(target_path))
                return {"ok": True, "restored_to": str(target_path.relative_to(self.personal_root)), "type": "file"}
        finally:
            con.close()

    def delete_snapshot(self, name: str) -> dict:
        con = self._connect()
        try:
            row = con.execute("SELECT id, name FROM snapshots WHERE name=?", (name,)).fetchone()
            if not row:
                return {"ok": False, "error": "snapshot_not_found"}
            snap_dir = self.snapshots_root / name
            if snap_dir.exists():
                shutil.rmtree(str(snap_dir))
            con.execute("DELETE FROM snapshots WHERE id=?", (row["id"],))
            con.commit()
            return {"ok": True}
        finally:
            con.close()

    # ── helpers ────────────────────────────────────────────

    def _hash_file(self, path: Path) -> str | None:
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            return None

    def _is_under(self, path: Path, root: Path) -> bool:
        try: path.relative_to(root); return True
        except ValueError: return False

    def stats(self) -> dict:
        con = self._connect()
        try:
            trash_count = con.execute("SELECT COUNT(*) FROM trash_entries WHERE restored_at IS NULL").fetchone()[0]
            version_count = con.execute("SELECT COUNT(*) FROM file_versions").fetchone()[0]
            snap_count = con.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
            return {"trash_count": trash_count, "version_count": version_count, "snapshot_count": snap_count}
        finally:
            con.close()
