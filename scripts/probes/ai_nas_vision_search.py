#!/usr/bin/env python3
"""Product-shaped visual search response assembly."""

from __future__ import annotations

import json
import math
from pathlib import Path

from ai_nas_common import _record_from_sqlite_row, open_index_db, search_photo_semantic_index
from ai_nas_embedding_adapter import run_product_text_embedding
from ai_nas_visual_evidence import degradation_item, evidence_chips, evidence_item
from ai_nas_visual_query import build_visual_query_plan


def _visual_state_for_path(db_path: Path, path: str) -> dict:
    con = open_index_db(db_path)
    try:
        row = con.execute(
            """
            SELECT relative_path, status, active_generation, acl_scope, security_partition_id,
                   privacy_class, degradation_json, updated_at
            FROM photo_visual_state
            WHERE path = ?
            """,
            (path,),
        ).fetchone()
        if not row:
            return {}
        try:
            degradation = json.loads(row["degradation_json"] or "[]")
        except json.JSONDecodeError:
            degradation = []
        return {
            "relative_path": row["relative_path"],
            "status": row["status"],
            "active_generation": row["active_generation"],
            "acl_scope": row["acl_scope"],
            "security_partition_id": row["security_partition_id"],
            "privacy_class": row["privacy_class"],
            "degradation": degradation,
            "updated_at": row["updated_at"],
        }
    finally:
        con.close()


def _evidence_from_match(match: dict) -> list[dict]:
    items: list[dict] = []
    for item in match.get("product_evidence_items") or []:
        if isinstance(item, dict):
            items.append(item)
    caption = match.get("image_caption") or {}
    if caption.get("status"):
        items.append(
            evidence_item(
                "caption",
                label=caption.get("status") or "caption",
                confidence=0.72 if caption.get("status") == "llm_caption_completed" else 0.20,
                model_id=caption.get("model_id") or "",
                runtime=caption.get("provider") or "",
                metadata={"caption": caption.get("caption") or "", "schema_version": caption.get("schema_version")},
            )
        )
    embedding = match.get("image_embedding") or {}
    if embedding.get("status"):
        label = embedding.get("model_id") or "image_embedding"
        items.append(
            evidence_item(
                "image_embedding",
                label=label,
                confidence=0.42 if embedding.get("production_clip_or_transformer") is False else 0.70,
                model_id=embedding.get("model_id") or "",
                runtime=embedding.get("engine") or "",
                metadata=embedding.get("metadata") or {},
            )
        )
    ocr = match.get("ocr") or {}
    if ocr.get("status"):
        items.append(
            evidence_item(
                "ocr",
                label=ocr.get("status") or "ocr",
                confidence=0.74 if ocr.get("status") == "ocr_completed" else 0.28,
                model_id=ocr.get("engine") or "",
                runtime=ocr.get("engine") or "",
                metadata={"text_preview": ocr.get("text_preview") or "", "error": ocr.get("error")},
            )
        )
    for reason in match.get("reasons") or []:
        items.append(evidence_item("ranking_reason", label=str(reason), metadata={}))
    return items


def _cap_confidence(
    confidence: float,
    degradations: list[dict],
    query_plan: dict,
    satisfied_stages: set[str] | None = None,
) -> tuple[float, list[dict]]:
    satisfied_stages = satisfied_stages or set()
    required_stages: set[str] = set()
    if query_plan.get("requires_region"):
        required_stages.update({"detector", "region_attributes"})
    if query_plan.get("requires_vector"):
        required_stages.add("image_text_embedding")
    if query_plan.get("requires_ocr"):
        required_stages.add("ocr")
    active = [
        item for item in (degradations or [])
        if (not required_stages or item.get("stage") in required_stages) and item.get("stage") not in satisfied_stages
    ]
    if (
        query_plan.get("requires_region")
        and "region_attributes" not in satisfied_stages
        and not any(item.get("stage") == "region_attributes" for item in active)
    ):
        active.append(degradation_item("region_query_without_region_attribute_index", stage="region_attributes", confidence_cap=0.40))
    if (
        query_plan.get("requires_vector")
        and "image_text_embedding" not in satisfied_stages
        and not any(item.get("stage") == "image_text_embedding" for item in active)
    ):
        active.append(degradation_item("semantic_query_without_product_image_text_embedding", stage="image_text_embedding", confidence_cap=0.48))
    cap = 1.0
    for item in active:
        value = item.get("confidence_cap")
        if isinstance(value, (int, float)):
            cap = min(cap, float(value))
    return round(min(float(confidence or 0), cap), 2), active


