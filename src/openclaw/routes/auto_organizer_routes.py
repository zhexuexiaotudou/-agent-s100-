from __future__ import annotations

from pathlib import Path
from typing import Any

from src.auto_organizer.service import AutoOrganizerService


def _service(report_root: str | Path | None, personal_root: str | Path | None) -> AutoOrganizerService:
    root = Path(report_root or "reports")
    personal = Path(personal_root or "Personal")
    return AutoOrganizerService(
        db_path=root / "auto_organizer" / "runtime" / "auto_organizer.db",
        personal_root=personal,
        report_root=root,
    )


def auto_organizer_route_response(
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    report_root: str | Path | None = None,
    personal_root: str | Path | None = None,
) -> tuple[int, dict[str, Any]]:
    normalized = path.rstrip("/") or "/"
    service = _service(report_root, personal_root)
    payload = payload or {}
    if method.upper() == "GET":
        if normalized == "/api/auto-organize/status":
            return 200, service.status()
        if normalized == "/api/auto-organize/recent":
            return 200, service.recent(limit=int(payload.get("limit") or 20))
        if normalized.startswith("/api/auto-organize/plan/"):
            result = service.plan(normalized.rsplit("/", 1)[-1])
            return (200 if result.get("ok") else 404), result
        return 404, {"ok": False, "error": "unknown_auto_organizer_route", "path": path, "raw_path_returned": False}
    if method.upper() != "POST":
        return 405, {"ok": False, "error": "method_not_allowed", "path": path, "raw_path_returned": False}
    if normalized == "/api/auto-organize/plan":
        result = service.create_plan(payload)
        return (200 if result.get("ok") else 400), result
    if normalized == "/api/auto-organize/dry-run":
        result = service.dry_run(payload)
        return (200 if result.get("ok") else 400), result
    if normalized == "/api/auto-organize/approve":
        result = service.approve(payload)
        return (200 if result.get("ok") else 400), result
    if normalized == "/api/auto-organize/execute":
        result = service.execute(payload)
        return (200 if result.get("ok") else 400), result
    if normalized == "/api/auto-organize/rollback":
        result = service.rollback(payload)
        return (200 if result.get("ok") else 400), result
    return 404, {"ok": False, "error": "unknown_auto_organizer_route", "path": path, "raw_path_returned": False}
