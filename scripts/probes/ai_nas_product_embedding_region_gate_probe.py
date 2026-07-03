#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ai_nas_common import build_sqlite_inventory, ensure_report_dir, iso_now, open_index_db, safe_write_json, safe_write_text
from ai_nas_embedding_adapter import run_product_image_embedding_for_record, upsert_product_image_embedding
from ai_nas_region_adapter import run_product_region_analysis_for_record, upsert_product_region_evidence
from ai_nas_vision_index import ensure_photo_visual_states, photo_visual_state_summary
from ai_nas_vision_runtime import vision_product_runtime_status
from ai_nas_vision_search import search_product_visual_index


TOOL_ID = "ai_nas_product_embedding_region_gate"
OK = "ok_ai_nas_product_embedding_region_gate"
FAILED = "failed_ai_nas_product_embedding_region_gate"


def write_fixture_image(path: Path, rgb: tuple[int, int, int], text: str) -> None:
    from PIL import Image, ImageDraw

    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (640, 420), rgb)
    draw = ImageDraw.Draw(image)
    draw.rectangle((32, 32, 608, 388), outline=(30, 60, 70), width=4)
    draw.text((62, 190), text, fill=(12, 18, 20))
    image.save(path, quality=92)


def prepare_fixture(run_dir: Path) -> Path:
    personal = run_dir / "Personal"
    if personal.exists():
        shutil.rmtree(personal)
    photos = personal / "Photos"
    write_fixture_image(photos / "person_white_top.jpg", (215, 224, 230), "person white top")
    write_fixture_image(photos / "person_blue_top.jpg", (118, 160, 225), "person blue top")
    write_fixture_image(photos / "white_car.jpg", (242, 242, 236), "white car")
    write_fixture_image(photos / "white_wall_room.jpg", (245, 245, 241), "white wall")
    write_fixture_image(photos / "white_document_screenshot.jpg", (250, 250, 250), "white document")
    return personal


def vector_for_payload(payload: dict) -> list[float]:
    input_type = str(payload.get("input_type") or "")
    if input_type == "text":
        text = str(payload.get("text") or "").lower()
        if "car" in text or "\u8f66" in text:
            return [0.0, 0.0, 1.0, 0.0]
        if "beach" in text or "\u6d77" in text:
            return [0.0, 1.0, 0.0, 0.0]
        return [1.0, 0.0, 0.0, 0.0]
    rel = str(payload.get("relative_path") or "")
    if "white_car" in rel:
        return [0.0, 0.0, 1.0, 0.0]
    if "blue" in rel:
        return [0.35, 0.0, 0.0, 0.65]
    if "white_top" in rel:
        return [1.0, 0.0, 0.0, 0.0]
    return [0.1, 0.0, 0.1, 0.0]


def regions_for_payload(payload: dict) -> list[dict]:
    rel = str(payload.get("relative_path") or "")
    if "person_white_top" in rel:
        return [
            {"label": "person", "region_kind": "person", "bbox": [120, 60, 420, 390], "confidence": 0.95},
            {
                "label": "shirt",
                "region_kind": "upper_clothing",
                "bbox": [160, 150, 380, 280],
                "confidence": 0.91,
                "attributes": {"upper_clothing.color": "white", "upper_clothing.garment": "shirt"},
            },
        ]
    if "person_blue_top" in rel:
        return [
            {"label": "person", "region_kind": "person", "bbox": [120, 60, 420, 390], "confidence": 0.94},
            {
                "label": "shirt",
                "region_kind": "upper_clothing",
                "bbox": [160, 150, 380, 280],
                "confidence": 0.90,
                "attributes": {"upper_clothing.color": "blue", "upper_clothing.garment": "shirt"},
            },
        ]
    if "white_car" in rel:
        return [
            {
                "label": "car",
                "region_kind": "object",
                "bbox": [80, 140, 560, 320],
                "confidence": 0.93,
                "attributes": {"object.color": "white"},
            }
        ]
    return []


class FixtureVisionHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or "0")
        payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        if self.path == "/embed":
            response = {
                "model_id": "fixture-siglip-product",
                "embedding": vector_for_payload(payload),
                "metadata": {"fixture": True},
            }
        elif self.path == "/region":
            response = {
                "model_id": "fixture-yolo-human-parsing-product",
                "regions": regions_for_payload(payload),
                "metadata": {"fixture": True},
            }
        else:
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return


def start_fixture_server() -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureVisionHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, f"http://{host}:{port}"


