from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


SOURCE_PRIORITY = [
    "asset_id",
    "ai_space_asset_view",
    "smart_asset_names",
    "smart_category_memberships",
    "yolo_labels",
    "person_attribute",
    "ocr_tags",
    "subtitle_tags",
    "media_index",
    "fallback_filename_heuristic",
]


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac"}
DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".csv", ".xlsx", ".pptx"}


def resolve_asset_for_source(
    source_rel: str,
    personal_root: str | Path,
    report_root: str | Path,
) -> dict[str, Any]:
    """Resolve a Personal-root source into AI-index evidence for product-grade planning."""
    personal = Path(personal_root)
    root = Path(report_root)
    rel = normalize_rel(source_rel)
    path = personal / rel
    if not path.exists() or not path.is_file():
        return {
            "ok": False,
            "degraded": True,
            "blocker": "source_file_not_found",
            "source_rel": rel,
            "raw_path_returned": False,
        }
    candidates = _candidate_asset_ids(path, rel, personal_root=personal)
    candidates.extend(_asset_ids_from_runtime_tables(root, path, rel, personal_root=personal))
    candidates = _dedupe([item for item in candidates if item])
    ai_views = _ai_space_views(root, candidates)
    smart_names = _smart_names(root, candidates)
    memberships = _smart_memberships(root, candidates)
    yolo_labels = _yolo_labels(root, candidates)
    person_attrs = _person_attrs(root, candidates)
    for asset_id in candidates:
        view = dict(ai_views.get(asset_id) or {})
        smart_name = smart_names.get(asset_id)
        categories = _dedupe(
            [
                *[item.get("category_name") for item in memberships.get(asset_id, []) if isinstance(item, dict)],
                *[item.get("category_name_zh") for item in memberships.get(asset_id, []) if isinstance(item, dict)],
                *[str(item) for item in view.get("category_names") or []],
            ]
        )
        labels = _dedupe([*yolo_labels.get(asset_id, []), *[str(item) for item in view.get("object_labels") or []]])
        attrs = _dedupe([*person_attrs.get(asset_id, []), *[str(item) for item in view.get("person_attrs") or []]])
        evidence_refs = _dedupe(
            [
                *[str(item) for item in view.get("evidence_refs") or []],
                *[item.get("evidence_ref") for item in yolo_labels.get(f"{asset_id}:evidence", []) if isinstance(item, dict)],
                *[item.get("evidence_ref") for item in memberships.get(asset_id, []) if isinstance(item, dict)],
            ]
        )
        if not (view or smart_name or categories or labels or attrs):
            continue
        source_parts: list[str] = []
        if view:
            source_parts.append("ai_space")
        if smart_name:
            source_parts.append("smart_naming")
        if categories:
            source_parts.append("smart_classification")
        if labels:
            source_parts.append("yolo")
        if attrs:
            source_parts.append("person_attribute")
        resolution_source = "+".join(source_parts) or "ai_index"
        return {
            "ok": True,
            "asset_id": asset_id,
            "resolution_source": resolution_source,
            "ai_driven": True,
            "modality": view.get("modality") or modality_for_path(path),
            "title_redacted": view.get("title_redacted") or path.name,
            "categories": categories,
            "category_names": categories,
            "display_name_zh": (smart_name or {}).get("display_name_zh"),
            "suggested_filename_zh": (smart_name or {}).get("suggested_filename_zh"),
            "object_labels": labels,
            "person_attrs": attrs,
            "ocr_tags": [],
            "subtitle_tags": [],
            "evidence_refs": evidence_refs,
            "confidence": _confidence(view, smart_name, categories, labels, attrs),
            "source_priority": SOURCE_PRIORITY,
            "smart_name": smart_name or {},
            "fallback_available": False,
            "fallback_used": False,
            "raw_path_returned": False,
        }
    return {
        "ok": False,
        "degraded": True,
        "blocker": "ai_index_missing_for_asset",
        "source_rel": rel,
        "asset_candidates": candidates[:10],
        "resolution_source": "fallback_filename",
        "ai_driven": False,
        "fallback_available": True,
        "fallback_used": True,
        "source_priority": SOURCE_PRIORITY,
        "raw_path_returned": False,
    }


