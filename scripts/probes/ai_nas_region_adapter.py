#!/usr/bin/env python3
"""Product detector and region-attribute adapter for OpenClaw AI-NAS."""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from ai_nas_common import PHOTO_EXTS, iso_now, open_index_db


PRODUCT_REGION_SCHEMA_VERSION = "ai_nas_product_region_attributes_v1"


def _endpoint() -> str:
    return str(
        os.environ.get("AI_NAS_VISION_REGION_ENDPOINT")
        or os.environ.get("AI_NAS_REGION_ATTRIBUTE_ENDPOINT")
        or os.environ.get("AI_NAS_VISION_DETECTOR_ENDPOINT")
        or os.environ.get("AI_NAS_YOLO_ENDPOINT")
        or ""
    ).strip()


def _model_id() -> str:
    return str(
        os.environ.get("AI_NAS_REGION_ATTRIBUTE_MODEL")
        or os.environ.get("AI_NAS_HUMAN_PARSING_MODEL")
        or os.environ.get("AI_NAS_VISION_DETECTOR_MODEL")
        or os.environ.get("AI_NAS_YOLO_MODEL")
        or "http-region-attribute"
    ).strip()


def product_region_runtime_status() -> dict:
    endpoint = _endpoint()
    model = _model_id()
    return {
        "schema_version": PRODUCT_REGION_SCHEMA_VERSION,
        "provider": "http_json_region_attributes",
        "configured": bool(endpoint),
        "endpoint_configured": bool(endpoint),
        "model_id": model,
        "ready": bool(endpoint),
        "required_response_fields": ["regions"],
        "optional_response_fields": ["attributes", "bbox", "confidence", "metadata"],
        "privacy_boundary": "private_endpoint_only; sends image bytes to configured detector/region endpoint",
    }


def _file_data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def _extract_json(raw: Any) -> Any:
    if isinstance(raw, dict) and isinstance(raw.get("choices"), list):
        try:
            content = raw["choices"][0]["message"]["content"]
            if isinstance(content, str):
                return json.loads(content)
            if isinstance(content, dict):
                return content
        except Exception:
            return raw
    return raw


def _bbox(value: Any) -> list[float]:
    if isinstance(value, dict):
        if all(key in value for key in ("x", "y", "width", "height")):
            value = [value["x"], value["y"], value["width"], value["height"]]
        elif all(key in value for key in ("x1", "y1", "x2", "y2")):
            value = [value["x1"], value["y1"], value["x2"], value["y2"]]
    if isinstance(value, list):
        out: list[float] = []
        for item in value[:4]:
            try:
                out.append(float(item))
            except (TypeError, ValueError):
                return []
        return out
    return []


def _region_kind(label: str, explicit: str = "") -> str:
    if explicit:
        return explicit
    lowered = label.lower()
    if "upper" in lowered or "shirt" in lowered or "top" in lowered or "clothing" in lowered:
        return "upper_clothing"
    if lowered in {"person", "people", "human"}:
        return "person"
    return "object"


def _attribute_rows(region: dict, default_confidence: float) -> list[dict]:
    raw = region.get("attributes") or region.get("attrs") or {}
    rows: list[dict] = []

    def add(key: str, value: Any, confidence: float | None = None) -> None:
        if value is None or value == "":
            return
        namespace, name = (key.split(".", 1) + [""])[:2] if "." in key else (_region_kind(str(region.get("label") or ""), str(region.get("region_kind") or "")), key)
        if not name:
            name = namespace
            namespace = "attribute"
        values = value if isinstance(value, list) else [value]
        for item in values:
            if item is None or item == "":
                continue
            rows.append(
                {
                    "namespace": str(namespace),
                    "name": str(name),
                    "value": str(item).lower().strip(),
                    "confidence": float(confidence if confidence is not None else default_confidence),
                }
            )

    if isinstance(raw, dict):
        for key, value in raw.items():
            if isinstance(value, dict):
                for subkey, subvalue in value.items():
                    add(f"{key}.{subkey}", subvalue)
            else:
                add(str(key), value)
    elif isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            namespace = str(item.get("namespace") or item.get("group") or "")
            name = str(item.get("name") or item.get("key") or "")
            key = f"{namespace}.{name}" if namespace and name else (name or namespace)
            add(key, item.get("value"), item.get("confidence"))
    for key in ("color", "dominant_color", "upper_color"):
        if key in region:
            add("upper_clothing.color" if _region_kind(str(region.get("label") or ""), str(region.get("region_kind") or "")) == "upper_clothing" else key, region.get(key))
    return rows


