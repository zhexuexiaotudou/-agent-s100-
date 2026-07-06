from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

from src.ai_space.service import AiSpaceService

from .category_templates import CATEGORY_PRIORITY
from .schema import connect, migrate


LABEL_ZH = {
    "person": "人物",
    "cat": "猫咪",
    "dog": "狗狗",
    "car": "汽车",
    "bus": "公交车",
    "truck": "卡车",
    "bicycle": "自行车",
    "motorcycle": "摩托车",
    "laptop": "笔记本电脑",
    "keyboard": "键盘",
    "mouse": "鼠标",
    "book": "书本",
    "cup": "杯子",
    "bottle": "瓶子",
    "tv": "电视",
    "cell phone": "手机",
}

COLOR_ZH = {
    "upper_white": "白色上衣",
    "upper_red": "红色衣服",
    "upper_black": "黑色衣服",
    "upper_blue": "蓝色衣服",
    "upper_green": "绿色衣服",
    "upper_yellow": "黄色衣服",
    "upper_gray": "灰色衣服",
    "upper_grey": "灰色衣服",
}

SAFE_CATEGORY_FALLBACK = {
    "image": "照片",
    "video": "视频",
    "audio": "音频",
    "document": "资料",
    "archive": "归档",
    "code": "代码",
    "other": "文件",
}

ILLEGAL_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]+')
SENSITIVE_NUMBER_RE = re.compile(r"(?<!\d)(?:1[3-9]\d{9}|\d{15,18}[\dXx]?|\d{5,})(?!\d)")


