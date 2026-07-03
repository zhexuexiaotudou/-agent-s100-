from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from .config_io import utc_stamp


VALID_MEMORY_TYPES = {"person", "case", "experience"}


class MemoryStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    def _init_schema(self) -> None:
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_records (
                    memory_id TEXT PRIMARY KEY,
                    memory_type TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    privacy_level TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_run_id TEXT,
                    expires_at TEXT,
                    long_term INTEGER NOT NULL DEFAULT 0,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            con.execute("CREATE INDEX IF NOT EXISTS idx_memory_scope ON memory_records(memory_type, scope, privacy_level)")
            con.commit()

    def write_memory(
        self,
        memory_type: str,
        scope: str,
        content: str,
        *,
        privacy_level: str = "none",
        source_run_id: str | None = None,
        expires_at: str | None = None,
        metadata: dict[str, Any] | None = None,
        allow_long_term: bool = False,
        policy_decision: str = "deny_by_default",
    ) -> dict[str, Any]:
        if memory_type not in VALID_MEMORY_TYPES:
            raise ValueError(f"invalid_memory_type:{memory_type}")
        if not allow_long_term:
            return {
                "status": "skipped",
                "reason": "long_term_memory_requires_policy_approval",
                "policy_decision": policy_decision,
                "memory_type": memory_type,
                "scope": scope,
            }
        memory_id = f"mem-{uuid.uuid4().hex[:16]}"
        now = utc_stamp()
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO memory_records(
                    memory_id, memory_type, scope, privacy_level, content, source_run_id,
                    expires_at, long_term, metadata_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    memory_type,
                    scope,
                    privacy_level,
                    content,
                    source_run_id,
                    expires_at,
                    1,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            con.commit()
        return {"status": "written", "memory_id": memory_id}

    def seed_memory(self, memory_type: str, scope: str, content: str, *, privacy_level: str = "none", source_run_id: str | None = None) -> str:
        result = self.write_memory(
            memory_type,
            scope,
            content,
            privacy_level=privacy_level,
            source_run_id=source_run_id,
            allow_long_term=True,
            policy_decision="seed_fixture",
        )
        return str(result["memory_id"])

    def read_memory(
        self,
        *,
        memory_type: str | None = None,
        scope: str | None = None,
        max_privacy_level: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if memory_type:
            clauses.append("memory_type = ?")
            params.append(memory_type)
        if scope:
            clauses.append("(scope = ? OR scope = 'global')")
            params.append(scope)
        privacy_rank = {"none": 0, "low": 1, "medium": 2, "high": 3}
        if max_privacy_level is not None:
            allowed = [key for key, rank in privacy_rank.items() if rank <= privacy_rank.get(max_privacy_level, 0)]
            clauses.append("privacy_level IN (%s)" % ",".join("?" for _ in allowed))
            params.extend(allowed)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self._connect() as con:
            rows = con.execute(
                f"SELECT * FROM memory_records{where} ORDER BY created_at DESC LIMIT ?",
                (*params, limit),
            ).fetchall()
        return [dict(row) for row in rows]

