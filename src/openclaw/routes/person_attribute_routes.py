from __future__ import annotations

from pathlib import Path
from typing import Any

from src.person_attribute.service import PersonAttributeService


def _roots(personal_root: str | Path | None) -> list[Path]:
    if not personal_root:
        return []
    root = Path(personal_root)
    roots = [root]
    fixture = root.parent / "yolo_v2_fixture"
    if fixture.exists():
        roots.append(fixture)
    demo = root.parent / "demo_data"
    if demo.exists():
        roots.append(demo)
    return roots


def _service(report_root: str | Path | None, personal_root: str | Path | None) -> PersonAttributeService:
    root = Path(report_root or "reports")
    return PersonAttributeService(
        db_path=root / "person_attribute" / "runtime" / "person_attribute.db",
        yolo_db_path=root / "yolo_index" / "runtime" / "yolo_index.db",
        roots=_roots(personal_root),
    )


def person_attribute_route_response(
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
    if normalized == "/api/person-attribute/status":
        return 200, service.status()
    if method.upper() != "POST":
        return 405, {"ok": False, "error": "method_not_allowed", "path": path}
    if normalized == "/api/person-attribute/rebuild":
        result = service.rebuild(payload)
        return (200 if result.get("ok") else 400), result
    if normalized == "/api/person-attribute/search":
        result = service.search(payload)
        return (200 if result.get("ok") else 400), result
    return 404, {"ok": False, "error": "unknown_person_attribute_route", "path": path}
