#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from dream7b_research_common import iter_jsonl, now_iso, write_json, write_text


def main() -> int:
    parser = argparse.ArgumentParser(description="BF16 boundary exporter placeholder with explicit blockers.")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--model-path", default="")
    args = parser.parse_args()
    cases = list(iter_jsonl(Path(args.cases)))
    blockers = []
    if not args.model_path:
        blockers.append("bf16_model_path_not_provided")
    else:
        blockers.append("dream_layer_to_hbm_segment_mapping_not_verified")
    blockers.append("bf16_boundary_export_not_run")
    payload = {"created_at": now_iso(), "verdict": "blocked_bf16_boundary_export", "case_count": len(cases), "blockers": blockers, "cases": [{"case_id": c["case_id"]} for c in cases]}
    write_json(Path(args.output_json), payload)
    write_text(Path(args.output_md), "# BF16 Boundary Export\n\n" + "\n".join(f"- `{b}`" for b in blockers) + "\n")
    print(args.output_json)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

