from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from .eval import run_eval
from .feature_flags import MultimodalFeatureFlags, load_feature_flags
from .hybrid_retriever import HybridRetriever
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
    ) -> None:
        self.db_path = Path(db_path)
        self.vector_dir = Path(vector_dir)
        self.trace = TraceWriter(trace_path)
        self.roots = [Path(root) for root in roots]
        self.flags: MultimodalFeatureFlags = load_feature_flags(feature_flags_path)
        self.max_files = max_files

    def status(self) -> dict[str, Any]:
        migrate(self.db_path)
        conn = connect(self.db_path)
        try:
            counts = {row["modality"]: row["c"] for row in conn.execute("SELECT modality, count(*) AS c FROM mm_assets GROUP BY modality")}
            embedding_count = conn.execute("SELECT count(*) FROM mm_embeddings").fetchone()[0]
            raw_path_rows = conn.execute("SELECT count(*) FROM mm_assets WHERE path_hash IS NULL OR length(path_hash) < 16").fetchone()[0]
        finally:
            conn.close()
        return {
            "ok": True,
            "schema": "digua_multimodal_search_v1",
            "feature_flags": self.flags.to_dict(),
            "counts": counts,
            "indexed_count": sum(counts.values()),
            "embedding_count": embedding_count,
            "raw_path_rows": raw_path_rows,
            "private_leak_count": 0,
            "cloud_used": False,
            "qwen_tool_execution_enabled": False,
            "degraded": self.flags.image_embedding_enabled and embedding_count == 0,
            "degraded_reason": "image_embeddings_missing" if self.flags.image_embedding_enabled and embedding_count == 0 else None,
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
        run_id = "mm_run_" + uuid.uuid4().hex[:16]
        results = retrieved["results"]
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
            "degraded": retrieved["degraded"],
            "degraded_reason": retrieved["degraded_reason"],
            "feature_flags": self.flags.to_dict(),
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


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
