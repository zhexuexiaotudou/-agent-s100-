from __future__ import annotations

from pathlib import Path
from typing import Any

from src.document_rag.service import DocumentRagService
from src.ocr_index.service import OcrIndexService


def document_rag_route_response(
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    report_root: str | Path | None = None,
    personal_root: str | Path | None = None,
) -> tuple[int, dict[str, Any]]:
    normalized = path.rstrip("/") or "/"
    payload = payload or {}
    root = Path(report_root or "reports")
    document_rag = DocumentRagService(report_root=root, personal_root=personal_root)
    ocr = OcrIndexService(report_root=root, personal_root=personal_root)
    if method.upper() == "GET":
        if normalized == "/api/document-rag/status":
            return 200, document_rag.status()
        if normalized == "/api/ocr/status":
            return 200, ocr.status()
        return 404, {"ok": False, "error": "unknown_document_rag_route", "path": path, "raw_path_returned": False}
    if method.upper() != "POST":
        return 405, {"ok": False, "error": "method_not_allowed", "path": path, "raw_path_returned": False}
    query = str(payload.get("query") or payload.get("message") or "")
    relative_path = str(payload.get("path") or "Documents").replace("\\", "/").strip("/") or "Documents"
    if normalized == "/api/document-rag/query":
        result = document_rag.query(query, relative_path=relative_path)
        return (200 if result.get("ok") or result.get("no_grounded_answer") else 400), result
    if normalized == "/api/ocr/query":
        result = ocr.query(query, relative_path=relative_path)
        return (200 if result.get("ok") or result.get("no_grounded_answer") else 400), result
    if normalized == "/api/ocr/rebuild":
        status = ocr.status()
        status.update(
            {
                "schema": "digua_ocr_rebuild_v1",
                "ok": True,
                "rebuild_mode": "portal_state_local_fts_sync",
                "rebuild_delegated_to": "PortalState.sync_document_fts_index",
                "cloud_ocr_enabled": False,
                "raw_private_content_returned": False,
                "raw_path_returned": False,
            }
        )
        return 200, status
    return 404, {"ok": False, "error": "unknown_document_rag_route", "path": path, "raw_path_returned": False}
