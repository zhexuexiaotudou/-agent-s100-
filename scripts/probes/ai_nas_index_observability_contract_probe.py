#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path

from ai_nas_common import (
    DEFAULT_REPORT_ROOT,
    build_sqlite_inventory,
    ensure_report_dir,
    iso_now,
    open_index_db,
    safe_write_json,
    safe_write_text,
    sqlite_index_status,
)


TOOL_ID = "ai_nas_index_observability_contract"


def prepare_fixture(root: Path) -> dict:
    if root.exists():
        shutil.rmtree(root)
    personal = root / "Personal"
    docs = personal / "Documents"
    photos = personal / "Photos"
    docs.mkdir(parents=True, exist_ok=True)
    photos.mkdir(parents=True, exist_ok=True)
    contract = docs / "2024-renovation-contract.txt"
    invoice = docs / "2024-renovation-invoice.txt"
    corrupt_pdf = docs / "2024-corrupt-scan.pdf"
    photo = photos / "2024-beach-photo.jpg"
    contract.write_text(
        "Renovation contract 2024. Deposit 20000 CNY on 2024-03-01. Final payment 8000 CNY on 2024-05-20.\n",
        encoding="utf-8",
    )
    invoice.write_text(
        "Invoice receipt 2024 renovation reimbursement. Amount 12000 CNY. Date 2024-04-15.\n",
        encoding="utf-8",
    )
    corrupt_pdf.write_bytes(b"%PDF-1.4\n% intentionally truncated AI-NAS observability fixture\n1 0 obj << /Type /Catalog >>\n")
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (320, 180), (80, 170, 230))
    draw = ImageDraw.Draw(image)
    draw.text((20, 80), "beach photo 2024", fill=(255, 255, 255))
    image.save(photo)
    return {
        "personal_root": personal,
        "contract": contract,
        "invoice": invoice,
        "corrupt_pdf": corrupt_pdf,
        "photo": photo,
    }


