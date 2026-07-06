from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from src.yolo_index.indexer import asset_id_for, collect_assets, path_hash
from src.yolo_index.schema import connect as connect_yolo
from src.yolo_index.schema import migrate as migrate_yolo

from .color_classifier import crop_mean_color
from .query_parser import parse_person_attribute_query
from .schema import connect, migrate


SAFE_FLAGS = {
    "face_identification_enabled": False,
    "biometric_recognition_enabled": False,
    "sensitive_attribute_inference_enabled": False,
    "cloud_used": False,
    "raw_path_returned": False,
}


class PersonAttributeService:
    def __init__(self, *, db_path: str | Path, yolo_db_path: str | Path, roots: list[str | Path], max_files: int = 5000) -> None:
        self.db_path = Path(db_path)
        self.yolo_db_path = Path(yolo_db_path)
        self.roots = [Path(root) for root in roots]
        self.max_files = max_files

    def status(self) -> dict[str, Any]:
        migrate(self.db_path)
        conn = connect(self.db_path)
        try:
            person_detection_count = conn.execute("SELECT count(*) FROM person_attribute_detections").fetchone()[0]
            attribute_count = conn.execute("SELECT count(*) FROM person_attribute_detections WHERE attribute_tags_json != '[]'").fetchone()[0]
            video_keyframe_count = conn.execute("SELECT count(*) FROM person_attribute_detections WHERE modality='video'").fetchone()[0]
        finally:
            conn.close()
        degraded = person_detection_count == 0 or attribute_count == 0
        return {
            "ok": True,
            "schema": "digua_person_attribute_search_v1",
            "person_detection_count": person_detection_count,
            "attribute_count": attribute_count,
            "video_keyframe_count": video_keyframe_count,
            **SAFE_FLAGS,
            "degraded": degraded,
            "degraded_reason": "person_attributes_missing" if degraded else None,
        }

    def rebuild(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        roots = [Path(root) for root in payload.get("roots") or self.roots]
        path_map = self._path_map(roots)
        migrate(self.db_path)
        migrate_yolo(self.yolo_db_path)
        yconn = connect_yolo(self.yolo_db_path)
        conn = connect(self.db_path)
        inserted = 0
        skipped_no_path = 0
        try:
            conn.execute("DELETE FROM person_attribute_detections")
            rows = [
                dict(row)
                for row in yconn.execute(
                    """
                    SELECT d.*, a.path_hash
                    FROM mm_yolo_detections d
                    JOIN mm_yolo_assets a ON a.asset_id=d.asset_id
                    WHERE d.label='person'
                    ORDER BY d.confidence DESC
                    """
                )
            ]
            for row in rows:
                image_path = path_map.get(row["asset_id"]) or path_map.get(row["path_hash"])
                if image_path is None and row.get("modality") != "video":
                    skipped_no_path += 1
                bbox = (float(row["bbox_x1"] or 0), float(row["bbox_y1"] or 0), float(row["bbox_x2"] or 1), float(row["bbox_y2"] or 1))
                upper = crop_mean_color(image_path, bbox, part="upper") if image_path else "unknown"
                lower = crop_mean_color(image_path, bbox, part="lower") if image_path else "unknown"
                tags = ["person_present"]
                if upper != "unknown":
                    tags.append(f"upper_{upper}")
                if lower != "unknown":
                    tags.append(f"lower_{lower}")
                for label in self._asset_labels(yconn, row["asset_id"]):
                    if label in {"laptop", "book", "car", "cup", "bag"}:
                        tags.append(f"co_occurs_with_{label}")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO person_attribute_detections(
                      id,asset_id,keyframe_id,detection_id,modality,bbox_json,upper_color,lower_color,
                      dominant_colors_json,attribute_tags_json,evidence_ref,confidence,timestamp_sec,created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        "pat_" + hashlib.sha256(str(row["detection_id"]).encode("utf-8")).hexdigest()[:24],
                        row["asset_id"],
                        row.get("keyframe_id"),
                        row["detection_id"],
                        row["modality"],
                        json.dumps(list(bbox)),
                        upper,
                        lower,
                        json.dumps([upper, lower], sort_keys=True),
                        json.dumps(sorted(set(tags)), sort_keys=True),
                        row["evidence_ref"],
                        row["confidence"],
                        row.get("timestamp_sec"),
                        _now(),
                    ),
                )
                inserted += 1
            conn.commit()
        finally:
            yconn.close()
            conn.close()
        status = self.status()
        return {
            "ok": True,
            "schema": "digua_person_attribute_search_v1",
            "inserted": inserted,
            "skipped_no_path": skipped_no_path,
            "status": status,
            **SAFE_FLAGS,
        }

    def search(self, payload: dict[str, Any]) -> dict[str, Any]:
        query = parse_person_attribute_query(str(payload.get("query") or ""))
        if query.blocked:
            return {
                "ok": True,
                "intent": "person_identity_recognition",
                "blocked": True,
                "blocked_reason": query.blocked_reason,
                "results": [],
                **SAFE_FLAGS,
            }
        migrate(self.db_path)
        clauses = ["1=1"]
        args: list[Any] = []
        if query.modality:
            clauses.append("modality=?")
            args.append(query.modality)
        if query.require_person:
            clauses.append("attribute_tags_json LIKE ?")
            args.append("%person_present%")
        if query.upper_color:
            clauses.append("attribute_tags_json LIKE ?")
            args.append(f"%upper_{query.upper_color}%")
        if query.co_occurs_with:
            clauses.append("attribute_tags_json LIKE ?")
            args.append(f"%co_occurs_with_{query.co_occurs_with}%")
        sql = f"""
            SELECT * FROM person_attribute_detections
            WHERE {' AND '.join(clauses)}
            ORDER BY confidence DESC
            LIMIT ?
        """
        args.append(int(payload.get("top_k") or 10))
        conn = connect(self.db_path)
        try:
            rows = [dict(row) for row in conn.execute(sql, args)]
        finally:
            conn.close()
        results = []
        for rank, row in enumerate(rows, 1):
            results.append(
                {
                    "rank": rank,
                    "asset_id": row["asset_id"],
                    "keyframe_id": row.get("keyframe_id"),
                    "modality": row["modality"],
                    "upper_color": row.get("upper_color"),
                    "lower_color": row.get("lower_color"),
                    "attribute_tags": json.loads(row.get("attribute_tags_json") or "[]"),
                    "confidence": row.get("confidence"),
                    "timestamp_sec": row.get("timestamp_sec"),
                    "evidence_ref": row.get("evidence_ref"),
                    "matched_by": ["person_attribute"],
                }
            )
        return {
            "ok": True,
            "schema": "digua_person_attribute_search_v1",
            "query": query.to_dict(),
            "blocked": False,
            "results": results,
            "degraded": not bool(results),
            "degraded_reason": None if results else "no_matching_person_attribute",
            **SAFE_FLAGS,
        }

    def _path_map(self, roots: list[Path]) -> dict[str, Path]:
        mapping: dict[str, Path] = {}
        for candidate in collect_assets(roots, max_files=self.max_files):
            try:
                mapping[asset_id_for(candidate.path)] = candidate.path
                mapping[path_hash(candidate.path)] = candidate.path
            except Exception:
                continue
        return mapping

    @staticmethod
    def _asset_labels(conn, asset_id: str) -> set[str]:
        return {row["label"] for row in conn.execute("SELECT DISTINCT label FROM mm_yolo_detections WHERE asset_id=?", (asset_id,))}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
