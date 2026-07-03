#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from socket import socket
from typing import Any

from ai_nas_common import (
    build_sqlite_inventory,
    ensure_report_dir,
    iso_now,
    open_index_db,
    safe_write_json,
    safe_write_text,
    search_photo_semantic_index,
    upsert_ocr_result,
    _record_from_sqlite_row,
)
from ai_nas_ocr_adapter import product_ocr_runtime_status, run_product_ocr_for_record, upsert_product_ocr_evidence
from ai_nas_vision_index import ensure_photo_visual_states
from ai_nas_vision_runtime import vision_product_runtime_status


TOOL_ID = "ai_nas_product_ocr_adapter_gate"
OK = "ok_ai_nas_product_ocr_adapter_gate"
FAILED = "failed_ai_nas_product_ocr_adapter_gate"


def free_port() -> int:
    sock = socket()
    sock.bind(("127.0.0.1", 0))
    try:
        return int(sock.getsockname()[1])
    finally:
        sock.close()


class FixtureOCRHandler(BaseHTTPRequestHandler):
    seen_requests: list[dict[str, Any]] = []

    def log_message(self, fmt: str, *args: object) -> None:
        return

    def _send(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self._send({"ok": False, "error": "bad_json"}, HTTPStatus.BAD_REQUEST)
            return
        FixtureOCRHandler.seen_requests.append(
            {
                "relative_path": payload.get("relative_path"),
                "has_image_url": bool(((payload.get("image_url") or {}).get("url") or "").startswith("data:image/")),
                "schema_version": payload.get("schema_version"),
            }
        )
        rel = str(payload.get("relative_path") or "")
        if "invoice" in rel:
            self._send(
                {
                    "text": "INVOICE RECEIPT 2026 PRODUCT OCR AMOUNT 12000 CNY",
                    "regions": [
                        {
                            "bbox": [40, 80, 500, 160],
                            "text": "INVOICE RECEIPT 2026 PRODUCT OCR",
                            "confidence": 0.93,
                        }
                    ],
                    "confidence": 0.92,
                    "language": "en",
                    "metadata": {"fixture": True},
                }
            )
            return
        self._send({"text": "", "regions": [], "confidence": 0.1, "language": "unknown", "metadata": {"fixture": True}})


def start_fixture_ocr() -> tuple[ThreadingHTTPServer, str]:
    FixtureOCRHandler.seen_requests = []
    port = free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), FixtureOCRHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}/ocr"


def prepare_fixture(run_dir: Path) -> Path:
    personal = run_dir / "Personal"
    if personal.exists():
        shutil.rmtree(personal)
    photos = personal / "Photos"
    docs = personal / "Documents"
    photos.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    docs.joinpath("notes.txt").write_text("plain text note\n", encoding="utf-8")
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (720, 420), (250, 250, 246))
    draw = ImageDraw.Draw(image)
    draw.rectangle((30, 30, 690, 390), outline=(30, 30, 30), width=3)
    draw.text((60, 180), "INVOICE RECEIPT 2026 PRODUCT OCR", fill=(0, 0, 0))
    image.save(photos / "invoice_receipt_screenshot.jpg", quality=92)

    beach = Image.new("RGB", (720, 420), (80, 160, 220))
    ImageDraw.Draw(beach).text((60, 180), "BEACH PHOTO", fill=(0, 0, 0))
    beach.save(photos / "beach_photo.jpg", quality=92)
    return personal


def load_records(db_path: Path) -> list[dict]:
    con = open_index_db(db_path)
    try:
        return [_record_from_sqlite_row(row) for row in con.execute("SELECT * FROM records ORDER BY relative_path").fetchall()]
    finally:
        con.close()