def record_snapshot(db_path: Path, path: Path) -> dict | None:
    con = open_index_db(db_path)
    try:
        row = con.execute(
            """
            SELECT path, relative_path, summary, parse_error, sha256, mtime_ns
            FROM records
            WHERE path = ?
            """,
            (str(path),),
        ).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def status_contract(status: dict, corrupt_rel: str, updated_rel: str) -> tuple[dict, list[str]]:
    checks = {
        "has_status": bool(status.get("status")),
        "has_last_scan_started_at": bool(status.get("last_scan_started_at")),
        "has_last_scan_finished_at": bool(status.get("last_scan_finished_at")),
        "has_last_run": isinstance(status.get("last_run"), dict),
        "has_queue_progress": isinstance(status.get("queue_progress"), dict),
        "queue_processed_reported": isinstance((status.get("queue_progress") or {}).get("processed"), int),
        "queue_max_files_reported": "max_files" in (status.get("queue_progress") or {}),
        "queue_completion_reported": "complete" in (status.get("queue_progress") or {}),
        "failed_count_reported": isinstance(status.get("failed_count"), int),
        "recent_failures_reported": isinstance(status.get("recent_failures"), list),
        "recent_changes_reported": isinstance(status.get("recent_changes"), list),
        "corrupt_pdf_failure_visible": any(
            item.get("relative_path") == corrupt_rel and item.get("reason") for item in status.get("recent_failures", [])
        ),
        "updated_change_visible": any(
            item.get("relative_path") == updated_rel and item.get("action") == "updated"
            for item in status.get("recent_changes", [])
        ),
    }
    failures = [name for name, ok in checks.items() if not ok]
    return checks, failures


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS SQLite index observability contract over an isolated fixture.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--fixture-root", type=Path, default=None)
    parser.add_argument("--max-files", type=int, default=5000)
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "index_observability_contract")
    fixture_root = args.fixture_root or (run_dir / "fixture")
    fixture = prepare_fixture(fixture_root)
    personal_root = fixture["personal_root"]
    db_path = run_dir / "index_observability_contract.sqlite3"
    corrupt_rel = fixture["corrupt_pdf"].relative_to(personal_root).as_posix()
    updated_rel = fixture["contract"].relative_to(personal_root).as_posix()

    initial_status = build_sqlite_inventory(personal_root, db_path, max_files=args.max_files)
    initial_corrupt = record_snapshot(db_path, fixture["corrupt_pdf"])

    time.sleep(0.05)
    fixture["contract"].write_text(
        "Renovation contract 2024 updated. Deposit 20000 CNY on 2024-03-01. Final payment 9000 CNY on 2024-06-01.\n",
        encoding="utf-8",
    )
    update_status = build_sqlite_inventory(personal_root, db_path, max_files=args.max_files)
    final_status = sqlite_index_status(db_path)
    final_contract = record_snapshot(db_path, fixture["contract"])
    final_corrupt = record_snapshot(db_path, fixture["corrupt_pdf"])
    checks, failures = status_contract(final_status, corrupt_rel, updated_rel)
    if not final_corrupt:
        failures.append("corrupt_pdf_record_missing")
    elif final_corrupt.get("summary") != "content_not_extracted":
        failures.append("corrupt_pdf_summary_not_explicit_content_not_extracted")
    if final_corrupt and not final_corrupt.get("parse_error"):
        failures.append("corrupt_pdf_parse_error_missing")
    if not final_contract:
        failures.append("updated_contract_record_missing")
    elif "9000 CNY" not in final_contract.get("summary", ""):
        failures.append("updated_contract_summary_not_refreshed")

    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_index_observability_contract" if not failures else "failed_ai_nas_index_observability_contract",
        "scope": "bounded SQLite/FTS index status observability contract over isolated Personal fixture",
        "personal_root": str(personal_root),
        "sqlite_index_path": str(db_path),
        "fixture": {key: str(value) for key, value in fixture.items()},
        "contract_checks": checks,
        "summary": {
            "last_scan_queryable": checks["has_last_scan_started_at"] and checks["has_last_scan_finished_at"],
            "queue_progress_queryable": checks["has_queue_progress"] and checks["queue_processed_reported"],
            "failed_files_queryable": checks["failed_count_reported"] and checks["corrupt_pdf_failure_visible"],
            "mtime_hash_update_visible": checks["updated_change_visible"] and bool(final_contract),
            "no_content_invented_for_failed_pdf": bool(final_corrupt and final_corrupt.get("summary") == "content_not_extracted"),
            "failures": failures,
        },
        "initial_status": {
            "status": initial_status.get("status"),
            "last_scan_started_at": initial_status.get("last_scan_started_at"),
            "last_scan_finished_at": initial_status.get("last_scan_finished_at"),
            "failed_count": initial_status.get("failed_count"),
            "queue_progress": initial_status.get("queue_progress"),
            "last_run": initial_status.get("last_run"),
        },
        "update_status": {
            "status": update_status.get("status"),
            "last_scan_started_at": update_status.get("last_scan_started_at"),
            "last_scan_finished_at": update_status.get("last_scan_finished_at"),
            "failed_count": update_status.get("failed_count"),
            "queue_progress": update_status.get("queue_progress"),
            "last_run": update_status.get("last_run"),
            "recent_changes": update_status.get("recent_changes"),
            "recent_failures": update_status.get("recent_failures"),
        },
        "record_evidence": {
            "initial_corrupt_pdf": initial_corrupt,
            "final_corrupt_pdf": final_corrupt,
            "final_updated_contract": final_contract,
        },
        "final_index_status": final_status,
        "audit": {
            "real_personal_source_modified": False,
            "fixture_files_created": True,
            "fixture_file_updated": True,
            "fixture_corrupt_pdf_created": True,
            "delete_performed_on_real_personal": False,
            "move_performed_on_real_personal": False,
            "overwrite_performed_on_real_personal": False,
            "service_installed": False,
            "service_started": False,
            "writes": "isolated fixture files plus SQLite/FTS index and Markdown/JSON observability contract reports",
        },
        "production_gap": "This proves index status observability fields over a bounded fixture; production still needs the same contract against a mounted NAS Personal root and resident daemon.",
    }

    json_path = run_dir / "index_observability_contract.json"
    md_path = run_dir / "index_observability_contract.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Index Observability Contract",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- last_scan_queryable: `{payload['summary']['last_scan_queryable']}`",
        f"- queue_progress_queryable: `{payload['summary']['queue_progress_queryable']}`",
        f"- failed_files_queryable: `{payload['summary']['failed_files_queryable']}`",
        f"- mtime_hash_update_visible: `{payload['summary']['mtime_hash_update_visible']}`",
        f"- no_content_invented_for_failed_pdf: `{payload['summary']['no_content_invented_for_failed_pdf']}`",
        f"- failures: `{failures}`",
        "- policy: isolated fixture only; no real Personal mutation, service install, or service start",
        "",
        "## Contract Checks",
        "",
    ]
    for key, value in checks.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Final Status", ""])
    queue = final_status.get("queue_progress") or {}
    lines.append(f"- status: `{final_status.get('status')}`")
    lines.append(f"- last_scan_started_at: `{final_status.get('last_scan_started_at')}`")
    lines.append(f"- last_scan_finished_at: `{final_status.get('last_scan_finished_at')}`")
    lines.append(f"- failed_count: `{final_status.get('failed_count')}`")
    lines.append(f"- queue_progress: processed `{queue.get('processed')}`, max_files `{queue.get('max_files')}`, complete `{queue.get('complete')}`")
    lines.extend(["", "## Recent Failures", ""])
    for failure in final_status.get("recent_failures") or []:
        lines.append(f"- `{failure.get('relative_path')}`: `{failure.get('reason')}`")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Production Gap", "", f"- {payload['production_gap']}"])
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
