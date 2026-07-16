from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any, Callable

from src.openclaw.routes.ai_space_routes import ai_space_route_response
from src.openclaw.routes.journal_routes import journal_route_response
from src.openclaw.routes.multimodal_search_routes import multimodal_route_response
from src.openclaw.routes.person_attribute_routes import person_attribute_route_response
from src.openclaw.routes.smart_classification_routes import smart_classification_route_response
from src.openclaw.routes.smart_naming_routes import smart_naming_route_response
from src.openclaw.routes.subtitle_extraction_routes import subtitle_extraction_route_response
from src.openclaw.routes.yolo_index_routes import yolo_route_response
from src.product_jobs.queue import ProductJobQueue


class ProductJobDispatcher:
    def __init__(self, *, report_root: Path, personal_root: Path | None) -> None:
        self.report_root = report_root
        self.personal_root = personal_root

    def dispatch(self, job: dict[str, Any]) -> dict[str, Any]:
        job_type = str(job.get("job_type") or "")
        payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
        routes: dict[str, tuple[Callable[..., tuple[int, dict]], str]] = {
            "multimodal_rebuild": (multimodal_route_response, "/api/multimodal-index/rebuild"),
            "clip_embedding": (multimodal_route_response, "/api/multimodal-index/rebuild"),
            "yolo_index": (yolo_route_response, "/api/yolo-index/rebuild"),
            "person_attribute_rebuild": (person_attribute_route_response, "/api/person-attribute/rebuild"),
            "ai_space_rebuild": (ai_space_route_response, "/api/ai-space/rebuild"),
            "smart_classification_rebuild": (smart_classification_route_response, "/api/smart-classification/rebuild"),
            "smart_naming_generate": (smart_naming_route_response, "/api/smart-naming/generate"),
            "smart_naming_batch": (smart_naming_route_response, "/api/smart-naming/batch-generate"),
            "subtitle_extract": (subtitle_extraction_route_response, "/api/subtitle/extract"),
            "journal_summary": (journal_route_response, "/api/journal/generate-summary"),
        }
        if job_type in {"media_upload", "media_index"}:
            return self._media_index(payload)
        if job_type == "ocr_rebuild":
            return {"ok": False, "error": "ocr_rebuild_requires_acl_aware_portal_sync"}
        route = routes.get(job_type)
        if route is None:
            return {"ok": False, "error": "unsupported_job_type", "job_type": job_type}
        handler, path = route
        kwargs = {
            "method": "POST",
            "payload": payload,
            "report_root": self.report_root,
        }
        if handler is not journal_route_response:
            kwargs["personal_root"] = self.personal_root
        status, result = handler(path, **kwargs)
        return {**result, "http_status": status}

    def _media_index(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.personal_root or not self.personal_root.exists():
            return {"ok": False, "error": "personal_root_not_configured"}
        from scripts.probes.ai_nas_media import MediaCenter

        center = MediaCenter(self.report_root / "media.sqlite3")
        result = center.index_photos(self.personal_root, asset_root=self.personal_root, source_id="product_job_worker")
        return {**result, "schema": "digua_media_job_v1", "raw_path_returned": False}


def run_once(queue: ProductJobQueue, dispatcher: ProductJobDispatcher, *, stale_after_seconds: int = 900) -> dict[str, Any]:
    claim = queue.claim_next(stale_after_seconds=stale_after_seconds)
    job = claim.get("job") if claim.get("ok") else None
    if not job:
        return {"ok": bool(claim.get("ok")), "processed": False, "error": claim.get("error")}
    job_id = str(job["job_id"])
    try:
        result = dispatcher.dispatch(job)
    except Exception as exc:
        queue.fail(job_id, f"worker_exception:{type(exc).__name__}:{exc}")
        return {"ok": False, "processed": True, "job_id": job_id, "error": f"worker_exception:{type(exc).__name__}"}
    if result.get("ok") is False or int(result.get("http_status") or 200) >= 400:
        error = str(result.get("error") or f"job_failed_http_{result.get('http_status')}")
        queue.fail(job_id, error)
        return {"ok": False, "processed": True, "job_id": job_id, "error": error}
    evidence_ref = str(result.get("verdict") or result.get("schema") or job["job_type"])
    queue.complete(job_id, evidence_ref=evidence_ref)
    return {"ok": True, "processed": True, "job_id": job_id, "evidence_ref": evidence_ref}


def main() -> int:
    parser = argparse.ArgumentParser(description="Digua AI product job worker.")
    parser.add_argument("--db-path", type=Path, default=Path("reports/product_jobs/runtime/product_jobs.db"))
    parser.add_argument("--report-root", type=Path, default=Path("reports"))
    parser.add_argument("--personal-root", type=Path, default=None)
    parser.add_argument("--poll-interval", type=float, default=5.0)
    parser.add_argument("--stale-after-seconds", type=int, default=900)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    queue = ProductJobQueue(args.db_path)
    dispatcher = ProductJobDispatcher(report_root=args.report_root, personal_root=args.personal_root)
    if args.once:
        print(run_once(queue, dispatcher, stale_after_seconds=args.stale_after_seconds), flush=True)
        return 0
    while True:
        result = run_once(queue, dispatcher, stale_after_seconds=args.stale_after_seconds)
        if result.get("processed"):
            print(result, flush=True)
            continue
        time.sleep(max(0.25, args.poll_interval))


if __name__ == "__main__":
    raise SystemExit(main())
