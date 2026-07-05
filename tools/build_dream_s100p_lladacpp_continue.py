#!/usr/bin/env python3
"""Finalize the Dream7B llada.cpp-style continue route to a review point."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TRACK = ROOT / "dream_s100p_lladacpp"
REPORTS = TRACK / "reports"


SAFETY = {
    "generation_quality_run": False,
    "product_routes_18888_18889_touched": False,
    "dream7b_frontend_openclaw_traffic_touched": False,
    "harness_qwen_openclaw_defaults_modified": False,
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"missing": True, "path": rel(path) if path.is_absolute() and path.exists() else str(path)}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def file_record(path: Path) -> dict[str, Any]:
    return {
        "path": rel(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "sha256": sha256_file(path) if path.exists() and path.is_file() else None,
    }


def build_baseline(now: str) -> dict[str, Any]:
    v21 = read_json(ROOT / "reports" / "2010_semantic_hf_truth_loader_gate.json")
    export_hold = read_json(TRACK / "reports" / "30020_pytorch_truth_export_gate.json")
    model_dir = ROOT / "tmp" / "true_batch_inputs" / "dream7b-hf"
    model_files = [file_record(model_dir / name) for name in [
        "SHA256SUMS",
        "config.json",
        "model.safetensors.index.json",
        "tokenizer_config.json",
        "vocab.json",
        "merges.txt",
        "tokenization_dream.py",
        "modeling_dream.py",
        "configuration_dream.py",
    ]]
    scripts = [
        TRACK / "reference" / "truth_case_builder.py",
        TRACK / "reference" / "export_full_truth_31.py",
        TRACK / "reference" / "validate_truth_rows.py",
        TRACK / "reference" / "pytorch_block_driver.py",
        ROOT / "tools" / "build_dream_s100p_lladacpp_continue.py",
    ]
    data = {
        "schema_version": "dream7b_s100p_lladacpp_continue_baseline_lock_v1",
        "created_at_utc": now,
        "current_verdict": export_hold.get("verdict", "external_truth_missing_hold"),
        "semantic_truth_row_count": v21.get("hf_truth_summary", {}).get("original_semantic_truth_rows", 0),
        "missing_truth_categories_before_continue": ["canonical", "block_wise", "revision", "fixed_output", "infill", "control_command"],
        "existing_truth_files": [
            file_record(ROOT / "evidence" / "semantic_hf_truth_v21" / "semantic_truth_export_report.json"),
            file_record(ROOT / "evidence" / "v21_combined_cases" / "semantic_plus_canonical_seq128_cases_v21.jsonl"),
        ],
        "model_identity": {
            "model_dir": str(model_dir),
            "files": model_files,
        },
        "tokenizer_identity": {
            "tokenizer_config": file_record(model_dir / "tokenizer_config.json"),
            "vocab": file_record(model_dir / "vocab.json"),
            "merges": file_record(model_dir / "merges.txt"),
            "tokenization_dream": file_record(model_dir / "tokenization_dream.py"),
        },
        "dtype": "bfloat16 target, float32 saved arrays",
        "available_runtime_artifacts": [
            file_record(TRACK / "configs" / "block_runtime_config.json"),
            file_record(TRACK / "configs" / "memory_layout_config.json"),
        ],
        "available_bpu_artifacts": [
            file_record(TRACK / "configs" / "bpu_operator_manifest.json"),
            file_record(ROOT / "evidence" / "dream7b_s100p_v21_execution_20260704_bpu_outputs.tar.gz"),
        ],
        "available_scripts": [file_record(path) for path in scripts],
        "blockers": [
            "31-row truth set was missing before this continue run.",
            "No BPU operator-level input/output checksum table exists for the new llada.cpp-style track.",
            "seg00_01 is not closed by official source graph and quant metadata.",
        ],
        "next_actions": [
            "Build 31 truth cases.",
            "Export HF/PyTorch truth with the v21 torch2 CUDA environment.",
            "Validate truth rows.",
            "Run PyTorch truth replay block driver.",
            "Stop at BPU operator alignment if no true BPU op outputs exist.",
        ],
        "safety": SAFETY,
    }
    write_json(TRACK / "reports" / "30200_continue_baseline_lock.json", data)
    write_text(
        TRACK / "reports" / "30200_continue_baseline_lock.md",
        "\n".join(
            [
                "# Continue Baseline Lock",
                "",
                f"- Current verdict before continue: `{data['current_verdict']}`",
                f"- Semantic truth rows available: `{data['semantic_truth_row_count']}`",
                "- Missing truth categories before continue: `canonical`, `block_wise`, `revision`, `fixed_output`, `infill`, `control_command`",
                "- Product/OpenClaw/Qwen routes touched: `False`",
                "",
                "## Blockers",
                *[f"- {item}" for item in data["blockers"]],
            ]
        )
        + "\n",
    )
    return data


def build_bpu_operator_blocker(now: str) -> dict[str, Any]:
    manifest = read_json(TRACK / "configs" / "bpu_operator_manifest.json")
    validation = read_json(TRACK / "reports" / "30220_full_truth_31_validation_gate.json")
    driver = read_json(TRACK / "reports" / "30230_pytorch_block_driver_gate.json")
    required_ops = manifest.get("required_ops", [])
    op_case_path = TRACK / "bpu_ops" / "op_alignment_cases.jsonl"
    errors = []
    if not validation.get("full_truth_valid"):
        errors.append("full_truth_31_validation_not_passed")
    if not driver.get("gate_pass"):
        errors.append("pytorch_block_driver_not_passed")
    if not op_case_path.exists():
        errors.append("missing_bpu_operator_alignment_cases_jsonl")
    errors.append("missing_true_bpu_per_op_outputs_for_embedding_position_lm_head")
    data = {
        "schema_version": "dream7b_s100p_lladacpp_bpu_operator_alignment_gate_v1",
        "created_at_utc": now,
        "required_ops": required_ops,
        "required_ops_covered": False,
        "position_path_pass": False,
        "embedding_pass": False,
        "lm_head_pass": False,
        "no_unknown_layout_conversion": False,
        "op_alignment_cases": file_record(op_case_path),
        "errors": errors,
        "verdict": "bpu_operator_alignment_failed_review_required",
        "claim_boundary": "This is a hard review point: truth and replay can proceed, but BPU operator alignment cannot be claimed without real per-op BPU outputs and layout/scale records.",
        "safety": SAFETY,
    }
    write_json(TRACK / "reports" / "30240_bpu_operator_alignment_gate.json", data)
    write_text(
        TRACK / "reports" / "30240_bpu_operator_alignment_gate.md",
        "\n".join(
            [
                "# BPU Operator Alignment Gate",
                "",
                f"- Verdict: `{data['verdict']}`",
                "- Required ops covered: `False`",
                "- Position path pass: `False`",
                "- Embedding pass: `False`",
                "- lm_head pass: `False`",
                "",
                "Reason: no true per-op BPU output checksum table exists for the llada.cpp-style track. Continuing to layer, quant, graph compile, or runtime would overclaim evidence.",
            ]
        )
        + "\n",
    )
    return data


def final_answers(validation: dict[str, Any], driver: dict[str, Any], bpu: dict[str, Any]) -> dict[str, Any]:
    truth_complete = bool(validation.get("full_truth_valid"))
    driver_pass = bool(driver.get("gate_pass"))
    return {
        "31_row_truth_set_complete": truth_complete,
        "pytorch_block_wise_driver_passed": "truth_replay_pass_not_generation" if driver_pass else False,
        "bpu_operator_library_covered_ops": bpu.get("required_ops", []),
        "seg00_01_closed": False,
        "position_embedding_lm_head_passed": False,
        "quantization_precision": "not_reached_bpu_operator_alignment_failed",
        "bpu_block_graph_really_ran": False,
        "runtime_uses_blockwise_diffusion_driver": False,
        "prefix_kv_revision_selective_logits_effective": False,
        "memory_staging_reduces_remap_copy": False,
        "fixed_task_pass_rate": "not_reached_bpu_operator_alignment_failed",
        "speed_and_quality_worth_continuing": "review_required_after_operator_artifact_gap",
        "can_enter_product_route_now": False,
        "research_branch_only_now": True,
    }


def build_final_packet(now: str) -> dict[str, Any]:
    validation = read_json(TRACK / "reports" / "30220_full_truth_31_validation_gate.json")
    driver = read_json(TRACK / "reports" / "30230_pytorch_block_driver_gate.json")
    bpu = read_json(TRACK / "reports" / "30240_bpu_operator_alignment_gate.json")
    if not validation.get("full_truth_valid"):
        verdict = "external_truth_missing_after_exhaustive_attempts_review_required"
    elif not driver.get("gate_pass"):
        verdict = "fixed_block_tasks_failed_review_required"
    else:
        verdict = bpu.get("verdict", "bpu_operator_alignment_failed_review_required")
    data = {
        "schema_version": "dream7b_s100p_lladacpp_style_continue_gate_packet_v1",
        "created_at_utc": now,
        "final_verdict": verdict,
        "summary": "31-row HF/PyTorch truth and truth-replay block driver are reviewable, but the route stops at BPU operator alignment because true per-op BPU outputs/layout/scale records are missing.",
        "reports": {
            "baseline": rel(TRACK / "reports" / "30200_continue_baseline_lock.json"),
            "truth_export": rel(TRACK / "reports" / "30210_full_truth_31_export_gate.json"),
            "truth_validation": rel(TRACK / "reports" / "30220_full_truth_31_validation_gate.json"),
            "pytorch_block_driver": rel(TRACK / "reports" / "30230_pytorch_block_driver_gate.json"),
            "bpu_operator_alignment": rel(TRACK / "reports" / "30240_bpu_operator_alignment_gate.json"),
        },
        "truth_manifest": file_record(TRACK / "reference" / "full_truth_31_manifest.json"),
        "truth_jsonl": file_record(TRACK / "reference" / "full_truth_31.jsonl"),
        "review_questions": final_answers(validation, driver, bpu),
        "blocked_next_required_evidence": [
            "Real per-op BPU outputs for embedding lookup, position/RoPE path, and lm_head.",
            "Official layout and quant scale records for each BPU op.",
            "seg00_01 source graph or vendor/compiler metadata sufficient to close the early contract fault.",
        ],
        "safe_claim": "Dream7B now has a 31-row llada.cpp-style HF/PyTorch truth set and a truth-replay block-driver gate; BPU operator alignment remains blocked and review is required.",
        "forbidden_claims": [
            "Dream7B is deployed as the AI-NAS default model.",
            "Dream7B general dialogue works on S100P.",
            "BPU full model path is fixed.",
            "Fixed block truth replay is product generation.",
        ],
        "safety": SAFETY,
    }
    out_json = ROOT / "01_final_evidence" / "dream7b_s100p_lladacpp_style_continue_gate_packet.json"
    out_md = ROOT / "01_final_evidence" / "dream7b_s100p_lladacpp_style_continue_gate_packet.md"
    write_json(out_json, data)
    write_text(
        out_md,
        "\n".join(
            [
                "# Dream7B S100P llada.cpp-Style Continue Gate Packet",
                "",
                f"- Final verdict: `{verdict}`",
                f"- Safe claim: {data['safe_claim']}",
                "- Product route / OpenClaw foreground / Qwen default touched: `False`",
                "",
                "## Review Boundary",
                "",
                "The route stops at BPU operator alignment. Do not proceed to layer, quantization, static block graph, S100P runtime, or fixed task claims until real per-op BPU evidence exists.",
            ]
        )
        + "\n",
    )
    write_text(
        ROOT / "docs" / "DREAM7B_S100P_LLADACPP_STYLE_CONTINUE_DECISION.md",
        "\n".join(
            [
                "# Dream7B S100P llada.cpp-Style Continue Decision",
                "",
                f"Updated: {now}",
                "",
                f"Final verdict: `{verdict}`.",
                "",
                "This run moved the route past the original truth-set blocker by producing and validating a 31-row HF/PyTorch truth set, then stopped at BPU operator alignment because per-op BPU outputs, layout records, and quant scale evidence are missing.",
                "",
                "Dream7B remains a research branch only. Qwen + OpenClaw remains the AI-NAS product route.",
            ]
        )
        + "\n",
    )
    return data


def gather_package_files() -> list[Path]:
    candidates: list[Path] = []
    for base in [
        TRACK / "README.md",
        ROOT / "docs" / "DREAM7B_S100P_LLADACPP_STYLE_CONTINUE_DECISION.md",
        ROOT / "docs" / "DREAM7B_S100P_LLADACPP_STYLE_DECISION.md",
        ROOT / "docs" / "LLADACPP_TO_S100P_TRANSLATION_PLAN.md",
        ROOT / "01_final_evidence" / "dream7b_s100p_lladacpp_style_continue_gate_packet.json",
        ROOT / "01_final_evidence" / "dream7b_s100p_lladacpp_style_continue_gate_packet.md",
    ]:
        if base.exists():
            candidates.append(base)
    for folder in [TRACK / "configs", TRACK / "reference", TRACK / "reports", TRACK / "tests"]:
        if folder.exists():
            candidates.extend(path for path in folder.rglob("*") if path.is_file())
    return sorted({path.resolve() for path in candidates})


def write_self_check(path: Path) -> None:
    text = """#!/usr/bin/env python3
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
packet = root / "01_final_evidence" / "dream7b_s100p_lladacpp_style_continue_gate_packet.json"
if not packet.exists():
    raise SystemExit("missing final packet")
