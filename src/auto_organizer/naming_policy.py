from __future__ import annotations

import hashlib
import mimetypes
import re
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


def suggest_name(path: Path, source_rel: str) -> dict[str, Any]:
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
            "source": "local_filename_and_existing_naming_policy",
            "modality": modality,
            "title_redacted": title[:160],
            "category_zh": category,
        },
        "naming_basis": generated.get("naming_reason") or {},
    }