def indexed_records(db_path: Path) -> list[dict]:
    from ai_nas_common import _record_from_sqlite_row

    con = open_index_db(db_path)
    try:
        return [_record_from_sqlite_row(row) for row in con.execute("SELECT * FROM records ORDER BY relative_path").fetchall()]
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate product image/text embedding and region attribute search.")
    parser.add_argument("--report-root", type=Path, default=Path("tmp/ai_nas_product_embedding_region_gate_local"))
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "product_embedding_region_gate")
    personal_root = prepare_fixture(run_dir)
    db_path = run_dir / "personal_inventory.sqlite3"
    server, base_url = start_fixture_server()

    env_names = [
        "AI_NAS_IMAGE_TEXT_EMBEDDING_ENDPOINT",
        "AI_NAS_IMAGE_TEXT_EMBEDDING_MODEL",
        "AI_NAS_VISION_DETECTOR_ENDPOINT",
        "AI_NAS_VISION_DETECTOR_MODEL",
        "AI_NAS_REGION_ATTRIBUTE_ENDPOINT",
        "AI_NAS_REGION_ATTRIBUTE_MODEL",
    ]
    old_env = {name: os.environ.get(name) for name in env_names}
    try:
        os.environ["AI_NAS_IMAGE_TEXT_EMBEDDING_ENDPOINT"] = base_url + "/embed"
        os.environ["AI_NAS_IMAGE_TEXT_EMBEDDING_MODEL"] = "fixture-siglip-product"
        os.environ["AI_NAS_VISION_DETECTOR_ENDPOINT"] = base_url + "/region"
        os.environ["AI_NAS_VISION_DETECTOR_MODEL"] = "fixture-yolo-human-parsing-product"
        os.environ["AI_NAS_REGION_ATTRIBUTE_ENDPOINT"] = base_url + "/region"
        os.environ["AI_NAS_REGION_ATTRIBUTE_MODEL"] = "fixture-yolo-human-parsing-product"

        index_status = build_sqlite_inventory(personal_root, db_path)
        records = indexed_records(db_path)
        runtime_before = vision_product_runtime_status()
        first_state = ensure_photo_visual_states(db_path, records, runtime=runtime_before)
        embedding_updates = []
        region_updates = []
        for record in records:
            emb = run_product_image_embedding_for_record(record)
            embedding_updates.append({"result": emb, "evidence": upsert_product_image_embedding(db_path, emb)})
            reg = run_product_region_analysis_for_record(record)
            region_updates.append({"result": reg, "evidence": upsert_product_region_evidence(db_path, reg)})
        final_state = ensure_photo_visual_states(db_path, records, runtime=vision_product_runtime_status())
        state_summary = photo_visual_state_summary(db_path)
        strict_search = search_product_visual_index(db_path, "\u627e\u7a7f\u767d\u8272\u4e0a\u8863\u7684\u7167\u7247", limit=5)
        car_search = search_product_visual_index(db_path, "white car", limit=5)
    finally:
        for name, value in old_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        server.shutdown()
        server.server_close()

    strict_results = strict_search.get("matches") or []
    strict_paths = [item.get("relative_path") for item in strict_results]
    car_paths = [item.get("relative_path") for item in (car_search.get("matches") or [])]
    failures: list[str] = []
    if not runtime_before.get("components", {}).get("image_text_embedding", {}).get("ready"):
        failures.append("product_embedding_runtime_not_ready")
    if not runtime_before.get("components", {}).get("detector", {}).get("ready"):
        failures.append("detector_runtime_not_ready")
    if not runtime_before.get("components", {}).get("region_attributes", {}).get("ready"):
        failures.append("region_runtime_not_ready")
    if sum(1 for item in embedding_updates if item["result"].get("status") == "product_image_text_embedding_completed") != 5:
        failures.append("not_all_product_embeddings_completed")
    if sum(1 for item in region_updates if item["result"].get("status") == "product_region_analysis_completed") < 3:
        failures.append("product_region_analysis_incomplete")
    if strict_search.get("query_plan", {}).get("search_kind") != "region_attribute_visual":
        failures.append(f"bad_strict_query_plan:{strict_search.get('query_plan')}")
    if strict_search.get("degraded"):
        failures.append(f"strict_region_search_degraded:{strict_search.get('degradation')}")
    if strict_paths[:1] != ["Photos/person_white_top.jpg"]:
        failures.append(f"strict_top_result_not_person_white_top:{strict_paths}")
    false_positive_needles = ("white_car", "white_wall", "white_document", "person_blue_top")
    if any(any(needle in str(path) for needle in false_positive_needles) for path in strict_paths):
        failures.append(f"strict_false_positive:{strict_paths}")
    top = strict_results[0] if strict_results else {}
    if not any((item.get("type") or item.get("kind")) == "region_attribute" for item in top.get("evidence_items") or []):
        failures.append("strict_result_missing_region_attribute_evidence")
    if top.get("confidence_kind") != "product_score":
        failures.append(f"strict_result_not_product_score:{top.get('confidence_kind')}")
    if car_paths[:1] != ["Photos/white_car.jpg"]:
        failures.append(f"embedding_top_result_not_white_car:{car_paths}")
    car_top = (car_search.get("matches") or [{}])[0]
    if not any((item.get("type") or item.get("kind")) == "image_text_embedding" for item in car_top.get("evidence_items") or []):
        failures.append("car_result_missing_embedding_evidence")
    product_statuses = state_summary.get("status_counts") or {}
    if not any("product" in str(status) for status in product_statuses):
        failures.append(f"visual_state_not_product_indexed:{product_statuses}")

    verdict = OK if not failures else FAILED
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "personal_root": str(personal_root),
        "sqlite_index_path": str(db_path),
        "fixture_base_url": base_url,
        "index_status": index_status,
        "runtime_before": runtime_before,
        "first_state": first_state,
        "embedding_updates": embedding_updates,
        "region_updates": region_updates,
        "final_state": final_state,
        "state_summary": state_summary,
        "strict_search": strict_search,
        "car_search": car_search,
        "strict_paths": strict_paths,
        "car_paths": car_paths,
        "failures": failures,
        "acceptance": {
            "image_text_embedding_written_to_product_table": True,
            "upper_clothing_color_bound_to_region": True,
            "white_car_white_wall_document_are_not_white_top": True,
            "product_evidence_is_returned": True,
        },
    }
    json_path = run_dir / "product_embedding_region_gate.json"
    md_path = run_dir / "product_embedding_region_gate.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Product Embedding + Region Gate",
        "",
        f"- verdict: `{verdict}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- strict_paths: `{strict_paths}`",
        f"- car_paths: `{car_paths}`",
        f"- state_counts: `{product_statuses}`",
        f"- failures: `{failures}`",
    ]
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(f"verdict: {verdict}")
    print(f"report: {json_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
