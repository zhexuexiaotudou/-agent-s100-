#!/usr/bin/env python3
"""AI-NAS Backup & Sync layer — folder sync, scheduled tasks, incremental backup, restore."""
from __future__ import annotations
import hashlib, json, os, shutil, sqlite3, time
from datetime import datetime, timezone
from pathlib import Path

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _now_compact() -> str:
    return time.strftime("%Y%m%d-%H%M%S")

def _init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript("""
        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS backup_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            source_path TEXT NOT NULL,
            dest_path TEXT NOT NULL,
            schedule_interval_seconds INTEGER DEFAULT 0,
            last_run_at TEXT,
            last_run_status TEXT DEFAULT 'never',
            last_run_files_copied INTEGER DEFAULT 0,
            last_run_bytes_copied INTEGER DEFAULT 0,
            last_run_error TEXT,
            created_at TEXT NOT NULL,
            enabled INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS backup_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL REFERENCES backup_tasks(id) ON DELETE CASCADE,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL DEFAULT 'running',
            files_scanned INTEGER DEFAULT 0,
            files_copied INTEGER DEFAULT 0,
            bytes_copied INTEGER DEFAULT 0,
            files_skipped INTEGER DEFAULT 0,
            error TEXT,
            restore_point_path TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_runs_task ON backup_runs(task_id);
    """)
    con.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('schema_version','1')")
    con.commit(); con.close()


