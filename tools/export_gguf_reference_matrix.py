#!/usr/bin/env python3
"""Record or run GGUF reference-matrix exports for Dream7B v5.

The current repo evidence only contains Q4_K_M logits from the prior v3/v4
tracks. This tool records unavailable F16/Q4_0 artifacts explicitly unless
paths and a supported logits exporter are supplied.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROWS = ["gguf_f16", "gguf_q4_0", "gguf_q4_k_m"]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def model_row(path_text: str) -> dict[str, Any]:
    if not path_text:
        return {"status": "unavailable", "reason": "artifact_path_not_supplied"}
    p = Path(path_text)
    row = {"path": str(p), "exists": p.exists()}
    if p.exists() and p.is_file():
        row.update({"status": "available", "size_bytes": p.stat().st_size})
        row["sha256"] = sha256_file(p) if p.stat().st_size <= 64 * 1024 * 1024 else "skipped_large_file"
    else:
        row.update({"status": "unavailable", "reason": "artifact_path_missing"})
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases-jsonl", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--gguf-f16", default="")
    ap.add_argument("--gguf-q4-0", default="")
    ap.add_argument("--gguf-q4-k-m", default="")
    args = ap.parse_args()

    rows = {
        "gguf_f16": model_row(args.gguf_f16),
        "gguf_q4_0": model_row(args.gguf_q4_0),
        "gguf_q4_k_m": model_row(args.gguf_q4_k_m),
    }
    payload = {
        "schema_version": "dream7b_gguf_reference_matrix_export_attempt_v5",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "cases_jsonl": args.cases_jsonl,
        "rows": rows,
        "status": "blocked_or_partial",
        "reason": "this tool records artifact availability; logits export requires an external Dream-compatible GGUF logits runner",
        "missing_rows": [row for row in ROWS if rows[row].get("status") != "available"],
    }
    write_json(Path(args.out_json), payload)
    print(args.out_json)
    return 0 if not payload["missing_rows"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
