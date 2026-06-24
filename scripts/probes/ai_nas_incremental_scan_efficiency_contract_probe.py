#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path

import ai_nas_common as common


TOOL_ID = "ai_nas_incremental_scan_efficiency_contract"


def prepare_fixture(root: Path) -> dict:
    if root.exists():
        shutil.rmtree(root)
    personal = root / "Personal"
    docs = personal / "Documents"
    inbox = personal / "Inbox"
    photos = personal / "Photos"
    docs.mkdir(parents=True, exist_ok=True)
    inbox.mkdir(parents=True, exist_ok=True)
    photos.mkdir(parents=True, exist_ok=True)
    contract = docs / "2024_renovation_contract.txt"
    invoice = docs / "2024_renovation_invoice.txt"
    chat = inbox / "2024_payment_chat_screenshot_note.txt"
    photo = photos / "2024_invoice_screenshot.jpg"
    contract.write_text(
        "Renovation contract 2024. Deposit 20000 CNY on 2024-03-01. Final payment 8000 CNY on 2024-05-20.\n",
        encoding="utf-8",
    )
    invoice.write_text(
        "Invoice receipt 2024 renovation reimbursement. Amount 12000 CNY. Date 2024-04-15.\n",
        encoding="utf-8",
    )
    chat.write_text(
        "Chat screenshot note: renovation payment discussed on 2024-04-20, amount 5000 CNY.\n",
        encoding="utf-8",
    )
    photo.write_bytes(b"fixture-image-bytes-renovation-invoice-screenshot-2024\n")
    return {
        "personal_root": personal,
        "contract": contract,
        "invoice": invoice,
        "chat": chat,
        "photo": photo,
    }


