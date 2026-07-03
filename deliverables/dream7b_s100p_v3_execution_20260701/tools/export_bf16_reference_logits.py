#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from common_artifact_utils import sha256_file, utc_now_iso, write_json


def file_manifest(root: Path, limit: int = 200) -> list[dict[str, object]]:
    if not root.exists():
        return []
    if root.is_file():
        return [{"path": str(root), "size_bytes": root.stat().st_size, "sha256": sha256_file(root)}]
    rows = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rows.append({"path": str(p), "size_bytes": p.stat().st_size, "sha256": sha256_file(p) if p.stat().st_size < 1024 * 1024 * 256 else "skipped_large_file"})
        if len(rows) >= limit:
            rows.append({"path": "...", "note": f"truncated at {limit} files"})
            break
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Report BF16/PyTorch Dream7B reference status.")
    parser.add_argument("--cases-jsonl", default="")
    parser.add_argument("--checkpoint-path", default="/mnt/nas/openclaw/models/dream7b")
    parser.add_argument("--output-json", default="reports/140_bf16_reference_status.json")
    parser.add_argument("--output-md", default="reports/140_bf16_reference_status.md")
    args = parser.parse_args()
    ckpt = Path(args.checkpoint_path)
    import_checks = {}
    for module in ["torch", "transformers"]:
        try:
            mod = __import__(module)
            import_checks[module] = {"available": True, "version": getattr(mod, "__version__", None)}
        except Exception as exc:
            import_checks[module] = {"available": False, "exception": f"{type(exc).__name__}:{exc}"}
    candidate_files = []
    if ckpt.exists():
        if ckpt.is_dir():
            for pattern in ["*.safetensors", "*.bin", "config.json", "tokenizer*", "*.json"]:
                candidate_files.extend(str(p) for p in ckpt.glob(pattern))
        else:
            candidate_files.append(str(ckpt))
    reason_parts = []
    if not ckpt.exists():
        reason_parts.append("checkpoint_path_not_found")
    if not import_checks.get("torch", {}).get("available"):
        reason_parts.append("torch_unavailable")
    if not import_checks.get("transformers", {}).get("available"):
        reason_parts.append("transformers_unavailable")
    reason_parts.append("verified_dream7b_diffusion_forward_wrapper_not_available")
    payload = {
        "schema_version": "dream7b_bf16_reference_status_v3",
        "created_at_utc": utc_now_iso(),
        "bf16_reference_status": "unavailable",
        "reason": ";".join(reason_parts),
        "no_bf16_ground_truth_claims_allowed": True,
        "python": sys.version,
        "cwd": os.getcwd(),
        "cases_jsonl": args.cases_jsonl,
        "checkpoint_path": str(ckpt),
        "checkpoint_exists": ckpt.exists(),
        "checkpoint_is_dir": ckpt.is_dir() if ckpt.exists() else False,
        "checkpoint_manifest": file_manifest(ckpt, limit=50) if ckpt.exists() else [],
        "candidate_model_files": candidate_files[:50],
        "dependency_imports": import_checks,
        "wrapper_limitations": [
            "No verified Dream7B diffusion PyTorch forward wrapper is available in this run.",
            "Generic AutoModelForCausalLM loading is not accepted as ground truth for Dream7B diffusion semantics.",
            "No BF16 logits or boundary activations were exported.",
        ],
    }
    write_json(Path(args.output_json), payload)
    Path(args.output_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_md).write_text(
        "# BF16 Reference Status V3\n\n"
        f"- bf16_reference_status: `{payload['bf16_reference_status']}`\n"
        f"- reason: `{payload['reason']}`\n"
        f"- checkpoint_exists: `{payload['checkpoint_exists']}`\n"
        "- no BF16 ground-truth failure claims are allowed.\n",
        encoding="utf-8",
    )
    print(args.output_json)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
