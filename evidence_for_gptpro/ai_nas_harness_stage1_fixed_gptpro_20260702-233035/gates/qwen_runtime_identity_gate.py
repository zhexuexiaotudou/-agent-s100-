#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from stage2_readiness_gates import qwen_runtime_identity_gate, write_numbered_report


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Qwen runtime identity gate.")
    parser.add_argument("--report-root", type=Path, default=ROOT / "reports")
    args = parser.parse_args()
    payload = qwen_runtime_identity_gate(args.report_root)
    write_numbered_report(payload, args.report_root)
    print(payload["verdict"])
    return 0 if payload["verdict"].startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
