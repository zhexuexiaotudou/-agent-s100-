#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from ai_nas_common import (
    DEFAULT_REPORT_ROOT,
    DEFAULT_SQLITE_INDEX_PATH,
    ensure_report_dir,
    safe_write_json,
    safe_write_text,
    sqlite_index_status,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only AI-NAS SQLite index status report.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--sqlite-index-path", type=Path, default=DEFAULT_SQLITE_INDEX_PATH)
    args = parser.parse_args()

    status = sqlite_index_status(args.sqlite_index_path)
    run_dir = ensure_report_dir(args.report_root, "index_status")
    json_path = run_dir / "index_status.json"
    md_path = run_dir / "index_status.md"
    safe_write_json(json_path, status)

    last_run = status.get("last_run") or {}
    queue = status.get("queue_progress") or {}
    ocr = status.get("ocr") or {}
    lines = [
        "# AI-NAS Index Status",
        "",
        f"- status: `{status.get('status')}`",
        f"- db_path: `{status.get('db_path')}`",
        f"- last_scan_started_at: `{status.get('last_scan_started_at')}`",
        f"- last_scan_finished_at: `{status.get('last_scan_finished_at')}`",
        f"- file_count: `{status.get('file_count')}`",
        f"- failed_count: `{status.get('failed_count')}`",
        f"- queue_progress: processed `{queue.get('processed')}`, max_files `{queue.get('max_files')}`, complete `{queue.get('complete')}`",
        f"- ocr_status_counts: `{ocr.get('status_counts', {})}`",
        "",
        "## Last Run",
        "",
        f"- added: `{last_run.get('added', 0)}`",
        f"- updated: `{last_run.get('updated', 0)}`",
        f"- unchanged: `{last_run.get('unchanged', 0)}`",
        f"- deleted: `{last_run.get('deleted', 0)}`",
        f"- failed: `{last_run.get('failed', 0)}`",
        "",
        "## Recent Changes",
        "",
    ]
    changes = status.get("recent_changes") or []
    if not changes:
        lines.append("- No recorded changes in the latest run.")
    for change in changes:
        lines.append(
            f"- `{change.get('action')}` `{change.get('relative_path') or change.get('path')}` "
            f"| `{change.get('reason')}` | `{change.get('created_at')}`"
        )
    lines.extend(["", "## Recent Failures", ""])
    failures = status.get("recent_failures") or []
    if not failures:
        lines.append("- No current document parse failures.")
    for failure in failures:
        lines.append(f"- `{failure.get('relative_path') or failure.get('path')}`: `{failure.get('reason')}`")
    lines.extend(["", "## OCR Results", ""])
    recent_ocr = ocr.get("recent") or []
    if not recent_ocr:
        lines.append("- No OCR extraction results recorded.")
    for item in recent_ocr:
        lines.append(
            f"- `{item.get('relative_path')}` | status `{item.get('status')}` | "
            f"engine `{item.get('engine')}` | error `{item.get('error')}`"
        )
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