def productize_visual_match(db_path: Path, match: dict, query_plan: dict) -> dict:
    state = _visual_state_for_path(db_path, str(match.get("path") or ""))
    evidence = _evidence_from_match(match)
    satisfied_stages: set[str] = set()
    state_degradation_stages = {item.get("stage") for item in (state.get("degradation") or [])}
    if state:
        for stage in ("detector", "region_attributes", "image_text_embedding", "ocr"):
            if stage not in state_degradation_stages:
                satisfied_stages.add(stage)
    for item in evidence:
        kind = item.get("type") or item.get("kind")
        if kind == "region_attribute":
            satisfied_stages.update({"detector", "region_attributes"})
        if kind in {"image_text_embedding", "image_embedding"} and (item.get("runtime") or "").startswith("http_json"):
            satisfied_stages.add("image_text_embedding")
    confidence, degradation = _cap_confidence(
        float(match.get("confidence") or 0),
        state.get("degradation") or [],
        query_plan,
        satisfied_stages=satisfied_stages,
    )
    enriched = dict(match)
    enriched["confidence_uncapped"] = match.get("confidence")
    enriched["confidence"] = confidence
    enriched["query_plan"] = query_plan
    enriched["visual_state"] = state
    enriched["degradation"] = degradation
    enriched["degraded"] = bool(degradation)
    enriched["evidence_items"] = evidence
    enriched["evidence_chips"] = evidence_chips(evidence)
    enriched["confidence_kind"] = "degradation_capped" if degradation else match.get("confidence_kind", "legacy_score")
    return enriched


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _base_match_from_record(record: dict, *, score: float, confidence: float, reasons: list[str], source: str) -> dict:
    return {
        "path": record["path"],
        "relative_path": record["relative_path"],
        "type": record["type"],
        "score": round(score, 3),
        "confidence": round(confidence, 2),
        "matched_intents": [],
        "missing_intents": [],
        "reasons": sorted(set(reasons))[:12],
        "evidence": "; ".join(sorted(set(reasons)))[:360],
        "summary": record.get("summary", ""),
        "photo": (record.get("metadata") or {}).get("photo") or {},
        "image_embedding": {},
        "image_caption": {},
        "privacy": {
            "face_recognition_performed": False,
            "person_identity_verified": False,
            "person_or_child_terms_source": "generic_detector_or_region_attribute_only",
            "requires_privacy_review_before_face_model": True,
        },
        "ocr": {},
        "source": source,
        "confidence_kind": "product_score",
    }


def _query_attribute_targets(query_plan: dict) -> list[tuple[str, str, list[str]]]:
    targets: list[tuple[str, str, list[str]]] = []
    for attr in query_plan.get("attributes") or []:
        name = str(attr.get("name") or "")
        values = [str(value).lower().strip() for value in (attr.get("values") or []) if str(value).strip()]
        if not name or not values:
            continue
        if "." in name:
            namespace, field = name.split(".", 1)
        else:
            namespace, field = "attribute", name
        targets.append((namespace, field, values))
    return targets


def _person_region_exists(con, path: str, generation: int) -> bool:
    row = con.execute(
        """
        SELECT COUNT(*) AS count
        FROM vision_regions
        WHERE path = ? AND generation = ?
          AND (region_kind = 'person' OR label IN ('person', 'people', 'human'))
        """,
        (path, generation),
    ).fetchone()
    return int(row["count"] if row else 0) > 0


