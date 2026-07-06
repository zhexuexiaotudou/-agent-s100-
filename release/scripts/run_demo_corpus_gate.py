#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build demo corpus and run Stage 10 demo corpus readiness gate.")
    parser.add_argument("--personal-root", type=Path, default=Path("/mnt/nas/openclaw/Personal"))
    parser.add_argument("--report-root", type=Path, default=Path("/mnt/nas/openclaw/reports/qwen25_ai_nas"))
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--fixture-ci", action="store_true")
    args = parser.parse_args()
    builder = [sys.executable, "demo_corpus/scripts/build_demo_corpus.py", "--personal-root", str(args.personal_root), "--report-root", str(args.report_root), "--write-to-personal"]
    if args.fixture_ci:
        builder.append("--fixture-ci")
    rc = subprocess.call(builder)
    if rc != 0:
        return rc
    return subprocess.call([sys.executable, "gates/stage10_demo_corpus_recording_readiness_gate.py", "--personal-root", str(args.personal_root), "--report-root", str(args.report_root), "--base-url", args.base_url])


if __name__ == "__main__":
    raise SystemExit(main())