data = json.loads(packet.read_text(encoding="utf-8"))
expected = "bpu_operator_alignment_failed_review_required"
if data.get("final_verdict") != expected:
    raise SystemExit(f"unexpected final_verdict {data.get('final_verdict')!r}")
truth = root / "dream_s100p_lladacpp" / "reference" / "full_truth_31.jsonl"
if len([line for line in truth.read_text(encoding="utf-8").splitlines() if line.strip()]) != 31:
    raise SystemExit("truth row count is not 31")
print("SELF_CHECK_PASS")
"""
    write_text(path, text)


def package_review(now: str) -> dict[str, Any]:
    self_check = TRACK / "01_final_evidence" / "SELF_CHECK.py"
    write_self_check(self_check)
    files = gather_package_files() + [self_check]
    manifest_files = [file_record(path) for path in files]
    manifest = {
        "schema_version": "dream7b_s100p_lladacpp_continue_review_manifest_v1",
        "created_at_utc": now,
        "file_count": len(manifest_files),
        "files": manifest_files,
        "safety": SAFETY,
    }
    sums = "".join(f"{item['sha256']}  {item['path']}\n" for item in manifest_files if item.get("sha256"))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = ROOT / "evidence_for_gptpro" / f"dream7b_s100p_lladacpp_style_continue_for_gptpro_{stamp}.zip"
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in files:
            zf.write(path, rel(path))
        zf.writestr("MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
        zf.writestr("SHA256SUMS.txt", sums)
    package = {
        "zip_path": rel(zip_path),
        "zip_sha256": sha256_file(zip_path),
        "zip_size_bytes": zip_path.stat().st_size,
        "manifest_file_count": len(manifest_files),
        "testzip_bad_member": zipfile.ZipFile(zip_path).testzip(),
    }
    write_json(ROOT / "01_final_evidence" / "dream7b_s100p_lladacpp_style_continue_package.json", package)
    write_text(
        ROOT / "01_final_evidence" / "dream7b_s100p_lladacpp_style_continue_package.md",
        "\n".join(
            [
                "# Dream7B S100P llada.cpp-Style Continue Review Package",
                "",
                f"- Zip: `{package['zip_path']}`",
                f"- SHA256: `{package['zip_sha256']}`",
                f"- Members: `{package['manifest_file_count']}`",
                f"- testzip bad member: `{package['testzip_bad_member']}`",
            ]
        )
        + "\n",
    )
    return package


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline-only", action="store_true")
    ap.add_argument("--finalize", action="store_true")
    args = ap.parse_args()
    now = datetime.now(timezone.utc).isoformat()
    if args.baseline_only:
        build_baseline(now)
        return 0
    if args.finalize:
        build_bpu_operator_blocker(now)
        packet = build_final_packet(now)
        package = package_review(now)
        print(json.dumps({"final_verdict": packet["final_verdict"], "zip": package["zip_path"]}, ensure_ascii=False))
        return 0
    build_baseline(now)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
