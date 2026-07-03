#!/usr/bin/env python3
"""Lightweight vector store for AI-NAS using SQLite + numpy.

Stores text documents with embedding vectors and supports:
- Indexing: add documents with pre-computed embeddings
- Search: cosine similarity search over stored vectors
- Evidence: every result carries score, source path, backend info
"""

from __future__ import annotations

import json
import sqlite3
import struct
import time
from pathlib import Path

import numpy as np

SCHEMA_VERSION = "ai_nas_vector_store_v1"


def _ensure_schema(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vector_docs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id TEXT UNIQUE NOT NULL,
            text TEXT NOT NULL,
            metadata_json TEXT DEFAULT '{}',
            vector_dim INTEGER NOT NULL,
            vector_blob BLOB NOT NULL,
            indexed_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_vector_docs_doc_id ON vector_docs(doc_id)")
    conn.commit()


def _vector_to_blob(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def _blob_to_vector(blob: bytes) -> list[float]:
    n = len(blob) // 4
    return list(struct.unpack(f"{n}f", blob))


class VectorStore:
    """SQLite-backed vector store for document embeddings."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        _ensure_schema(self._conn)

    def close(self):
        self._conn.close()

    @property
    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) as cnt FROM vector_docs").fetchone()
        return row["cnt"] if row else 0

    def index_document(self, doc_id: str, text: str, vector: list[float], metadata: dict | None = None) -> dict:
        blob = _vector_to_blob(vector)
        meta = json.dumps(metadata or {}, ensure_ascii=False)
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        try:
            self._conn.execute(
                "INSERT OR REPLACE INTO vector_docs (doc_id, text, metadata_json, vector_dim, vector_blob, indexed_at) VALUES (?, ?, ?, ?, ?, ?)",
                (doc_id, text, meta, len(vector), blob, now),
            )
            self._conn.commit()
            return {"ok": True, "doc_id": doc_id, "action": "indexed"}
        except Exception as e:
            return {"ok": False, "doc_id": doc_id, "error": str(e)}

    def index_batch(self, items: list[dict]) -> dict:
        """Batch index. Each item: {doc_id, text, vector, metadata?}"""
        indexed = 0
        errors = []
        for item in items:
            result = self.index_document(
                item["doc_id"], item["text"], item["vector"], item.get("metadata")
            )
            if result["ok"]:
                indexed += 1
            else:
                errors.append(result)
        return {"ok": len(errors) == 0, "indexed": indexed, "errors": errors}

    def search(self, query_vector: list[float], top_k: int = 10, min_score: float = 0.01) -> dict:
        """Cosine similarity search. Returns ranked results with evidence."""
        query_np = np.array(query_vector)
        q_norm = np.linalg.norm(query_np)
        if q_norm == 0:
            return {"ok": True, "results": [], "evidence": {"backend": "vector_store", "total_docs": self.count, "error": "zero_query_vector"}}

        rows = self._conn.execute(
            "SELECT doc_id, text, metadata_json, vector_dim, vector_blob FROM vector_docs"
        ).fetchall()

        results = []
        for row in rows:
            doc_vec = np.array(_blob_to_vector(row["vector_blob"]))
            d_norm = np.linalg.norm(doc_vec)
            if d_norm == 0:
                continue
            score = float(np.dot(query_np, doc_vec) / (q_norm * d_norm))
            if score < min_score:
                continue
            results.append({
                "doc_id": row["doc_id"],
                "text": row["text"][:200],
                "score": round(score, 4),
                "metadata": json.loads(row["metadata_json"]) if row["metadata_json"] else {},
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        results = results[:top_k]

        return {
            "ok": True,
            "results": results,
            "evidence": {
                "backend": "vector_store_sqlite",
                "schema_version": SCHEMA_VERSION,
                "total_docs": self.count,
                "returned": len(results),
                "query_dim": len(query_vector),
            },
        }

    def semantic_search(self, query: str, top_k: int = 10, *, embedding_provider=None) -> dict:
        """End-to-end semantic search: embed query, then vector search."""
        if embedding_provider is None:
            from ai_nas_text_embedding_provider import embed_text
            embedding_provider = embed_text
        emb_result = embedding_provider(query)
        if not emb_result.get("ok"):
            return {"ok": False, "error": "embedding_failed", "results": [], "evidence": {}}
        vec_result = self.search(emb_result["vector"], top_k=top_k)
        vec_result["evidence"]["embedding_backend"] = emb_result.get("backend", "unknown")
        return vec_result

    def delete_document(self, doc_id: str) -> dict:
        self._conn.execute("DELETE FROM vector_docs WHERE doc_id = ?", (doc_id,))
        self._conn.commit()
        return {"ok": True, "doc_id": doc_id, "action": "deleted"}

    def status(self) -> dict:
        return {
            "backend": "vector_store_sqlite",
            "schema_version": SCHEMA_VERSION,
            "db_path": str(self.db_path),
            "doc_count": self.count,
            "dim": self._get_dim(),
        }

    def _get_dim(self) -> int:
        row = self._conn.execute("SELECT vector_dim FROM vector_docs LIMIT 1").fetchone()
        return row["vector_dim"] if row else 0


# ---- smoke test ----
if __name__ == "__main__":
    import sys, tempfile
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from ai_nas_text_embedding_provider import embed_text
    tmp = Path(tempfile.gettempdir()) / "ai_nas_vector_store_test.sqlite3"
    store = VectorStore(tmp)
    docs = ["装修合同样本", "航空旅行数据", "发票报销凭证", "厨房改造协议", "公司财务年报"]
    for i, doc in enumerate(docs):
        emb = embed_text(doc)
        store.index_document(f"doc_{i}", doc, emb["vector"])
    results = store.semantic_search("装修合同")
    print(f"Search '装修合同': {store.count} docs indexed")
    for r in results.get("results", []):
        print(f"  {r['score']:.4f} {r['text']}")
    store.close()
    tmp.unlink(missing_ok=True)
    print("Smoke test passed")
