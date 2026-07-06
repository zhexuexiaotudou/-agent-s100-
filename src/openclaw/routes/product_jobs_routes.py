from __future__ import annotations

from pathlib import Path
from typing import Any

from src.product_jobs.queue import ProductJobQueue


def _queue(report_root: str | Path | None) -> ProductJobQueue:
    root = Path(report_root or "reports")
    return ProductJobQueue(root / "product_jobs" / "runtime" / "product_jobs.db")


def product_jobs_route_response(
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    report_root: str | Path | None = None,
    personal_root: str | Path | None = None,
) -> tuple[int, dict[str, Any]]:
    normalized = path.rstrip("/") or "/"
    queue = _queue(report_root)
    payload = payload or {}
    if normalized == "/api/jobs/status":
        return 200, queue.status()
    if normalized == "/api/jobs/recent":
        return 200, queue.recent()
    if normalized.startswith("/api/jobs/") and method.upper() == "GET":
        return 200, queue.get(normalized.rsplit("/", 1)[-1])
    if method.upper() != "POST":
        return 405, {"ok": False, "error": "method_not_allowed", "path": path}
    if normalized == "/api/jobs/enqueue":
        result = queue.enqueue(str(payload.get("job_type") or ""), payload.get("payload") or {})
        return (200 if result.get("ok") else 400), result
    if normalized == "/api/jobs/cancel":
        result = queue.cancel(str(payload.get("job_id") or ""))
        return (200 if result.get("ok") else 404), result
    return 404, {"ok": False, "error": "unknown_product_jobs_route", "path": path}
