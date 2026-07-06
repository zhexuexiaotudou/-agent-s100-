from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

from src.smart_classification.chinese_namer import ChineseSmartNamer


ILLEGAL_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]+')


def asset_id_for_rel(source_rel: str, *, size_bytes: int, mtime: int) -> str:
    seed = f"{source_rel}:{size_bytes}:{mtime}"
    return "autoasset_" + hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:24]


def path_hash(value: str) -> str:
    return hashlib.sha256(normalize_rel(value).encode("utf-8", errors="replace")).hexdigest()


def short_hash(value: str, length: int) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:length]


def normalize_rel(value: str) -> str:
    return str(value or "").replace("\\", "/").strip("/")


def safe_filename(value: str) -> str:
    text = ILLEGAL_FILENAME_CHARS.sub("_", str(value or "").strip())
    text = re.sub(r"_+", "_", text).strip("._ ")
    return text or "本地资料"


def modality_for_path(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
        return "image"
    if ext in {".mp4", ".mov", ".mkv", ".avi"}:
        return "video"
    if ext in {".mp3", ".wav", ".m4a", ".flac"}:
        return "audio"
    if ext in {".pdf", ".docx", ".txt", ".md", ".csv", ".xlsx", ".pptx"}:
        return "document"
    return "other"


def category_for_title(title: str, modality: str) -> str:
    lower = title.lower()
    if any(term in lower for term in ["person", "people", "white_shirt", "red_shirt", "portrait"]) or any(term in title for term in ["人物", "人像"]):
        return "人物照片"
    if any(term in lower for term in ["cat", "dog", "pet"]) or any(term in title for term in ["猫", "狗", "宠物"]):
        return "宠物动物"
    if any(term in lower for term in ["invoice", "receipt", "bill"]) or any(term in title for term in ["发票", "票据", "报销"]):
        return "票据发票"
    if any(term in lower for term in ["contract", "agreement"]) or "合同" in title:
        return "合同资料"
    if any(term in lower for term in ["laptop", "computer", "keyboard", "mouse", "desk"]) or any(term in title for term in ["电脑", "笔记本", "桌面"]):
        return "电子设备"
    if any(term in lower for term in ["course", "lesson", "assignment"]) or any(term in title for term in ["课程", "作业", "课件"]):
        return "课程资料"
    if modality == "video":
        return "电影视频"
    if modality == "audio":
        return "音乐音频"
    return "待整理"


def suggest_name(path: Path, source_rel: str, *, report_root: str | Path | None = None, personal_root: str | Path | None = None) -> dict[str, Any]:
    ai_metadata = _lookup_ai_metadata(path, source_rel, report_root=report_root, personal_root=personal_root)
    if ai_metadata:
        return _suggest_name_from_ai_metadata(path, source_rel, ai_metadata)
    return _suggest_name_from_filename(path, source_rel)


def _suggest_name_from_filename(path: Path, source_rel: str) -> dict[str, Any]:
    stat = path.stat()
    modality = modality_for_path(path)
    title = path.name
    asset_id = asset_id_for_rel(source_rel, size_bytes=int(stat.st_size), mtime=int(stat.st_mtime))
    generated = ChineseSmartNamer().generate(
        {
            "asset_id": asset_id,
            "title_redacted": title,
            "modality": modality,
            "category_names": [category_for_title(title, modality)],
            "object_labels": [],
            "person_attrs": ["person_present"] if "person" in title.lower() else [],
            "mtime": int(stat.st_mtime or time.time()),
        }
    )
    category = category_for_title(title, modality)
    suggested = safe_filename(generated.get("suggested_filename_zh") or generated.get("display_name_zh") or path.name)
    if path.suffix and not suggested.lower().endswith(path.suffix.lower()):
        suggested = safe_filename(suggested + path.suffix.lower())
    return {
        "asset_id": asset_id,
        "category_zh": category,
        "display_name_zh": generated.get("display_name_zh"),
        "suggested_filename_zh": suggested,
        "classification_basis": {
            "source": "fallback_filename_heuristic",
            "fallback_used": True,
            "modality": modality,
            "title_redacted": title[:160],
            "category_zh": category,
        },
        "naming_basis": generated.get("naming_reason") or {},
    }


def _suggest_name_from_ai_metadata(path: Path, source_rel: str, metadata: dict[str, Any]) -> dict[str, Any]:
    stat = path.stat()
    modality = str(metadata.get("modality") or modality_for_path(path))
    asset_id = str(metadata.get("asset_id") or asset_id_for_rel(source_rel, size_bytes=int(stat.st_size), mtime=int(stat.st_mtime)))
    title = str(metadata.get("title_redacted") or path.name)
    categories = [str(item) for item in metadata.get("category_names") or [] if item]
    labels = [str(item) for item in metadata.get("object_labels") or [] if item]
    attrs = [str(item) for item in metadata.get("person_attrs") or [] if item]
    smart_name = metadata.get("smart_name") if isinstance(metadata.get("smart_name"), dict) else {}
    generated = {
        "asset_id": asset_id,
        "display_name_zh": smart_name.get("display_name_zh"),
        "suggested_filename_zh": smart_name.get("suggested_filename_zh"),
        "naming_reason": smart_name.get("naming_reason") or {},
    }
    if not generated.get("display_name_zh") or not generated.get("suggested_filename_zh"):
        generated = ChineseSmartNamer().generate(
            {
                "asset_id": asset_id,
                "title_redacted": title,
                "modality": modality,
                "category_names": categories,
                "object_labels": labels,
                "person_attrs": attrs,
                "mtime": int(stat.st_mtime or time.time()),
            }
        )
    category = _choose_category(categories, generated, title, modality)
    suggested = safe_filename(str(generated.get("suggested_filename_zh") or generated.get("display_name_zh") or path.name))
    if path.suffix and not suggested.lower().endswith(path.suffix.lower()):
        suggested = safe_filename(suggested + path.suffix.lower())
    return {
        "asset_id": asset_id,
        "category_zh": category,
        "display_name_zh": generated.get("display_name_zh"),
        "suggested_filename_zh": suggested,
        "classification_basis": {
            "source": str(metadata.get("source") or "ai_index"),
            "fallback_used": False,
            "source_priority": [
                "asset_id",
                "ai_space_asset_view",
                "smart_asset_names",
                "smart_category_memberships",
                "yolo_labels",
                "person_attribute",
                "ocr_tags",
                "subtitle_tags",
                "fallback_filename_heuristic",
            ],
            "matched_asset_id": asset_id,
            "modality": modality,
            "title_redacted": title[:160],
            "category_zh": category,
            "category_names": categories[:20],
            "object_labels": labels[:20],
            "person_attrs": attrs[:20],
            "evidence_refs": [str(item) for item in metadata.get("evidence_refs") or []][:20],
        },
        "naming_basis": generated.get("naming_reason") or {},
    }


def _choose_category(categories: list[str], generated: dict[str, Any], title: str, modality: str) -> str:
    for value in categories:
        text = str(value or "").strip()
        if text and text != "\u5f85\u6574\u7406":
            return text
    reason = generated.get("naming_reason") if isinstance(generated.get("naming_reason"), dict) else {}
    main = str(reason.get("main_category") or "").strip()
    if main:
        return main
    return category_for_title(title, modality)


def _lookup_ai_metadata(
    path: Path,
    source_rel: str,
    *,
    report_root: str | Path | None,
    personal_root: str | Path | None,
) -> dict[str, Any] | None:
    if not report_root:
        return None
    root = Path(report_root)
    candidates = _candidate_asset_ids(path, source_rel, personal_root=personal_root)
    candidates.extend(_asset_ids_from_runtime_tables(root, path, source_rel, personal_root=personal_root))
    candidates = _dedupe([item for item in candidates if item])
    if not candidates:
        return None
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
        source = "ai_space_smart_index" if view or smart_name or categories else "yolo_person_attribute_index"
        return {
            "source": source,
            "asset_id": asset_id,
            "modality": view.get("modality") or modality_for_path(path),
            "title_redacted": view.get("title_redacted") or path.name,
            "category_names": categories,
            "object_labels": labels,
            "person_attrs": attrs,
            "evidence_refs": evidence_refs,
            "smart_name": smart_name or {},
        }
    return None


def _candidate_asset_ids(path: Path, source_rel: str, *, personal_root: str | Path | None) -> list[str]:
    stat = path.stat()
    rel = normalize_rel(source_rel)
    candidates = [
        "mm_" + short_hash(f"{rel}:{int(stat.st_size)}:{int(stat.st_mtime)}", 24),
        asset_id_for_rel(rel, size_bytes=int(stat.st_size), mtime=int(stat.st_mtime)),
    ]
    try:
        resolved = path.resolve(strict=False)
        if personal_root:
            rel_to_root = resolved.relative_to(Path(personal_root).resolve(strict=False)).as_posix()
            candidates.insert(0, "mm_" + short_hash(f"{rel_to_root}:{int(stat.st_size)}:{int(stat.st_mtime)}", 24))
        yolo_path_hash = hashlib.sha256(str(resolved).encode("utf-8", errors="replace")).hexdigest()
        candidates.append("yasset_" + hashlib.sha256(f"{yolo_path_hash}:{int(stat.st_size)}:{int(stat.st_mtime)}".encode("utf-8")).hexdigest()[:24])
    except Exception:
        pass
    return _dedupe(candidates)


def _asset_ids_from_runtime_tables(root: Path, path: Path, source_rel: str, *, personal_root: str | Path | None) -> list[str]:
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
    if personal_root:
        try:
            rel_to_root = path.resolve(strict=False).relative_to(Path(personal_root).resolve(strict=False)).as_posix()
            queries.append(
                (
                    root / "multimodal_search" / "runtime" / "multimodal_search.db",
                    "SELECT asset_id FROM mm_assets WHERE path_hash=?",
                    (short_hash(rel_to_root, 32),),
                )
            )
        except Exception:
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
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(sql_template.format(placeholders), asset_ids)]
    except sqlite3.Error:
        return []
    finally:
        try:
            conn.close()  # type: ignore[name-defined]
        except Exception:
            pass


def _query_scalar_list(db_path: Path, sql: str, params: tuple[Any, ...]) -> list[str]:
    if not db_path.exists():
        return []
    try:
        conn = sqlite3.connect(str(db_path))
        return [str(row[0]) for row in conn.execute(sql, params) if row[0]]
    except sqlite3.Error:
        return []
    finally:
        try:
            conn.close()  # type: ignore[name-defined]
        except Exception:
            pass


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
