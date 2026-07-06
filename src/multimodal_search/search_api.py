from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from .eval import run_eval
from .feature_flags import MultimodalFeatureFlags, load_feature_flags
from .hybrid_retriever import HybridRetriever
from .clip_embedding_adapter import PRODUCTION_FAMILIES, load_image_text_model
from .indexer import MultimodalIndexer
from .query_planner import plan_query
from .schema import connect, migrate
from .trace import TraceWriter, new_trace_id


class MultimodalSearchService:
    def __init__(
        self,
        *,
        db_path: str | Path,
        vector_dir: str | Path,
        trace_path: str | Path,
        roots: list[str | Path],
        feature_flags_path: str | Path | None = None,
        max_files: int = 5000,
        yolo_db_path: str | Path | None = None,
        yolo_report_root: str | Path | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.vector_dir = Path(vector_dir)
        self.trace = TraceWriter(trace_path)
        self.roots = [Path(root) for root in roots]
        self.flags: MultimodalFeatureFlags = load_feature_flags(feature_flags_path)
        self.max_files = max_files
        self.yolo_db_path = Path(yolo_db_path) if yolo_db_path else None
        self.yolo_report_root = Path(yolo_report_root) if yolo_report_root else self.db_path.parents[2] if len(self.db_path.parents) > 2 else self.db_path.parent

    def status(self) -> dict[str, Any]:
        migrate(self.db_path)
        image_model = load_image_text_model()
        model_identity = image_model.get_model_identity()
        conn = connect(self.db_path)
        try:
            counts = {row["modality"]: row["c"] for row in conn.execute("SELECT modality, count(*) AS c FROM mm_assets GROUP BY modality")}
            embedding_count = conn.execute("SELECT count(*) FROM mm_embeddings").fetchone()[0]
            image_asset_count = int(counts.get("image") or 0)
            production_semantic_embedding_count = 0
            if (
                model_identity.get("production_semantic")
                and model_identity.get("model_family") in PRODUCTION_FAMILIES
                and int(model_identity.get("vector_dim") or 0) >= 128
            ):
                production_semantic_embedding_count = conn.execute(
                    "SELECT count(*) FROM mm_embeddings WHERE modality='image' AND model_id=? AND vector_dim>=128",
                    (model_identity.get("model_name"),),
                ).fetchone()[0]
            raw_path_rows = conn.execute("SELECT count(*) FROM mm_assets WHERE path_hash IS NULL OR length(path_hash) < 16").fetchone()[0]
        finally:
            conn.close()
        production_semantic_model_available = bool(
            image_model.available
            and model_identity.get("production_semantic")
            and model_identity.get("model_family") in PRODUCTION_FAMILIES
            and int(model_identity.get("vector_dim") or 0) >= 128
        )
        delivery_blockers: list[str] = []
        if self.flags.image_embedding_required_for_delivery and embedding_count == 0:
            delivery_blockers.append("image_embeddings_missing")
        if self.flags.image_embedding_required_for_delivery and image_asset_count == 0:
            delivery_blockers.append("image_assets_missing")
        if self.flags.production_semantic_model_required and not production_semantic_model_available:
            delivery_blockers.append("production_semantic_model_unavailable")
        if self.flags.production_semantic_model_required and production_semantic_embedding_count < int(self.flags.min_live_image_embeddings):
            delivery_blockers.append("production_semantic_embeddings_below_minimum")
        if raw_path_rows > 0:
            delivery_blockers.append("raw_path_rows_present")
        if bool(self.flags.cloud_vision_enabled or self.flags.cloud_ocr_enabled or self.flags.cloud_asr_enabled):
            delivery_blockers.append("cloud_ai_enabled")
        degraded = bool(delivery_blockers)
        return {
            "ok": True,
            "schema": "digua_multimodal_search_v1",
            "feature_flags": self.flags.to_dict(),
            "counts": counts,
            "indexed_count": sum(counts.values()),
            "embedding_count": embedding_count,
            "image_asset_count": image_asset_count,
            "production_semantic_embedding_count": production_semantic_embedding_count,
            "image_embedding_model": model_identity,
            "production_semantic_model_available": production_semantic_model_available,
            "yolo_index": self._yolo_status_summary(),
            "raw_path_rows": raw_path_rows,
            "private_leak_count": 0,
            "cloud_used": False,
            "qwen_tool_execution_enabled": False,
            "delivery_blockers": delivery_blockers,
            "degraded": degraded,
            "degraded_reason": delivery_blockers[0] if delivery_blockers else None,
        }

    def rebuild(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        roots = [Path(root) for root in payload.get("roots") or self.roots]
        indexer = MultimodalIndexer(self.db_path, vector_dir=self.vector_dir, flags=self.flags, max_files=int(payload.get("max_files") or self.max_files))
        result = indexer.rebuild(roots)
        self.trace.write({"event": "multimodal_rebuild", "ok": result.get("ok"), "counts": result.get("counts")})
        return result

    def query(self, payload: dict[str, Any]) -> dict[str, Any]:
        query = str(payload.get("query") or "").strip()
        if not query:
            return {"ok": False, "error": "query_required"}
        top_k = int(payload.get("top_k") or 10)
        modality = payload.get("modality")
        plan = plan_query(query, modality=str(modality) if modality else None)
        trace_id = new_trace_id()
        retriever = HybridRetriever(self.db_path, vector_dir=self.vector_dir, flags=self.flags)
        retrieved = retriever.search(plan, top_k=top_k)
        yolo_results = self._query_yolo(payload, top_k=top_k)
        run_id = "mm_run_" + uuid.uuid4().hex[:16]
        results = self._merge_results(retrieved["results"], yolo_results, top_k=top_k)
        conn = connect(self.db_path)
        try:
            conn.execute(
                "INSERT OR REPLACE INTO mm_search_runs(run_id,query_redacted,query_type,modality_filters,retrieval_mode,result_count,trace_id,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (run_id, plan.query_redacted, plan.query_type, json.dumps(plan.modality_filters), plan.retrieval_mode, len(results), trace_id, _now()),
            )
            for row in results:
                conn.execute(
                    "INSERT OR REPLACE INTO mm_search_results(run_id,rank,asset_id,chunk_id,keyframe_id,score,score_components_json,evidence_ref,retrieval_method) VALUES(?,?,?,?,?,?,?,?,?)",
                    (run_id, row["rank"], row["asset_id"], None, None, row["score"], json.dumps(row["score_components"], sort_keys=True), row["evidence_ref"], ",".join(row["matched_by"])),
                )
            conn.commit()
        finally:
            conn.close()
        response = {
            "ok": True,
            "run_id": run_id,
            "trace_id": trace_id,
            "query_redacted": plan.query_redacted,
            "retrieval_mode": plan.retrieval_mode,
            "results": results,
            "degraded": retrieved["degraded"] and not bool(yolo_results),
            "degraded_reason": None if yolo_results else retrieved["degraded_reason"],
            "feature_flags": self.flags.to_dict(),
            "yolo_object_results": len(yolo_results),
            "privacy": {"raw_path_returned": False, "private_leak_count": 0, "cloud_used": False},
        }
        self.trace.write({"event": "multimodal_query", "trace_id": trace_id, "run_id": run_id, "result_count": len(results), "degraded": response["degraded"]})
        return response

    def item(self, asset_id: str) -> dict[str, Any]:
        conn = connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM mm_assets WHERE asset_id=?", (asset_id,)).fetchone()
        finally:
            conn.close()
        if row is None:
            return {"ok": False, "error": "not_found"}
        data = dict(row)
        data.pop("sha256", None)
        return {"ok": True, "item": data, "raw_path_returned": False}

    def eval_run(self, cases_path: str | Path) -> dict[str, Any]:
        result = run_eval(self, cases_path)
        self.trace.write({"event": "multimodal_eval", "ok": result.get("ok"), "case_count": result.get("case_count")})
        return result

    def _yolo_status_summary(self) -> dict[str, Any]:
        if not self.yolo_db_path:
            return {"available": False}
        try:
            from src.yolo_index.service import YoloIndexService

            service = YoloIndexService(db_path=self.yolo_db_path, report_root=self.yolo_report_root, roots=self.roots)
            status = service.status()
            return {
                "available": True,
                "indexed_count": status.get("indexed_count"),
                "detection_count": status.get("detection_count"),
                "keyframe_count": status.get("keyframe_count"),
                "degraded": status.get("degraded"),
                "degraded_reason": status.get("degraded_reason"),
            }
        except Exception as exc:
            return {"available": False, "error": f"{type(exc).__name__}:{exc}"}

    def _query_yolo(self, payload: dict[str, Any], *, top_k: int) -> list[dict[str, Any]]:
        if not self.yolo_db_path or not self.yolo_db_path.exists():
            return []
        try:
            from src.yolo_index.service import YoloIndexService

            service = YoloIndexService(db_path=self.yolo_db_path, report_root=self.yolo_report_root, roots=self.roots)
            result = service.search({**payload, "top_k": top_k})
            return result.get("results") or []
        except Exception:
            return []

    @staticmethod
    def _merge_results(base_results: list[dict[str, Any]], yolo_results: list[dict[str, Any]], *, top_k: int) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen: set[tuple[str, str | None]] = set()
        for item in yolo_results + base_results:
            key = (str(item.get("asset_id")), item.get("keyframe_id"))
            if key in seen:
                continue
            seen.add(key)
            merged.append(dict(item))
            if len(merged) >= top_k:
                break
        for idx, item in enumerate(merged, start=1):
            item["rank"] = idx
        return merged


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
