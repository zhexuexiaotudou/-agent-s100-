from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Iterable

from .event_model import JournalEvent, utc_now
from .journal_migrations import load_schema_sql


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def _loads(text: str) -> Any:
    return json.loads(text) if text else None


class JournalDB:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def migrate(self) -> dict[str, Any]:
        with self.connect() as conn:
            conn.executescript(load_schema_sql())
            version = conn.execute("SELECT max(version) AS version FROM journal_schema_version").fetchone()["version"]
        return {"ok": True, "db_path": str(self.db_path), "schema_version": version}

    def insert_event(self, event: JournalEvent) -> str:
        event.validate()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO journal_events(
                  event_id, event_ts, source, event_type, project_id, folder_hash,
                  title, summary, evidence_refs_json, privacy_level, raw_content_stored,
                  denied, token_counts_json, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.event_ts,
                    event.source,
                    event.event_type,
                    event.project_id,
                    event.folder_hash,
                    event.title,
                    event.summary,
                    _json(event.evidence_refs),
                    event.privacy_level,
                    int(event.raw_content_stored),
                    int(event.denied),
                    _json(event.token_counts),
                    _json(event.metadata),
                    event.created_at,
                ),
            )
            conn.execute("DELETE FROM journal_events_fts WHERE event_id = ?", (event.event_id,))
            conn.execute(
                "INSERT INTO journal_events_fts(event_id, title, summary, project_id, source) VALUES (?, ?, ?, ?, ?)",
                (event.event_id, event.title, event.summary, event.project_id, event.source),
            )
        return event.event_id

    def insert_events(self, events: Iterable[JournalEvent]) -> list[str]:
        ids: list[str] = []
        for event in events:
            ids.append(self.insert_event(event))
        return ids

    def list_events(self, *, project_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        sql = "SELECT * FROM journal_events"
        params: list[Any] = []
        if project_id:
            sql += " WHERE project_id = ?"
            params.append(project_id)
        sql += " ORDER BY event_ts ASC, event_id ASC LIMIT ?"
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._event_row(row) for row in rows]

    def search_events(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT e.* FROM journal_events_fts f
                JOIN journal_events e ON e.event_id = f.event_id
                WHERE journal_events_fts MATCH ?
                ORDER BY e.event_ts DESC
                LIMIT ?
                """,
                (query, limit),
            ).fetchall()
        return [self._event_row(row) for row in rows]

    def insert_manual_entry(
        self,
        *,
        project_id: str,
        title: str,
        body: str,
        evidence_refs: list[str],
        privacy_level: str = "local_private",
        event_id: str | None = None,
    ) -> str:
        entry_id = "manual_" + uuid.uuid4().hex[:20]
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO journal_manual_entries(
                  entry_id, created_at, updated_at, project_id, title, body,
                  evidence_refs_json, privacy_level, event_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (entry_id, now, now, project_id, title, body, _json(evidence_refs), privacy_level, event_id),
            )
        return entry_id

    def list_manual_entries(self, *, project_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        sql = "SELECT * FROM journal_manual_entries"
        params: list[Any] = []
        if project_id:
            sql += " WHERE project_id = ?"
            params.append(project_id)
        sql += " ORDER BY created_at ASC LIMIT ?"
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            {
                "entry_id": row["entry_id"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "project_id": row["project_id"],
                "title": row["title"],
                "body": row["body"],
                "evidence_refs": _loads(row["evidence_refs_json"]) or [],
                "privacy_level": row["privacy_level"],
                "event_id": row["event_id"],
            }
            for row in rows
        ]

    def upsert_project(self, project_id: str, label: str, folder_hashes: list[str], *, manual_override: bool = False) -> None:
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO journal_project_map(project_id, label, folder_hashes_json, rule_version, manual_override, created_at, updated_at)
                VALUES (?, ?, ?, 'journal-classifier-v1', ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                  label=excluded.label,
                  folder_hashes_json=excluded.folder_hashes_json,
                  manual_override=excluded.manual_override,
                  updated_at=excluded.updated_at
                """,
                (project_id, label, _json(folder_hashes), int(manual_override), now, now),
            )

    def list_projects(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM journal_project_map ORDER BY project_id").fetchall()
        return [
            {
                "project_id": row["project_id"],
                "label": row["label"],
                "folder_hashes": _loads(row["folder_hashes_json"]) or [],
                "rule_version": row["rule_version"],
                "manual_override": bool(row["manual_override"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def insert_summary(self, summary: dict[str, Any]) -> str:
        summary_id = str(summary["summary_id"])
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO journal_summary_runs(
                  summary_id, period_type, period_start, period_end, project_id, title,
                  markdown, event_count, manual_entry_count, local_qwen_used, cloud_used,
                  token_trace_id, hallucinated_event_count, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    summary_id,
                    summary["period_type"],
                    summary["period_start"],
                    summary["period_end"],
                    summary["project_id"],
                    summary["title"],
                    summary["markdown"],
                    int(summary["event_count"]),
                    int(summary["manual_entry_count"]),
                    int(summary.get("local_qwen_used", True)),
                    int(summary.get("cloud_used", False)),
                    summary["token_trace_id"],
                    int(summary.get("hallucinated_event_count", 0)),
                    summary.get("created_at") or utc_now(),
                ),
            )
        return summary_id

    def list_summaries(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM journal_summary_runs ORDER BY created_at ASC").fetchall()
        return [dict(row) for row in rows]

    def insert_export(self, export: dict[str, Any]) -> str:
        export_id = str(export["export_id"])
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO journal_exports(
                  export_id, created_at, export_type, period_type, project_id,
                  path, sha256, private_leak_count, redaction_lookup_exported
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    export_id,
                    export.get("created_at") or utc_now(),
                    export["export_type"],
                    export["period_type"],
                    export["project_id"],
                    export["path"],
                    export["sha256"],
                    int(export.get("private_leak_count", 0)),
                    int(export.get("redaction_lookup_exported", False)),
                ),
            )
        return export_id

    def insert_token_privacy_trace(self, trace: dict[str, Any]) -> str:
        trace_id = str(trace["trace_id"])
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO journal_token_privacy_traces(
                  trace_id, created_at, route, cloud_allowed, prompt_tokens,
                  evidence_tokens, output_tokens, redaction_count, private_leak_count, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace_id,
                    trace.get("created_at") or utc_now(),
                    trace["route"],
                    int(trace.get("cloud_allowed", False)),
                    int(trace["prompt_tokens"]),
                    int(trace["evidence_tokens"]),
                    int(trace["output_tokens"]),
                    int(trace.get("redaction_count", 0)),
                    int(trace.get("private_leak_count", 0)),
                    _json(trace.get("metadata", {})),
                ),
            )
        return trace_id

    def stats(self) -> dict[str, int]:
        tables = [
            "journal_events",
            "journal_manual_entries",
            "journal_project_map",
            "journal_summary_runs",
            "journal_exports",
            "journal_token_privacy_traces",
        ]
        with self.connect() as conn:
            return {table: int(conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]) for table in tables}

    @staticmethod
    def _event_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "event_id": row["event_id"],
            "event_ts": row["event_ts"],
            "source": row["source"],
            "event_type": row["event_type"],
            "project_id": row["project_id"],
            "folder_hash": row["folder_hash"],
            "title": row["title"],
            "summary": row["summary"],
            "evidence_refs": _loads(row["evidence_refs_json"]) or [],
            "privacy_level": row["privacy_level"],
            "raw_content_stored": bool(row["raw_content_stored"]),
            "denied": bool(row["denied"]),
            "token_counts": _loads(row["token_counts_json"]) or {},
            "metadata": _loads(row["metadata_json"]) or {},
            "created_at": row["created_at"],
        }