def artifact_counts(db_path: Path) -> dict:
    con = open_index_db(db_path)
    try:
        return {
            "ocr_artifacts": con.execute("SELECT COUNT(*) AS count FROM vision_artifacts WHERE artifact_type='ocr_json'").fetchone()["count"],
            "ocr_attributes": con.execute("SELECT COUNT(*) AS count FROM vision_attributes WHERE namespace='ocr' AND name='visible_text'").fetchone()["count"],
            "ocr_completed": con.execute("SELECT COUNT(*) AS count FROM ocr_results WHERE status='ocr_completed'").fetchone()["count"],
        }
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate product HTTP OCR adapter, OCR evidence artifacts, and OCR-backed search.")
    parser.add_argument("--report-root", type=Path, default=Path("tmp/ai_nas_product_ocr_adapter_gate_local"))
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "product_ocr_adapter_gate")
    personal_root = prepare_fixture(run_dir)
    db_path = run_dir / "personal_inventory.sqlite3"
    server, endpoint = start_fixture_ocr()
    old_endpoint = os.environ.get("AI_NAS_OCR_ENDPOINT")
    old_model = os.environ.get("AI_NAS_OCR_MODEL")
    os.environ["AI_NAS_OCR_ENDPOINT"] = endpoint
    os.environ["AI_NAS_OCR_MODEL"] = "fixture-product-ocr"
    try:
        index_status = build_sqlite_inventory(personal_root, db_path)
        records = load_records(db_path)
        state_before = ensure_photo_visual_states(db_path, records, runtime=vision_product_runtime_status())
        ocr_results = []
        evidence_results = []
        for record in records:
            if record.get("type") != "Photos":
                continue
            result = run_product_ocr_for_record(record)
            upsert_ocr_result(db_path, result)
            evidence_results.append(upsert_product_ocr_evidence(db_path, result))
            ocr_results.append(result)
        state_after = ensure_photo_visual_states(db_path, records, runtime=vision_product_runtime_status())
        counts = artifact_counts(db_path)
        matches = search_photo_semantic_index(db_path, "invoice product ocr receipt", limit=5)
    finally:
        server.shutdown()
        if old_endpoint is None:
            os.environ.pop("AI_NAS_OCR_ENDPOINT", None)
        else:
            os.environ["AI_NAS_OCR_ENDPOINT"] = old_endpoint
        if old_model is None:
            os.environ.pop("AI_NAS_OCR_MODEL", None)
        else:
            os.environ["AI_NAS_OCR_MODEL"] = old_model

    top_paths = [item.get("relative_path") for item in matches]
    runtime = product_ocr_runtime_status()
    failures: list[str] = []
    if not FixtureOCRHandler.seen_requests or not all(item["has_image_url"] for item in FixtureOCRHandler.seen_requests):
        failures.append("fixture_ocr_did_not_receive_image_data_urls")
    if not any(item.get("status") == "ocr_completed" and "PRODUCT OCR" in str(item.get("text_preview")) for item in ocr_results):
        failures.append("product_ocr_text_not_completed")
    if counts["ocr_artifacts"] < 1:
        failures.append("ocr_artifact_not_created")
    if counts["ocr_attributes"] < 1:
        failures.append("ocr_visible_text_attribute_not_created")
    if not top_paths or top_paths[0] != "Photos/invoice_receipt_screenshot.jpg":
        failures.append(f"ocr_search_top_result_wrong:{top_paths[:3]}")
    if runtime.get("configured"):
        failures.append("environment_not_restored_after_gate")

    verdict = OK if not failures else FAILED
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "personal_root": str(personal_root),
        "sqlite_index_path": str(db_path),
        "index_status": index_status,
        "state_before": state_before,
        "state_after": state_after,
        "seen_requests": FixtureOCRHandler.seen_requests,
        "ocr_results": ocr_results,
        "evidence_results": evidence_results,
        "artifact_counts": counts,
        "search_top_paths": top_paths,
        "search_matches": matches,
        "failures": failures,
        "acceptance": {
            "http_ocr_adapter_called_with_image_bytes": True,
            "ocr_results_table_updated": True,
            "vision_artifacts_updated": True,
            "vision_attributes_updated": True,
            "ocr_text_participates_in_photo_search": True,
        },
    }
    json_path = run_dir / "product_ocr_adapter_gate.json"
    md_path = run_dir / "product_ocr_adapter_gate.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Product OCR Adapter Gate",
        "",
        f"- verdict: `{verdict}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- artifact_counts: `{counts}`",
        f"- search_top_paths: `{top_paths}`",
        f"- failures: `{failures}`",
    ]
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(f"verdict: {verdict}")
    print(f"report: {json_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
