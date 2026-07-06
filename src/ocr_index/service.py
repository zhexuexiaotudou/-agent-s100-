from __future__ import annotations

from pathlib import Path
from typing import Any

from src.document_rag.service import DocumentRagService


class OcrIndexService:
    def __init__(self, *, report_root: str | Path, personal_root: str | Path | None = None) -> None:
        self.document_rag = DocumentRagService(report_root=report_root, personal_root=personal_root)

    def status(self) -> dict[str, Any]:
        status = self.document_rag.status()
        return {
            "ok": True,
            "schema": "digua_ocr_status_v1",
            "route_module": "src.openclaw.routes.document_rag_routes",
            "ocr_index_backing": "document_fts",
            "document_count": status.get("document_count"),
            "chunk_count": status.get("chunk_count"),
            "cloud_ocr_enabled": False,
            "cloud_used": False,
            "raw_private_content_returned": False,
            "raw_path_returned": False,
            "degraded": status.get("degraded", False),
            "degraded_reason": status.get("degraded_reason"),
        }

    def query(self, query: str, *, relative_path: str = "Documents") -> dict[str, Any]:
        payload = self.document_rag.query(query, relative_path=relative_path)
        payload["schema"] = "digua_ocr_query_v1"
        payload["mode"] = "ocr"
        payload["ocr_index_backing"] = "document_fts"
        return payload