def _normalize_regions(raw: Any) -> dict:
    raw = _extract_json(raw)
    if not isinstance(raw, dict):
        raw = {"regions": []}
    source_regions = raw.get("regions") or raw.get("detections") or raw.get("objects") or []
    if isinstance(source_regions, dict):
        source_regions = [source_regions]
    regions: list[dict] = []
    for item in source_regions:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or item.get("class") or item.get("name") or item.get("object") or "").strip()
        if not label:
            continue
        try:
            confidence = float(item.get("confidence") if item.get("confidence") is not None else item.get("score", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        region = {
            "region_kind": _region_kind(label, str(item.get("region_kind") or item.get("kind") or "")),
            "label": label.lower(),
            "bbox": _bbox(item.get("bbox") or item.get("box") or item.get("rect") or []),
            "confidence": confidence,
            "attributes": _attribute_rows(item, confidence),
            "metadata": item.get("metadata") if isinstance(item.get("metadata"), dict) else {},
        }
        regions.append(region)
    return {
        "model_id": str(raw.get("model_id") or raw.get("model") or _model_id()),
        "regions": regions,
        "metadata": raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {},
    }


def request_product_regions(path: Path, relative_path: str) -> dict:
    endpoint = _endpoint()
    if not endpoint:
        raise RuntimeError("product_region_endpoint_not_configured")
    timeout = float(os.environ.get("AI_NAS_REGION_ATTRIBUTE_TIMEOUT_SECONDS") or "90")
    payload = {
        "schema_version": PRODUCT_REGION_SCHEMA_VERSION,
        "model": _model_id(),
        "relative_path": relative_path,
        "mime_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        "image_url": {"url": _file_data_url(path), "detail": "high"},
        "instructions": (
            "Return JSON regions with label, bbox, confidence, and attributes. "
            "For clothing queries, bind color to upper_clothing.color rather than global image color."
        ),
    }
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    api_key = str(os.environ.get("AI_NAS_REGION_ATTRIBUTE_API_KEY") or os.environ.get("AI_NAS_VISION_DETECTOR_API_KEY") or "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw_text = response.read().decode("utf-8", errors="replace")
    try:
        raw = json.loads(raw_text) if raw_text.strip() else {}
    except json.JSONDecodeError:
        raw = {}
    return _normalize_regions(raw)


def run_product_region_analysis_for_record(record: dict) -> dict:
    path = Path(str(record.get("path") or ""))
    rel = str(record.get("relative_path") or path.name)
    now = iso_now()
    runtime = product_region_runtime_status()
    if not runtime["configured"]:
        return {
            "path": str(path),
            "relative_path": rel,
            "status": "blocked_missing_product_region_adapter",
            "model_id": runtime.get("model_id") or "",
            "regions": [],
            "runtime": "http_json_region_attributes",
            "error": "AI_NAS_VISION_REGION_ENDPOINT or compatible detector endpoint is not configured",
            "metadata": {"runtime": runtime},
            "updated_at": now,
        }
    if path.suffix.lower() not in PHOTO_EXTS:
        return {
            "path": str(path),
            "relative_path": rel,
            "status": "blocked_unsupported_product_region_input",
            "model_id": runtime.get("model_id") or "",
            "regions": [],
            "runtime": "http_json_region_attributes",
            "error": f"product region analysis accepts image files only: {path.suffix.lower()}",
            "metadata": {"runtime": runtime},
            "updated_at": now,
        }
    try:
        normalized = request_product_regions(path, rel)
        regions = normalized.get("regions") or []
        return {
            "path": str(path),
            "relative_path": rel,
            "status": "product_region_analysis_completed" if regions else "product_region_analysis_completed_no_regions",
            "model_id": normalized.get("model_id") or runtime.get("model_id") or _model_id(),
            "regions": regions,
            "runtime": "http_json_region_attributes",
            "error": None,
            "metadata": {"runtime": runtime, "adapter_metadata": normalized.get("metadata") or {}},
            "updated_at": now,
        }
    except (urllib.error.URLError, TimeoutError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        return {
            "path": str(path),
            "relative_path": rel,
            "status": "product_region_analysis_failed",
            "model_id": runtime.get("model_id") or _model_id(),
            "regions": [],
            "runtime": "http_json_region_attributes",
            "error": f"{type(exc).__name__}:{exc}",
            "metadata": {"runtime": runtime},
            "updated_at": now,
        }


def upsert_product_region_evidence(db_path: Path, result: dict) -> dict:
    if result.get("status") not in {"product_region_analysis_completed", "product_region_analysis_completed_no_regions"}:
        return {"ok": True, "regions_created": 0, "reason": result.get("status")}
    path = str(result.get("path") or "")
    rel = str(result.get("relative_path") or "")
    if not path or not rel:
        return {"ok": False, "regions_created": 0, "error": "missing_path_or_relative_path"}
    now = iso_now()
    model_id = str(result.get("model_id") or _model_id())
    regions = result.get("regions") or []
    metadata = result.get("metadata") or {}
    con = open_index_db(db_path)
    try:
        state = con.execute(
            "SELECT active_generation, privacy_class FROM photo_visual_state WHERE path = ?",
            (path,),
        ).fetchone()
        generation = int(state["active_generation"]) if state else 0
        privacy_class = str(state["privacy_class"] or "standard") if state else "standard"
        old_ids = [
            int(row["id"])
            for row in con.execute(
                """
                SELECT id FROM vision_regions
                WHERE path = ? AND generation = ? AND model_id = ? AND runtime = 'http_json_region_attributes'
                """,
                (path, generation, model_id),
            )
        ]
        if old_ids:
            placeholders = ",".join("?" for _ in old_ids)
            con.execute(f"DELETE FROM vision_attributes WHERE region_id IN ({placeholders})", old_ids)
            con.execute(f"DELETE FROM vision_regions WHERE id IN ({placeholders})", old_ids)
        created_ids: list[int] = []
        attribute_count = 0
        for region in regions:
            cur = con.execute(
                """
                INSERT INTO vision_regions(
                    path, relative_path, generation, region_kind, label, bbox_json,
                    mask_artifact_id, confidence, model_id, runtime, metadata_json, created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?)
                """,
                (
                    path,
                    rel,
                    generation,
                    str(region.get("region_kind") or "object"),
                    str(region.get("label") or ""),
                    json.dumps(region.get("bbox") or [], separators=(",", ":")),
                    float(region.get("confidence") or 0),
                    model_id,
                    str(result.get("runtime") or "http_json_region_attributes"),
                    json.dumps(region.get("metadata") or {}, ensure_ascii=False),
                    now,
                ),
            )
            region_id = int(cur.lastrowid)
            created_ids.append(region_id)
            for attr in region.get("attributes") or []:
                con.execute(
                    """
                    INSERT INTO vision_attributes(
                        region_id, path, relative_path, generation, namespace, name, value,
                        confidence, model_id, runtime, evidence_json, created_at
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        region_id,
                        path,
                        rel,
                        generation,
                        str(attr.get("namespace") or "attribute"),
                        str(attr.get("name") or "value"),
                        str(attr.get("value") or ""),
                        float(attr.get("confidence") or 0),
                        model_id,
                        str(result.get("runtime") or "http_json_region_attributes"),
                        json.dumps({"region_id": region_id}, ensure_ascii=False),
                        now,
                    ),
                )
                attribute_count += 1
        artifact_id = "regions-" + hashlib.sha256(f"{path}:{generation}:{model_id}:{now}".encode("utf-8")).hexdigest()[:24]
        artifact_payload = {
            "status": result.get("status"),
            "model_id": model_id,
            "region_count": len(regions),
            "attribute_count": attribute_count,
            "metadata": metadata,
        }
        con.execute(
            """
            INSERT OR REPLACE INTO vision_artifacts(
                artifact_id, path, relative_path, generation, artifact_type, uri,
                mime_type, size_bytes, model_id, privacy_class, metadata_json, created_at
            )
            VALUES(?, ?, ?, ?, 'region_attributes_json', ?, 'application/json', ?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                path,
                rel,
                generation,
                f"sqlite://vision_regions/{created_ids[0] if created_ids else 0}",
                len(json.dumps(artifact_payload, ensure_ascii=False).encode("utf-8")),
                model_id,
                privacy_class,
                json.dumps(artifact_payload, ensure_ascii=False),
                now,
            ),
        )
        con.commit()
        return {
            "ok": True,
            "regions_created": len(created_ids),
            "attributes_created": attribute_count,
            "artifact_id": artifact_id,
            "generation": generation,
        }
    finally:
        con.close()


def product_region_summary(db_path: Path, limit: int = 20) -> dict:
    con = open_index_db(db_path)
    try:
        region_counts = {
            row["label"]: row["count"]
            for row in con.execute(
                "SELECT label, COUNT(*) AS count FROM vision_regions GROUP BY label ORDER BY count DESC"
            )
        }
        attribute_counts = {
            f"{row['namespace']}.{row['name']}={row['value']}": row["count"]
            for row in con.execute(
                """
                SELECT namespace, name, value, COUNT(*) AS count
                FROM vision_attributes
                WHERE region_id IS NOT NULL
                GROUP BY namespace, name, value
                ORDER BY count DESC
                LIMIT ?
                """,
                (limit,),
            )
        }
        recent = [
            {
                "relative_path": row["relative_path"],
                "label": row["label"],
                "region_kind": row["region_kind"],
                "confidence": row["confidence"],
                "model_id": row["model_id"],
                "created_at": row["created_at"],
            }
            for row in con.execute(
                """
                SELECT relative_path, label, region_kind, confidence, model_id, created_at
                FROM vision_regions
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
        ]
    finally:
        con.close()
    return {"region_counts": region_counts, "attribute_counts": attribute_counts, "recent": recent}
