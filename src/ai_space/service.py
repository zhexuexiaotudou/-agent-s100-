from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from src.multimodal_search.schema import connect as connect_mm
from src.multimodal_search.schema import migrate as migrate_mm
from src.person_attribute.schema import connect as connect_person
from src.person_attribute.schema import migrate as migrate_person
from src.yolo_index.schema import connect as connect_yolo
from src.yolo_index.schema import migrate as migrate_yolo

from .schema import connect, migrate
from .summary_builder import symbolic_summary


KIND_BY_MODALITY = {
    "image": "photo",
    "video": "video",
    "audio": "audio",
    "document": "document",
    "archive": "archive",
    "code": "code",
}


class AiSpaceService:
    def __init__(
        self,
        *,
        db_path: str | Path,
        multimodal_db_path: str | Path,
        yolo_db_path: str | Path,
        person_db_path: str | Path,
        smart_db_path: str | Path | None = None,
        subtitle_db_path: str | Path | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.multimodal_db_path = Path(multimodal_db_path)
        self.yolo_db_path = Path(yolo_db_path)
        self.person_db_path = Path(person_db_path)
        self.smart_db_path = Path(smart_db_path) if smart_db_path else None
        self.subtitle_db_path = Path(subtitle_db_path) if subtitle_db_path else None

    def status(self) -> dict[str, Any]:
        migrate(self.db_path)
        conn = connect(self.db_path)
        try:
            asset_count = conn.execute("SELECT count(*) FROM ai_space_asset_views").fetchone()[0]
            evidence_count = conn.execute("SELECT count(*) FROM ai_space_asset_views WHERE evidence_refs_json != '[]'").fetchone()[0]
            modality_counts = {row["modality"]: row["c"] for row in conn.execute("SELECT modality, count(*) AS c FROM ai_space_asset_views GROUP BY modality")}
        finally:
            conn.close()
        return {
            "ok": True,
            "schema": "digua_ai_space_v1",
            "asset_count": asset_count,
            "evidence_count": evidence_count,
            "modality_counts": modality_counts,
            "cloud_used": False,
            "raw_path_returned": False,
            "degraded": asset_count == 0,
            "degraded_reason": "ai_space_assets_missing" if asset_count == 0 else None,
        }

    def rebuild(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        migrate(self.db_path)
        migrate_mm(self.multimodal_db_path)
        migrate_yolo(self.yolo_db_path)
        migrate_person(self.person_db_path)
        assets = self._multimodal_assets()
        labels = self._yolo_labels()
        person_attrs = self._person_attrs()
        categories = self._category_names()
        transcripts = self._transcript_assets()
        conn = connect(self.db_path)
        try:
            conn.execute("DELETE FROM ai_space_asset_views")
            for asset in assets:
                asset_id = asset["asset_id"]
                object_labels = sorted(labels.get(asset_id, set()))
                person = sorted(person_attrs.get(asset_id, set()))
                category_names = sorted(categories.get(asset_id, set()))
                transcript_status = "indexed" if asset_id in transcripts else "none"
                ocr_status = "indexed" if asset.get("modality") in {"document", "code"} else "none"
                evidence_refs = sorted({f"asset:{asset_id[:16]}", *[f"yolo:{label}" for label in object_labels[:3]]})
                conn.execute(
                    """
                    INSERT OR REPLACE INTO ai_space_asset_views(
                      asset_id,modality,title_redacted,asset_kind,capture_time,time_bucket,object_labels_json,
                      person_attrs_json,ocr_status,transcript_status,category_names_json,summary_redacted,
                      privacy_level,evidence_refs_json,updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        asset_id,
                        asset["modality"],
                        asset.get("title_redacted"),
                        KIND_BY_MODALITY.get(asset["modality"], "other"),
                        None,
                        _time_bucket(asset.get("mtime")),
                        json.dumps(object_labels, sort_keys=True),
                        json.dumps(person, sort_keys=True),
                        ocr_status,
                        transcript_status,
                        json.dumps(category_names, ensure_ascii=False, sort_keys=True),
                        symbolic_summary(
                            modality=asset["modality"],
                            labels=object_labels,
                            ocr_status=ocr_status,
                            transcript_status=transcript_status,
                        ),
                        asset.get("privacy_level") or "private_local_only",
                        json.dumps(evidence_refs, sort_keys=True),
                        _now(),
                    ),
                )
            conn.commit()
        finally:
            conn.close()
        return {"ok": True, "schema": "digua_ai_space_v1", "rebuilt_assets": len(assets), "status": self.status(), "cloud_used": False, "raw_path_returned": False}

    def assets(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        rows = self._select_views(payload, limit=int(payload.get("limit") or 80))
        return {"ok": True, "schema": "digua_ai_space_v1", "assets": rows, "raw_path_returned": False, "cloud_used": False}

    def facets(self) -> dict[str, Any]:
        rows = self._select_views({}, limit=10000)
        facets = {"modality": {}, "time_bucket": {}, "object_label": {}, "category": {}, "privacy_level": {}}
        for row in rows:
            _bump(facets["modality"], row.get("modality"))
            _bump(facets["time_bucket"], row.get("time_bucket"))
            _bump(facets["privacy_level"], row.get("privacy_level"))
            for label in row.get("object_labels", []):
                _bump(facets["object_label"], label)
            for category in row.get("category_names", []):
                _bump(facets["category"], category)
        return {"ok": True, "schema": "digua_ai_space_v1", "facets": facets, "raw_path_returned": False, "cloud_used": False}

    def search(self, payload: dict[str, Any]) -> dict[str, Any]:
        query = str(payload.get("query") or "").strip().lower()
        rows = self._select_views({}, limit=10000)
        hits = []
        for row in rows:
            haystack = " ".join(
                [
                    str(row.get("title_redacted") or ""),
                    str(row.get("display_name_zh") or ""),
                    str(row.get("suggested_filename_zh") or ""),
                    str(row.get("modality") or ""),
                    str(row.get("asset_kind") or ""),
                    str(row.get("summary_redacted") or ""),
                    " ".join(row.get("object_labels", [])),
                    " ".join(row.get("person_attrs", [])),
                    " ".join(row.get("category_names", [])),
                ]
            ).lower()
            if not query or query in haystack or _query_alias_match(query, row):
                hits.append(row)
        return {"ok": True, "schema": "digua_ai_space_v1", "query_redacted": query[:200], "results": hits[: int(payload.get("top_k") or 20)], "raw_path_returned": False, "cloud_used": False}

    def item(self, asset_id: str) -> dict[str, Any]:
        rows = self._select_views({"asset_id": asset_id}, limit=1)
        if not rows:
            return {"ok": False, "error": "not_found", "raw_path_returned": False}
        return {"ok": True, "asset": rows[0], "raw_path_returned": False, "cloud_used": False}

    def _multimodal_assets(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        assets: list[dict[str, Any]] = []
        conn = connect_mm(self.multimodal_db_path)
        try:
            for row in conn.execute("SELECT asset_id,modality,title_redacted,file_type,mtime,privacy_level FROM mm_assets ORDER BY mtime DESC"):
                item = dict(row)
                seen.add(item["asset_id"])
                assets.append(item)
        finally:
            conn.close()
        yconn = connect_yolo(self.yolo_db_path)
        try:
            for row in yconn.execute("SELECT asset_id,modality,title_redacted,file_type,mtime,privacy_level FROM mm_yolo_assets ORDER BY mtime DESC"):
                item = dict(row)
                if item["asset_id"] in seen:
                    continue
                seen.add(item["asset_id"])
                assets.append(item)
        finally:
            yconn.close()
        return assets

    def _yolo_labels(self) -> dict[str, set[str]]:
        conn = connect_yolo(self.yolo_db_path)
        out: dict[str, set[str]] = {}
        try:
            for row in conn.execute("SELECT asset_id,label FROM mm_yolo_detections"):
                out.setdefault(row["asset_id"], set()).add(row["label"])
        finally:
            conn.close()
        return out

    def _person_attrs(self) -> dict[str, set[str]]:
        conn = connect_person(self.person_db_path)
        out: dict[str, set[str]] = {}
        try:
            for row in conn.execute("SELECT asset_id,attribute_tags_json FROM person_attribute_detections"):
                out.setdefault(row["asset_id"], set()).update(json.loads(row["attribute_tags_json"] or "[]"))
        finally:
            conn.close()
        return out

    def _category_names(self) -> dict[str, set[str]]:
        if not self.smart_db_path or not self.smart_db_path.exists():
            return {}
        import sqlite3

        out: dict[str, set[str]] = {}
        conn = sqlite3.connect(str(self.smart_db_path))
        conn.row_factory = sqlite3.Row
        try:
            for row in conn.execute(
                "SELECT m.asset_id,c.name FROM smart_category_memberships m JOIN smart_categories c ON c.category_id=m.category_id"
            ):
                out.setdefault(row["asset_id"], set()).add(row["name"])
        except sqlite3.Error:
            return {}
        finally:
            conn.close()
        return out

    def _transcript_assets(self) -> set[str]:
        if not self.subtitle_db_path or not self.subtitle_db_path.exists():
            return set()
        import sqlite3

        conn = sqlite3.connect(str(self.subtitle_db_path))
        conn.row_factory = sqlite3.Row
        try:
            return {row["asset_id"] for row in conn.execute("SELECT DISTINCT asset_id FROM media_transcripts")}
        except sqlite3.Error:
            return set()
        finally:
            conn.close()

    def _select_views(self, filters: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
        migrate(self.db_path)
        clauses = []
        args: list[Any] = []
        for field in ("asset_id", "modality", "asset_kind", "time_bucket", "privacy_level"):
            if filters.get(field):
                clauses.append(f"{field}=?")
                args.append(filters[field])
        sql = "SELECT * FROM ai_space_asset_views"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        args.append(limit)
        conn = connect(self.db_path)
        try:
            rows = [self._decode(dict(row)) for row in conn.execute(sql, args)]
        finally:
            conn.close()
        names = self._smart_names([str(row.get("asset_id") or "") for row in rows])
        for row in rows:
            item = names.get(str(row.get("asset_id") or ""))
            if not item:
                continue
            row["display_name_zh"] = item.get("display_name_zh")
            row["suggested_filename_zh"] = item.get("suggested_filename_zh")
            row["smart_naming"] = {
                "display_name_zh": item.get("display_name_zh"),
                "suggested_filename_zh": item.get("suggested_filename_zh"),
                "risk_flags": item.get("risk_flags") or {},
            }
        return rows

    def _smart_names(self, asset_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not self.smart_db_path or not self.smart_db_path.exists() or not asset_ids:
            return {}
        import sqlite3

        placeholders = ",".join("?" for _ in asset_ids)
        conn = sqlite3.connect(str(self.smart_db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = [dict(row) for row in conn.execute(f"SELECT * FROM smart_asset_names WHERE asset_id IN ({placeholders})", asset_ids)]
        except sqlite3.Error:
            return {}
        finally:
            conn.close()
        out: dict[str, dict[str, Any]] = {}
        for row in rows:
            try:
                row["risk_flags"] = json.loads(row.get("risk_flags_json") or "{}")
            except json.JSONDecodeError:
                row["risk_flags"] = {}
            out[row["asset_id"]] = row
        return out

    @staticmethod
    def _decode(row: dict[str, Any]) -> dict[str, Any]:
        row["object_labels"] = json.loads(row.pop("object_labels_json") or "[]")
        row["person_attrs"] = json.loads(row.pop("person_attrs_json") or "[]")
        row["category_names"] = json.loads(row.pop("category_names_json") or "[]")
        row["evidence_refs"] = json.loads(row.pop("evidence_refs_json") or "[]")
        return row


def _time_bucket(mtime: Any) -> str:
    try:
        age = time.time() - float(mtime)
    except Exception:
        return "older"
    if age < 86400:
        return "today"
    if age < 86400 * 7:
        return "this_week"
    if age < 86400 * 31:
        return "this_month"
    return "older"


def _query_alias_match(query: str, row: dict[str, Any]) -> bool:
    aliases = {
        "white clothes": "upper_white",
        "white shirt": "upper_white",
        "\u767d\u8272\u8863\u670d": "upper_white",
        "\u767d\u8863\u670d": "upper_white",
        "\u7968\u636e": "\u7968\u636e\u53d1\u7968",
        "\u53d1\u7968": "\u7968\u636e\u53d1\u7968",
        "\u89c6\u9891": "video",
        "\u5408\u540c": "\u5408\u540c\u8d44\u6599",
    }
    target = aliases.get(query, query)
    hay = " ".join([row.get("modality") or "", " ".join(row.get("person_attrs", [])), " ".join(row.get("category_names", []))]).lower()
    return target.lower() in hay


def _bump(bucket: dict[str, int], key: Any) -> None:
    if not key:
        return
    bucket[str(key)] = bucket.get(str(key), 0) + 1


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
