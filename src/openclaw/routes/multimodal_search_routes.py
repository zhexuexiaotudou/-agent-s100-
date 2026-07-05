from __future__ import annotations

from pathlib import Path
from typing import Any

from src.multimodal_search.search_api import MultimodalSearchService


def _service(report_root: str | Path | None, personal_root: str | Path | None) -> MultimodalSearchService:
    root = Path(report_root or "reports")
    runtime = root / "multimodal_search" / "runtime"
    roots = [Path(personal_root)] if personal_root else [root]
    return MultimodalSearchService(
        db_path=runtime / "multimodal_search.db",
        vector_dir=runtime / "vectors",
        trace_path=root / "multimodal_search" / "multimodal_search_trace.jsonl",
        roots=roots,
        feature_flags_path=Path("configs/multimodal_search_feature_flags.json"),
        max_files=5000,
        yolo_db_path=root / "yolo_index" / "runtime" / "yolo_index.db",
        yolo_report_root=root,
    )


def multimodal_route_response(
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
    if normalized == "/api/multimodal-search/status":
        return 200, service.status()
    if normalized == "/api/multimodal-index/stats":
        return 200, service.status()
    if normalized == "/api/multimodal-search/eval/summary":
        return 200, {"ok": True, "status": service.status()}
    if normalized.startswith("/api/multimodal-index/item/"):
        result = service.item(normalized.rsplit("/", 1)[-1])
        return (200 if result.get("ok") else 404), result
    if method.upper() != "POST":
        return 405, {"ok": False, "error": "method_not_allowed", "path": path}
    if normalized == "/api/multimodal-index/rebuild":
        result = service.rebuild(payload)
        return (200 if result.get("ok") else 400), result
    if normalized == "/api/multimodal-search/query":
        result = service.query(payload)
        return (200 if result.get("ok") else 400), result
    if normalized == "/api/multimodal-search/eval/run":
        cases_path = payload.get("cases_path") or "benchmarks/multimodal_search_eval_cases.jsonl"
        result = service.eval_run(cases_path)
        return (200 if result.get("ok") else 400), result
    return 404, {"ok": False, "error": "unknown_multimodal_route", "path": path}
