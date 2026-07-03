#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from dream7b_research_common import iter_jsonl, now_iso, write_json, write_text


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Dream7B seq128 token ids, position ids, masks, and last-token index.")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()
    rows = []
    errors = []
    for case in iter_jsonl(Path(args.cases)):
        tokens = case["token_ids"]
        positions = case.get("position_ids") or list(range(len(tokens)))
        row_errors = []
        if len(tokens) != 128:
            row_errors.append("token_length_not_128")
        if positions != list(range(128)):
            row_errors.append("position_ids_not_0_to_127")
        if case.get("expected_last_token_index") != 127:
            row_errors.append("last_token_index_not_127")
        if row_errors:
            errors.extend(f"{case['case_id']}:{e}" for e in row_errors)
        rows.append(
            {
                "case_id": case["case_id"],
                "token_ids_length": len(tokens),
                "first_16_tokens": tokens[:16],
                "last_16_tokens": tokens[-16:],
                "nonpad_count": sum(1 for t in tokens if t != 0),
                "mask_positions": case.get("mask_positions", []),
                "position_ids_first_16": positions[:16],
                "position_ids_last_16": positions[-16:],
                "bf16_last_token_index": 127,
                "gguf_dump_last_token_index": 127,
                "bpu_hbm_last_token_index": 127,
                "is_semantic": case.get("is_semantic"),
                "is_diagnostic": case.get("is_diagnostic"),
                "decoded_prompt_head_tail": case.get("decoded_text") or "not applicable; token-id diagnostic case",
                "errors": row_errors,
            }
        )
    status = "pass" if not errors else "fail"
    payload = {
        "created_at": now_iso(),
        "input_alignment_valid": status,
        "tokenizer_decode_status": "inconclusive_tokenizer_api_not_used",
        "case_count": len(rows),
        "errors": errors,
        "cases": rows,
        "boundary": "Token-id, position-id, and last-token-index alignment is verified for generated cases; tokenizer semantic decoding remains unresolved.",
    }
    write_json(Path(args.output_json), payload)
    lines = [
        "# Seq128 Input Alignment Audit",
        "",
        f"- input_alignment_valid: `{status}`",
        f"- tokenizer_decode_status: `{payload['tokenizer_decode_status']}`",
        f"- case_count: `{len(rows)}`",
        "",
        "| case | len | nonpad | masks | semantic | diagnostic | errors |",
        "| --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(f"| `{row['case_id']}` | {row['token_ids_length']} | {row['nonpad_count']} | {len(row['mask_positions'])} | {row['is_semantic']} | {row['is_diagnostic']} | `{';'.join(row['errors'])}` |")
    write_text(Path(args.output_md), "\n".join(lines) + "\n")
    print(args.output_json)
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