def normalize_rel(value: str) -> str:
    return str(value or "").replace("\\", "/").strip("/")


def short_hash(value: str, length: int) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:length]


def modality_for_path(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in VIDEO_EXTENSIONS:
        return "video"
    if ext in AUDIO_EXTENSIONS:
        return "audio"
    if ext in DOCUMENT_EXTENSIONS:
        return "document"
    return "other"


def _candidate_asset_ids(path: Path, source_rel: str, *, personal_root: Path) -> list[str]:
    stat = path.stat()
    rel = normalize_rel(source_rel)
    candidates = [
        "mm_" + short_hash(f"{rel}:{int(stat.st_size)}:{int(stat.st_mtime)}", 24),
        "mm_" + short_hash(f"{path.name}:{int(stat.st_size)}:{int(stat.st_mtime)}", 24),
        "autoasset_" + short_hash(f"{rel}:{int(stat.st_size)}:{int(stat.st_mtime)}", 24),
    ]
    try:
        resolved = path.resolve(strict=False)
        rel_to_root = resolved.relative_to(personal_root.resolve(strict=False)).as_posix()
        candidates.insert(0, "mm_" + short_hash(f"{rel_to_root}:{int(stat.st_size)}:{int(stat.st_mtime)}", 24))
        yolo_path_hash = hashlib.sha256(str(resolved).encode("utf-8", errors="replace")).hexdigest()
        candidates.append("yasset_" + hashlib.sha256(f"{yolo_path_hash}:{int(stat.st_size)}:{int(stat.st_mtime)}".encode("utf-8")).hexdigest()[:24])
    except (OSError, ValueError):
        pass
    return _dedupe(candidates)


def _asset_ids_from_runtime_tables(root: Path, path: Path, source_rel: str, *, personal_root: Path) -> list[str]:
    stat = path.stat()
    rel_hash = short_hash(normalize_rel(source_rel), 32)
    abs_hash = hashlib.sha256(str(path.resolve(strict=False)).encode("utf-8", errors="replace")).hexdigest()
    title = path.name[:160]
    ids: list[str] = []
    queries = [
        (
            root / "multimodal_search" / "runtime" / "multimodal_search.db",
            "SELECT asset_id FROM mm_assets WHERE path_hash=? OR (title_redacted=? AND size_bytes=? AND mtime=?)",
            (rel_hash, title, int(stat.st_size), int(stat.st_mtime)),
        ),
        (
            root / "yolo_index" / "runtime" / "yolo_index.db",
            "SELECT asset_id FROM mm_yolo_assets WHERE path_hash=? OR (title_redacted=? AND size_bytes=? AND mtime=?)",
            (abs_hash, title, int(stat.st_size), int(stat.st_mtime)),
        ),
    ]
    try:
        rel_to_root = path.resolve(strict=False).relative_to(personal_root.resolve(strict=False)).as_posix()
        queries.append(
            (
                root / "multimodal_search" / "runtime" / "multimodal_search.db",
                "SELECT asset_id FROM mm_assets WHERE path_hash=?",
                (short_hash(rel_to_root, 32),),
            )
        )
    except (OSError, ValueError):
        pass
    for db_path, sql, params in queries:
        ids.extend(_query_scalar_list(db_path, sql, params))
    return ids


def _ai_space_views(root: Path, asset_ids: list[str]) -> dict[str, dict[str, Any]]:
    rows = _query_rows(root / "ai_space" / "runtime" / "ai_space.db", "SELECT * FROM ai_space_asset_views WHERE asset_id IN ({})", asset_ids)
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        row["object_labels"] = _loads(row.pop("object_labels_json", "[]"), [])
        row["person_attrs"] = _loads(row.pop("person_attrs_json", "[]"), [])
        row["category_names"] = _loads(row.pop("category_names_json", "[]"), [])
        row["evidence_refs"] = _loads(row.pop("evidence_refs_json", "[]"), [])
        out[str(row["asset_id"])] = row
    return out


def _smart_names(root: Path, asset_ids: list[str]) -> dict[str, dict[str, Any]]:
    rows = _query_rows(root / "smart_classification" / "runtime" / "smart_classification.db", "SELECT * FROM smart_asset_names WHERE asset_id IN ({})", asset_ids)
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        row["naming_reason"] = _loads(row.pop("naming_reason_json", "{}"), {})
        row["risk_flags"] = _loads(row.pop("risk_flags_json", "{}"), {})
        out[str(row["asset_id"])] = row
    return out


def _smart_memberships(root: Path, asset_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    sql = """
        SELECT m.asset_id,m.score,m.matched_by_json,m.evidence_refs_json,c.name,c.name_zh
        FROM smart_category_memberships m
        LEFT JOIN smart_categories c ON c.category_id=m.category_id
        WHERE m.asset_id IN ({})
        ORDER BY m.score DESC
    """
    rows = _query_rows(root / "smart_classification" / "runtime" / "smart_classification.db", sql, asset_ids)
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        out.setdefault(str(row["asset_id"]), []).append(
            {
                "category_name": row.get("name"),
                "category_name_zh": row.get("name_zh"),
                "score": row.get("score"),
                "matched_by": _loads(row.get("matched_by_json"), []),
                "evidence_ref": ",".join(str(item) for item in _loads(row.get("evidence_refs_json"), [])),
            }
        )
    return out


def _yolo_labels(root: Path, asset_ids: list[str]) -> dict[str, list[Any]]:
    rows = _query_rows(root / "yolo_index" / "runtime" / "yolo_index.db", "SELECT asset_id,label,evidence_ref FROM mm_yolo_detections WHERE asset_id IN ({})", asset_ids)
    out: dict[str, list[Any]] = {}
    for row in rows:
        out.setdefault(str(row["asset_id"]), []).append(str(row.get("label") or ""))
        out.setdefault(f"{row['asset_id']}:evidence", []).append({"evidence_ref": row.get("evidence_ref")})
    return out


def _person_attrs(root: Path, asset_ids: list[str]) -> dict[str, list[str]]:
    rows = _query_rows(root / "person_attribute" / "runtime" / "person_attribute.db", "SELECT asset_id,attribute_tags_json FROM person_attribute_detections WHERE asset_id IN ({})", asset_ids)
    out: dict[str, list[str]] = {}
    for row in rows:
        out.setdefault(str(row["asset_id"]), []).extend(str(item) for item in _loads(row.get("attribute_tags_json"), []))
    return out


def _query_rows(db_path: Path, sql_template: str, asset_ids: list[str]) -> list[dict[str, Any]]:
    if not db_path.exists() or not asset_ids:
        return []
    placeholders = ",".join("?" for _ in asset_ids)
    try:
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute(sql_template.format(placeholders), asset_ids)]
    except sqlite3.Error:
        return []


def _query_scalar_list(db_path: Path, sql: str, params: tuple[Any, ...]) -> list[str]:
    if not db_path.exists():
        return []
    try:
        with sqlite3.connect(str(db_path)) as conn:
            return [str(row[0]) for row in conn.execute(sql, params) if row[0]]
    except sqlite3.Error:
        return []


def _loads(value: Any, fallback: Any) -> Any:
    try:
        return json.loads(value or json.dumps(fallback))
    except (TypeError, json.JSONDecodeError):
        return fallback


def _dedupe(values: list[Any]) -> list[Any]:
    seen: set[str] = set()
    out: list[Any] = []
    for value in values:
        if value is None:
            continue
        key = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _confidence(view: dict[str, Any], smart_name: dict[str, Any] | None, categories: list[Any], labels: list[Any], attrs: list[Any]) -> float:
    score = 0.0
    if view:
        score += 0.35
    if smart_name:
        score += 0.2
    if categories:
        score += 0.2
    if labels:
        score += 0.15
    if attrs:
        score += 0.1
    return min(score, 0.95)
