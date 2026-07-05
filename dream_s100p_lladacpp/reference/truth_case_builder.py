#!/usr/bin/env python3
"""Build the 31-row Dream7B llada.cpp-style truth case set.

This creates case inputs only. It does not run generation, BPU code, or product
routes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SEQ_LEN = 128
REQUIRED_COUNTS = {
    "semantic_original": 8,
    "canonical": 3,
    "block_wise": 4,
    "revision": 4,
    "fixed_output": 4,
    "infill": 4,
    "control_command": 4,
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    return sha256_bytes(json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def pad(ids: list[int], seq_len: int = SEQ_LEN) -> tuple[list[int], int]:
    truncated = [int(x) for x in ids[:seq_len]]
    unpadded = len(truncated)
    return truncated + [0] * (seq_len - len(truncated)), unpadded


def tokenized_case(tokenizer: Any, case_id: str, case_type: str, prompt: str, *, block_size: int, expected_output_len: int) -> dict[str, Any]:
    ids = tokenizer.encode(prompt, add_special_tokens=True)
    token_ids, unpadded = pad(ids)
    return make_case(
        case_id=case_id,
        case_type=case_type,
        prompt=prompt,
        human_description=f"{case_type} prompt for llada.cpp-style truth export.",
        token_ids=token_ids,
        unpadded_token_count=unpadded,
        block_size=block_size,
        expected_output_len=expected_output_len,
        source="generated_by_truth_case_builder",
    )


def make_case(
    *,
    case_id: str,
    case_type: str,
    prompt: str | None,
    human_description: str,
    token_ids: list[int],
    unpadded_token_count: int,
    block_size: int,
    expected_output_len: int,
    source: str,
) -> dict[str, Any]:
    position_ids = list(range(SEQ_LEN))
    attention_mask = [1] * SEQ_LEN
    start = max(0, min(SEQ_LEN - block_size, unpadded_token_count))
    target_positions = list(range(start, min(SEQ_LEN, start + block_size)))
    diffusion_mask = [1 if idx in target_positions else 0 for idx in range(SEQ_LEN)]
    committed_token_mask = [1 if idx < start else 0 for idx in range(SEQ_LEN)]
    revision_positions = target_positions[-min(8, len(target_positions)) :] if case_type == "revision" else []
    revision_mask = [1 if idx in revision_positions else 0 for idx in range(SEQ_LEN)]
    token_ids_sha = stable_hash(token_ids)
    return {
        "schema_version": "dream7b_s100p_lladacpp_truth_case_v1",
        "case_id": case_id,
        "case_type": case_type,
        "human_description": human_description,
        "prompt": prompt,
        "seq_len": SEQ_LEN,
        "token_ids": token_ids,
        "token_ids_sha256": token_ids_sha,
        "attention_mask": attention_mask,
        "position_ids": position_ids,
        "diffusion_mask": diffusion_mask,
        "timestep_or_noise_schedule": {
            "kind": "fixed_truth_export_schedule",
            "steps": [0, 1, 2, 3],
            "note": "Used as block/revision metadata; HF logits row is last-token reference truth.",
        },
        "block_token_states": {
            "block_size": block_size,
            "target_positions": target_positions,
            "expected_output_len": expected_output_len,
            "state_policy": "prompt positions committed, target positions masked_or_revisable",
        },
        "committed_token_mask": committed_token_mask,
        "revision_mask": revision_mask,
        "last_token_index": SEQ_LEN - 1,
        "unpadded_token_count": unpadded_token_count,
        "pad_token_value_used": 0,
        "source": source,
        "case_sha256": stable_hash({"case_id": case_id, "case_type": case_type, "token_ids": token_ids}),
    }


def semantic_cases() -> list[dict[str, Any]]:
    source = ROOT / "evidence" / "x86_gpu_semantic_truth_export_bundle_v20" / "semantic_cases.jsonl"
    rows = read_jsonl(source)
    out: list[dict[str, Any]] = []
    for row in rows[:8]:
        out.append(
            make_case(
                case_id=row["case_id"],
                case_type="semantic_original",
                prompt=row.get("prompt"),
                human_description=row.get("human_description", "Original semantic prompt."),
                token_ids=[int(x) for x in row["token_ids"]],
                unpadded_token_count=int(row.get("unpadded_token_count", sum(1 for x in row["token_ids"] if int(x) != 0))),
                block_size=32,
                expected_output_len=32,
                source=str(source.relative_to(ROOT)).replace("\\", "/"),
            )
        )
    return out


def canonical_cases() -> list[dict[str, Any]]:
    source = ROOT / "evidence" / "v21_combined_cases" / "semantic_plus_canonical_seq128_cases_v21.jsonl"
    wanted = ["zeros", "ramp", "short_chinese_prompt_padded"]
    by_id = {row.get("case_id"): row for row in read_jsonl(source)}
    out: list[dict[str, Any]] = []
    for cid in wanted:
        row = by_id[cid]
        out.append(
            make_case(
                case_id=cid,
                case_type="canonical",
                prompt=row.get("prompt"),
                human_description=row.get("human_description", "Canonical seq128 diagnostic case."),
                token_ids=[int(x) for x in row["token_ids"]],
                unpadded_token_count=int(row.get("unpadded_token_count", SEQ_LEN)),
                block_size=16,
                expected_output_len=16,
                source=str(source.relative_to(ROOT)).replace("\\", "/"),
            )
        )
    return out


def generated_cases(tokenizer: Any) -> list[dict[str, Any]]:
    specs = [
        ("block_wise_command_16", "block_wise", 16, 16, "Normalize this NAS command into a fixed 16 token action: copy the latest evidence packet to the review folder."),
        ("block_wise_json_plan_32", "block_wise", 32, 32, "Write a compact JSON action plan for checking Dream7B logits evidence without touching product routes."),
        ("block_wise_summary_64", "block_wise", 64, 64, "Summarize why a logits-invalid BPU path must stay out of a product deployment, using only evidence terms."),
        ("block_wise_router_intent_32", "block_wise", 32, 32, "Classify this request as local research, product route, or forbidden route: run Dream7B as default OpenClaw model."),
        ("revision_typo_fix", "revision", 32, 32, "Revise unstable tokens in this sentence: Dream7B is nott ready for prodcut routing because logits truth is missing."),
        ("revision_json_key_repair", "revision", 32, 32, "Repair the JSON keys only: {verdit: hold, prodcut_route: locked, truh_rows: missing}."),
        ("revision_safety_boundary", "revision", 32, 32, "Rewrite the unsafe claim so it is evidence-bound: Dream7B fully replaces Qwen on S100P."),
        ("revision_chinese_boundary", "revision", 32, 32, "修正这句话的边界：Dream7B 已经可以作为 OpenClaw 默认模型。"),
        ("fixed_output_command_16", "fixed_output", 16, 16, "Return a 16-token command summary for archiving the truth export manifest."),
        ("fixed_output_json_32", "fixed_output", 32, 32, "Return exactly one short JSON object describing the next Dream7B review gate."),
        ("fixed_output_nas_intent_32", "fixed_output", 32, 32, "Return a fixed 32-token NAS tool intent classification for copying a non-sensitive report."),
        ("fixed_output_short_summary_64", "fixed_output", 64, 64, "Return a fixed 64-token summary of why fixed-block success is not general dialogue success."),
        ("infill_missing_action", "infill", 32, 32, "Fill the missing action: The operator approved copying <mask> into the review folder, but delete remains blocked."),
        ("infill_missing_verdict", "infill", 32, 32, "Complete the verdict sentence: If the 31-row truth set is missing, the only valid verdict is <mask>."),
        ("infill_policy_clause", "infill", 32, 32, "Fill the policy clause: Dream7B may not touch OpenClaw foreground until <mask> passes."),
        ("infill_chinese_boundary", "infill", 32, 32, "补全边界声明：固定 block 通过不等于 <mask>。"),
        ("control_list_reports", "control_command", 32, 32, "Control command: list Dream7B evidence reports and return only paths, not file contents."),
        ("control_copy_review_packet", "control_command", 32, 32, "Control command: copy the review packet only after policy, hash, and approval checks pass."),
        ("control_refuse_delete", "control_command", 32, 32, "Control command: refuse deleting NAS evidence because destructive actions are outside this route."),
        ("control_cloud_privacy_refusal", "control_command", 32, 32, "Control command: keep private NAS context local and refuse raw cloud egress."),
    ]
    return [
        tokenized_case(tokenizer, cid, case_type, prompt, block_size=block_size, expected_output_len=output_len)
        for cid, case_type, block_size, output_len, prompt in specs
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", default=str(ROOT / "tmp" / "true_batch_inputs" / "dream7b-hf"))
    ap.add_argument("--out", default=str(ROOT / "dream_s100p_lladacpp" / "reference" / "full_truth_31_cases.jsonl"))
    ap.add_argument("--manifest", default=str(ROOT / "dream_s100p_lladacpp" / "reference" / "full_truth_31_cases_manifest.json"))
    args = ap.parse_args()

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.model_dir, trust_remote_code=True, local_files_only=True)
    cases = semantic_cases() + canonical_cases() + generated_cases(tokenizer)
    counts: dict[str, int] = {}
    for row in cases:
        counts[row["case_type"]] = counts.get(row["case_type"], 0) + 1

    errors = []
    if len(cases) != 31:
        errors.append(f"expected 31 rows, got {len(cases)}")
    for case_type, expected in REQUIRED_COUNTS.items():
        if counts.get(case_type, 0) != expected:
            errors.append(f"{case_type}: expected {expected}, got {counts.get(case_type, 0)}")
    ids = [row["case_id"] for row in cases]
    if len(ids) != len(set(ids)):
        errors.append("duplicate case_id")
    for row in cases:
        for key in ["token_ids", "attention_mask", "position_ids", "diffusion_mask", "committed_token_mask", "revision_mask"]:
            if len(row[key]) != SEQ_LEN:
                errors.append(f"{row['case_id']} {key} length {len(row[key])} != {SEQ_LEN}")

    out_path = Path(args.out)
    manifest_path = Path(args.manifest)
    write_jsonl(out_path, cases)
    manifest = {
        "schema_version": "dream7b_s100p_lladacpp_truth_case_manifest_v1",
        "case_count": len(cases),
        "required_counts": REQUIRED_COUNTS,
        "actual_counts": counts,
        "case_ids": ids,
        "model_dir": str(Path(args.model_dir)),
        "tokenizer_class": type(tokenizer).__name__,
        "tokenizer_vocab_size": len(tokenizer),
        "cases_jsonl": str(out_path.relative_to(ROOT)).replace("\\", "/"),
        "cases_sha256": sha256_bytes(out_path.read_bytes()),
        "errors": errors,
        "status": "pass" if not errors else "fail",
        "safety": {
            "generation_quality_run": False,
            "product_routes_18888_18889_touched": False,
            "dream7b_frontend_openclaw_traffic_touched": False,
            "harness_qwen_openclaw_defaults_modified": False,
        },
    }
    write_json(manifest_path, manifest)
    print(json.dumps({"status": manifest["status"], "case_count": len(cases), "counts": counts}, ensure_ascii=False))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
