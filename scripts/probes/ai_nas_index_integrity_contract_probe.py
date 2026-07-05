#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from ai_nas_common import (
    DEFAULT_REPORT_ROOT,
    build_sqlite_inventory,
    ensure_report_dir,
    iso_now,
    open_index_db,
    safe_write_json,
    safe_write_text,
    search_sqlite_index,
    sha256_file,
    sqlite_index_status,
)


TOOL_ID = "ai_nas_sqlite_index_integrity_contract"
REQUIRED_TABLES = {
    "records",
    "records_fts",
    "index_runs",
    "change_log",
    "failures",
    "embeddings",
    "ocr_results",
    "image_embeddings",
}
REQUIRED_INDEXES = {
    "idx_embeddings_model",
    "idx_ocr_results_status",
    "idx_image_embeddings_status",
    "idx_image_embeddings_model",
}


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
    invoice = docs / "2024_reimbursement_invoice.txt"
    chat = inbox / "2024_payment_chat_screenshot_note.txt"
    transient = docs / "temporary_deleted_after_first_scan.txt"
    contract.write_text(
        "Renovation contract 2024. Deposit 20000 CNY on 2024-03-01. Final payment 8000 CNY on 2024-05-20.\n",
        encoding="utf-8",
    )
    invoice.write_text(
        "Reimbursement invoice receipt 2024. Amount 12000 CNY. Date 2024-04-15. Payment node final milestone.\n",
        encoding="utf-8",
    )
    chat.write_text(
        "Chat screenshot note: renovation payment discussed on 2024-04-20, amount 5000 CNY.\n",
        encoding="utf-8",
    )
    transient.write_text("This file should disappear from SQLite, FTS, and embeddings after deletion.\n", encoding="utf-8")
    return {
        "personal_root": personal,
        "contract": contract,
        "invoice": invoice,
        "chat": chat,
        "transient": transient,
    }


