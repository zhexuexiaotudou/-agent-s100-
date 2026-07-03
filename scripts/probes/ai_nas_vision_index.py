#!/usr/bin/env python3
"""Product-grade visual index state management.

This module binds scanned NAS records to the final visual data plane. It does
not pretend unavailable models ran; it records active generations, ACL scope,
privacy class, and degradation so search/UI can explain current capability.
"""

from __future__ import annotations

import json
from pathlib import Path

from ai_nas_common import PHOTO_EXTS, iso_now, open_index_db


def _top_scope(relative_path: str) -> str:
    clean = str(relative_path or "").replace("\\", "/").strip("/")
    return clean.split("/", 1)[0] if clean else ""


def _source_revision(record: dict) -> str:
    parts = [
        str(record.get("sha256") or ""),
        str(record.get("size_bytes") or record.get("size") or ""),
        str(record.get("mtime_ns") or record.get("mtime") or ""),
    ]
    return ":".join(parts)


def _privacy_class(record: dict) -> str:
    rel = str(record.get("relative_path") or "").lower()
    name = str(record.get("name") or "").lower()
    metadata = record.get("metadata") or {}
    ocr = metadata.get("ocr") or {}
    haystack = " ".join([rel, name, str(ocr.get("status") or "")])
    if any(term in haystack for term in ("passport", "id_card", "identity", "身份证", "证件")):
        return "identity_document"
    if any(term in haystack for term in ("invoice", "receipt", "bill", "发票", "收据", "报销")):
        return "invoice_or_receipt"
    if any(term in haystack for term in ("private", "secret", "confidential", "隐私")):
        return "private"
    return "standard"


def _legacy_state(con, path: str) -> dict:
    caption = con.execute(
        "SELECT status, model_id, caption FROM image_captions WHERE path = ?",
        (path,),
    ).fetchone()
    embedding = con.execute(
        "SELECT status, model_id, dim FROM image_embeddings WHERE path = ?",
        (path,),
    ).fetchone()
    ocr = con.execute(
        "SELECT status, engine FROM ocr_results WHERE path = ?",
        (path,),
    ).fetchone()
    product_embedding = con.execute(
        """
        SELECT status, model_id, dim
        FROM vision_embeddings_v2
        WHERE path = ? AND scope = 'image'
          AND status = 'product_image_text_embedding_completed'
        ORDER BY id DESC
        LIMIT 1
        """,
        (path,),
    ).fetchone()
    region_count = con.execute(
        "SELECT COUNT(*) AS count FROM vision_regions WHERE path = ?",
        (path,),
    ).fetchone()
    region_attribute_count = con.execute(
        """
        SELECT COUNT(*) AS count
        FROM vision_attributes
        WHERE path = ? AND region_id IS NOT NULL
        """,
        (path,),
    ).fetchone()
    return {
        "caption": dict(caption) if caption else None,
        "embedding": dict(embedding) if embedding else None,
        "ocr": dict(ocr) if ocr else None,
        "product_embedding": dict(product_embedding) if product_embedding else None,
        "region_count": int(region_count["count"] if region_count else 0),
        "region_attribute_count": int(region_attribute_count["count"] if region_attribute_count else 0),
    }


def _degradation_for_legacy(legacy: dict, runtime: dict | None = None) -> list[dict]:
    runtime = runtime or {}
    components = runtime.get("components") or {}
    degradation: list[dict] = []
    caption = legacy.get("caption") or {}
    embedding = legacy.get("embedding") or {}
    product_embedding = legacy.get("product_embedding") or {}
    ocr = legacy.get("ocr") or {}
    if caption.get("status") != "llm_caption_completed":
        degradation.append(
            {
                "stage": "caption_vlm",
                "reason": caption.get("status") or "caption_not_indexed",
                "confidence_cap": 0.55,
            }
        )
    if product_embedding.get("status") == "product_image_text_embedding_completed":
        pass
    elif embedding.get("status") != "local_visual_embedding_completed":
        degradation.append(
            {
                "stage": "image_text_embedding",
                "reason": embedding.get("status") or "semantic_embedding_not_indexed",
                "confidence_cap": 0.45,
            }
        )
    elif embedding.get("model_id") == "local_visual_embedding_v1":
        degradation.append(
            {
                "stage": "image_text_embedding",
                "reason": "legacy_local_visual_embedding_is_not_clip_or_siglip",
                "confidence_cap": 0.48,
            }
        )
    if ocr.get("status") not in {"ocr_completed", "ocr_completed_no_text"}:
        degradation.append(
            {
                "stage": "ocr",
                "reason": ocr.get("status") or "ocr_not_indexed",
                "confidence_cap": 0.65,
            }
        )
    if int(legacy.get("region_count") or 0) > 0:
        pass
    elif not (components.get("detector") or {}).get("ready"):
        degradation.append(
            {
                "stage": "detector",
                "reason": "person_object_detector_not_configured",
                "confidence_cap": 0.40,
            }
        )
    else:
        degradation.append(
            {
                "stage": "detector",
                "reason": "person_object_detector_not_indexed",
                "confidence_cap": 0.45,
            }
        )
    if int(legacy.get("region_attribute_count") or 0) > 0:
        pass
    elif not (components.get("region_attributes") or {}).get("ready"):
        degradation.append(
            {
                "stage": "region_attributes",
                "reason": "region_attribute_model_not_configured",
                "confidence_cap": 0.40,
            }
        )
    else:
        degradation.append(
            {
                "stage": "region_attributes",
                "reason": "region_attribute_model_not_indexed",
                "confidence_cap": 0.45,
            }
        )
    return degradation


