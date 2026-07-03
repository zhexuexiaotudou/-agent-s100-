#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from dream7b_research_common import host_metadata, iter_jsonl, now_iso, sha256_file, write_json, write_text


def main() -> int:
    parser = argparse.ArgumentParser(description="Export BF16/PyTorch Dream7B last-token logits when checkpoint and dependencies are available.")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--model-path", default="")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    out_root = Path(args.output_root)
    out_root.mkdir(parents=True, exist_ok=True)
    cases = list(iter_jsonl(Path(args.cases)))
    blockers = []
    if not args.model_path:
        blockers.append("bf16_model_path_not_provided")
    elif not Path(args.model_path).exists():
        blockers.append(f"bf16_model_path_missing:{args.model_path}")
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except Exception as exc:
        blockers.append(f"bf16_dependency_unavailable:{type(exc).__name__}:{exc}")
    # The actual Dream diffusion forward wrapper is intentionally not guessed here.
    blockers.append("dream_bf16_forward_wrapper_not_verified")
    payload = {
        "created_at": now_iso(),
        "reference_type": "bf16_pytorch",
        "host": host_metadata(),
        "model_path": args.model_path,
        "model_sha256": sha256_file(Path(args.model_path)) if args.model_path and Path(args.model_path).is_file() else None,
        "device": args.device,
        "case_count": len(cases),
        "cases": [{"case_id": case["case_id"], "expected_seq_len": case.get("expected_seq_len"), "last_token_index": case.get("expected_last_token_index")} for case in cases],
        "verdict": "blocked_bf16_reference_export",
        "blockers": blockers,
        "boundary": "No BF16 logits are emitted unless a verified Dream7B PyTorch forward wrapper and checkpoint path are provided.",
    }
    write_json(out_root / "bf16_reference_export.json", payload)
    write_text(
        out_root / "bf16_reference_export.md",
        "# BF16 Reference Export\n\n"
        f"- verdict: `{payload['verdict']}`\n"
        f"- case_count: `{len(cases)}`\n\n"
        "## Blockers\n\n"
        + "\n".join(f"- `{item}`" for item in blockers)
        + "\n",
    )
    print(out_root / "bf16_reference_export.json")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

