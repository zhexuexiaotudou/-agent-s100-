#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from ai_nas_common import build_sqlite_inventory, ensure_image_embeddings_for_photos, ensure_report_dir, iso_now, safe_write_json, safe_write_text
from ai_nas_vision_index import ensure_photo_visual_states, photo_visual_state_summary
from ai_nas_vision_runtime import vision_product_runtime_status
from ai_nas_vision_schema import vision_product_schema_status


TOOL_ID = "ai_nas_visual_index_generation_gate"
OK = "ok_ai_nas_visual_index_generation_gate"
FAILED = "failed_ai_nas_visual_index_generation_gate"


def prepare_fixture(run_dir: Path) -> Path:
    personal = run_dir / "Personal"
    if personal.exists():
        shutil.rmtree(personal)
    photos = personal / "Photos"
    docs = personal / "Documents"
    photos.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    docs.joinpath("invoice_2026.txt").write_text("Invoice amount 12000 CNY\n", encoding="utf-8")
    from PIL import Image, ImageDraw

    fixtures = [
        ("family_white_top.jpg", (235, 236, 232), "person white top"),
        ("white_car_invoice.jpg", (245, 245, 240), "white car invoice"),
        ("beach_blue_top.jpg", (90, 160, 220), "beach blue top"),
    ]
    for name, rgb, text in fixtures:
        image = Image.new("RGB", (480, 300), rgb)
        draw = ImageDraw.Draw(image)
        draw.text((36, 140), text, fill=(20, 20, 20))
        image.save(photos / name, quality=90)
    return personal


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate visual active generation and ACL-aware product state.")
    parser.add_argument("--report-root", type=Path, default=Path("tmp/ai_nas_visual_index_generation_gate_local"))
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "visual_index_generation_gate")
    personal_root = prepare_fixture(run_dir)
    db_path = run_dir / "personal_inventory.sqlite3"
    index_status = build_sqlite_inventory(personal_root, db_path)
    embedding_update = ensure_image_embeddings_for_photos(db_path, limit=50)
    records = index_status.get("records") or []
    if not records:
        from ai_nas_common import open_index_db, _record_from_sqlite_row

        con = open_index_db(db_path)
        try:
            records = [_record_from_sqlite_row(row) for row in con.execute("SELECT * FROM records ORDER BY relative_path").fetchall()]
        finally:
            con.close()
    runtime = vision_product_runtime_status()
    state_update = ensure_photo_visual_states(db_path, records, runtime=runtime)
    state_summary = photo_visual_state_summary(db_path)
    schema = vision_product_schema_status(db_path)

    recent = state_summary.get("recent") or []
    failures: list[str] = []
    if not schema.get("schema_ready"):
        failures.append("schema_not_ready")
    if state_update.get("attempted") != 3:
        failures.append(f"expected_three_photo_states:{state_update.get('attempted')}")
    if not recent:
        failures.append("no_visual_state_rows")
    for row in recent:
        rel = row.get("relative_path", "")
        if not row.get("acl_scope"):
            failures.append(f"{rel}:missing_acl_scope")
        if not str(row.get("security_partition_id") or "").startswith("scope:"):
            failures.append(f"{rel}:missing_security_partition")
        if int(row.get("generation") or 0) < 1:
            failures.append(f"{rel}:generation_not_incremented")
        degradation = row.get("degradation") or []
        if not degradation:
            failures.append(f"{rel}:missing_degradation_for_unconfigured_product_models")
    if not (state_summary.get("status_counts") or {}):
        failures.append("missing_status_counts")
    if not (state_update.get("privacy_counts") or {}):
        failures.append("missing_privacy_counts")

    verdict = OK if not failures else FAILED
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "personal_root": str(personal_root),
        "sqlite_index_path": str(db_path),
        "schema": schema,
        "runtime": runtime,
        "index_status": index_status,
        "embedding_update": embedding_update,
        "state_update": state_update,
        "state_summary": state_summary,
        "failures": failures,
        "acceptance": {
            "active_generation_per_photo": True,
            "security_partition_recorded": True,
            "privacy_class_recorded": True,
            "degraded_mode_recorded_when_models_missing": True,
        },
    }
    json_path = run_dir / "visual_index_generation_gate.json"
    md_path = run_dir / "visual_index_generation_gate.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Visual Index Generation Gate",
        "",
        f"- verdict: `{verdict}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- attempted: `{state_update.get('attempted')}`",
        f"- status_counts: `{state_summary.get('status_counts')}`",
        f"- privacy_counts: `{state_update.get('privacy_counts')}`",
        f"- failures: `{failures}`",
    ]
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(f"verdict: {verdict}")
    print(f"report: {json_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
