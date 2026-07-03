#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from dream7b_research_common import now_iso, write_json, write_text


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory raw evidence files with size and sha256.")
    parser.add_argument("--root", default="evidence")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--hash", action="store_true")
    args = parser.parse_args()
    root = Path(args.root)
    rows = []
    total = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        stat = path.stat()
        total += stat.st_size
        row = {
            "relative_path": path.relative_to(root.parent).as_posix(),
            "size_bytes": stat.st_size,
            "sha256": sha256_file(path) if args.hash else None,
        }
        rows.append(row)
    payload = {
        "created_at": now_iso(),
        "root": str(root),
        "file_count": len(rows),
        "total_size_bytes": total,
        "sha256_computed": bool(args.hash),
        "files": rows,
    }
    write_json(Path(args.output_json), payload)
    lines = [
        "# Raw Evidence Inventory",
        "",
        f"- file_count: `{payload['file_count']}`",
        f"- total_size_bytes: `{payload['total_size_bytes']}`",
        f"- sha256_computed: `{payload['sha256_computed']}`",
        "",
        "| file | size_bytes | sha256 |",
        "| --- | ---: | --- |",
    ]
    for row in rows:
        lines.append(f"| `{row['relative_path']}` | {row['size_bytes']} | `{row['sha256']}` |")
    write_text(Path(args.output_md), "\n".join(lines) + "\n")
    print(args.output_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
