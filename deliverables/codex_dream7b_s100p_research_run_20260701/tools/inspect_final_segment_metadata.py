#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from dream7b_research_common import now_iso, sha256_file, write_json, write_text
from run_s100p_hbm_chain_dump_logits import hbm_path, model_name, quant_metadata


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect seq128 final segment HBM metadata.")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--hbm-root", default="/mnt/nas/openclaw/models/dream7b-hbm/seq128-b1-lmheadq16-lasttoken")
    parser.add_argument("--seq-len", type=int, default=128)
    parser.add_argument("--w-bits", type=int, default=8)
    parser.add_argument("--lm-head-w-bits", type=int, default=16)
    parser.add_argument("--final-logits-mode", default="last-token")
    args = parser.parse_args()
    args.layer_count = 28
    path = hbm_path(args, 27)
    name = model_name(args, 27)
    from hbm_runtime import HB_HBMRuntime

    runtime = None
    load_error = None
    try:
        runtime = HB_HBMRuntime(str(path))
    except Exception as exc:  # pragma: no cover - depends on S100P runtime state.
        load_error = repr(exc)
    payload = {
        "created_at": now_iso(),
        "segment": "27:28",
        "hbm_path": str(path),
        "hbm_exists": path.is_file(),
        "hbm_size_bytes": path.stat().st_size if path.is_file() else None,
        "hbm_sha256": sha256_file(path) if path.is_file() else None,
        "model_name_expected": name,
        "model_names": list(getattr(runtime, "model_names", [])) if runtime is not None else [],
        "output_quant_metadata": quant_metadata(runtime, name) if runtime is not None else {},
        "declared_output_shape": [1, 152064],
        "lm_head_weight_bits": args.lm_head_w_bits,
        "vocab_size": 152064,
        "runtime_load_error": load_error,
        "verdict": (
            "ok_final_segment_metadata"
            if runtime is not None and path.is_file() and name in list(getattr(runtime, "model_names", []))
            else "blocked_final_segment_metadata_runtime_load_error"
        ),
    }
    write_json(Path(args.output_json), payload)
    write_text(Path(args.output_md), "# Final Segment Metadata\n\n" + "\n".join(f"- {k}: `{v}`" for k, v in payload.items() if k != "output_quant_metadata") + "\n")
    print(args.output_json)
    return 0 if payload["verdict"].startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
