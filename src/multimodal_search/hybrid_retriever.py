from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .evidence_builder import build_result
from .feature_flags import MultimodalFeatureFlags
from .clip_embedding_adapter import load_image_text_model
from .query_planner import QueryPlan
from .schema import connect
from .vector_store import NumpyVectorStore


class HybridRetriever:
    def __init__(self, db_path: str | Path, *, vector_dir: str | Path, flags: MultimodalFeatureFlags | None = None) -> None:
        self.db_path = Path(db_path)
        self.vector_dir = Path(vector_dir)
        self.flags = flags or MultimodalFeatureFlags()
        self.image_model = load_image_text_model()
        self.vector_store = NumpyVectorStore(self.vector_dir)

    def search(self, plan: QueryPlan, *, top_k: int = 10) -> dict[str, Any]:
        fts_rows = self._fts(plan, top_k=top_k * 2)
        metadata_rows = self._metadata(plan, top_k=top_k * 2)
        image_rows: list[dict[str, Any]] = []
        degraded = False
        degraded_reason = None
        image_vectors_allowed = not plan.modality_filters or "image" in plan.modality_filters
        if image_vectors_allowed and self.flags.image_embedding_enabled and self.image_model.available:
            try:
                query_vec = self.image_model.embed_text(plan.visual_query_en)
                image_rows = self._image_vectors(query_vec, top_k=top_k * 2)
            except Exception as exc:
                degraded = True
                degraded_reason = f"image_embedding_search_failed:{type(exc).__name__}"
        elif image_vectors_allowed and self.flags.image_embedding_enabled:
            degraded = True
            degraded_reason = "image_embedding_model_unavailable"
        fused = self._fuse(fts_rows, image_rows, metadata_rows)
        results: list[dict[str, Any]] = []
        for rank, (asset_id, item) in enumerate(fused[:top_k], 1):
            row = self._asset(asset_id)
            if not row:
                continue
            if item.get("snippet_redacted"):
                row["snippet_redacted"] = item["snippet_redacted"]
            if row.get("modality") == "image":
                row["thumbnail_url"] = f"/api/multimodal-index/item/{asset_id}"
            matched_by = sorted(item["matched_by"])
            results.append(build_result(row, rank=rank, score=item["score"], matched_by=matched_by, components=item["components"]))
        return {
            "retrieval_mode": plan.retrieval_mode,
            "results": results,
            "degraded": degraded,
            "degraded_reason": degraded_reason,
        }

    def _fts(self, plan: QueryPlan, *, top_k: int) -> list[dict[str, Any]]:
        conn = connect(self.db_path)
        try:
            terms = " OR ".join(part.replace('"', "") for part in plan.original_terms if part.strip()) or plan.query_redacted
            try:
                rows = conn.execute(
                    """
                    SELECT a.asset_id, c.chunk_id, c.text_redacted, bm25(mm_text_chunks_fts) AS bm
                    FROM mm_text_chunks_fts f
                    JOIN mm_text_chunks c ON c.chunk_id = f.chunk_id
                    JOIN mm_assets a ON a.asset_id = c.asset_id
                    WHERE mm_text_chunks_fts MATCH ?
                    LIMIT ?
                    """,
                    (terms, top_k),
                ).fetchall()
            except Exception:
                rows = conn.execute(
                    """
                    SELECT a.asset_id, c.chunk_id, c.text_redacted, 1.0 AS bm
                    FROM mm_text_chunks c JOIN mm_assets a ON a.asset_id = c.asset_id
                    WHERE c.text_redacted LIKE ?
                    LIMIT ?
                    """,
                    (f"%{plan.query_redacted}%", top_k),
                ).fetchall()
        finally:
            conn.close()
        out = []
        for index, row in enumerate(rows):
            out.append({"asset_id": row["asset_id"], "score": 1.0 / (1 + index), "chunk_id": row["chunk_id"], "snippet_redacted": row["text_redacted"][:220], "method": "fts"})
        return out

    def _metadata(self, plan: QueryPlan, *, top_k: int) -> list[dict[str, Any]]:
        conn = connect(self.db_path)
        try:
            clauses = []
            args: list[Any] = []
            if plan.modality_filters:
                clauses.append("modality IN (%s)" % ",".join(["?"] * len(plan.modality_filters)))
                args.extend(plan.modality_filters)
            for term in plan.original_terms:
                if term:
                    clauses.append("(title_redacted LIKE ? OR modality LIKE ? OR file_type LIKE ?)")
                    args.extend([f"%{term}%", f"%{term}%", f"%{term}%"])
            where = "WHERE " + " OR ".join(clauses) if clauses else ""
            rows = conn.execute(f"SELECT * FROM mm_assets {where} LIMIT ?", (*args, top_k)).fetchall()
        finally:
            conn.close()
        return [{"asset_id": row["asset_id"], "score": 0.35 / (1 + idx), "method": "metadata"} for idx, row in enumerate(rows)]

    def _image_vectors(self, query_vec, *, top_k: int) -> list[dict[str, Any]]:
        rows = self.vector_store.search(
            query_vec,
            top_k=top_k,
            modality="image",
            model_id=self.image_model.get_model_identity()["model_name"],
        )
        return [{"asset_id": row["asset_id"], "score": row["score"], "method": "image_embedding"} for row in rows]

    def _asset(self, asset_id: str) -> dict[str, Any] | None:
        conn = connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM mm_assets WHERE asset_id=?", (asset_id,)).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return dict(row)

    def _fuse(self, *groups: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
        fused: dict[str, dict[str, Any]] = {}
        for group in groups:
            for rank, row in enumerate(group, 1):
                item = fused.setdefault(row["asset_id"], {"score": 0.0, "matched_by": set(), "components": {"fts": None, "image_embedding": None, "metadata": None}})
                method = row["method"]
                score = float(row["score"])
                item["score"] += 1.0 / (60 + rank) + score
                item["matched_by"].add(method)
                item["components"][method] = max(item["components"].get(method) or 0.0, score)
                if row.get("snippet_redacted"):
                    item["snippet_redacted"] = row["snippet_redacted"]
        return sorted(fused.items(), key=lambda item: item[1]["score"], reverse=True)
