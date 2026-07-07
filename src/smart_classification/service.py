from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from src.ai_space.service import AiSpaceService

from .category_templates import DEFAULT_CATEGORIES
from .chinese_namer import SmartNamingService
from .rule_engine import match_rule
from .schema import connect, migrate


class SmartClassificationService:
    def __init__(self, *, db_path: str | Path, ai_space_service: AiSpaceService) -> None:
        self.db_path = Path(db_path)
        self.ai_space = ai_space_service

    def status(self) -> dict[str, Any]:
        migrate(self.db_path)
        conn = connect(self.db_path)
        try:
            category_count = conn.execute("SELECT count(*) FROM smart_categories WHERE enabled=1").fetchone()[0]
            membership_count = conn.execute("SELECT count(*) FROM smart_category_memberships").fetchone()[0]
            hit_categories = conn.execute("SELECT count(DISTINCT category_id) FROM smart_category_memberships").fetchone()[0]
            name_count = conn.execute("SELECT count(*) FROM smart_asset_names").fetchone()[0]
        finally:
            conn.close()
        return {
            "ok": True,
            "schema": "digua_smart_classification_v1",
            "category_count": category_count,
            "membership_count": membership_count,
            "hit_category_count": hit_categories,
            "smart_name_count": name_count,
            "physical_file_moved": False,
            "physical_file_renamed": False,
            "destructive_actions_enabled": False,
            "cloud_used": False,
            "raw_path_returned": False,
            "face_recognition_used": False,
            "biometric_recognition_enabled": False,
            "sensitive_attribute_inference_enabled": False,
            "degraded": category_count == 0,
            "degraded_reason": "smart_categories_missing" if category_count == 0 else None,
        }

    def ensure_defaults(self) -> None:
        migrate(self.db_path)
        default_ids = {category_id for category_id, *_rest in DEFAULT_CATEGORIES}
        conn = connect(self.db_path)
        try:
            conn.execute(
                """
                UPDATE smart_categories
                SET enabled=0, updated_at=?
                WHERE category_id NOT IN ({})
                  AND (created_by IS NULL OR created_by='system')
                """.format(",".join("?" for _ in default_ids)),
                (_now(), *sorted(default_ids)),
            )
            for index, (category_id, name_zh, name_en, icon, rule) in enumerate(DEFAULT_CATEGORIES):
                now = _now()
                existing = conn.execute("SELECT created_by FROM smart_categories WHERE category_id=?", (category_id,)).fetchone()
                if existing is None:
                    conn.execute(
                        """
                        INSERT INTO smart_categories(category_id,name,name_zh,name_en,icon,description,rule_json,created_by,created_at,updated_at,enabled)
                        VALUES(?,?,?,?,?,?,?,?,?,?,1)
                        """,
                        (category_id, name_zh, name_zh, name_en, icon, "built-in virtual category", json.dumps(rule, ensure_ascii=False, sort_keys=True), "system", now, now),
                    )
                elif (existing["created_by"] or "system") == "system":
                    conn.execute(
                        """
                        UPDATE smart_categories
                        SET name=?,name_zh=?,name_en=?,icon=?,description=?,rule_json=?,updated_at=?,enabled=1
                        WHERE category_id=?
                        """,
                        (name_zh, name_zh, name_en, icon, f"built-in virtual category #{index + 1}", json.dumps(rule, ensure_ascii=False, sort_keys=True), now, category_id),
                    )
            conn.commit()
        finally:
            conn.close()

    def create_category(self, payload: dict[str, Any]) -> dict[str, Any]:
        migrate(self.db_path)
        name = str(payload.get("name") or "").strip()
        if not name:
            return {"ok": False, "error": "name_required"}
        rule = payload.get("rule") or {}
        category_id = "cat_" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]
        now = _now()
        conn = connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO smart_categories(category_id,name,name_zh,name_en,icon,description,rule_json,created_by,created_at,updated_at,enabled)
                VALUES(?,?,?,?,?,?,?,?,?,?,1)
                """,
                (category_id, name, name, payload.get("name_en"), payload.get("icon") or "folder", payload.get("description"), json.dumps(rule, ensure_ascii=False, sort_keys=True), "operator", now, now),
            )
            conn.commit()
        finally:
            conn.close()
        return {"ok": True, "category_id": category_id, "raw_path_returned": False}

    def categories(self) -> dict[str, Any]:
        self.ensure_defaults()
        conn = connect(self.db_path)
        try:
            rows = [dict(row) for row in conn.execute("SELECT * FROM smart_categories WHERE enabled=1 ORDER BY name")]
            counts = {row["category_id"]: row["c"] for row in conn.execute("SELECT category_id,count(*) AS c FROM smart_category_memberships GROUP BY category_id")}
        finally:
            conn.close()
        for row in rows:
            row["rule"] = json.loads(row.pop("rule_json") or "{}")
            row["name_zh"] = row.get("name_zh") or row.get("name")
            row["item_count"] = counts.get(row["category_id"], 0)
        return {"ok": True, "schema": "digua_smart_classification_v1", "categories": rows, "raw_path_returned": False}

    def rebuild(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        self.ensure_defaults()
        conn = connect(self.db_path)
        try:
            preserve_ids: set[str] = set()
            categories_before = [dict(row) for row in conn.execute("SELECT category_id,rule_json FROM smart_categories WHERE enabled=1")]
            for category in categories_before:
                try:
                    rule = json.loads(category.get("rule_json") or "{}")
                except json.JSONDecodeError:
                    rule = {}
                if rule.get("preserve_memberships_on_rebuild"):
                    preserve_ids.add(str(category["category_id"]))
            preserved_asset_ids: set[str] = set()
            if preserve_ids:
                placeholders = ",".join("?" for _ in preserve_ids)
                preserved_asset_ids = {
                    str(row["asset_id"])
                    for row in conn.execute(
                        f"SELECT DISTINCT asset_id FROM smart_category_memberships WHERE category_id IN ({placeholders})",
                        tuple(sorted(preserve_ids)),
                    )
                }
                conn.execute(
                    f"DELETE FROM smart_category_memberships WHERE category_id NOT IN ({placeholders})",
                    tuple(sorted(preserve_ids)),
                )
            else:
                conn.execute("DELETE FROM smart_category_memberships")
            conn.commit()
        finally:
            conn.close()
        self.ai_space.rebuild({})
        assets = self.ai_space.assets({"limit": 10000}).get("assets") or []
        conn = connect(self.db_path)
        inserted = 0
        try:
            categories = [dict(row) for row in conn.execute("SELECT * FROM smart_categories WHERE enabled=1")]
            if preserve_ids:
                placeholders = ",".join("?" for _ in preserve_ids)
                conn.execute(
                    f"DELETE FROM smart_category_memberships WHERE category_id NOT IN ({placeholders})",
                    tuple(sorted(preserve_ids)),
                )
            else:
                conn.execute("DELETE FROM smart_category_memberships")
            for category in categories:
                category_id = str(category["category_id"])
                if category_id in preserve_ids:
                    continue
                rule = json.loads(category["rule_json"] or "{}")
                for asset in assets:
                    if str(asset.get("asset_id") or "") in preserved_asset_ids:
                        continue
                    ok, score, matched_by = match_rule(asset, rule)
                    if not ok:
                        continue
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO smart_category_memberships(category_id,asset_id,score,matched_by_json,evidence_refs_json,created_at)
                        VALUES(?,?,?,?,?,?)
                        """,
                        (
                            category["category_id"],
                            asset["asset_id"],
                            score,
                            json.dumps(matched_by, sort_keys=True),
                            json.dumps(asset.get("evidence_refs") or [f"asset:{asset['asset_id'][:16]}"], sort_keys=True),
                            _now(),
                        ),
                    )
                    inserted += 1
            conn.commit()
        finally:
            conn.close()
        self.ai_space.rebuild({})
        naming = SmartNamingService(db_path=self.db_path, ai_space_service=self.ai_space).batch_generate({"limit": 10000})
        return {
            "ok": True,
            "schema": "digua_smart_classification_v1",
            "inserted_memberships": inserted,
            "generated_smart_names": naming.get("generated_count"),
            "status": self.status(),
            "physical_file_moved": False,
            "physical_file_renamed": False,
            "raw_path_returned": False,
        }

    def category_items(self, category_id: str) -> dict[str, Any]:
        conn = connect(self.db_path)
        try:
            rows = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT m.*, n.display_name_zh, n.suggested_filename_zh
                    FROM smart_category_memberships m
                    LEFT JOIN smart_asset_names n ON n.asset_id=m.asset_id
                    WHERE m.category_id=?
                    ORDER BY m.score DESC
                    """,
                    (category_id,),
                )
            ]
        finally:
            conn.close()
        for row in rows:
            row["matched_by"] = json.loads(row.pop("matched_by_json") or "[]")
            row["evidence_refs"] = json.loads(row.pop("evidence_refs_json") or "[]")
        return {"ok": True, "schema": "digua_smart_classification_v1", "category_id": category_id, "items": rows, "raw_path_returned": False}

    def materialize_copy_plan(self, category_id: str) -> dict[str, Any]:
        items = self.category_items(category_id).get("items") or []
        return {
            "ok": True,
            "schema": "digua_smart_classification_copy_plan_v1",
            "category_id": category_id,
            "plan_only": True,
            "execute_requires_harness": True,
            "physical_file_moved": False,
            "steps": ["preview", "dry_run", "typed_approval", "execute_via_harness", "rollback_manifest"],
            "item_count": len(items),
            "items": [
                {
                    "asset_id": item["asset_id"],
                    "display_name_zh": item.get("display_name_zh"),
                    "suggested_filename_zh": item.get("suggested_filename_zh"),
                    "evidence_refs": item.get("evidence_refs") or [],
                }
                for item in items[:50]
            ],
            "raw_path_returned": False,
        }


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
