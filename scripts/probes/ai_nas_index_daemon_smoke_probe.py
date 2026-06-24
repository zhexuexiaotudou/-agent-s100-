#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sqlite3
import time
from pathlib import Path

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


TOOL_ID = "ai_nas_index_daemon_smoke"


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


def prepare_fixture(root: Path) -> dict:
    personal = root / "Personal"
    if root.exists():
        shutil.rmtree(root)
    (personal / "Documents").mkdir(parents=True, exist_ok=True)
    (personal / "Photos").mkdir(parents=True, exist_ok=True)
    baseline = personal / "Documents" / "2024-renovation-contract.txt"
    baseline.write_text(
        "2024 renovation contract\nPayment node: deposit 20000 CNY on 2024-03-01.\n",
        encoding="utf-8",
    )
    return {
        "fixture_root": str(root),
        "personal_root": str(personal),
        "baseline_file": str(baseline),
    }


def latest_change_for(db_path: Path, relative_path: str, action: str) -> dict | None:
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


def scan_cycle(personal_root: Path, db_path: Path, max_files: int = 5000) -> dict:
    started = time.perf_counter()
    status = build_sqlite_inventory(personal_root, db_path, max_files=max_files)
    elapsed_ms = (time.perf_counter() - started) * 1000
    last_run = status.get("last_run") or {}
    return {
        "run_id": status.get("run_id"),
        "elapsed_ms": round(elapsed_ms, 3),
        "status": status.get("status"),
        "file_count": status.get("file_count"),
        "failed_count": status.get("failed_count"),
        "queue_progress": status.get("queue_progress"),
        "last_run": {
            "added": last_run.get("added", 0),
            "updated": last_run.get("updated", 0),
            "unchanged": last_run.get("unchanged", 0),
            "deleted": last_run.get("deleted", 0),
            "failed": last_run.get("failed", 0),
        },
    }


def mutate_and_scan(
    personal_root: Path,
    db_path: Path,
    action: str,
    relative_path: str,
    content: str | None,
) -> dict:
    target = personal_root / relative_path
    before = time.perf_counter()
    if action in {"added", "updated"}:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content or "", encoding="utf-8")
    elif action == "deleted":
        if target.exists():
            target.unlink()
    else:
        raise ValueError(f"unsupported_action:{action}")
    # Give filesystems with coarse timestamp behavior a chance to publish mtime.
    time.sleep(0.05)
    cycle = scan_cycle(personal_root, db_path)
    latency_ms = (time.perf_counter() - before) * 1000
    change = latest_change_for(db_path, relative_path.replace("\\", "/"), action)
    return {
        "action": action,
        "relative_path": relative_path.replace("\\", "/"),
        "detected": bool(change),
        "detection_latency_ms": round(latency_ms, 3),
        "cycle": cycle,
        "change_log": change,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded AI-NAS index daemon smoke test over an isolated Personal fixture.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--fixture-root", type=Path, default=None)
    parser.add_argument("--max-files", type=int, default=5000)
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "index_daemon_smoke")
    fixture_root = args.fixture_root or (run_dir / "fixture")
    fixture = prepare_fixture(fixture_root)
    personal_root = Path(fixture["personal_root"])
    db_path = run_dir / "index_daemon_smoke.sqlite3"

    baseline = scan_cycle(personal_root, db_path, max_files=args.max_files)
    events = [
        mutate_and_scan(
            personal_root,
            db_path,
            "added",
            "Documents/2024-renovation-invoice.txt",
            "Invoice for 2024 renovation payment. Amount: 12000 CNY. Date: 2024-04-15.\n",
        ),
        mutate_and_scan(
            personal_root,
            db_path,
            "updated",
            "Documents/2024-renovation-contract.txt",
            "2024 renovation contract revised\nPayment node: deposit 20000 CNY on 2024-03-01. Final 8000 CNY on 2024-05-20.\n",
        ),
        mutate_and_scan(
            personal_root,
            db_path,
            "deleted",
            "Documents/2024-renovation-invoice.txt",
            None,
        ),
    ]
    final_status = sqlite_index_status(db_path)
    latencies = [event["detection_latency_ms"] for event in events if event["detected"]]
    all_detected = all(event["detected"] for event in events)
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_index_daemon_smoke" if all_detected else "failed_ai_nas_index_daemon_smoke",
        "scope": "bounded short-lived polling-daemon smoke over isolated fixture Personal root",
        "fixture": fixture,
        "sqlite_index_path": str(db_path),
        "baseline_cycle": baseline,
        "events": events,
        "final_index_status": final_status,
        "summary": {
            "event_count": len(events),
            "detected_count": sum(1 for event in events if event["detected"]),
            "failed_detection_count": sum(1 for event in events if not event["detected"]),
            "detection_latency_ms": {
                "p50": percentile(latencies, 0.50),
                "p95": percentile(latencies, 0.95),
                "p99": percentile(latencies, 0.99),
                "max": round(max(latencies), 3) if latencies else None,
            },
            "queue_progress": final_status.get("queue_progress"),
        },
        "audit": {
            "real_personal_source_modified": False,
            "fixture_files_created": True,
            "fixture_file_deleted": True,
            "delete_performed_on_real_personal": False,
            "move_performed": False,
            "overwrite_performed_on_real_personal": False,
            "service_installed": False,
            "service_started": False,
            "writes": "isolated fixture files plus SQLite/FTS index and Markdown/JSON smoke reports",
        },
        "production_gap": "This proves the incremental scan/change-log contract in a bounded polling smoke; a true resident daemon still needs installation and long-running NAS-backed validation.",
    }

    json_path = run_dir / "index_daemon_smoke.json"
    md_path = run_dir / "index_daemon_smoke.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Index Daemon Smoke",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- sqlite_index_path: `{db_path}`",
        f"- detected_count: `{payload['summary']['detected_count']}` / `{payload['summary']['event_count']}`",
        f"- detection_p95_ms: `{payload['summary']['detection_latency_ms']['p95']}`",
        f"- detection_p99_ms: `{payload['summary']['detection_latency_ms']['p99']}`",
        "- policy: isolated fixture only; no real Personal source delete, move, overwrite, service install, or service start",
        "",
        "## Events",
        "",
    ]
    for event in events:
        lines.append(
            f"- `{event['action']}` `{event['relative_path']}` detected `{event['detected']}` "
            f"latency_ms `{event['detection_latency_ms']}` run_id `{event['cycle'].get('run_id')}`"
        )
        if event["change_log"]:
            lines.append(f"  - change_log_id: `{event['change_log']['id']}` reason `{event['change_log']['reason']}`")
    lines.extend(["", "## Queue Progress", ""])
    queue = payload["summary"]["queue_progress"] or {}
    lines.append(f"- processed: `{queue.get('processed')}`")
    lines.append(f"- max_files: `{queue.get('max_files')}`")
    lines.append(f"- complete: `{queue.get('complete')}`")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Production Gap", "", f"- {payload['production_gap']}"])
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0 if all_detected else 1


if __name__ == "__main__":
    raise SystemExit(main())
