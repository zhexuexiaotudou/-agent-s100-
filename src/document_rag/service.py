from __future__ import annotations

import hashlib
import re
import sqlite3
from pathlib import Path
from typing import Any


def terms_for_query(query: str) -> list[str]:
    text = re.sub(r"[^\w\u4e00-\u9fff]+", " ", str(query or ""), flags=re.UNICODE)
    return [part for part in text.split() if part][:12]


def fts_query(query: str) -> str:
    terms = terms_for_query(query)
    return " OR ".join(f'"{term}"' for term in terms)


class DocumentRagService:
    def __init__(self, *, report_root: str | Path, personal_root: str | Path | None = None) -> None:
        self.report_root = Path(report_root)
        self.personal_root = Path(personal_root) if personal_root else None
        self.db_path = self.report_root / "document_fts.sqlite3"

    def status(self) -> dict[str, Any]:
        stats = {"document_count": 0, "chunk_count": 0}
        if self.db_path.exists():
            try:
                with sqlite3.connect(str(self.db_path)) as conn:
                    stats["document_count"] = int(conn.execute("SELECT count(*) FROM documents").fetchone()[0])
                    stats["chunk_count"] = int(conn.execute("SELECT count(*) FROM document_chunks").fetchone()[0])
            except sqlite3.Error:
                stats["degraded_reason"] = "document_fts_unreadable"
        return {
            "ok": True,
            "schema": "digua_document_rag_status_v1",
            "route_module": "src.openclaw.routes.document_rag_routes",
            "retrieval_mode": "sqlite_fts_first",
            "document_count": stats["document_count"],
            "chunk_count": stats["chunk_count"],
            "fts_db_hash": hashlib.sha256(str(self.db_path).encode("utf-8", errors="replace")).hexdigest()[:16],
            "cloud_ocr_enabled": False,
            "cloud_used": False,
            "raw_private_content_returned": False,
            "raw_path_returned": False,
            **({"degraded": True, "degraded_reason": stats["degraded_reason"]} if stats.get("degraded_reason") else {"degraded": False}),
        }

    def query(self, query: str, *, relative_path: str = "Documents", top_k: int = 8) -> dict[str, Any]:
        query = str(query or "").strip()
        if not query:
            return self._no_grounded("query_required", relative_path=relative_path)
        if not self.db_path.exists():
            return self._no_grounded("document_fts_db_missing", relative_path=relative_path)
        match = fts_query(query)
        if not match:
            return self._no_grounded("query_terms_empty", relative_path=relative_path)
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT c.id AS chunk_id,c.redacted_text,c.source_hash,c.chunk_index,
                           d.title,d.relative_path,d.file_type,bm25(document_chunks_fts) AS rank
                    FROM document_chunks_fts
                    JOIN document_chunks c ON c.id=document_chunks_fts.chunk_id
                    JOIN documents d ON d.id=c.document_id
                    WHERE document_chunks_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (match, int(top_k)),
                ).fetchall()
        except sqlite3.Error as exc:
            return self._no_grounded(f"document_fts_query_failed:{type(exc).__name__}", relative_path=relative_path)
        evidence = []
        terms = terms_for_query(query)
        for index, row in enumerate(rows, start=1):
            rel = str(row["relative_path"] or "")
            if relative_path and relative_path not in {"", "."} and not rel.startswith(str(relative_path).strip("/")):
                continue
            snippet = _snippet(str(row["redacted_text"] or ""), terms)
            evidence.append(
                {
                    "evidence_ref": f"ev_{index}_{str(row['source_hash'])[:10]}",
                    "chunk_id": row["chunk_id"],
                    "name": row["title"],
                    "relative_path_hash": hashlib.sha256(rel.encode("utf-8", errors="replace")).hexdigest()[:16],
                    "extension": row["file_type"],
                    "chunk_index": row["chunk_index"],
                    "source_hash": row["source_hash"],
                    "snippet": snippet,
                    "score": float(row["rank"] or 0),
                }
            )
        if not evidence:
            return self._no_grounded("no_grounded_answer", relative_path=relative_path)
        names = ", ".join(str(item.get("name") or item.get("relative_path_hash")) for item in evidence[:3])
        refs = ", ".join(item["evidence_ref"] for item in evidence)
        return {
            "ok": True,
            "schema": "digua_document_rag_query_v1",
            "route_module": "src.openclaw.routes.document_rag_routes",
            "answer": f"Local SQLite FTS RAG found {len(evidence)} grounded evidence chunk(s): {names}. Evidence refs: {refs}.",
            "evidence_refs": [item["evidence_ref"] for item in evidence],
            "retrieved_chunks": evidence,
            "no_grounded_answer": False,
            "retrieval_mode": "sqlite_fts_first",
            "cloud_ocr_enabled": False,
            "cloud_used": False,
            "raw_private_content_returned": False,
            "raw_path_returned": False,
        }

    @staticmethod
    def _no_grounded(error: str, *, relative_path: str) -> dict[str, Any]:
        return {
            "ok": False,
            "schema": "digua_document_rag_query_v1",
            "route_module": "src.openclaw.routes.document_rag_routes",
            "error": error,
            "answer": "",
            "path": relative_path,
            "evidence_refs": [],
            "retrieved_chunks": [],
            "no_grounded_answer": True,
            "retrieval_mode": "sqlite_fts_first",
            "cloud_ocr_enabled": False,
            "cloud_used": False,
            "raw_private_content_returned": False,
            "raw_path_returned": False,
        }


def _snippet(text: str, terms: list[str], *, max_chars: int = 220) -> str:
    lower = text.lower()
    index = 0
    for term in terms:
        found = lower.find(term.lower())
        if found >= 0:
            index = max(0, found - 60)
            break
    return text[index : index + max_chars]
