#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
import time
from pathlib import Path
import shutil

from ai_nas_common import (
    DEFAULT_REPORT_ROOT,
    build_sqlite_inventory,
    ensure_report_dir,
    iso_now,
    open_sqlite_connection,
    safe_write_json,
    safe_write_text,
    sqlite_index_status,
)


TOOL_ID = "ai_nas_index_rename_detection"


def prepare_fixture(root: Path) -> Path:
    if root.exists():
        shutil.rmtree(root)
    personal = root / "Personal"
    docs = personal / "Documents"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "2024-renovation-contract-draft.txt").write_text(
        "Renovation contract 2024. Deposit 20000 CNY on 2024-03-01. Final 8000 CNY on 2024-05-20.\n",
        encoding="utf-8",
    )
    return personal


def record_for_path(db_path: Path, path: Path) -> dict | None:
    con = open_sqlite_connection(db_path, row_factory=True)
    try:
        row = con.execute("SELECT * FROM records WHERE path = ?", (str(path),)).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def latest_change(db_path: Path, relative_path: str, action: str) -> dict | None:
    con = open_sqlite_connection(db_path, row_factory=True)
    try:
        row = con.execute(
            """
            SELECT id, run_id, action, path, relative_path, reason, created_at
            FROM change_log
            WHERE relative_path = ? AND action = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (relative_path, action),
        ).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 4)
    rank = (len(ordered) - 1) * pct
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 4)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded AI-NAS rename/move detection acceptance over an isolated Personal fixture.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--fixture-root", type=Path, default=None)
    parser.add_argument("--max-files", type=int, default=5000)
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "index_rename_detection")
    fixture_root = args.fixture_root or (run_dir / "fixture")
    personal_root = prepare_fixture(fixture_root)
    db_path = run_dir / "index_rename_detection.sqlite3"
    old_rel = "Documents/2024-renovation-contract-draft.txt"
    new_rel = "Documents/Contracts/2024-renovation-contract-final.txt"
    old_path = personal_root / old_rel
    new_path = personal_root / new_rel

    baseline_started = time.perf_counter()
    baseline_status = build_sqlite_inventory(personal_root, db_path, max_files=args.max_files)
    baseline_ms = (time.perf_counter() - baseline_started) * 1000
    old_record = record_for_path(db_path, old_path)

    new_path.parent.mkdir(parents=True, exist_ok=True)
    rename_started = time.perf_counter()
    old_path.rename(new_path)
    # Give filesystems with coarse timestamp behavior a chance to publish the path change.
    time.sleep(0.05)
    scan_status = build_sqlite_inventory(personal_root, db_path, max_files=args.max_files)
    detection_ms = (time.perf_counter() - rename_started) * 1000

    new_record = record_for_path(db_path, new_path)
    old_deleted = latest_change(db_path, old_rel, "deleted")
    new_added = latest_change(db_path, new_rel, "added")
    same_sha = bool(old_record and new_record and old_record.get("sha256") == new_record.get("sha256"))
    rename_candidate = {
        "old_relative_path": old_rel,
        "new_relative_path": new_rel,
        "old_sha256": old_record.get("sha256") if old_record else None,
        "new_sha256": new_record.get("sha256") if new_record else None,
        "same_sha256": same_sha,
        "old_deleted_change_log": old_deleted,
        "new_added_change_log": new_added,
        "inferred_action": "rename_or_move" if same_sha and old_deleted and new_added else None,
        "confidence": 0.99 if same_sha and old_deleted and new_added else 0.0,
        "reason": "same SHA256 observed at a new relative path while old path is deleted and new path is added in the same incremental scan window",
    }
    failures = []
    if not old_record:
        failures.append("baseline_old_record_missing")
    if not new_record:
        failures.append("new_record_missing_after_rename")
    if not old_deleted:
        failures.append("old_path_deleted_change_missing")
    if not new_added:
        failures.append("new_path_added_change_missing")
    if not same_sha:
        failures.append("rename_candidate_sha_mismatch")

    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_index_rename_detection" if not failures else "failed_ai_nas_index_rename_detection",
        "scope": "bounded rename/move inference over isolated SQLite/FTS Personal fixture",
        "personal_root": str(personal_root),
        "sqlite_index_path": str(db_path),
        "baseline_cycle": {
            "elapsed_ms": round(baseline_ms, 3),
            "status": baseline_status.get("status"),
            "file_count": baseline_status.get("file_count"),
            "last_run": baseline_status.get("last_run"),
        },
        "rename_event": {
            "old_relative_path": old_rel,
            "new_relative_path": new_rel,
            "detection_latency_ms": round(detection_ms, 3),
            "scan_status": {
                "status": scan_status.get("status"),
                "file_count": scan_status.get("file_count"),
                "last_run": scan_status.get("last_run"),
            },
            "candidate": rename_candidate,
        },
        "summary": {
            "rename_candidate_detected": bool(rename_candidate["inferred_action"]),
            "same_sha256": same_sha,
            "old_deleted_detected": bool(old_deleted),
            "new_added_detected": bool(new_added),
            "detection_latency_ms": {
                "p50": percentile([detection_ms], 0.50),
                "p95": percentile([detection_ms], 0.95),
                "p99": percentile([detection_ms], 0.99),
                "max": round(detection_ms, 3),
            },
            "failures": failures,
        },
        "final_index_status": sqlite_index_status(db_path),
        "audit": {
            "real_personal_source_modified": False,
            "fixture_files_created": True,
            "fixture_file_renamed": True,
            "rename_performed_on_real_personal": False,
            "delete_performed_on_real_personal": False,
            "move_performed_on_real_personal": False,
            "overwrite_performed_on_real_personal": False,
            "service_installed": False,
            "service_started": False,
            "writes": "isolated fixture files plus SQLite/FTS index and Markdown/JSON rename detection reports",
        },
        "production_gap": "This proves rename/move inference from add/delete change_log pairs and SHA256 in a bounded fixture; production still needs resident NAS-backed rename telemetry.",
    }
    json_path = run_dir / "index_rename_detection.json"
    md_path = run_dir / "index_rename_detection.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Index Rename Detection",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- old_relative_path: `{old_rel}`",
        f"- new_relative_path: `{new_rel}`",
        f"- rename_candidate_detected: `{payload['summary']['rename_candidate_detected']}`",
        f"- same_sha256: `{same_sha}`",
        f"- detection_p95_ms: `{payload['summary']['detection_latency_ms']['p95']}`",
        f"- failures: `{failures}`",
        "- policy: isolated fixture only; no real Personal rename, move, delete, overwrite, service install, or service start",
        "",
        "## Candidate",
        "",
        f"- inferred_action: `{rename_candidate['inferred_action']}`",
        f"- confidence: `{rename_candidate['confidence']}`",
        f"- reason: {rename_candidate['reason']}",
        "",
        "## Change Log Evidence",
        "",
        f"- old_deleted_change_log: `{old_deleted}`",
        f"- new_added_change_log: `{new_added}`",
        "",
        "## Audit",
        "",
    ]
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Production Gap", "", f"- {payload['production_gap']}"])
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
