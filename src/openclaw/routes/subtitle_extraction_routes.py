from __future__ import annotations

from pathlib import Path
from typing import Any

from src.subtitle_extraction.service import SubtitleExtractionService


def _service(report_root: str | Path | None) -> SubtitleExtractionService:
    root = Path(report_root or "reports")
    return SubtitleExtractionService(
        db_path=root / "subtitle_extraction" / "runtime" / "subtitle_extraction.db",
        artifact_dir=root / "subtitle_extraction" / "artifacts",
    )


def subtitle_extraction_route_response(
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
    if normalized == "/api/subtitle/status":
        return 200, service.status()
    if normalized.startswith("/api/subtitle/transcript/"):
        result = service.transcript(normalized.rsplit("/", 1)[-1])
        return (200 if result.get("ok") else 404), result
    if method.upper() != "POST":
        return 405, {"ok": False, "error": "method_not_allowed", "path": path}
    if normalized == "/api/subtitle/extract":
        result = service.extract(payload)
        return (200 if result.get("ok") else 400), result
    if normalized == "/api/subtitle/search":
        result = service.search(payload)
        return (200 if result.get("ok") else 400), result
    if normalized == "/api/subtitle/summarize":
        result = service.summarize(payload)
        return (200 if result.get("ok") else 400), result
    return 404, {"ok": False, "error": "unknown_subtitle_route", "path": path}