class BackupManager:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        _init_db(db_path)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.db_path))
        con.execute("PRAGMA foreign_keys=ON")
        con.row_factory = sqlite3.Row
        return con

    # ── Task management ────────────────────────────────────

    def create_task(self, name: str, source: str, dest: str, interval_seconds: int = 0) -> dict:
        if not name or not source or not dest:
            return {"ok": False, "error": "name_source_dest_required"}
        src = Path(source); dst = Path(dest)
        if not src.exists():
            return {"ok": False, "error": "source_not_found"}
        con = self._connect()
        try:
            con.execute(
                "INSERT INTO backup_tasks(name, source_path, dest_path, schedule_interval_seconds, created_at) VALUES(?,?,?,?,?)",
                (name, str(src), str(dst), interval_seconds, _now_iso()),
            )
            con.commit()
            tid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
            return {"ok": True, "task": {"id": tid, "name": name, "source": str(src), "dest": str(dst)}}
        except sqlite3.IntegrityError:
            return {"ok": False, "error": "task_name_exists"}
        finally:
            con.close()

    def list_tasks(self) -> list[dict]:
        con = self._connect()
        try:
            rows = con.execute("SELECT * FROM backup_tasks ORDER BY name").fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()

    def delete_task(self, name: str) -> dict:
        con = self._connect()
        try:
            cur = con.execute("DELETE FROM backup_tasks WHERE name=?", (name,))
            con.commit()
            return {"ok": cur.rowcount > 0}
        finally:
            con.close()

    # ── Backup execution ───────────────────────────────────

    def run_backup(self, task_name: str) -> dict:
        """Execute a backup task: copy new/changed files from source to dest."""
        con = self._connect()
        try:
            task = con.execute("SELECT * FROM backup_tasks WHERE name=?", (task_name,)).fetchone()
            if not task:
                return {"ok": False, "error": "task_not_found"}
            src = Path(task["source_path"]); dst = Path(task["dest_path"]); dst.mkdir(parents=True, exist_ok=True)
            started = _now_iso()
            rid = con.execute(
                "INSERT INTO backup_runs(task_id, started_at, status) VALUES(?,?,?)",
                (task["id"], started, "running"),
            ).lastrowid
            con.commit()
        finally:
            con.close()

        scanned, copied, skipped, bytes_copied = 0, 0, 0, 0
        error = None; restore_point_dir = None
        try:
            if not src.exists():
                raise FileNotFoundError(str(src))
            if src.is_file():
                restore_point_dir = dst / f"restore_{_now_compact()}"
                restore_point_dir.mkdir(parents=True, exist_ok=True)
                for f in src.parent.rglob(src.name):
                    scanned += 1
                    dest_file = restore_point_dir / f.name
                    if dest_file.exists() and self._files_equal(f, dest_file):
                        skipped += 1
                    else:
                        shutil.copy2(str(f), str(dest_file))
                        copied += 1
                        bytes_copied += dest_file.stat().st_size
            else:
                # Snapshot restore point before sync
                restore_point_dir = dst / f"restore_{_now_compact()}"
                restore_point_dir.mkdir(parents=True, exist_ok=True)
                for f in src.rglob("*"):
                    if f.is_file():
                        scanned += 1; rel = f.relative_to(src).as_posix()
                        dest_file = dst / rel
                        if dest_file.exists() and self._files_equal(f, dest_file):
                            skipped += 1
                        else:
                            dest_file.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(str(f), str(dest_file))
                            copied += 1
                            bytes_copied += dest_file.stat().st_size
            status = "completed"
        except Exception as e:
            status = "failed"; error = f"{type(e).__name__}:{e}"

        con = self._connect()
        try:
            con.execute(
                "UPDATE backup_runs SET finished_at=?, status=?, files_scanned=?, files_copied=?, bytes_copied=?, files_skipped=?, error=?, restore_point_path=? WHERE id=?",
                (_now_iso(), status, scanned, copied, bytes_copied, skipped, error, str(restore_point_dir) if restore_point_dir else None, rid),
            )
            con.execute(
                "UPDATE backup_tasks SET last_run_at=?, last_run_status=?, last_run_files_copied=?, last_run_bytes_copied=?, last_run_error=? WHERE id=?",
                (_now_iso(), status, copied, bytes_copied, error, task["id"]),
            )
            con.commit()
        finally:
            con.close()
        return {"ok": status == "completed", "status": status, "run_id": rid, "scanned": scanned, "copied": copied, "skipped": skipped, "bytes_copied": bytes_copied, "restore_point": str(restore_point_dir) if restore_point_dir else None, "error": error}

    def list_runs(self, task_name: str | None = None, limit: int = 50) -> list[dict]:
        con = self._connect()
        try:
            if task_name:
                rows = con.execute(
                    "SELECT r.*, t.name as task_name FROM backup_runs r JOIN backup_tasks t ON r.task_id=t.id WHERE t.name=? ORDER BY r.started_at DESC LIMIT ?",
                    (task_name, limit),
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT r.*, t.name as task_name FROM backup_runs r JOIN backup_tasks t ON r.task_id=t.id ORDER BY r.started_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()

    def restore_from_run(self, run_id: int, target_path: str | None = None) -> dict:
        """Restore files from backup destination to the original or target path."""
        con = self._connect()
        try:
            run = con.execute("SELECT r.*, t.source_path, t.dest_path FROM backup_runs r JOIN backup_tasks t ON r.task_id=t.id WHERE r.id=?", (run_id,)).fetchone()
            if not run: return {"ok": False, "error": "run_not_found"}
            if run["status"] != "completed": return {"ok": False, "error": "run_not_completed"}
            src = Path(run["dest_path"])
            if not src.exists(): return {"ok": False, "error": "backup_dest_missing"}
            target = Path(target_path) if target_path else Path(run["source_path"])
            target.mkdir(parents=True, exist_ok=True)
            count = 0
            for f in src.rglob("*"):
                if f.is_file():
                    rel = f.relative_to(src).as_posix()
                    dest = target / rel; dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(f), str(dest)); count += 1
            return {"ok": True, "restored_files": count, "target": str(target)}
        finally:
            con.close()

    def check_due_tasks(self) -> list[dict]:
        """Return tasks that are due for scheduled execution."""
        con = self._connect()
        try:
            rows = con.execute(
                "SELECT * FROM backup_tasks WHERE enabled=1 AND schedule_interval_seconds > 0 AND (last_run_at IS NULL OR datetime(last_run_at, '+' || schedule_interval_seconds || ' seconds') <= datetime('now'))"
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []
        finally:
            con.close()

    def _files_equal(self, a: Path, b: Path) -> bool:
        try:
            if a.stat().st_size != b.stat().st_size: return False
            return a.stat().st_mtime == b.stat().st_mtime or hashlib.sha256(a.read_bytes()).digest() == hashlib.sha256(b.read_bytes()).digest()
        except OSError:
            return False

    def stats(self) -> dict:
        con = self._connect()
        try:
            tasks = con.execute("SELECT COUNT(*) FROM backup_tasks").fetchone()[0]
            runs = con.execute("SELECT COUNT(*) FROM backup_runs").fetchone()[0]
            return {"task_count": tasks, "run_count": runs}
        finally:
            con.close()