def manifest(root: Path) -> dict:
    return {
        path.relative_to(root).as_posix(): {
            "size": path.stat().st_size,
            "mtime_ns": path.stat().st_mtime_ns,
            "sha256": common.sha256_file(path),
        }
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def run_inventory_with_build_counter(personal_root: Path, db_path: Path, max_files: int) -> tuple[dict, list[str]]:
    original = common.build_record_for_path
    calls: list[str] = []

    def counted_build_record(path: Path, root: Path) -> dict:
        calls.append(path.relative_to(root).as_posix())
        return original(path, root)

    common.build_record_for_path = counted_build_record
    try:
        status = common.build_sqlite_inventory(personal_root, db_path, max_files=max_files)
    finally:
        common.build_record_for_path = original
    return status, calls


def latest_run_changes(db_path: Path) -> list[dict]:
    con = common.open_index_db(db_path)
    try:
        return [
            dict(row)
            for row in con.execute(
                """
                SELECT action, relative_path, reason, created_at
                FROM change_log
                WHERE run_id = COALESCE((SELECT MAX(id) FROM index_runs), -1)
                ORDER BY id
                """
            )
        ]
    finally:
        con.close()


def index_counts(db_path: Path) -> dict:
    con = common.open_index_db(db_path)
    try:
        return {
            "records": con.execute("SELECT COUNT(*) AS count FROM records").fetchone()["count"],
            "records_fts": con.execute("SELECT COUNT(*) AS count FROM records_fts").fetchone()["count"],
            "embeddings": con.execute("SELECT COUNT(*) AS count FROM embeddings").fetchone()["count"],
        }
    finally:
        con.close()


def unlink_with_retry(path: Path, attempts: int = 10, delay_seconds: float = 0.1) -> None:
    for attempt in range(attempts):
        try:
            path.unlink()
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(delay_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS incremental SQLite/FTS scan efficiency contract.")
    parser.add_argument("--report-root", type=Path, default=common.DEFAULT_REPORT_ROOT)
    parser.add_argument("--fixture-root", type=Path, default=None)
    parser.add_argument("--max-files", type=int, default=5000)
    args = parser.parse_args()

    run_dir = common.ensure_report_dir(args.report_root, "incremental_scan_efficiency_contract")
    fixture_root = args.fixture_root or (run_dir / "fixture")
    fixture = prepare_fixture(fixture_root)
    personal_root = fixture["personal_root"]
    db_path = run_dir / "incremental_scan_efficiency.sqlite3"

    initial_manifest = manifest(personal_root)
    first_status, first_build_calls = run_inventory_with_build_counter(personal_root, db_path, args.max_files)
    first_counts = index_counts(db_path)

    second_manifest_before = manifest(personal_root)
    second_status, second_build_calls = run_inventory_with_build_counter(personal_root, db_path, args.max_files)
    second_counts = index_counts(db_path)
    second_changes = latest_run_changes(db_path)
    second_manifest_after = manifest(personal_root)

    time.sleep(0.05)
    fixture["contract"].write_text(
        "Renovation contract 2024 updated. Deposit 20000 CNY on 2024-03-01. Final payment 9000 CNY on 2024-06-01.\n",
        encoding="utf-8",
    )
    new_note = personal_root / "Documents" / "2024_renovation_payment_addendum.txt"
    new_note.write_text(
        "Payment addendum 2024. Extra milestone 3000 CNY on 2024-06-15 for renovation acceptance.\n",
        encoding="utf-8",
    )
    deleted_rel = fixture["invoice"].relative_to(personal_root).as_posix()
    unlink_with_retry(fixture["invoice"])
    third_manifest_before = manifest(personal_root)
    third_status, third_build_calls = run_inventory_with_build_counter(personal_root, db_path, args.max_files)
    third_counts = index_counts(db_path)
    third_changes = latest_run_changes(db_path)
    third_manifest_after = manifest(personal_root)

    expected_first_calls = sorted(initial_manifest)
    expected_third_calls = sorted(
        [
            fixture["contract"].relative_to(personal_root).as_posix(),
            new_note.relative_to(personal_root).as_posix(),
        ]
    )
    third_actions = {(item.get("action"), item.get("relative_path")) for item in third_changes}
    second_last_run = second_status.get("last_run") or {}
    third_last_run = third_status.get("last_run") or {}

    checks = {
        "initial_scan_builds_all_files": sorted(first_build_calls) == expected_first_calls,
        "no_change_scan_builds_zero_records": len(second_build_calls) == 0,
        "no_change_scan_reports_all_files_unchanged": second_last_run.get("unchanged") == len(initial_manifest),
        "no_change_scan_has_no_change_log_rows": len(second_changes) == 0,
        "no_change_scan_preserves_source_manifest": second_manifest_before == second_manifest_after,
        "changed_scan_builds_only_added_and_updated_files": sorted(third_build_calls) == expected_third_calls,
        "changed_scan_records_deleted_file": ("deleted", deleted_rel) in third_actions,
        "changed_scan_records_updated_file": ("updated", fixture["contract"].relative_to(personal_root).as_posix()) in third_actions,
        "changed_scan_records_added_file": ("added", new_note.relative_to(personal_root).as_posix()) in third_actions,
        "changed_scan_unchanged_count_expected": third_last_run.get("unchanged") == len(initial_manifest) - 2,
        "fts_count_matches_records_after_incremental_scan": third_counts["records"] == third_counts["records_fts"],
        "embedding_count_matches_records_after_incremental_scan": third_counts["records"] == third_counts["embeddings"],
        "fixture_manifest_stable_during_third_scan": third_manifest_before == third_manifest_after,
    }
    failures = [name for name, ok in checks.items() if not ok]

    payload = {
        "generated_at": common.iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_incremental_scan_efficiency_contract"
        if not failures
        else "failed_ai_nas_incremental_scan_efficiency_contract",
        "scope": "bounded SQLite/FTS incremental scan efficiency contract over isolated Personal fixture",
        "personal_root": str(personal_root),
        "sqlite_index_path": str(db_path),
        "fixture": {key: str(value) for key, value in fixture.items()},
        "expected_build_calls": {
            "first_scan": expected_first_calls,
            "second_no_change_scan": [],
            "third_changed_scan": expected_third_calls,
        },
        "observed_build_calls": {
            "first_scan": first_build_calls,
            "second_no_change_scan": second_build_calls,
            "third_changed_scan": third_build_calls,
        },
        "scan_runs": {
            "first": {
                "last_run": first_status.get("last_run"),
                "counts": first_counts,
            },
            "second_no_change": {
                "last_run": second_last_run,
                "counts": second_counts,
                "change_log": second_changes,
            },
            "third_changed": {
                "last_run": third_last_run,
                "counts": third_counts,
                "change_log": third_changes,
            },
        },
        "summary": {
            "initial_file_count": len(initial_manifest),
            "second_scan_build_record_calls": len(second_build_calls),
            "second_scan_unchanged": second_last_run.get("unchanged"),
            "third_scan_build_record_calls": len(third_build_calls),
            "third_scan_added": third_last_run.get("added"),
            "third_scan_updated": third_last_run.get("updated"),
            "third_scan_deleted": third_last_run.get("deleted"),
            "third_scan_unchanged": third_last_run.get("unchanged"),
            "sqlite_fts_consistent": third_counts["records"] == third_counts["records_fts"],
            "embedding_rows_consistent": third_counts["records"] == third_counts["embeddings"],
            "failures": failures,
        },
        "contract_checks": checks,
        "audit": {
            "real_personal_source_modified": False,
            "fixture_only": True,
            "download_performed": False,
            "network_call_performed": False,
            "service_restart_performed": False,
            "kill_performed": False,
            "delete_performed_on_real_personal": False,
            "delete_performed": "isolated fixture invoice only to verify deleted change_log and index cleanup",
            "move_performed_on_real_personal": False,
            "overwrite_performed_on_real_personal": False,
            "writes": "isolated fixture files plus SQLite/FTS index and Markdown/JSON incremental scan reports",
        },
        "production_gap": "This proves unchanged files are not re-extracted in the SQLite/FTS indexer over a bounded fixture; production still needs the same efficiency telemetry on a mounted NAS Personal root.",
    }

    json_path = run_dir / "incremental_scan_efficiency_contract.json"
    md_path = run_dir / "incremental_scan_efficiency_contract.md"
    common.safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Incremental Scan Efficiency Contract",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- initial_file_count: `{payload['summary']['initial_file_count']}`",
        f"- second_scan_build_record_calls: `{payload['summary']['second_scan_build_record_calls']}`",
        f"- second_scan_unchanged: `{payload['summary']['second_scan_unchanged']}`",
        f"- third_scan_build_record_calls: `{payload['summary']['third_scan_build_record_calls']}`",
        f"- third_scan_added: `{payload['summary']['third_scan_added']}`",
        f"- third_scan_updated: `{payload['summary']['third_scan_updated']}`",
        f"- third_scan_deleted: `{payload['summary']['third_scan_deleted']}`",
        f"- third_scan_unchanged: `{payload['summary']['third_scan_unchanged']}`",
        f"- sqlite_fts_consistent: `{payload['summary']['sqlite_fts_consistent']}`",
        f"- embedding_rows_consistent: `{payload['summary']['embedding_rows_consistent']}`",
        f"- failures: `{failures}`",
        "- policy: bounded fixture only; no real Personal mutation, service install, network, or destructive production action",
        "",
        "## Build Calls",
        "",
        f"- first_scan: `{first_build_calls}`",
        f"- second_no_change_scan: `{second_build_calls}`",
        f"- third_changed_scan: `{third_build_calls}`",
        "",
        "## Contract Checks",
        "",
    ]
    for key, value in checks.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Third Scan Change Log", ""])
    for item in third_changes:
        lines.append(f"- {item.get('action')}: `{item.get('relative_path')}` reason `{item.get('reason')}`")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Production Gap", "", f"- {payload['production_gap']}"])
    common.safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