def _visual_status(legacy: dict) -> str:
    caption = legacy.get("caption") or {}
    embedding = legacy.get("embedding") or {}
    product_embedding = legacy.get("product_embedding") or {}
    has_regions = int(legacy.get("region_count") or 0) > 0
    has_attributes = int(legacy.get("region_attribute_count") or 0) > 0
    if product_embedding.get("status") == "product_image_text_embedding_completed" and has_regions and has_attributes:
        return "indexed_with_product_embedding_and_region_attributes"
    if product_embedding.get("status") == "product_image_text_embedding_completed":
        return "indexed_with_product_embedding"
    if has_regions and has_attributes:
        return "indexed_with_product_region_attributes"
    if caption.get("status") == "llm_caption_completed" and embedding.get("status"):
        return "indexed_with_caption_and_legacy_embedding"
    if embedding.get("status") == "local_visual_embedding_completed":
        return "indexed_with_legacy_embedding_degraded"
    if caption.get("status"):
        return "caption_state_only_degraded"
    return "metadata_only_degraded"


def ensure_photo_visual_states(db_path: Path, records: list[dict], runtime: dict | None = None) -> dict:
    now = iso_now()
    attempted = 0
    inserted = 0
    updated = 0
    skipped = 0
    items: list[dict] = []
    con = open_index_db(db_path)
    try:
        for record in records:
            rel = str(record.get("relative_path") or "").replace("\\", "/").strip("/")
            ext = str(record.get("extension") or Path(rel).suffix).lower()
            if record.get("type") != "Photos" or ext not in PHOTO_EXTS:
                skipped += 1
                continue
            path = str(record.get("path") or "")
            if not path or not rel:
                skipped += 1
                continue
            attempted += 1
            legacy = _legacy_state(con, path)
            source_revision = _source_revision(record)
            existing = con.execute(
                "SELECT source_revision, active_generation FROM photo_visual_state WHERE path = ?",
                (path,),
            ).fetchone()
            generation = int(existing["active_generation"]) if existing else 0
            if not existing or str(existing["source_revision"] or "") != source_revision:
                generation += 1
            degradation = _degradation_for_legacy(legacy, runtime=runtime)
            status = _visual_status(legacy)
            acl_scope = _top_scope(rel)
            partition = f"scope:{acl_scope or 'default'}"
            privacy_class = _privacy_class(record)
            con.execute(
                """
                INSERT INTO photo_visual_state(
                    path, relative_path, source_revision, acl_scope, security_partition_id,
                    acl_epoch, privacy_class, active_generation, status, degradation_json,
                    indexed_at, updated_at
                )
                VALUES(?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    relative_path=excluded.relative_path,
                    source_revision=excluded.source_revision,
                    acl_scope=excluded.acl_scope,
                    security_partition_id=excluded.security_partition_id,
                    privacy_class=excluded.privacy_class,
                    active_generation=excluded.active_generation,
                    status=excluded.status,
                    degradation_json=excluded.degradation_json,
                    indexed_at=excluded.indexed_at,
                    updated_at=excluded.updated_at
                """,
                (
                    path,
                    rel,
                    source_revision,
                    acl_scope,
                    partition,
                    privacy_class,
                    generation,
                    status,
                    json.dumps(degradation, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            if existing:
                updated += 1
            else:
                inserted += 1
            items.append(
                {
                    "relative_path": rel,
                    "generation": generation,
                    "status": status,
                    "acl_scope": acl_scope,
                    "security_partition_id": partition,
                    "privacy_class": privacy_class,
                    "degradation": degradation,
                }
            )
        con.commit()
        counts = {
            row["status"]: row["count"]
            for row in con.execute("SELECT status, COUNT(*) AS count FROM photo_visual_state GROUP BY status")
        }
        privacy_counts = {
            row["privacy_class"]: row["count"]
            for row in con.execute("SELECT privacy_class, COUNT(*) AS count FROM photo_visual_state GROUP BY privacy_class")
        }
    finally:
        con.close()
    return {
        "ok": True,
        "updated_at": now,
        "attempted": attempted,
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "status_counts": counts,
        "privacy_counts": privacy_counts,
        "items": items[:50],
    }


def photo_visual_state_summary(db_path: Path, limit: int = 20) -> dict:
    con = open_index_db(db_path)
    try:
        counts = {
            row["status"]: row["count"]
            for row in con.execute("SELECT status, COUNT(*) AS count FROM photo_visual_state GROUP BY status")
        }
        rows = [
            {
                "relative_path": row["relative_path"],
                "status": row["status"],
                "generation": row["active_generation"],
                "acl_scope": row["acl_scope"],
                "security_partition_id": row["security_partition_id"],
                "privacy_class": row["privacy_class"],
                "degradation": json.loads(row["degradation_json"] or "[]"),
                "updated_at": row["updated_at"],
            }
            for row in con.execute(
                """
                SELECT relative_path, status, active_generation, acl_scope, security_partition_id,
                       privacy_class, degradation_json, updated_at
                FROM photo_visual_state
                ORDER BY updated_at DESC, relative_path
                LIMIT ?
                """,
                (max(1, int(limit or 20)),),
            )
        ]
        return {"status_counts": counts, "recent": rows}
    finally:
        con.close()
