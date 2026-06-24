#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from ai_nas_common import (
    DEFAULT_PERSONAL_ROOT,
    DEFAULT_REPORT_ROOT,
    DEFAULT_SQLITE_INDEX_PATH,
    _record_from_sqlite_row,
    build_sqlite_inventory,
    ensure_report_dir,
    ocr_candidate_record,
    ocr_engine_status,
    ocr_results_summary,
    open_index_db,
    run_ocr_for_record,
    safe_write_json,
    safe_write_text,
    upsert_ocr_result,
)


def load_ocr_candidates(db_path: Path, include_images: bool, limit: int) -> list[dict]:
    con = open_index_db(db_path)
    try:
        records = [_record_from_sqlite_row(row) for row in con.execute("SELECT * FROM records ORDER BY relative_path")]
    finally:
        con.close()
    candidates = [record for record in records if ocr_candidate_record(record, include_images=include_images)]
    return candidates[:limit]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run bounded OCR extraction for indexed scanned PDFs and invoice/screenshot images.")
    parser.add_argument("--personal-root", type=Path, default=DEFAULT_PERSONAL_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--sqlite-index-path", type=Path, default=DEFAULT_SQLITE_INDEX_PATH)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--include-images", action="store_true")
    parser.add_argument("--no-refresh-index", action="store_true")
    args = parser.parse_args()

    if not args.no_refresh_index:
        build_sqlite_inventory(args.personal_root, args.sqlite_index_path)
    elif not args.sqlite_index_path.exists():
        build_sqlite_inventory(args.personal_root, args.sqlite_index_path)

    runtime = ocr_engine_status()
    candidates = load_ocr_candidates(args.sqlite_index_path, args.include_images, max(1, args.limit))
    results = []
    for record in candidates:
        result = run_ocr_for_record(record, max_pages=max(1, args.max_pages))
        upsert_ocr_result(args.sqlite_index_path, result)
        results.append(result)
    summary = ocr_results_summary(args.sqlite_index_path)
    completed = [item for item in results if item["status"] == "ocr_completed"]
    blocked = [item for item in results if item["status"] == "blocked_missing_ocr_engine"]
    failed = [item for item in results if item["status"] == "ocr_failed"]
    payload = {
        "verdict": "ok_ai_nas_ocr_extract" if not failed else "limited_ai_nas_ocr_extract",
        "personal_root": str(args.personal_root),
        "sqlite_index_path": str(args.sqlite_index_path),
        "runtime": runtime,
        "candidate_count": len(candidates),
        "completed_count": len(completed),
        "blocked_count": len(blocked),
        "failed_count": len(failed),
        "include_images": args.include_images,
        "max_pages": args.max_pages,
        "results": results,
        "ocr_results_summary": summary,
        "audit": {
            "tool_id": "ai_nas_ocr_extract",
            "source_files_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "writes": "SQLite ocr_results rows plus Markdown/JSON report only",
            "invent_content": False,
        },
    }

    run_dir = ensure_report_dir(args.report_root, "ocr_extract")
    json_path = run_dir / "ocr_extract.json"
    md_path = run_dir / "ocr_extract.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS OCR Extract",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- ocr_ready: `{runtime['ocr_ready']}`",
        f"- candidate_count: `{len(candidates)}`",
        f"- completed_count: `{len(completed)}`",
        f"- blocked_count: `{len(blocked)}`",
        f"- failed_count: `{len(failed)}`",
        "- policy: OCR text only when runtime exists; otherwise explicit blocked status; no invented content",
        "",
        "## Results",
        "",
    ]
    if not results:
        lines.append("- No indexed OCR candidates found.")
    for item in results:
        lines.append(f"- `{item['relative_path']}` | status `{item['status']}` | engine `{item.get('engine')}`")
        if item.get("error"):
            lines.append(f"  - error: `{item['error']}`")
        if item.get("text_preview"):
            lines.append(f"  - text_preview: {item['text_preview'][:240]}")
    lines.extend(["", "## OCR Status Summary", ""])
    lines.append(f"- status_counts: `{summary['status_counts']}`")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
