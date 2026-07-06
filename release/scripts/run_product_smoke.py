#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the product smoke test from a release package.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--report-root", type=Path, default=Path("/mnt/nas/openclaw/reports/product_delivery"))
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    return subprocess.call([sys.executable, "scripts/product_smoke_test.py", "--base-url", args.base_url, "--report-root", str(args.report_root), "--timeout", str(args.timeout)])


if __name__ == "__main__":
    raise SystemExit(main())

