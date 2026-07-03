#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from ai_nas_common import (
    DEFAULT_INDEX_PATH,
    DEFAULT_PERSONAL_ROOT,
    DEFAULT_REPORT_ROOT,
    bootstrap_demo,
    build_inventory,
    ensure_report_dir,
    write_inventory_reports,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Personal library inventory for AI-NAS MVP.")
    parser.add_argument("--personal-root", type=Path, default=DEFAULT_PERSONAL_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--index-path", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--max-files", type=int, default=5000)
    parser.add_argument("--bootstrap-demo", action="store_true", help="Create bounded demo files if they do not already exist.")
    args = parser.parse_args()

    created = bootstrap_demo(args.personal_root) if args.bootstrap_demo else []
    payload = build_inventory(args.personal_root, max_files=args.max_files)
    payload["bootstrap_demo_created"] = created
    run_dir = ensure_report_dir(args.report_root, "personal_inventory")
    json_path, md_path = write_inventory_reports(payload, run_dir, args.index_path)
    print(md_path)
    print(json_path)
    print(args.index_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
