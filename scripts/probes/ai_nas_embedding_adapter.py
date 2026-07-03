#!/usr/bin/env python3
"""Product image/text embedding adapter for OpenClaw AI-NAS.

The adapter is HTTP-first because the encoder may run on a GPU/NPU box or an
S100P-side worker. The local histogram embedding remains a compatibility
fallback elsewhere; this module records only product-grade shared-space vectors.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import mimetypes
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from ai_nas_common import PHOTO_EXTS, iso_now, open_index_db


PRODUCT_EMBEDDING_SCHEMA_VERSION = "ai_nas_product_image_text_embedding_v1"


def product_embedding_runtime_status() -> dict:
    endpoint = str(
        os.environ.get("AI_NAS_IMAGE_TEXT_EMBEDDING_ENDPOINT")
        or os.environ.get("AI_NAS_CLIP_ENDPOINT")
        or os.environ.get("AI_NAS_SIGLIP_ENDPOINT")
        or ""
    ).strip()
    model = str(
        os.environ.get("AI_NAS_IMAGE_TEXT_EMBEDDING_MODEL")
        or os.environ.get("AI_NAS_SIGLIP_MODEL")
        or os.environ.get("AI_NAS_CLIP_MODEL")
        or ""
    ).strip()
    return {
        "schema_version": PRODUCT_EMBEDDING_SCHEMA_VERSION,
        "provider": "http_json_image_text_embedding",
        "configured": bool(endpoint),
        "endpoint_configured": bool(endpoint),
        "model_id": model,
        "ready": bool(endpoint),
        "required_response_fields": ["embedding"],
        "optional_response_fields": ["dim", "metadata"],
        "privacy_boundary": "private_endpoint_only; sends images or query text to configured embedding endpoint",
    }


def _endpoint() -> str:
    return str(
        os.environ.get("AI_NAS_IMAGE_TEXT_EMBEDDING_ENDPOINT")
        or os.environ.get("AI_NAS_CLIP_ENDPOINT")
        or os.environ.get("AI_NAS_SIGLIP_ENDPOINT")
        or ""
    ).strip()


def _model_id() -> str:
    return str(
        os.environ.get("AI_NAS_IMAGE_TEXT_EMBEDDING_MODEL")
        or os.environ.get("AI_NAS_SIGLIP_MODEL")
        or os.environ.get("AI_NAS_CLIP_MODEL")
        or "http-image-text-embedding"
    ).strip()


def _file_data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def _normalize_vector(value: Any) -> list[float]:
    if isinstance(value, dict):
        for key in ("embedding", "vector", "image_embedding", "text_embedding"):
            if key in value:
                return _normalize_vector(value[key])
        if isinstance(value.get("data"), list) and value["data"]:
            return _normalize_vector(value["data"][0])
    if isinstance(value, list):
        out: list[float] = []
        for item in value:
            try:
                out.append(float(item))
            except (TypeError, ValueError):
                return []
        return out
    return []


def _l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(item * item for item in vector))
    if norm <= 0:
        return vector
    return [round(item / norm, 8) for item in vector]


def _normalize_response(raw: Any, input_type: str) -> dict:
    vector = _normalize_vector(raw)
    metadata: dict[str, Any] = {}
    model_id = _model_id()
    if isinstance(raw, dict):
        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        model_id = str(raw.get("model_id") or raw.get("model") or model_id)
        if not vector and isinstance(raw.get("data"), list) and raw["data"]:
            first = raw["data"][0]
            vector = _normalize_vector(first)
            if isinstance(first, dict):
                metadata = first.get("metadata") if isinstance(first.get("metadata"), dict) else metadata
    vector = _l2_normalize(vector)
    return {
        "model_id": model_id,
        "input_type": input_type,
        "vector": vector,
        "dim": len(vector),
        "metadata": metadata,
    }


def request_product_embedding(*, input_type: str, text: str = "", path: Path | None = None, relative_path: str = "") -> dict:
    endpoint = _endpoint()
    if not endpoint:
        raise RuntimeError("product_embedding_endpoint_not_configured")
    model = _model_id()
    timeout = float(os.environ.get("AI_NAS_IMAGE_TEXT_EMBEDDING_TIMEOUT_SECONDS") or "60")
    payload: dict[str, Any] = {
        "schema_version": PRODUCT_EMBEDDING_SCHEMA_VERSION,
        "model": model,
        "input_type": input_type,
        "relative_path": relative_path,
    }
    if input_type == "image":
        if path is None:
            raise RuntimeError("image_embedding_requires_path")
        payload["mime_type"] = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        payload["image_url"] = {"url": _file_data_url(path), "detail": "low"}
    elif input_type == "text":
        payload["text"] = text
    else:
        raise RuntimeError(f"unsupported_embedding_input_type:{input_type}")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    api_key = str(os.environ.get("AI_NAS_IMAGE_TEXT_EMBEDDING_API_KEY") or "").strip()
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
    return _normalize_response(raw, input_type)


def run_product_image_embedding_for_record(record: dict) -> dict:
    path = Path(str(record.get("path") or ""))
    rel = str(record.get("relative_path") or path.name)
    now = iso_now()
    runtime = product_embedding_runtime_status()
    if not runtime["configured"]:
        return {
            "path": str(path),
            "relative_path": rel,
            "scope": "image",
            "status": "blocked_missing_product_image_text_embedding_adapter",
            "model_id": runtime.get("model_id") or "",
            "dim": 0,
            "vector": [],
            "runtime": "http_json_image_text_embedding",
            "error": "AI_NAS_IMAGE_TEXT_EMBEDDING_ENDPOINT is not configured",
            "metadata": {"runtime": runtime},
            "updated_at": now,
        }
    if path.suffix.lower() not in PHOTO_EXTS:
        return {
            "path": str(path),
            "relative_path": rel,
            "scope": "image",
            "status": "blocked_unsupported_product_embedding_input",
            "model_id": runtime.get("model_id") or "",
            "dim": 0,
            "vector": [],
            "runtime": "http_json_image_text_embedding",
            "error": f"product image/text embedding accepts image files only: {path.suffix.lower()}",
            "metadata": {"runtime": runtime},
            "updated_at": now,
        }
    try:
        normalized = request_product_embedding(input_type="image", path=path, relative_path=rel)
        vector = normalized.get("vector") or []
        return {
            "path": str(path),
            "relative_path": rel,
            "scope": "image",
            "status": "product_image_text_embedding_completed" if vector else "product_image_text_embedding_empty",
            "model_id": normalized.get("model_id") or runtime.get("model_id") or _model_id(),
            "dim": int(normalized.get("dim") or len(vector)),
            "vector": vector,
            "runtime": "http_json_image_text_embedding",
            "error": None if vector else "embedding endpoint returned an empty vector",
            "metadata": {"runtime": runtime, "adapter_metadata": normalized.get("metadata") or {}},
            "updated_at": now,
        }
    except (urllib.error.URLError, TimeoutError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        return {
            "path": str(path),
            "relative_path": rel,
            "scope": "image",
            "status": "product_image_text_embedding_failed",
            "model_id": runtime.get("model_id") or _model_id(),
            "dim": 0,
            "vector": [],
            "runtime": "http_json_image_text_embedding",
            "error": f"{type(exc).__name__}:{exc}",
            "metadata": {"runtime": runtime},
            "updated_at": now,
        }


def run_product_text_embedding(query: str) -> dict:
    runtime = product_embedding_runtime_status()
    now = iso_now()
    if not runtime["configured"]:
        return {
            "query": str(query or ""),
            "scope": "text_query",
            "status": "blocked_missing_product_image_text_embedding_adapter",
            "model_id": runtime.get("model_id") or "",
            "dim": 0,
            "vector": [],
            "runtime": "http_json_image_text_embedding",
            "error": "AI_NAS_IMAGE_TEXT_EMBEDDING_ENDPOINT is not configured",
            "metadata": {"runtime": runtime},
            "updated_at": now,
        }
    try:
        normalized = request_product_embedding(input_type="text", text=str(query or ""), relative_path="")
        vector = normalized.get("vector") or []
        return {
            "query": str(query or ""),
            "scope": "text_query",
            "status": "product_text_embedding_completed" if vector else "product_text_embedding_empty",
            "model_id": normalized.get("model_id") or runtime.get("model_id") or _model_id(),
            "dim": int(normalized.get("dim") or len(vector)),
            "vector": vector,
            "runtime": "http_json_image_text_embedding",
            "error": None if vector else "embedding endpoint returned an empty text vector",
            "metadata": {"runtime": runtime, "adapter_metadata": normalized.get("metadata") or {}},
            "updated_at": now,
        }
    except (urllib.error.URLError, TimeoutError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        return {
            "query": str(query or ""),
            "scope": "text_query",
            "status": "product_text_embedding_failed",
            "model_id": runtime.get("model_id") or _model_id(),
            "dim": 0,
            "vector": [],
            "runtime": "http_json_image_text_embedding",
            "error": f"{type(exc).__name__}:{exc}",
            "metadata": {"runtime": runtime},
            "updated_at": now,
        }


def upsert_product_image_embedding(db_path: Path, result: dict) -> dict:
    if result.get("status") != "product_image_text_embedding_completed":
        return {"ok": True, "embedding_created": False, "reason": result.get("status")}
    path = str(result.get("path") or "")
    rel = str(result.get("relative_path") or "")
    vector = result.get("vector") or []
    if not path or not rel or not vector:
        return {"ok": False, "embedding_created": False, "error": "missing_path_relative_path_or_vector"}
    now = iso_now()
    con = open_index_db(db_path)
    try:
        state = con.execute(
            "SELECT active_generation, privacy_class FROM photo_visual_state WHERE path = ?",
            (path,),
        ).fetchone()
        generation = int(state["active_generation"]) if state else 0
        privacy_class = str(state["privacy_class"] or "standard") if state else "standard"
        model_id = str(result.get("model_id") or _model_id())
        metadata = result.get("metadata") or {}
        con.execute(
            """
            DELETE FROM vision_embeddings_v2
            WHERE path = ? AND generation = ? AND scope = 'image' AND model_id = ?
            """,
            (path, generation, model_id),
        )
        cur = con.execute(
            """
            INSERT INTO vision_embeddings_v2(
                path, relative_path, generation, scope, region_id, model_id, dim,
                vector_json, status, runtime, metadata_json, created_at
            )
            VALUES(?, ?, ?, 'image', NULL, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                path,
                rel,
                generation,
                model_id,
                int(result.get("dim") or len(vector)),
                json.dumps(vector, separators=(",", ":")),
                result.get("status"),
                str(result.get("runtime") or "http_json_image_text_embedding"),
                json.dumps(metadata, ensure_ascii=False),
                now,
            ),
        )
        artifact_id = "embedding-" + hashlib.sha256(f"{path}:{generation}:{model_id}:{now}".encode("utf-8")).hexdigest()[:24]
        artifact_payload = {
            "status": result.get("status"),
            "model_id": model_id,
            "dim": int(result.get("dim") or len(vector)),
            "scope": "image",
            "metadata": metadata,
        }
        con.execute(
            """
            INSERT OR REPLACE INTO vision_artifacts(
                artifact_id, path, relative_path, generation, artifact_type, uri,
                mime_type, size_bytes, model_id, privacy_class, metadata_json, created_at
            )
            VALUES(?, ?, ?, ?, 'image_text_embedding_json', ?, 'application/json', ?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                path,
                rel,
                generation,
                f"sqlite://vision_embeddings_v2/{int(cur.lastrowid)}",
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
            "embedding_created": True,
            "embedding_id": int(cur.lastrowid),
            "artifact_id": artifact_id,
            "generation": generation,
            "dim": int(result.get("dim") or len(vector)),
        }
    finally:
        con.close()


def product_embedding_summary(db_path: Path, limit: int = 20) -> dict:
    con = open_index_db(db_path)
    try:
        status_counts = {
            row["status"]: row["count"]
            for row in con.execute(
                """
                SELECT status, COUNT(*) AS count
                FROM vision_embeddings_v2
                WHERE scope = 'image'
                GROUP BY status
                """
            )
        }
        recent = [
            {
                "relative_path": row["relative_path"],
                "model_id": row["model_id"],
                "scope": row["scope"],
                "dim": row["dim"],
                "status": row["status"],
                "runtime": row["runtime"],
                "created_at": row["created_at"],
            }
            for row in con.execute(
                """
                SELECT relative_path, model_id, scope, dim, status, runtime, created_at
                FROM vision_embeddings_v2
                WHERE scope = 'image'
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
        ]
    finally:
        con.close()
    return {"status_counts": status_counts, "recent": recent}
