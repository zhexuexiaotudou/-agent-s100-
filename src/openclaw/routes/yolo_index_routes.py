from __future__ import annotations

from pathlib import Path
from typing import Any

from src.yolo_index.service import YoloIndexService


def _service(report_root: str | Path | None, personal_root: str | Path | None) -> YoloIndexService:
    root = Path(report_root or "reports")
    runtime = root / "yolo_index" / "runtime"
    roots = [Path(personal_root)] if personal_root else [root]
    return YoloIndexService(
        db_path=runtime / "yolo_index.db",
        report_root=root,
        roots=roots,
        max_files=100,
    )


def yolo_route_response(
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    report_root: str | Path | None = None,
    personal_root: str | Path | None = None,
) -> tuple[int, dict[str, Any]]:
    normalized = path.rstrip("/") or "/"
    payload = payload or {}
    service = _service(report_root, personal_root)
    if normalized == "/api/yolo-index/status":
        return 200, service.status()
    if normalized == "/api/yolo-index/eval/summary":
        return 200, service.eval_summary()
    if normalized.startswith("/api/yolo-index/item/"):
        result = service.item(normalized.rsplit("/", 1)[-1])
        return (200 if result.get("ok") else 404), result
    if method.upper() != "POST":
        return 405, {"ok": False, "error": "method_not_allowed", "path": path}
    if normalized == "/api/yolo-index/rebuild":
        result = service.rebuild(payload)
        return (200 if result.get("ok") else 400), result
    if normalized == "/api/yolo-index/search":
        result = service.search(payload)
        return (200 if result.get("ok") else 400), result
    if normalized == "/api/yolo-index/eval/run":
        cases_path = payload.get("cases_path") or "benchmarks/yolo_object_search_eval_cases.jsonl"
        result = service.eval_run(cases_path)
        return (200 if result.get("ok") else 400), result
    return 404, {"ok": False, "error": "unknown_yolo_index_route", "path": path}
