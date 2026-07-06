from __future__ import annotations

from pathlib import Path
from typing import Any

from src.ai_space.service import AiSpaceService
from src.smart_classification.service import SmartClassificationService


def _service(report_root: str | Path | None) -> SmartClassificationService:
    root = Path(report_root or "reports")
    ai_space = AiSpaceService(
        db_path=root / "ai_space" / "runtime" / "ai_space.db",
        multimodal_db_path=root / "multimodal_search" / "runtime" / "multimodal_search.db",
        yolo_db_path=root / "yolo_index" / "runtime" / "yolo_index.db",
        person_db_path=root / "person_attribute" / "runtime" / "person_attribute.db",
        smart_db_path=root / "smart_classification" / "runtime" / "smart_classification.db",
        subtitle_db_path=root / "subtitle_extraction" / "runtime" / "subtitle_extraction.db",
    )
    return SmartClassificationService(db_path=root / "smart_classification" / "runtime" / "smart_classification.db", ai_space_service=ai_space)


def smart_classification_route_response(
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
    if normalized == "/api/smart-classification/status":
        return 200, service.status()
    if normalized == "/api/smart-classification/categories":
        if method.upper() == "GET":
            return 200, service.categories()
        if method.upper() == "POST":
            result = service.create_category(payload)
            return (200 if result.get("ok") else 400), result
    if normalized.startswith("/api/smart-classification/category/") and normalized.endswith("/items"):
        category_id = normalized.split("/")[-2]
        return 200, service.category_items(category_id)
    if method.upper() != "POST":
        return 405, {"ok": False, "error": "method_not_allowed", "path": path}
    if normalized == "/api/smart-classification/rebuild":
        result = service.rebuild(payload)
        return (200 if result.get("ok") else 400), result
    if normalized.startswith("/api/smart-classification/category/") and normalized.endswith("/materialize-copy-plan"):
        category_id = normalized.split("/")[-2]
        return 200, service.materialize_copy_plan(category_id)
    return 404, {"ok": False, "error": "unknown_smart_classification_route", "path": path}
