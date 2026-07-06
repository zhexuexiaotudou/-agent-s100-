#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset only the generated Personal DemoCorpus tree.")
    parser.add_argument("--personal-root", type=Path, default=Path("/mnt/nas/openclaw/Personal"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    target = args.personal_root / "DemoCorpus"
    payload = {"ok": True, "dry_run": not args.apply, "target": str(target), "removed": False, "personal_root_removed": False}
    if args.apply and target.exists():
        shutil.rmtree(target)
        payload["removed"] = True
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

