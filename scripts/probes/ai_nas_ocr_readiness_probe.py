#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from ai_nas_common import (
    DEFAULT_INDEX_PATH,
    DEFAULT_PERSONAL_ROOT,
    DEFAULT_REPORT_ROOT,
    ensure_report_dir,
    load_index,
    ocr_engine_status,
    safe_write_json,
    safe_write_text,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Report local OCR readiness and indexed scanned-document gaps.")
    parser.add_argument("--personal-root", type=Path, default=DEFAULT_PERSONAL_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--index-path", type=Path, default=DEFAULT_INDEX_PATH)
    args = parser.parse_args()

    index = load_index(args.index_path, args.personal_root, args.report_root)
    runtime = ocr_engine_status()
    ocr_required = []
    extraction_failures = []
    for record in index.get("records", []):
        metadata = record.get("metadata") or {}
        ocr = metadata.get("ocr") or {}
        if ocr.get("required") is True:
            ocr_required.append(
                {
                    "relative_path": record["relative_path"],
                    "path": record["path"],
                    "parse_error": record.get("parse_error"),
                    "ocr": ocr,
                    "pdf": metadata.get("pdf", {}),
                }
            )
        if record.get("parse_error"):
            extraction_failures.append(
                {
                    "relative_path": record["relative_path"],
                    "path": record["path"],
                    "parse_error": record.get("parse_error"),
                }
            )

    missing = []
    if not runtime["tesseract_cli"]:
        missing.append("tesseract CLI")
    if not runtime["pytesseract_importable"]:
        missing.append("pytesseract Python package")
    payload = {
        "generated_from_index_at": index.get("generated_at"),
        "personal_root": str(args.personal_root),
        "ocr_ready": runtime["ocr_ready"],
        "local_scan_detection_ready": runtime["local_scan_detection_ready"],
        "runtime": runtime,
        "missing_requirements": missing,
        "ocr_required_count": len(ocr_required),
        "extraction_failure_count": len(extraction_failures),
        "ocr_required_files": ocr_required,
        "extraction_failures": extraction_failures,
        "policy": {
            "invent_content": False,
            "source_files_modified": False,
            "writes": "Markdown/JSON readiness report only",
        },
    }

    run_dir = ensure_report_dir(args.report_root, "ocr_readiness")
    json_path = run_dir / "ocr_readiness.json"
    md_path = run_dir / "ocr_readiness.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS OCR Readiness",
        "",
        f"- ocr_ready: `{payload['ocr_ready']}`",
        f"- local_scan_detection_ready: `{payload['local_scan_detection_ready']}`",
        f"- missing_requirements: `{payload['missing_requirements']}`",
        f"- ocr_required_count: `{payload['ocr_required_count']}`",
        f"- extraction_failure_count: `{payload['extraction_failure_count']}`",
        "- policy: do not invent content; report readiness and failures only",
        "",
        "## Runtime",
        "",
    ]
    for key, value in runtime.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## OCR Required Files", ""])
    if not ocr_required:
        lines.append("- No indexed files currently require OCR.")
    for item in ocr_required:
        pdf = item.get("pdf") or {}
        lines.append(
            f"- `{item['relative_path']}` | pages `{pdf.get('page_count')}` | "
            f"embedded_images `{pdf.get('embedded_image_count')}` | status `{item['ocr'].get('status')}`"
        )
    lines.extend(["", "## Extraction Failures", ""])
    if not extraction_failures:
        lines.append("- No indexed extraction failures.")
    for item in extraction_failures:
        lines.append(f"- `{item['relative_path']}`: `{item['parse_error']}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