def _product_region_attribute_matches(db_path: Path, query_plan: dict, limit: int) -> list[dict]:
    targets = _query_attribute_targets(query_plan)
    if not targets:
        return []
    con = open_index_db(db_path)
    by_path: dict[str, dict] = {}
    try:
        for namespace, name, values in targets:
            placeholders = ",".join("?" for _ in values)
            rows = con.execute(
                f"""
                SELECT records.*, vision_attributes.id AS attribute_id,
                       vision_attributes.namespace AS attribute_namespace,
                       vision_attributes.name AS attribute_name,
                       vision_attributes.value AS attribute_value,
                       vision_attributes.confidence AS attribute_confidence,
                       vision_attributes.model_id AS attribute_model_id,
                       vision_attributes.runtime AS attribute_runtime,
                       vision_attributes.region_id AS attribute_region_id,
                       vision_regions.region_kind AS region_kind,
                       vision_regions.label AS region_label,
                       vision_regions.bbox_json AS region_bbox_json,
                       vision_regions.confidence AS region_confidence,
                       vision_regions.generation AS product_generation
                FROM vision_attributes
                JOIN vision_regions ON vision_regions.id = vision_attributes.region_id
                JOIN records ON records.path = vision_attributes.path
                WHERE vision_attributes.namespace = ?
                  AND vision_attributes.name = ?
                  AND lower(vision_attributes.value) IN ({placeholders})
                  AND vision_regions.region_kind = ?
                """,
                (namespace, name, *values, namespace if namespace == "upper_clothing" else namespace),
            ).fetchall()
            for row in rows:
                record = _record_from_sqlite_row(row)
                path = str(record.get("path") or "")
                generation = int(row["product_generation"] or 0)
                if "person" in (query_plan.get("entities") or []) and not _person_region_exists(con, path, generation):
                    continue
                item = by_path.setdefault(
                    path,
                    _base_match_from_record(
                        record,
                        score=0,
                        confidence=0,
                        reasons=[],
                        source="product_region_attribute_search",
                    ),
                )
                attr_conf = float(row["attribute_confidence"] or 0)
                region_conf = float(row["region_confidence"] or 0)
                item["score"] = float(item.get("score") or 0) + 18.0 + attr_conf * 6.0 + region_conf * 3.0
                item["confidence"] = max(float(item.get("confidence") or 0), min(0.96, 0.68 + attr_conf * 0.22 + region_conf * 0.08))
                label = f"{row['attribute_namespace']}.{row['attribute_name']}={row['attribute_value']}"
                item.setdefault("matched_intents", []).extend([str(row["attribute_value"]), str(row["region_label"])])
                item.setdefault("reasons", []).append(f"product region attribute matches `{label}`")
                if "person" in (query_plan.get("entities") or []):
                    item.setdefault("reasons", []).append("person region exists for clothing attribute binding")
                item.setdefault("product_evidence_items", []).append(
                    evidence_item(
                        "region_attribute",
                        label=label,
                        confidence=max(attr_conf, 0.01),
                        model_id=str(row["attribute_model_id"] or ""),
                        runtime=str(row["attribute_runtime"] or ""),
                        region_id=int(row["attribute_region_id"] or 0),
                        metadata={
                            "region_kind": row["region_kind"],
                            "region_label": row["region_label"],
                            "bbox": json.loads(row["region_bbox_json"] or "[]"),
                            "generation": generation,
                        },
                    )
                )
        matches = list(by_path.values())
    finally:
        con.close()
    for item in matches:
        item["score"] = round(float(item.get("score") or 0), 3)
        item["confidence"] = round(float(item.get("confidence") or 0), 2)
        item["matched_intents"] = sorted(set(item.get("matched_intents") or []))
        item["reasons"] = sorted(set(item.get("reasons") or []))[:12]
    matches.sort(key=lambda item: (item["score"], item["confidence"], item["relative_path"]), reverse=True)
    return matches[:limit]