class ChineseSmartNamer:
    def generate(self, asset: dict[str, Any]) -> dict[str, Any]:
        asset_id = str(asset.get("asset_id") or "")
        title = str(asset.get("title_redacted") or asset.get("name_redacted") or asset_id or "asset")
        modality = str(asset.get("modality") or "other")
        categories = [str(item) for item in asset.get("category_names") or [] if item]
        labels = [str(item) for item in asset.get("object_labels") or [] if item]
        attrs = [str(item) for item in asset.get("person_attrs") or asset.get("attribute_tags") or [] if item]

        main = self._main_category(modality, categories, labels, attrs, title)
        feature = self._core_feature(categories, labels, attrs, title)
        scene = self._scene_or_attribute(modality, labels, attrs, title)
        date = self._date(asset)
        seq = self._sequence(asset_id or title)
        display_parts = [_clean_segment(main), _clean_segment(feature), _clean_segment(scene), date, seq]
        display = "_".join(part for part in display_parts if part)
        display = _collapse_underscores(display) or f"{SAFE_CATEGORY_FALLBACK.get(modality, '文件')}_{date}_{seq}"

        ext = _safe_extension(title)
        suggested = _safe_filename(display + ext)
        risk_flags = {
            "identity_inference_used": False,
            "face_recognition_used": False,
            "age_gender_race_emotion_health_inferred": False,
            "sensitive_number_removed": bool(SENSITIVE_NUMBER_RE.search(title)),
            "physical_file_renamed": False,
            "cloud_used": False,
        }
        return {
            "asset_id": asset_id,
            "display_name_zh": display[:96],
            "suggested_filename_zh": suggested[:120],
            "naming_reason": {
                "main_category": main,
                "core_feature": feature,
                "scene_or_attribute": scene,
                "date": date,
                "sequence": seq,
                "used_fields": ["modality", "category_names", "object_labels", "person_attrs", "title_redacted"],
            },
            "risk_flags": risk_flags,
            "raw_path_returned": False,
            "physical_file_renamed": False,
            "cloud_used": False,
        }

    def _main_category(self, modality: str, categories: list[str], labels: list[str], attrs: list[str], title: str) -> str:
        for wanted in CATEGORY_PRIORITY:
            if wanted in categories and wanted != "待整理":
                return wanted
        lower = title.lower()
        if "person_present" in attrs or "person" in lower or "人物" in title:
            return "人物照片"
        for label in labels:
            if label in LABEL_ZH:
                if label in {"cat", "dog"}:
                    return "宠物动物"
                if label in {"car", "bus", "truck", "bicycle", "motorcycle"}:
                    return "车辆交通"
                if label in {"laptop", "keyboard", "mouse", "tv", "cell phone"}:
                    return "电子设备"
                if label == "person":
                    return "人物照片"
        if any(term in lower for term in ["invoice", "receipt", "bill"]) or any(term in title for term in ["发票", "票据"]):
            return "票据发票"
        if any(term in lower for term in ["contract", "agreement"]) or "合同" in title:
            return "合同资料"
        return SAFE_CATEGORY_FALLBACK.get(modality, "文件")

    def _core_feature(self, categories: list[str], labels: list[str], attrs: list[str], title: str) -> str:
        for attr in attrs:
            if attr in COLOR_ZH:
                return COLOR_ZH[attr]
        for category in ("白色上衣", "红色衣服", "黑色衣服", "猫咪照片", "狗狗照片", "票据发票"):
            if category in categories:
                return category.replace("照片", "")
        lower = title.lower()
        title_terms = [
            ("white", "白色上衣"),
            ("red", "红色衣服"),
            ("black", "黑色衣服"),
            ("cat", "猫咪"),
            ("dog", "狗狗"),
            ("mountain", "山景"),
            ("grass", "草地"),
            ("invoice", "票据"),
            ("receipt", "票据"),
            ("laptop", "笔记本电脑"),
            ("car", "汽车"),
        ]
        for term, zh in title_terms:
            if term in lower:
                return zh
        for label in labels:
            if label in LABEL_ZH:
                return LABEL_ZH[label]
        return "本地资料"

    def _scene_or_attribute(self, modality: str, labels: list[str], attrs: list[str], title: str) -> str:
        lower = title.lower()
        if any(term in lower for term in ["indoor", "desk", "laptop"]) or any(label in labels for label in ["laptop", "keyboard", "mouse", "book"]):
            return "室内"
        if any(term in lower for term in ["grass", "mountain", "outdoor"]):
            return "户外"
        if any(term in lower for term in ["street", "car"]):
            return "街道"
        if any(term in lower for term in ["invoice", "receipt", "contract", "course"]) or modality == "document":
            return "资料"
        if "person_present" in attrs:
            return "照片"
        return SAFE_CATEGORY_FALLBACK.get(modality, "本地")

    def _date(self, asset: dict[str, Any]) -> str:
        for key in ("capture_time", "mtime"):
            value = asset.get(key)
            if not value:
                continue
            try:
                if isinstance(value, (int, float)):
                    return time.strftime("%Y%m%d", time.localtime(float(value)))
                text = str(value)
                digits = re.sub(r"\D", "", text)
                if len(digits) >= 8:
                    return digits[:8]
            except Exception:
                continue
        return time.strftime("%Y%m%d", time.localtime())

    @staticmethod
    def _sequence(seed: str) -> str:
        value = int(hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:6], 16) % 999 + 1
        return f"{value:03d}"


