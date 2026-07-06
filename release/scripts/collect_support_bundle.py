#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import time
import zipfile
from pathlib import Path


INCLUDE_GLOBS = [
    "reports/stage10_*.json",
    "reports/stage10_*.md",
    "reports/product_delivery/*/product_smoke_test.json",
    "reports/product_delivery/*/product_smoke_test.md",
    "demo_corpus/manifests/*.jsonl",
    "demo_corpus/licenses/*.md",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect a redacted support bundle for Digua AI-NAS release debugging.")
    parser.add_argument("--out", type=Path, default=Path(f"support_bundle_{time.strftime('%Y%m%d-%H%M%S')}.zip"))
    args = parser.parse_args()
    files: list[Path] = []
    for pattern in INCLUDE_GLOBS:
        files.extend(Path(".").glob(pattern))
    with zipfile.ZipFile(args.out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(set(files)):
            if path.is_file():
                zf.write(path, path.as_posix())
    digest = hashlib.sha256(args.out.read_bytes()).hexdigest()
    args.out.with_suffix(args.out.suffix + ".sha256").write_text(f"{digest}  {args.out.name}\n", encoding="utf-8")
    print(args.out)
    print(digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

