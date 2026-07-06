from __future__ import annotations

from pathlib import Path
from typing import Any

from src.ai_space.service import AiSpaceService
from src.smart_classification.chinese_namer import SmartNamingService


def _service(report_root: str | Path | None) -> SmartNamingService:
    root = Path(report_root or "reports")
    ai_space = AiSpaceService(
        db_path=root / "ai_space" / "runtime" / "ai_space.db",
        multimodal_db_path=root / "multimodal_search" / "runtime" / "multimodal_search.db",
        yolo_db_path=root / "yolo_index" / "runtime" / "yolo_index.db",
        person_db_path=root / "person_attribute" / "runtime" / "person_attribute.db",
        smart_db_path=root / "smart_classification" / "runtime" / "smart_classification.db",
        subtitle_db_path=root / "subtitle_extraction" / "runtime" / "subtitle_extraction.db",
    )
    return SmartNamingService(db_path=root / "smart_classification" / "runtime" / "smart_classification.db", ai_space_service=ai_space)


def smart_naming_route_response(
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    report_root: str | Path | None = None,
    personal_root: str | Path | None = None,
) -> tuple[int, dict[str, Any]]:
    normalized = path.rstrip("/") or "/"
    service = _service(report_root)
    payload = payload or {}
    if normalized == "/api/smart-naming/status":
        return 200, service.status()
    if normalized.startswith("/api/smart-naming/item/"):
        result = service.item(normalized.rsplit("/", 1)[-1])
        return (200 if result.get("ok") else 404), result
    if method.upper() != "POST":
        return 405, {"ok": False, "error": "method_not_allowed", "path": path}
    if normalized == "/api/smart-naming/generate":
        result = service.generate(payload)
        return (200 if result.get("ok") else 400), result
    if normalized == "/api/smart-naming/batch-generate":
        result = service.batch_generate(payload)
        return (200 if result.get("ok") else 400), result
    return 404, {"ok": False, "error": "unknown_smart_naming_route", "path": path}
