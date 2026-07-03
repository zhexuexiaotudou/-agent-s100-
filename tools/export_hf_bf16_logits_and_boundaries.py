#!/usr/bin/env python3
"""Attempt to export Dream7B HF/PyTorch BF16 logits and boundaries.

This tool deliberately refuses to treat a generic causal-LM load as validated
Dream diffusion ground truth. If a verified wrapper module is not supplied, it
writes a blocked metadata report instead of fabricating BF16 logits.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def file_manifest(root: Path, limit: int = 200) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    out = []
    for p in sorted(x for x in root.rglob("*") if x.is_file()):
        if len(out) >= limit:
            out.append({"path": "...", "note": "manifest truncated"})
            break
        item: dict[str, Any] = {"path": str(p), "size_bytes": p.stat().st_size}
        if p.stat().st_size <= 64 * 1024 * 1024:
            item["sha256"] = sha256_file(p)
        else:
            item["sha256"] = "skipped_large_file"
        out.append(item)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--cases-jsonl", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--verified-wrapper", default="")
    args = ap.parse_args()

    checkpoint = Path(args.checkpoint)
    out_dir = Path(args.out_dir)
    metadata = {
        "schema_version": "dream7b_hf_bf16_export_attempt_v5",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "checkpoint_path": str(checkpoint),
        "checkpoint_exists": checkpoint.exists(),
        "checkpoint_is_dir": checkpoint.is_dir(),
        "cases_jsonl": args.cases_jsonl,
        "verified_wrapper": args.verified_wrapper or None,
        "checkpoint_manifest": file_manifest(checkpoint),
        "status": "blocked",
        "reason": "verified_dream7b_diffusion_forward_wrapper_not_supplied",
        "no_bf16_ground_truth_claims_allowed": True,
        "wrapper_limitations": [
            "Dream7B diffusion semantics require a verified forward wrapper.",
            "Generic AutoModelForCausalLM loading is not accepted as BF16 ground truth in this evidence thread.",
            "No logits or boundary activations are exported in blocked mode.",
        ],
    }
    if args.verified_wrapper and not Path(args.verified_wrapper).exists():
        metadata["reason"] = "verified_wrapper_path_missing"
    write_json(out_dir / "metadata.json", metadata)
    print(out_dir / "metadata.json")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
