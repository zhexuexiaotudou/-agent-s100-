#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from dream7b_research_common import default_probe_cases, write_jsonl


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Dream7B seq128 probe case JSONL files.")
    parser.add_argument("--run-root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    root = Path(args.run_root)
    cases = default_probe_cases()
    minimal = [case for case in cases if case["case_id"] in {"zeros", "ramp", "single_token_repeat", "alternating_tokens", "real_prompt_padded", "real_prompt_mask_tail"}]
    battery_ids = {
        "zeros",
        "ramp",
        "repeated_frequent_token",
        "repeated_rare_token",
        "alternating_two_tokens",
        "short_english_prompt_padded",
        "short_chinese_prompt_padded",
        "openclaw_style_prompt_padded",
        "exactly_128_token_synthetic_prompt",
        "prompt_with_mask_tail",
    }
    battery = [case for case in cases if case["case_id"] in battery_ids]
    write_jsonl(root / "cases" / "seq128_probe_cases.jsonl", minimal)
    write_jsonl(root / "cases" / "seq128_logits_probe_battery.jsonl", battery)
    print(root / "cases" / "seq128_probe_cases.jsonl")
    print(root / "cases" / "seq128_logits_probe_battery.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

