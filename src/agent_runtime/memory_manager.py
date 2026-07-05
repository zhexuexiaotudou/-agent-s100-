from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Iterable

from .privacy import private_leak_count, redact_text, stable_hash


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS memory_schema_version(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
INSERT OR IGNORE INTO memory_schema_version(version, applied_at) VALUES(1, datetime('now'));

CREATE TABLE IF NOT EXISTS memory_events(
  event_id TEXT PRIMARY KEY,
  event_ts TEXT NOT NULL,
  memory_type TEXT NOT NULL,
  title TEXT NOT NULL,
  summary TEXT NOT NULL,
  evidence_refs_json TEXT NOT NULL,
  source_hash TEXT NOT NULL,
  privacy_level TEXT NOT NULL,
  raw_content_stored INTEGER NOT NULL DEFAULT 0,
  private_leak_count INTEGER NOT NULL DEFAULT 0,
  metadata_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_facts(
  fact_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  statement TEXT NOT NULL,
  confidence REAL NOT NULL,
  evidence_refs_json TEXT NOT NULL,
  raw_content_stored INTEGER NOT NULL DEFAULT 0,
  private_leak_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS memory_procedures(
  procedure_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  title TEXT NOT NULL,
  steps_json TEXT NOT NULL,
  evidence_refs_json TEXT NOT NULL,
  raw_content_stored INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS memory_preferences(
  preference_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  preference TEXT NOT NULL,
  scope TEXT NOT NULL,
  evidence_refs_json TEXT NOT NULL,
  raw_content_stored INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS memory_reflections(
  reflection_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  reflection TEXT NOT NULL,
  next_action TEXT NOT NULL,
  evidence_refs_json TEXT NOT NULL,
  raw_content_stored INTEGER NOT NULL DEFAULT 0
);

CREATE VIRTUAL TABLE IF NOT EXISTS memory_events_fts USING fts5(event_id UNINDEXED, title, summary, memory_type);
"""


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class AgentMemoryManager:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def migrate(self) -> dict[str, Any]:
        conn = self.connect()
        try:
            conn.executescript(SCHEMA_SQL)
            conn.commit()
        finally:
            conn.close()
        return {"ok": True, "db_path": str(self.db_path), "schema": "agent_runtime_memory_v1"}

    def record_event(
        self,
        *,
        memory_type: str,
        title: str,
        summary: str,
        evidence_refs: Iterable[str] | None = None,
        source: str = "agent_runtime",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.migrate()
        safe_title, title_redactions = redact_text(title)
        safe_summary, summary_redactions = redact_text(summary)
        safe_metadata = {}
        for key, value in (metadata or {}).items():
            if str(key).lower() in {"raw_content", "raw_path", "redaction_map", "secret"}:
                safe_metadata[f"{key}_omitted"] = True
                continue
            safe_value, _ = redact_text(value) if isinstance(value, str) else (value, 0)
            safe_metadata[str(key)] = safe_value
        event_id = "mem_evt_" + stable_hash({"title": safe_title, "summary": safe_summary, "ts": _now(), "nonce": uuid.uuid4().hex}, 20)
        record = {
            "event_id": event_id,
            "event_ts": _now(),
            "memory_type": memory_type,
            "title": safe_title,
            "summary": safe_summary,
            "evidence_refs": list(evidence_refs or []),
            "source_hash": stable_hash(source, 24),
            "privacy_level": "local_private_redacted",
            "raw_content_stored": False,
            "private_leak_count": title_redactions + summary_redactions + private_leak_count(safe_metadata),
            "metadata": safe_metadata,
        }
        conn = self.connect()
        try:
            conn.execute(
                """
                INSERT INTO memory_events(
                  event_id,event_ts,memory_type,title,summary,evidence_refs_json,source_hash,
                  privacy_level,raw_content_stored,private_leak_count,metadata_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    record["event_id"],
                    record["event_ts"],
                    record["memory_type"],
                    record["title"],
                    record["summary"],
                    _json(record["evidence_refs"]),
                    record["source_hash"],
                    record["privacy_level"],
                    0,
                    int(record["private_leak_count"]),
                    _json(record["metadata"]),
                ),
            )
            conn.execute(
                "INSERT INTO memory_events_fts(event_id,title,summary,memory_type) VALUES(?,?,?,?)",
                (record["event_id"], record["title"], record["summary"], record["memory_type"]),
            )
            conn.commit()
        finally:
            conn.close()
        record["ok"] = record["private_leak_count"] == 0
        return record

    def promote_fact(self, statement: str, evidence_refs: Iterable[str], *, confidence: float = 0.8) -> dict[str, Any]:
        self.migrate()
        safe_statement, redactions = redact_text(statement)
        fact_id = "mem_fact_" + stable_hash({"statement": safe_statement, "evidence": list(evidence_refs)}, 20)
        conn = self.connect()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO memory_facts(
                  fact_id,created_at,statement,confidence,evidence_refs_json,raw_content_stored,private_leak_count
                ) VALUES(?,?,?,?,?,?,?)
                """,
                (fact_id, _now(), safe_statement, float(confidence), _json(list(evidence_refs)), 0, redactions),
            )
            conn.commit()
        finally:
            conn.close()
        return {"ok": redactions == 0, "fact_id": fact_id, "private_leak_count": redactions}

    def record_procedure(self, title: str, steps: Iterable[str], evidence_refs: Iterable[str]) -> dict[str, Any]:
        self.migrate()
        safe_title, title_redactions = redact_text(title)
        safe_steps: list[str] = []
        redactions = title_redactions
        for step in steps:
            safe, count = redact_text(step)
            safe_steps.append(safe)
            redactions += count
        procedure_id = "mem_proc_" + stable_hash({"title": safe_title, "steps": safe_steps}, 20)
        conn = self.connect()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO memory_procedures(
                  procedure_id,created_at,title,steps_json,evidence_refs_json,raw_content_stored
                ) VALUES(?,?,?,?,?,?)
                """,
                (procedure_id, _now(), safe_title, _json(safe_steps), _json(list(evidence_refs)), 0),
            )
            conn.commit()
        finally:
            conn.close()
        return {"ok": redactions == 0, "procedure_id": procedure_id, "private_leak_count": redactions}

    def record_preference(self, preference: str, scope: str, evidence_refs: Iterable[str]) -> dict[str, Any]:
        self.migrate()
        safe_preference, redactions = redact_text(preference)
        preference_id = "mem_pref_" + stable_hash({"preference": safe_preference, "scope": scope}, 20)
        conn = self.connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO memory_preferences VALUES(?,?,?,?,?,?)",
                (preference_id, _now(), safe_preference, scope, _json(list(evidence_refs)), 0),
            )
            conn.commit()
        finally:
            conn.close()
        return {"ok": redactions == 0, "preference_id": preference_id, "private_leak_count": redactions}

    def record_reflection(self, reflection: str, next_action: str, evidence_refs: Iterable[str]) -> dict[str, Any]:
        self.migrate()
        safe_reflection, r1 = redact_text(reflection)
        safe_next, r2 = redact_text(next_action)
        reflection_id = "mem_ref_" + stable_hash({"reflection": safe_reflection, "next_action": safe_next}, 20)
        conn = self.connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO memory_reflections VALUES(?,?,?,?,?,?)",
                (reflection_id, _now(), safe_reflection, safe_next, _json(list(evidence_refs)), 0),
            )
            conn.commit()
        finally:
            conn.close()
        return {"ok": (r1 + r2) == 0, "reflection_id": reflection_id, "private_leak_count": r1 + r2}

    def stats(self) -> dict[str, Any]:
        self.migrate()
        conn = self.connect()
        try:
            counts = {
                "events": conn.execute("SELECT count(*) FROM memory_events").fetchone()[0],
                "facts": conn.execute("SELECT count(*) FROM memory_facts").fetchone()[0],
                "procedures": conn.execute("SELECT count(*) FROM memory_procedures").fetchone()[0],
                "preferences": conn.execute("SELECT count(*) FROM memory_preferences").fetchone()[0],
                "reflections": conn.execute("SELECT count(*) FROM memory_reflections").fetchone()[0],
                "raw_content_rows": conn.execute("SELECT count(*) FROM memory_events WHERE raw_content_stored != 0").fetchone()[0],
                "private_leak_count": conn.execute("SELECT coalesce(sum(private_leak_count), 0) FROM memory_events").fetchone()[0],
            }
        finally:
            conn.close()
        counts.update(
            {
                "ok": counts["raw_content_rows"] == 0 and counts["private_leak_count"] == 0,
                "db_path": str(self.db_path),
                "schema": "agent_runtime_memory_v1",
                "qwen_execution_authority": False,
                "cloud_private_raw_egress": False,
            }
        )
        return counts


def seed_memory(manager: AgentMemoryManager, *, event_count: int = 50) -> dict[str, Any]:
    for index in range(event_count):
        manager.record_event(
            memory_type=["fact", "procedure", "preference", "reflection"][index % 4],
            title=f"Agent Runtime event {index}",
            summary=f"OpenClaw gateway and Harness policy event {index} with no raw NAS path stored.",
            evidence_refs=[f"ev_mem_{index}"],
            source=f"agent_runtime_seed_{index}",
        )
    for index in range(12):
        manager.promote_fact(f"Runtime fact {index}: Qwen remains advisory and dispatcher-only actions stay bounded.", [f"ev_fact_{index}"])
    for index in range(6):
        manager.record_procedure(
            f"Runtime procedure {index}",
            ["Compile context pack", "Retrieve with FTS-first RAG", "Return evidence refs only"],
            [f"ev_proc_{index}"],
        )
        manager.record_preference(f"Preference {index}: keep privacy-first local default.", "agent_runtime", [f"ev_pref_{index}"])
        manager.record_reflection(f"Reflection {index}: evaluate before rollout.", "Run S100P smoke and safety regression.", [f"ev_ref_{index}"])
    return manager.stats()
