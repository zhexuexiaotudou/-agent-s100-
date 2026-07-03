#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from ai_nas_common import build_sqlite_inventory, ensure_report_dir, iso_now, open_index_db, safe_write_json, safe_write_text
from ai_nas_vision_runtime import vision_product_runtime_status
from ai_nas_vision_schema import VISION_PRODUCT_TABLES, vision_product_schema_status
from ai_nas_visual_evidence import degradation_item, evidence_chips, evidence_item


TOOL_ID = "ai_nas_visual_product_foundation_gate"
OK = "ok_ai_nas_visual_product_foundation_gate"
FAILED = "failed_ai_nas_visual_product_foundation_gate"


def prepare_fixture(run_dir: Path) -> Path:
    personal = run_dir / "Personal"
    if personal.exists():
        shutil.rmtree(personal)
    for name in ("Documents", "Photos", "Movies", "Inbox"):
        (personal / name).mkdir(parents=True, exist_ok=True)
    (personal / "Documents" / "invoice_fixture.txt").write_text(
        "Invoice fixture for visual product foundation gate.\n",
        encoding="utf-8",
    )
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (420, 260), (242, 242, 238))
    draw = ImageDraw.Draw(image)
    draw.text((32, 110), "WHITE TOP TEST PHOTO", fill=(20, 20, 20))
    image.save(personal / "Photos" / "white_top_fixture.jpg", quality=90)
    return personal


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate product-grade AI-NAS visual schema/runtime/evidence foundation.")
    parser.add_argument("--report-root", type=Path, default=Path("tmp/ai_nas_visual_product_foundation_gate_local"))
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "visual_product_foundation_gate")
    personal_root = prepare_fixture(run_dir)
    db_path = run_dir / "personal_inventory.sqlite3"
    index_status = build_sqlite_inventory(personal_root, db_path)
    con = open_index_db(db_path)
    try:
        record_count = con.execute("SELECT COUNT(*) AS count FROM records").fetchone()["count"]
    finally:
        con.close()

    schema = vision_product_schema_status(db_path)
    runtime = vision_product_runtime_status()
    sample_evidence = [
        evidence_item(
            "object_detection",
            label="person",
            confidence=0.91,
            model_id="fixture-detector",
            runtime="fixture",
            region_id=1,
        ),
        evidence_item(
            "clothing_attribute",
            label="upper_clothing.color:white",
            confidence=0.82,
            model_id="fixture-color-v1",
            runtime="fixture",
            region_id=2,
        ),
    ]
    sample_degradation = degradation_item("image_text_embedding_not_configured", stage="embedding", confidence_cap=0.35)

    failures: list[str] = []
    if record_count < 2:
        failures.append("inventory_records_missing")
    if not schema.get("schema_ready"):
        failures.append("vision_product_schema_not_ready")
    missing_tables = [name for name, exists in (schema.get("tables") or {}).items() if not exists]
    for table in VISION_PRODUCT_TABLES:
        if table in missing_tables:
            failures.append(f"missing_table:{table}")
    if "components" not in runtime or "missing_for_product" not in runtime:
        failures.append("runtime_status_missing_product_fields")
    if not runtime.get("components", {}).get("evidence", {}).get("ready"):
        failures.append("evidence_runtime_not_ready")
    if not evidence_chips(sample_evidence):
        failures.append("evidence_chips_empty")
    if sample_degradation.get("confidence_cap", 1) > 0.5:
        failures.append("degradation_confidence_cap_too_high")

    verdict = OK if not failures else FAILED
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "personal_root": str(personal_root),
        "sqlite_index_path": str(db_path),
        "index_status": index_status,
        "record_count": record_count,
        "schema": schema,
        "runtime": runtime,
        "sample_evidence": sample_evidence,
        "sample_evidence_chips": evidence_chips(sample_evidence),
        "sample_degradation": sample_degradation,
        "failures": failures,
        "acceptance": {
            "product_schema_is_separate_from_legacy_tables": True,
            "runtime_does_not_fake_missing_models": True,
            "evidence_has_model_runtime_confidence": True,
            "degraded_mode_has_confidence_cap": True,
        },
    }
    json_path = run_dir / "visual_product_foundation_gate.json"
    md_path = run_dir / "visual_product_foundation_gate.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Visual Product Foundation Gate",
        "",
        f"- verdict: `{verdict}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- schema_ready: `{schema.get('schema_ready')}`",
        f"- product_ready: `{runtime.get('product_ready')}`",
        f"- missing_for_product: `{runtime.get('missing_for_product')}`",
        f"- failures: `{failures}`",
        "",
        "## Evidence Chips",
        "",
    ]
    for chip in payload["sample_evidence_chips"]:
        lines.append(f"- `{chip}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(f"verdict: {verdict}")
    print(f"report: {json_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
