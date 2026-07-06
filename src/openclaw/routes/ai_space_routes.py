from __future__ import annotations

from pathlib import Path
from typing import Any

from src.ai_space.service import AiSpaceService


def _service(report_root: str | Path | None) -> AiSpaceService:
    root = Path(report_root or "reports")
    return AiSpaceService(
        db_path=root / "ai_space" / "runtime" / "ai_space.db",
        multimodal_db_path=root / "multimodal_search" / "runtime" / "multimodal_search.db",
        yolo_db_path=root / "yolo_index" / "runtime" / "yolo_index.db",
        person_db_path=root / "person_attribute" / "runtime" / "person_attribute.db",
        smart_db_path=root / "smart_classification" / "runtime" / "smart_classification.db",
        subtitle_db_path=root / "subtitle_extraction" / "runtime" / "subtitle_extraction.db",
    )


def ai_space_route_response(
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
    if normalized == "/api/ai-space/status":
        return 200, service.status()
    if normalized == "/api/ai-space/assets":
        return 200, service.assets(payload)
    if normalized == "/api/ai-space/facets":
        return 200, service.facets()
    if normalized.startswith("/api/ai-space/asset/"):
        result = service.item(normalized.rsplit("/", 1)[-1])
        return (200 if result.get("ok") else 404), result
    if method.upper() != "POST":
        return 405, {"ok": False, "error": "method_not_allowed", "path": path}
    if normalized == "/api/ai-space/rebuild":
        result = service.rebuild(payload)
        return (200 if result.get("ok") else 400), result
    if normalized == "/api/ai-space/search":
        result = service.search(payload)
        return (200 if result.get("ok") else 400), result
    return 404, {"ok": False, "error": "unknown_ai_space_route", "path": path}