class SmartNamingService:
    def __init__(self, *, db_path: str | Path, ai_space_service: AiSpaceService) -> None:
        self.db_path = Path(db_path)
        self.ai_space = ai_space_service
        self.namer = ChineseSmartNamer()

    def status(self) -> dict[str, Any]:
        migrate(self.db_path)
        conn = connect(self.db_path)
        try:
            name_count = conn.execute("SELECT count(*) FROM smart_asset_names").fetchone()[0]
        finally:
            conn.close()
        return {
            "ok": True,
            "schema": "digua_smart_naming_v1",
            "name_count": name_count,
            "cloud_used": False,
            "raw_path_returned": False,
            "physical_file_renamed": False,
            "face_recognition_used": False,
            "sensitive_attribute_inference_enabled": False,
        }

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        asset = self._asset_from_payload(payload)
        if not asset.get("asset_id"):
            return {"ok": False, "error": "asset_id_required", "raw_path_returned": False}
        result = self.namer.generate(asset)
        self._save(result, asset)
        return {"ok": True, "schema": "digua_smart_naming_v1", "item": result, "raw_path_returned": False}

    def batch_generate(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        requested = [str(item) for item in payload.get("asset_ids") or [] if item]
        if requested:
            assets = []
            for asset_id in requested:
                item = self.ai_space.item(asset_id).get("asset")
                if item:
                    assets.append(item)
        else:
            assets = self.ai_space.assets({"limit": int(payload.get("limit") or 10000)}).get("assets") or []
        items = []
        for asset in assets:
            result = self.namer.generate(asset)
            self._save(result, asset)
            items.append(result)
        return {"ok": True, "schema": "digua_smart_naming_v1", "generated_count": len(items), "items": items[:100], "raw_path_returned": False}

    def item(self, asset_id: str) -> dict[str, Any]:
        migrate(self.db_path)
        conn = connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM smart_asset_names WHERE asset_id=?", (asset_id,)).fetchone()
        finally:
            conn.close()
        if row is None:
            return {"ok": False, "error": "not_found", "asset_id": asset_id, "raw_path_returned": False}
        item = dict(row)
        item["naming_reason"] = json.loads(item.pop("naming_reason_json") or "{}")
        item["risk_flags"] = json.loads(item.pop("risk_flags_json") or "{}")
        return {"ok": True, "schema": "digua_smart_naming_v1", "item": item, "raw_path_returned": False}

    def names_for_assets(self, asset_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not asset_ids:
            return {}
        migrate(self.db_path)
        placeholders = ",".join("?" for _ in asset_ids)
        conn = connect(self.db_path)
        try:
            rows = [dict(row) for row in conn.execute(f"SELECT * FROM smart_asset_names WHERE asset_id IN ({placeholders})", asset_ids)]
        except sqlite3.Error:
            return {}
        finally:
            conn.close()
        out: dict[str, dict[str, Any]] = {}
        for row in rows:
            row["naming_reason"] = json.loads(row.pop("naming_reason_json") or "{}")
            row["risk_flags"] = json.loads(row.pop("risk_flags_json") or "{}")
            out[row["asset_id"]] = row
        return out

    def _asset_from_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        asset = payload.get("asset") if isinstance(payload.get("asset"), dict) else None
        if asset:
            return dict(asset)
        asset_id = str(payload.get("asset_id") or "")
        if not asset_id:
            return {}
        item = self.ai_space.item(asset_id).get("asset")
        if item:
            return dict(item)
        return {
            "asset_id": asset_id,
            "title_redacted": payload.get("title_redacted") or payload.get("filename_redacted") or asset_id,
            "modality": payload.get("modality") or "image",
            "category_names": payload.get("category_names") or [],
            "object_labels": payload.get("object_labels") or [],
            "person_attrs": payload.get("person_attrs") or [],
            "mtime": payload.get("mtime"),
        }

    def _save(self, result: dict[str, Any], asset: dict[str, Any]) -> None:
        migrate(self.db_path)
        conn = connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO smart_asset_names(
                  asset_id,display_name_zh,suggested_filename_zh,naming_reason_json,
                  risk_flags_json,source_title_redacted,updated_at
                ) VALUES(?,?,?,?,?,?,?)
                """,
                (
                    result["asset_id"],
                    result["display_name_zh"],
                    result["suggested_filename_zh"],
                    json.dumps(result["naming_reason"], ensure_ascii=False, sort_keys=True),
                    json.dumps(result["risk_flags"], ensure_ascii=False, sort_keys=True),
                    str(asset.get("title_redacted") or "")[:160],
                    _now(),
                ),
            )
            conn.commit()
        finally:
            conn.close()


def _clean_segment(value: str) -> str:
    text = str(value or "").strip()
    text = SENSITIVE_NUMBER_RE.sub("", text)
    text = ILLEGAL_FILENAME_CHARS.sub("", text)
    text = re.sub(r"\s+", "", text)
    return text[:24]


def _collapse_underscores(value: str) -> str:
    return re.sub(r"_+", "_", value).strip("_")


def _safe_extension(title: str) -> str:
    ext = Path(str(title or "")).suffix.lower()
    if ext in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".mp4", ".mov", ".mkv", ".mp3", ".wav", ".pdf", ".txt"}:
        return ext
    return ""


def _safe_filename(value: str) -> str:
    text = ILLEGAL_FILENAME_CHARS.sub("_", value)
    text = _collapse_underscores(text)
    return text or "本地资料"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