def _product_embedding_matches(db_path: Path, query: str, limit: int, *, exclude_paths: set[str] | None = None) -> list[dict]:
    exclude_paths = exclude_paths or set()
    query_embedding = run_product_text_embedding(query)
    if query_embedding.get("status") != "product_text_embedding_completed":
        return []
    query_vector = query_embedding.get("vector") or []
    con = open_index_db(db_path)
    matches: list[dict] = []
    try:
        rows = con.execute(
            """
            SELECT records.*, vision_embeddings_v2.id AS embedding_id,
                   vision_embeddings_v2.model_id AS product_embedding_model_id,
                   vision_embeddings_v2.dim AS product_embedding_dim,
                   vision_embeddings_v2.vector_json AS product_embedding_vector_json,
                   vision_embeddings_v2.runtime AS product_embedding_runtime,
                   vision_embeddings_v2.generation AS product_generation
            FROM vision_embeddings_v2
            JOIN records ON records.path = vision_embeddings_v2.path
            WHERE vision_embeddings_v2.scope = 'image'
              AND vision_embeddings_v2.status = 'product_image_text_embedding_completed'
              AND vision_embeddings_v2.dim = ?
            """,
            (len(query_vector),),
        ).fetchall()
        for row in rows:
            if str(row["path"]) in exclude_paths:
                continue
            try:
                vector = json.loads(row["product_embedding_vector_json"] or "[]")
            except json.JSONDecodeError:
                vector = []
            similarity = _cosine(query_vector, [float(item) for item in vector])
            record = _record_from_sqlite_row(row)
            match = _base_match_from_record(
                record,
                score=10.0 + similarity * 10.0,
                confidence=max(0.08, min(0.94, 0.52 + similarity * 0.42)),
                reasons=[f"product image/text embedding cosine={similarity:.3f}"],
                source="product_image_text_embedding_search",
            )
            match["matched_intents"] = list(query_embedding.get("metadata", {}).get("tokens") or [])
            match["image_embedding"] = {
                "model_id": row["product_embedding_model_id"],
                "status": "product_image_text_embedding_completed",
                "engine": row["product_embedding_runtime"],
                "metadata": {"similarity": round(similarity, 4), "generation": row["product_generation"]},
                "production_clip_or_transformer": True,
            }
            match["product_evidence_items"] = [
                evidence_item(
                    "image_text_embedding",
                    label=str(row["product_embedding_model_id"] or "image_text_embedding"),
                    confidence=max(0.01, min(1.0, similarity)),
                    model_id=str(row["product_embedding_model_id"] or ""),
                    runtime=str(row["product_embedding_runtime"] or ""),
                    metadata={"similarity": round(similarity, 4), "scope": "image", "generation": row["product_generation"]},
                )
            ]
            matches.append(match)
    finally:
        con.close()
    matches.sort(key=lambda item: (item["score"], item["confidence"], item["relative_path"]), reverse=True)
    return matches[:limit]


def search_product_visual_index(db_path: Path, query: str, limit: int = 10) -> dict:
    query_plan = build_visual_query_plan(query)
    product_raw_matches: list[dict] = []
    if query_plan.get("requires_region"):
        product_raw_matches.extend(_product_region_attribute_matches(db_path, query_plan, limit=limit))
    seen_paths = {str(item.get("path") or "") for item in product_raw_matches}
    if query_plan.get("requires_vector") and not query_plan.get("strict_attributes"):
        product_raw_matches.extend(_product_embedding_matches(db_path, query, limit=limit, exclude_paths=seen_paths))
    legacy_matches = []
    if not product_raw_matches:
        legacy_matches = search_photo_semantic_index(db_path, query, limit=limit)
    raw_matches = product_raw_matches + legacy_matches
    matches = [productize_visual_match(db_path, item, query_plan) for item in raw_matches]
    degraded = bool(query_plan.get("requires_region") or query_plan.get("requires_vector")) and not matches
    degradation = []
    if degraded:
        if query_plan.get("requires_region"):
            degradation.append(degradation_item("no_region_attribute_results_available", stage="region_attributes", confidence_cap=0.0))
        if query_plan.get("requires_vector") and not query_plan.get("strict_attributes"):
            degradation.append(degradation_item("no_product_image_text_embedding_results_available", stage="image_text_embedding", confidence_cap=0.0))
    elif query_plan.get("strict_attributes") and not product_raw_matches:
        degradation.append(degradation_item("strict_attribute_search_using_legacy_caption_fallback", stage="region_attributes", confidence_cap=0.40))
    return {
        "ok": True,
        "query": str(query or ""),
        "query_plan": query_plan,
        "matches": matches,
        "degraded": bool(degraded or degradation or any(item.get("degraded") for item in matches)),
        "degradation": degradation,
        "search_runtime": "product_visual_search_v2_product_tables_with_legacy_fallback",
    }
