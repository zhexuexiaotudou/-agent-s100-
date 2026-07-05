from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path
from typing import Any

from .privacy import private_leak_count, redact_text, stable_hash


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS rag_documents(
  document_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  relative_path_hash TEXT NOT NULL,
  file_type TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rag_chunks(
  chunk_id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  redacted_text TEXT NOT NULL,
  source_hash TEXT NOT NULL,
  private_leak_count INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY(document_id) REFERENCES rag_documents(document_id) ON DELETE CASCADE
);
CREATE VIRTUAL TABLE IF NOT EXISTS rag_chunks_fts USING fts5(chunk_id UNINDEXED, redacted_text, source_hash);
"""


TEXT_EXTS = {".txt", ".md", ".csv", ".json", ".log", ".py", ".js", ".html", ".css"}


def _terms(query: str) -> list[str]:
    return [part.lower() for part in re.findall(r"[\w\u4e00-\u9fff]{2,}", query) if len(part) >= 2][:8]


def _chunks(text: str, size: int = 700) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    return [text[i : i + size] for i in range(0, len(text), size)] if text else []


class AgentRuntimeRag:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def migrate(self) -> None:
        conn = self.connect()
        try:
            conn.executescript(SCHEMA_SQL)
            conn.commit()
        finally:
            conn.close()

    def sync_documents(self, root: str | Path, *, limit: int = 200) -> dict[str, Any]:
        self.migrate()
        root_path = Path(root)
        indexed_docs = 0
        indexed_chunks = 0
        conn = self.connect()
        try:
            for path in root_path.rglob("*") if root_path.exists() else []:
                if indexed_docs >= limit:
                    break
                if path.is_symlink() or not path.is_file() or path.suffix.lower() not in TEXT_EXTS:
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                    stat = path.stat()
                except OSError:
                    continue
                rel = path.relative_to(root_path).as_posix()
                doc_id = "rag_doc_" + stable_hash(rel, 24)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO rag_documents(document_id,title,relative_path_hash,file_type,updated_at)
                    VALUES(?,?,?,?,?)
                    """,
                    (doc_id, path.name, stable_hash(rel, 24), path.suffix.lower(), time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stat.st_mtime))),
                )
                old_ids = [row[0] for row in conn.execute("SELECT chunk_id FROM rag_chunks WHERE document_id=?", (doc_id,)).fetchall()]
                for chunk_id in old_ids:
                    conn.execute("DELETE FROM rag_chunks_fts WHERE chunk_id=?", (chunk_id,))
                conn.execute("DELETE FROM rag_chunks WHERE document_id=?", (doc_id,))
                for chunk_index, chunk in enumerate(_chunks(text)):
                    redacted, redactions = redact_text(chunk)
                    chunk_id = "rag_chk_" + stable_hash({"doc": doc_id, "index": chunk_index}, 24)
                    source_hash = stable_hash(f"{rel}:{chunk_index}", 24)
                    conn.execute(
                        """
                        INSERT INTO rag_chunks(chunk_id,document_id,chunk_index,redacted_text,source_hash,private_leak_count)
                        VALUES(?,?,?,?,?,?)
                        """,
                        (chunk_id, doc_id, chunk_index, redacted, source_hash, redactions),
                    )
                    conn.execute(
                        "INSERT INTO rag_chunks_fts(chunk_id,redacted_text,source_hash) VALUES(?,?,?)",
                        (chunk_id, redacted, source_hash),
                    )
                    indexed_chunks += 1
                indexed_docs += 1
            conn.commit()
        finally:
            conn.close()
        return {
            "ok": indexed_docs > 0,
            "retrieval_mode": "sqlite_fts_first",
            "indexed_documents": indexed_docs,
            "indexed_chunks": indexed_chunks,
            "embedding_enabled": False,
            "reranker_enabled": False,
            "db_path": str(self.db_path),
        }

    def query(self, query: str, *, limit: int = 6) -> dict[str, Any]:
        self.migrate()
        parts = _terms(query)
        if not parts:
            return {"ok": False, "error": "query_terms_empty", "evidence": [], "evidence_count": 0}
        match_query = " OR ".join(parts)
        conn = self.connect()
        try:
            try:
                rows = conn.execute(
                    """
                    SELECT c.chunk_id,c.redacted_text,c.source_hash,c.chunk_index,d.title,d.file_type,
                           bm25(rag_chunks_fts) AS rank
                    FROM rag_chunks_fts
                    JOIN rag_chunks c ON c.chunk_id = rag_chunks_fts.chunk_id
                    JOIN rag_documents d ON d.document_id = c.document_id
                    WHERE rag_chunks_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (match_query, limit),
                ).fetchall()
            except sqlite3.DatabaseError:
                like = f"%{parts[0]}%"
                rows = conn.execute(
                    """
                    SELECT c.chunk_id,c.redacted_text,c.source_hash,c.chunk_index,d.title,d.file_type,0 AS rank
                    FROM rag_chunks c JOIN rag_documents d ON d.document_id = c.document_id
                    WHERE c.redacted_text LIKE ?
                    LIMIT ?
                    """,
                    (like, limit),
                ).fetchall()
        finally:
            conn.close()
        evidence = []
        for index, row in enumerate(rows, start=1):
            snippet = str(row["redacted_text"])[:260]
            evidence.append(
                {
                    "evidence_ref": f"rag_ev_{index}_{str(row['source_hash'])[:10]}",
                    "chunk_id": row["chunk_id"],
                    "title": row["title"],
                    "file_type": row["file_type"],
                    "chunk_index": row["chunk_index"],
                    "source_hash": row["source_hash"],
                    "snippet": snippet,
                    "score": float(row["rank"] or 0),
                }
            )
        return {
            "ok": True,
            "query": query,
            "retrieval_mode": "sqlite_fts_first",
            "embedding_enabled": False,
            "reranker_enabled": False,
            "evidence": evidence,
            "evidence_refs": [item["evidence_ref"] for item in evidence],
            "evidence_count": len(evidence),
        }

    def answer(self, query: str) -> dict[str, Any]:
        result = self.query(query)
        evidence = result.get("evidence") or []
        if not evidence:
            answer = "No reliable local evidence was found. The runtime refuses to answer without evidence_refs."
            no_evidence_refusal = True
        else:
            refs = ", ".join(result.get("evidence_refs") or [])
            titles = ", ".join(item["title"] for item in evidence[:3])
            answer = f"Local FTS-first RAG found {len(evidence)} evidence chunks from {titles}. Evidence refs: {refs}."
            no_evidence_refusal = False
        payload = {
            "ok": True,
            "query": query,
            "answer": answer,
            "evidence": evidence,
            "evidence_refs": result.get("evidence_refs") or [],
            "evidence_count": len(evidence),
            "no_evidence_refusal": no_evidence_refusal,
            "retrieval_mode": result.get("retrieval_mode") or "sqlite_fts_first",
            "embedding_enabled": False,
            "reranker_enabled": False,
            "cloud_used": False,
            "qwen_execution_authority": False,
            "raw_private_content_returned": False,
        }
        payload["private_leak_count"] = private_leak_count(payload)
        return payload


def seed_rag_fixture(root: str | Path, *, count: int = 45) -> Path:
    base = Path(root)
    base.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        topic = ["harness", "memory", "multimodal", "privacy", "rollback"][index % 5]
        (base / f"rag_case_{index:02d}_{topic}.md").write_text(
            (
                f"Agent Runtime RAG case {index}. Topic {topic}. "
                "OpenClaw remains the gateway. Qwen is advisory only. "
                "The answer must cite evidence_refs and use SQLite FTS-first retrieval. "
                "Private raw NAS content is redacted before any optional cloud route.\n"
            ),
            encoding="utf-8",
        )
    return base