def source_manifest(root: Path) -> dict:
    return {
        path.relative_to(root).as_posix(): {
            "sha256": sha256_file(path),
            "mtime_ns": path.stat().st_mtime_ns,
            "size": path.stat().st_size,
        }
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def db_snapshot(db_path: Path, deleted_path: Path | None = None) -> dict:
    con = open_index_db(db_path)
    try:
        tables = {
            row["name"]
            for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            )
        }
        indexes = {row["name"] for row in con.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        integrity = [row[0] for row in con.execute("PRAGMA integrity_check")]
        quick_check = [row[0] for row in con.execute("PRAGMA quick_check")]
        record_count = con.execute("SELECT COUNT(*) AS count FROM records").fetchone()["count"]
        fts_count = con.execute("SELECT COUNT(*) AS count FROM records_fts").fetchone()["count"]
        embedding_count = con.execute("SELECT COUNT(*) AS count FROM embeddings").fetchone()["count"]
        orphan_embeddings = con.execute(
            """
            SELECT COUNT(*) AS count
            FROM embeddings
            LEFT JOIN records ON records.path = embeddings.path
            WHERE records.path IS NULL
            """
        ).fetchone()["count"]
        orphan_fts = con.execute(
            """
            SELECT COUNT(*) AS count
            FROM records_fts
            LEFT JOIN records ON records.path = records_fts.path
            WHERE records.path IS NULL
            """
        ).fetchone()["count"]
        orphan_ocr = con.execute(
            """
            SELECT COUNT(*) AS count
            FROM ocr_results
            LEFT JOIN records ON records.path = ocr_results.path
            WHERE records.path IS NULL
            """
        ).fetchone()["count"]
        orphan_image_embeddings = con.execute(
            """
            SELECT COUNT(*) AS count
            FROM image_embeddings
            LEFT JOIN records ON records.path = image_embeddings.path
            WHERE records.path IS NULL
            """
        ).fetchone()["count"]
        deleted_presence = {}
        if deleted_path is not None:
            value = str(deleted_path)
            deleted_presence = {
                "records": con.execute("SELECT COUNT(*) AS count FROM records WHERE path=?", (value,)).fetchone()["count"],
                "records_fts": con.execute("SELECT COUNT(*) AS count FROM records_fts WHERE path=?", (value,)).fetchone()["count"],
                "embeddings": con.execute("SELECT COUNT(*) AS count FROM embeddings WHERE path=?", (value,)).fetchone()["count"],
                "ocr_results": con.execute("SELECT COUNT(*) AS count FROM ocr_results WHERE path=?", (value,)).fetchone()["count"],
                "image_embeddings": con.execute("SELECT COUNT(*) AS count FROM image_embeddings WHERE path=?", (value,)).fetchone()["count"],
            }
    finally:
        con.close()
    return {
        "tables": sorted(tables),
        "indexes": sorted(indexes),
        "integrity_check": integrity,
        "quick_check": quick_check,
        "record_count": int(record_count),
        "fts_count": int(fts_count),
        "embedding_count": int(embedding_count),
        "orphan_counts": {
            "embeddings": int(orphan_embeddings),
            "records_fts": int(orphan_fts),
            "ocr_results": int(orphan_ocr),
            "image_embeddings": int(orphan_image_embeddings),
        },
        "deleted_path_presence": deleted_presence,
    }


def evaluate_snapshot(snapshot: dict, require_deleted_absent: bool = False) -> list[str]:
    failures = []
    missing_tables = sorted(REQUIRED_TABLES - set(snapshot["tables"]))
    missing_indexes = sorted(REQUIRED_INDEXES - set(snapshot["indexes"]))
    if missing_tables:
        failures.append(f"missing_tables:{','.join(missing_tables)}")
    if missing_indexes:
        failures.append(f"missing_indexes:{','.join(missing_indexes)}")
    if snapshot["integrity_check"] != ["ok"]:
        failures.append("pragma_integrity_check_not_ok")
    if snapshot["quick_check"] != ["ok"]:
        failures.append("pragma_quick_check_not_ok")
    if snapshot["record_count"] != snapshot["fts_count"]:
        failures.append("records_fts_count_mismatch")
    if snapshot["record_count"] != snapshot["embedding_count"]:
        failures.append("records_embedding_count_mismatch")
    for table, count in snapshot["orphan_counts"].items():
        if count:
            failures.append(f"orphan_rows:{table}:{count}")
    if require_deleted_absent:
        for table, count in snapshot.get("deleted_path_presence", {}).items():
            if count:
                failures.append(f"deleted_path_still_present:{table}")
    return failures


def grounded_search_ok(db_path: Path) -> tuple[bool, list[dict], list[str]]:
    matches = search_sqlite_index(db_path, "2024 renovation payment invoice chat screenshot", limit=6)
    failures = []
    if not matches:
        failures.append("search_returned_no_matches")
    for idx, match in enumerate(matches[:3]):
        label = match.get("relative_path") or f"match_{idx}"
        if not match.get("reasons"):
            failures.append(f"{label}:missing_reasons")
        if not match.get("evidence"):
            failures.append(f"{label}:missing_evidence")
        if match.get("confidence") is None:
            failures.append(f"{label}:missing_confidence")
    return not failures, matches, failures


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS SQLite/FTS index integrity and recovery contract.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--fixture-root", type=Path, default=None)
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "sqlite_index_integrity_contract")
    fixture_root = args.fixture_root or (run_dir / "fixture")
    fixture = prepare_fixture(fixture_root)
    personal_root = fixture["personal_root"]
    db_path = run_dir / "sqlite_index_integrity.sqlite3"
    source_before = source_manifest(personal_root)
    first_status = build_sqlite_inventory(personal_root, db_path)
    first_snapshot = db_snapshot(db_path)

    deleted_path = fixture["transient"]
    deleted_rel = deleted_path.relative_to(personal_root).as_posix()
    deleted_path.unlink()
    second_status = build_sqlite_inventory(personal_root, db_path)
    second_snapshot = db_snapshot(db_path, deleted_path=deleted_path)
    source_after = source_manifest(personal_root)
    search_ok, matches, search_failures = grounded_search_ok(db_path)

    expected_source_after = dict(source_before)
    expected_source_after.pop(deleted_rel)
    failures = []
    failures.extend(f"first:{failure}" for failure in evaluate_snapshot(first_snapshot))
    failures.extend(f"second:{failure}" for failure in evaluate_snapshot(second_snapshot, require_deleted_absent=True))
    failures.extend(f"search:{failure}" for failure in search_failures)
    if source_after != expected_source_after:
        failures.append("unexpected_source_manifest_change_beyond_fixture_delete")
    if (second_status.get("last_run") or {}).get("deleted", 0) < 1:
        failures.append("deleted_change_not_recorded")

    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_sqlite_index_integrity_contract" if not failures else "failed_ai_nas_sqlite_index_integrity_contract",
        "scope": "bounded SQLite/FTS integrity, schema, orphan cleanup, and grounded-search contract",
        "personal_root": str(personal_root),
        "sqlite_index_path": str(db_path),
        "fixture": {key: str(value) for key, value in fixture.items()},
        "deleted_fixture_relative_path": deleted_rel,
        "first_status": first_status,
        "second_status": second_status,
        "first_snapshot": first_snapshot,
        "second_snapshot": second_snapshot,
        "search": {
            "ok": search_ok,
            "match_count": len(matches),
            "top_matches": matches[:3],
            "failures": search_failures,
        },
        "summary": {
            "required_tables_present": not sorted(REQUIRED_TABLES - set(second_snapshot["tables"])),
            "required_indexes_present": not sorted(REQUIRED_INDEXES - set(second_snapshot["indexes"])),
            "integrity_check_ok": second_snapshot["integrity_check"] == ["ok"],
            "fts_count_matches_records": second_snapshot["record_count"] == second_snapshot["fts_count"],
            "embedding_count_matches_records": second_snapshot["record_count"] == second_snapshot["embedding_count"],
            "orphan_rows_absent": not any(second_snapshot["orphan_counts"].values()),
            "deleted_path_absent_from_index": not any(second_snapshot["deleted_path_presence"].values()),
            "grounded_search_ok": search_ok,
            "unexpected_source_mutation": source_after != expected_source_after,
            "failures": failures,
        },
        "audit": {
            "source_files_modified": "isolated fixture deletion only",
            "personal_source_modified": False,
            "fixture_only": True,
            "download_performed": False,
            "network_call_performed": False,
            "service_restart_performed": False,
            "kill_performed": False,
            "delete_performed": "isolated fixture file only to test index cleanup",
            "move_performed": False,
            "overwrite_performed": False,
            "writes": "isolated fixture files, SQLite index, and Markdown/JSON index integrity reports only",
        },
    }
    json_path = run_dir / "sqlite_index_integrity_contract.json"
    md_path = run_dir / "sqlite_index_integrity_contract.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS SQLite Index Integrity Contract",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- required_tables_present: `{payload['summary']['required_tables_present']}`",
        f"- required_indexes_present: `{payload['summary']['required_indexes_present']}`",
        f"- integrity_check_ok: `{payload['summary']['integrity_check_ok']}`",
        f"- fts_count_matches_records: `{payload['summary']['fts_count_matches_records']}`",
        f"- embedding_count_matches_records: `{payload['summary']['embedding_count_matches_records']}`",
        f"- orphan_rows_absent: `{payload['summary']['orphan_rows_absent']}`",
        f"- deleted_path_absent_from_index: `{payload['summary']['deleted_path_absent_from_index']}`",
        f"- grounded_search_ok: `{payload['summary']['grounded_search_ok']}`",
        f"- failures: `{failures}`",
        "- policy: bounded fixture only; verifies productized SQLite/FTS integrity without touching real Personal data",
        "",
        "## Snapshots",
        "",
        f"- first records: `{first_snapshot['record_count']}` fts: `{first_snapshot['fts_count']}` embeddings: `{first_snapshot['embedding_count']}`",
        f"- second records: `{second_snapshot['record_count']}` fts: `{second_snapshot['fts_count']}` embeddings: `{second_snapshot['embedding_count']}`",
        f"- orphan_counts: `{second_snapshot['orphan_counts']}`",
        f"- deleted_path_presence: `{second_snapshot['deleted_path_presence']}`",
        "",
        "## Audit",
        "",
    ]
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
