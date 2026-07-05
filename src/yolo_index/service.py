from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from .backend import BaseYoloBackend, backend_from_env
from .eval import run_eval
from .indexer import YoloIndexer
from .labels import label_zh, labels_from_query
from .schema import connect, migrate


class YoloIndexService:
    def __init__(
        self,
        *,
        db_path: str | Path,
        report_root: str | Path,
        roots: list[str | Path],
        backend: BaseYoloBackend | None = None,
        max_files: int = 100,
    ) -> None:
        self.db_path = Path(db_path)
        self.report_root = Path(report_root)
        self.roots = [Path(root) for root in roots]
        self.backend = backend or backend_from_env()
        self.max_files = max_files
        self.eval_summary_path = self.report_root / "yolo_index" / "eval_summary.json"

    def status(self) -> dict[str, Any]:
        migrate(self.db_path)
        conn = connect(self.db_path)
        try:
            asset_counts = {row["modality"]: row["c"] for row in conn.execute("SELECT modality, count(*) AS c FROM mm_yolo_assets GROUP BY modality")}
            detection_count = conn.execute("SELECT count(*) FROM mm_yolo_detections").fetchone()[0]
            keyframe_count = conn.execute("SELECT count(*) FROM mm_video_keyframes").fetchone()[0]
            label_counts = {row["label"]: row["c"] for row in conn.execute("SELECT label, count(*) AS c FROM mm_yolo_detections GROUP BY label ORDER BY c DESC")}
            raw_path_rows = conn.execute("SELECT count(*) FROM mm_yolo_assets WHERE path_hash IS NULL OR length(path_hash) < 16").fetchone()[0]
        finally:
            conn.close()
        return {
            "ok": True,
            "schema": "digua_yolo_index_v2",
            "backend": self.backend.status(),
            "asset_counts": asset_counts,
            "indexed_count": sum(asset_counts.values()),
            "detection_count": detection_count,
            "keyframe_count": keyframe_count,
            "label_counts": label_counts,
            "raw_path_rows": raw_path_rows,
            "private_leak_count": 0,
            "cloud_used": False,
            "local_only": True,
            "qwen_tool_execution_enabled": False,
            "degraded": detection_count == 0,
            "degraded_reason": "no_yolo_detections_indexed" if detection_count == 0 else None,
        }

    def rebuild(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        roots = [Path(root) for root in payload.get("roots") or self.roots]
        max_files = int(payload.get("max_files") or self.max_files)
        include_video = bool(payload.get("include_video", True))
        indexer = YoloIndexer(self.db_path, report_root=self.report_root, backend=self.backend, max_files=max_files)
        return indexer.rebuild(roots, max_files=max_files, include_video=include_video)

    def search(self, payload: dict[str, Any]) -> dict[str, Any]:
        query = str(payload.get("query") or "").strip()
        labels = [str(payload.get("label"))] if payload.get("label") else labels_from_query(query)
        labels = [label for label in labels if label]
        top_k = int(payload.get("top_k") or 10)
        modality = payload.get("modality")
        run_id = "yolo_search_" + uuid.uuid4().hex[:16]
        if not labels:
            return {
                "ok": True,
                "run_id": run_id,
                "query_redacted": query[:120],
                "labels": [],
                "results": [],
                "degraded": True,
                "degraded_reason": "no_supported_object_label_in_query",
                "privacy": {"raw_path_returned": False, "cloud_used": False},
            }
        migrate(self.db_path)
        placeholders = ",".join("?" for _ in labels)
        params: list[Any] = labels[:]
        modality_sql = ""
        if modality and modality != "all":
            modality_sql = " AND d.modality=?"
            params.append(str(modality))
        sql = f"""
            SELECT
              a.asset_id,a.modality,a.title_redacted,a.path_hash,a.privacy_level,
              d.keyframe_id,d.label,d.label_zh,d.confidence,d.bbox_x1,d.bbox_y1,d.bbox_x2,d.bbox_y2,
              d.timestamp_sec,d.evidence_ref,d.model_id,d.model_backend
            FROM mm_yolo_detections d
            JOIN mm_yolo_assets a ON a.asset_id=d.asset_id
            WHERE d.label IN ({placeholders}) {modality_sql}
            ORDER BY d.confidence DESC
            LIMIT ?
        """
        params.append(max(top_k * 8, top_k))
        conn = connect(self.db_path)
        try:
            rows = [dict(row) for row in conn.execute(sql, params)]
        finally:
            conn.close()
        grouped: dict[tuple[str, str | None], dict[str, Any]] = {}
        for row in rows:
            key = (row["asset_id"], row.get("keyframe_id"))
            item = grouped.setdefault(
                key,
                {
                    "asset_id": row["asset_id"],
                    "keyframe_id": row.get("keyframe_id"),
                    "title_redacted": row.get("title_redacted"),
                    "modality": row.get("modality"),
                    "path_hash": row.get("path_hash"),
                    "privacy_level": row.get("privacy_level"),
                    "score": 0.0,
                    "matched_by": ["yolo_object"],
                    "object_labels": [],
                    "detections": [],
                    "evidence_ref": row.get("evidence_ref"),
                    "timestamp_sec": row.get("timestamp_sec"),
                },
            )
            item["score"] = max(float(item["score"]), float(row["confidence"]))
            if row["label"] not in item["object_labels"]:
                item["object_labels"].append(row["label"])
            item["detections"].append(
                {
                    "label": row["label"],
                    "label_zh": row.get("label_zh") or label_zh(row["label"]),
                    "confidence": row["confidence"],
                    "bbox": [row.get("bbox_x1"), row.get("bbox_y1"), row.get("bbox_x2"), row.get("bbox_y2")],
                    "bbox_units": "normalized_0_1",
                    "timestamp_sec": row.get("timestamp_sec"),
                    "evidence_ref": row.get("evidence_ref"),
                    "model_id": row.get("model_id"),
                    "model_backend": row.get("model_backend"),
                }
            )
        results = sorted(grouped.values(), key=lambda item: item["score"], reverse=True)[:top_k]
        for idx, item in enumerate(results, start=1):
            item["rank"] = idx
            item["score_components"] = {"yolo_object_confidence": item["score"]}
        return {
            "ok": True,
            "run_id": run_id,
            "query_redacted": query[:120],
            "labels": labels,
            "results": results,
            "degraded": not bool(results),
            "degraded_reason": None if results else "no_matching_yolo_detection",
            "privacy": {"raw_path_returned": False, "cloud_used": False},
        }

    def item(self, asset_id: str) -> dict[str, Any]:
        migrate(self.db_path)
        conn = connect(self.db_path)
        try:
            asset = conn.execute("SELECT * FROM mm_yolo_assets WHERE asset_id=?", (asset_id,)).fetchone()
            detections = [dict(row) for row in conn.execute("SELECT * FROM mm_yolo_detections WHERE asset_id=? ORDER BY confidence DESC", (asset_id,))]
        finally:
            conn.close()
        if asset is None:
            return {"ok": False, "error": "not_found"}
        item = dict(asset)
        item["detections"] = [
            {
                "label": row["label"],
                "label_zh": row["label_zh"],
                "confidence": row["confidence"],
                "keyframe_id": row["keyframe_id"],
                "timestamp_sec": row["timestamp_sec"],
                "bbox": [row["bbox_x1"], row["bbox_y1"], row["bbox_x2"], row["bbox_y2"]],
                "evidence_ref": row["evidence_ref"],
            }
            for row in detections
        ]
        return {"ok": True, "item": item, "raw_path_returned": False}

    def eval_run(self, cases_path: str | Path) -> dict[str, Any]:
        result = run_eval(self, cases_path)
        self.eval_summary_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {**result, "generated_at": _now()}
        self.eval_summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return payload

    def eval_summary(self) -> dict[str, Any]:
        if not self.eval_summary_path.exists():
            return {"ok": True, "available": False, "summary": None}
        try:
            payload = json.loads(self.eval_summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"ok": False, "error": "eval_summary_unreadable"}
        return {"ok": True, "available": True, "summary": payload}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
