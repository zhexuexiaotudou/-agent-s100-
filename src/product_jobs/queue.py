from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any


JOB_TYPES = {
    "media_upload",
    "media_index",
    "multimodal_rebuild",
    "clip_embedding",
    "yolo_index",
    "person_attribute_rebuild",
    "subtitle_extract",
    "ai_space_rebuild",
    "smart_classification_rebuild",
    "smart_naming_generate",
    "smart_naming_batch",
    "journal_summary",
}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS product_jobs (
  job_id TEXT PRIMARY KEY,
  job_type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL,
  evidence_ref TEXT,
  error TEXT,
  attempt_count INTEGER NOT NULL DEFAULT 0,
  claimed_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""


class ProductJobQueue:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def migrate(self) -> None:
        conn = self.connect()
        try:
            conn.executescript(SCHEMA_SQL)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(product_jobs)")}
            if "attempt_count" not in columns:
                conn.execute("ALTER TABLE product_jobs ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0")
            if "claimed_at" not in columns:
                conn.execute("ALTER TABLE product_jobs ADD COLUMN claimed_at TEXT")
            conn.commit()
        finally:
            conn.close()

    def enqueue(self, job_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if job_type not in JOB_TYPES:
            return {"ok": False, "error": "unsupported_job_type", "supported_job_types": sorted(JOB_TYPES)}
        job_id = "job_" + uuid.uuid4().hex[:20]
        now = _now()
        conn = self.connect()
        try:
            conn.execute(
                "INSERT INTO product_jobs(job_id,job_type,payload_json,status,evidence_ref,error,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (job_id, job_type, json.dumps(payload or {}, ensure_ascii=False, sort_keys=True), "queued", None, None, now, now),
            )
            conn.commit()
        finally:
            conn.close()
        return {"ok": True, "job_id": job_id, "job_type": job_type, "status": "queued"}

    def status(self) -> dict[str, Any]:
        conn = self.connect()
        try:
            counts = {row["status"]: row["c"] for row in conn.execute("SELECT status,count(*) AS c FROM product_jobs GROUP BY status")}
        finally:
            conn.close()
        return {"ok": True, "schema": "digua_product_jobs_v1", "counts": counts, "supported_job_types": sorted(JOB_TYPES)}

    def recent(self, limit: int = 50) -> dict[str, Any]:
        conn = self.connect()
        try:
            rows = [self._row(dict(row)) for row in conn.execute("SELECT * FROM product_jobs ORDER BY created_at DESC LIMIT ?", (limit,))]
        finally:
            conn.close()
        return {"ok": True, "jobs": rows}

    def get(self, job_id: str) -> dict[str, Any]:
        conn = self.connect()
        try:
            row = conn.execute("SELECT * FROM product_jobs WHERE job_id=?", (job_id,)).fetchone()
        finally:
            conn.close()
        if row is None:
            return {"ok": False, "error": "not_found"}
        return {"ok": True, "job": self._row(dict(row))}

    def cancel(self, job_id: str) -> dict[str, Any]:
        now = _now()
        conn = self.connect()
        try:
            cur = conn.execute("UPDATE product_jobs SET status='cancelled',updated_at=? WHERE job_id=? AND status IN ('queued','running')", (now, job_id))
            conn.commit()
        finally:
            conn.close()
        return {"ok": cur.rowcount > 0, "job_id": job_id, "status": "cancelled" if cur.rowcount > 0 else "unchanged"}

    def claim_next(self, *, stale_after_seconds: int = 900) -> dict[str, Any]:
        now = _now()
        stale_before = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - max(1, stale_after_seconds)))
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "UPDATE product_jobs SET status='queued',error='worker_lease_expired',claimed_at=NULL,updated_at=? WHERE status='running' AND COALESCE(claimed_at,updated_at) < ?",
                (now, stale_before),
            )
            row = conn.execute("SELECT * FROM product_jobs WHERE status='queued' ORDER BY created_at,job_id LIMIT 1").fetchone()
            if row is None:
                conn.commit()
                return {"ok": True, "job": None}
            cur = conn.execute(
                "UPDATE product_jobs SET status='running',attempt_count=attempt_count+1,claimed_at=?,updated_at=?,error=NULL WHERE job_id=? AND status='queued'",
                (now, now, row["job_id"]),
            )
            if cur.rowcount != 1:
                conn.rollback()
                return {"ok": False, "error": "claim_race"}
            claimed = conn.execute("SELECT * FROM product_jobs WHERE job_id=?", (row["job_id"],)).fetchone()
            conn.commit()
            return {"ok": True, "job": self._row(dict(claimed))}
        finally:
            conn.close()

    def mark_running(self, job_id: str) -> dict[str, Any]:
        return self._set_status(job_id, "running")

    def complete(self, job_id: str, *, evidence_ref: str | None = None) -> dict[str, Any]:
        return self._set_status(job_id, "completed", evidence_ref=evidence_ref)

    def fail(self, job_id: str, error: str) -> dict[str, Any]:
        return self._set_status(job_id, "failed", error=error[:1000])

    def _set_status(self, job_id: str, status: str, *, evidence_ref: str | None = None, error: str | None = None) -> dict[str, Any]:
        now = _now()
        conn = self.connect()
        try:
            cur = conn.execute(
                "UPDATE product_jobs SET status=?,evidence_ref=COALESCE(?, evidence_ref),error=?,claimed_at=NULL,updated_at=? WHERE job_id=?",
                (status, evidence_ref, error, now, job_id),
            )
            conn.commit()
        finally:
            conn.close()
        return {"ok": cur.rowcount > 0, "job_id": job_id, "status": status if cur.rowcount > 0 else "not_found"}

    @staticmethod
    def _row(row: dict[str, Any]) -> dict[str, Any]:
        row["payload"] = json.loads(row.pop("payload_json") or "{}")
        return row


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
