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


GENERIC_MODALITY_TERMS = {
    "image",
    "images",
    "photo",
    "photos",
    "picture",
    "pictures",
    "video",
    "videos",
    "document",
    "documents",
    "audio",
    "code",
    "\u56fe\u7247",
    "\u7167\u7247",
    "\u56fe\u50cf",
    "\u89c6\u9891",
    "\u6587\u6863",
    "\u97f3\u9891",
}


def select_relevant_image_rows(
    rows: list[dict[str, Any]],
    *,
    min_score: float,
    relative_margin: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ranked = sorted(rows, key=lambda row: float(row.get("score") or 0.0), reverse=True)
    top_score = float(ranked[0].get("score") or 0.0) if ranked else 0.0
    threshold = max(float(min_score), top_score - max(0.0, float(relative_margin)))
    selected = [row for row in ranked if float(row.get("score") or 0.0) >= threshold] if top_score >= float(min_score) else []
    return selected, {
        "candidate_count": len(ranked),
        "selected_count": len(selected),
        "filtered_low_relevance_count": len(ranked) - len(selected),
        "top_score": round(top_score, 6),
        "effective_threshold": round(threshold, 6),
        "absolute_min_score": float(min_score),
        "relative_margin": float(relative_margin),
    }


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
        relevance_policy: dict[str, Any] = {
            "policy": "evidence_only",
            "candidate_count": 0,
            "selected_count": 0,
            "filtered_low_relevance_count": 0,
            "variant_count": 0,
            "variant_thresholds": [],
        }
        degraded = False
        degraded_reason = None
        image_vectors_allowed = not plan.modality_filters or "image" in plan.modality_filters
        if image_vectors_allowed and not plan.visual_semantic_search_supported:
            relevance_policy = {
                **relevance_policy,
                "policy": "unsupported_chinese_visual_concept",
            }
            degraded = True
            degraded_reason = "unsupported_chinese_visual_concept"
        elif image_vectors_allowed and self.flags.image_embedding_enabled and self.image_model.available:
            try:
                image_rows, relevance_policy = self._image_vectors(plan, top_k=top_k * 2)
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
            "relevance_policy": relevance_policy,
        }

    @staticmethod
    def _content_terms(plan: QueryPlan) -> list[str]:
        terms: list[str] = []
        for raw in plan.original_terms:
            term = str(raw or "").strip()
            if not term or term.lower() in GENERIC_MODALITY_TERMS:
                continue
            if term not in terms:
                terms.append(term)
        return terms

    def _fts(self, plan: QueryPlan, *, top_k: int) -> list[dict[str, Any]]:
        conn = connect(self.db_path)
        try:
            content_terms = self._content_terms(plan)
            terms = " OR ".join(part.replace('"', "") for part in content_terms) or plan.query_redacted
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
            modality_clauses: list[str] = []
            term_clauses: list[str] = []
            args: list[Any] = []
            if plan.modality_filters:
                modality_clauses.append("modality IN (%s)" % ",".join(["?"] * len(plan.modality_filters)))
                args.extend(plan.modality_filters)
            term_args: list[Any] = []
            for term in self._content_terms(plan):
                if term:
                    term_clauses.append("(title_redacted LIKE ? OR file_type LIKE ?)")
                    term_args.extend([f"%{term}%", f"%{term}%"])
            allow_modality_only_fallback = bool(plan.modality_filters) and "image" not in plan.modality_filters
            if not term_clauses:
                if not allow_modality_only_fallback:
                    return []
                where = "WHERE " + " AND ".join(modality_clauses)
                rows = conn.execute(f"SELECT * FROM mm_assets {where} LIMIT ?", (*args, top_k)).fetchall()
                return [{"asset_id": row["asset_id"], "score": 0.35 / (1 + idx), "method": "metadata"} for idx, row in enumerate(rows)]
            clauses = modality_clauses + ["(" + " OR ".join(term_clauses) + ")"]
            args.extend(term_args)
            where = "WHERE " + " AND ".join(clauses)
            rows = conn.execute(f"SELECT * FROM mm_assets {where} LIMIT ?", (*args, top_k)).fetchall()
            if not rows and allow_modality_only_fallback:
                fallback_args = list(plan.modality_filters)
                fallback_where = "WHERE " + " AND ".join(modality_clauses)
                rows = conn.execute(f"SELECT * FROM mm_assets {fallback_where} LIMIT ?", (*fallback_args, top_k)).fetchall()
        finally:
            conn.close()
        return [{"asset_id": row["asset_id"], "score": 0.35 / (1 + idx), "method": "metadata"} for idx, row in enumerate(rows)]

    def _image_vectors(self, plan: QueryPlan, *, top_k: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        identity = self.image_model.get_model_identity()
        model_name = identity["model_name"]
        min_score = float(self.flags.image_semantic_min_score)
        relative_margin = float(self.flags.image_semantic_relative_margin)
        selected_by_asset: dict[str, dict[str, Any]] = {}
        candidate_assets: set[str] = set()
        variant_policies: list[dict[str, Any]] = []
        queries = plan.visual_query_variants_en
        for query in queries:
            query_vec = self.image_model.embed_text(query)
            candidates = self.vector_store.search(
                query_vec,
                top_k=top_k,
                modality="image",
                model_id=model_name,
            )
            candidate_assets.update(str(row.get("asset_id") or "") for row in candidates)
            selected, policy = select_relevant_image_rows(
                candidates,
                min_score=min_score,
                relative_margin=relative_margin,
            )
            variant_policies.append(policy)
            for row in selected:
                asset_id = str(row.get("asset_id") or "")
                previous = selected_by_asset.get(asset_id)
                if previous is None or float(row.get("score") or 0.0) > float(previous.get("score") or 0.0):
                    selected_by_asset[asset_id] = row
        ranked = sorted(selected_by_asset.values(), key=lambda row: float(row.get("score") or 0.0), reverse=True)
        selected_rows = [
            {"asset_id": row["asset_id"], "score": row["score"], "method": "image_embedding"}
            for row in ranked[:top_k]
        ]
        return selected_rows, {
            "policy": "absolute_min_plus_top_score_margin",
            "candidate_count": len(candidate_assets),
            "selected_count": len(selected_rows),
            "filtered_low_relevance_count": max(0, len(candidate_assets) - len(selected_rows)),
            "variant_count": len(queries),
            "absolute_min_score": min_score,
            "relative_margin": relative_margin,
            "variant_thresholds": [item["effective_threshold"] for item in variant_policies],
        }

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
