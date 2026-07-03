#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUN_ROOT_DEFAULT = Path("deliverables/dream7b_s100p_v3_execution_20260701")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def opt_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"_missing": True, "_path": str(path)}
    return read_json(path)


def small_stats(stats: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(stats, dict):
        return {}
    keys = [
        "shape",
        "dtype",
        "min",
        "max",
        "mean",
        "std",
        "abs_max",
        "nonzero_count",
        "constant",
        "allzero",
        "nan_count",
        "inf_count",
        "p0",
        "p1",
        "p5",
        "p50",
        "p95",
        "p99",
        "p100",
    ]
    return {k: stats.get(k) for k in keys if k in stats}


def compact_compare(compare: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(compare, dict):
        return {}
    keys = [
        "shape_match",
        "top1_agreement",
        "ref_top1",
        "candidate_top1",
        "top5_overlap_count",
        "ref_top1_in_candidate_top5",
        "cosine",
        "l2_relative_error",
        "max_abs_error",
        "mean_abs_error",
        "kl_divergence",
        "candidate_nonzero_count",
        "candidate_normalized_entropy",
        "candidate_top1_probability",
    ]
    return {k: compare.get(k) for k in keys if k in compare}


def top_values(items: list[dict[str, Any]] | None, limit: int = 5) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    return items[:limit]


def source_materials() -> list[dict[str, Any]]:
    return [
        {
            "id": "llada_cpp_mobile_npu",
            "title": "Efficient On-Device Diffusion LLM Inference with Mobile NPU",
            "url": "https://arxiv.org/html/2606.13740v1",
            "read_status": "read",
            "usable_design_points": [
                "Use an NPU-aware split between dense accelerator work and CPU-side correction/logits work.",
                "Use selective CPU logits work as a diagnostic pattern for vocabulary-sized lm_head pressure.",
                "Use graph-guided tensor residency, staging, and producer-consumer lifetimes as validation concepts.",
            ],
            "s100p_adaptation": [
                "Do not port Qualcomm Hexagon code.",
                "Run S100P segments 0..26, dump seg26 hidden, and try CPU/HF lm_head as a hybrid localization test.",
                "Interpret the result only as logits numerical validity and root-cause localization.",
            ],
        },
        {
            "id": "llama_cpp_npu_mobile_npu",
            "title": "Scaling LLM Test-Time Compute with Mobile NPU on Smartphones",
            "url": "https://arxiv.org/html/2509.23324v1",
            "read_status": "read",
            "usable_design_points": [
                "Treat mobile NPU execution as hardware-layout-sensitive, not as a generic CPU/GPU backend.",
                "Audit quantized dequantization, signedness, byte order, and tile or stride layout before blaming model quality.",
                "Separate offline layout or quantization choices from runtime dequant and vector access behavior.",
            ],
            "s100p_adaptation": [
                "Add per-tensor/per-channel scale availability checks.",
                "Compare official dequant, signed/unsigned reinterpretation, endian swap, and layout variants.",
                "Record raw int min/max/std and nonzero_count for final logits and late hidden states.",
            ],
        },
        {
            "id": "upstream_llama_cpp_diffusion_readme",
            "title": "llama.cpp examples/diffusion README",
            "url": "https://github.com/ggml-org/llama.cpp/blob/master/examples/diffusion/README.md",
            "read_status": "read",
            "usable_design_points": [
                "Diffusion CLI uses explicit diffusion steps, token-selection algorithms, block length, context, batch, and ubatch controls.",
                "Dream and LLaDA GGUF examples are supported as diffusion text-generation architectures.",
            ],
            "s100p_adaptation": [
                "Keep probe cases as explicit token IDs, position IDs, attention masks, and last-token index.",
                "Do not run generation quality in this track; use logits-only probes.",
            ],
        },
        {
            "id": "diffuse_cpp_dream_llada_gguf",
            "title": "diffuse-cpp Dream/LLaDA GGUF conversion and quantization README",
            "url": "https://github.com/iafiscal1212/diffuse-cpp",
            "read_status": "read",
            "usable_design_points": [
                "Dream-v0-Instruct-7B conversion to GGUF F16 is documented via convert-dream.py.",
                "Q4_K_M, Q8_0, and F16 are documented quantization/reference formats.",
                "The runtime operates on token IDs, which matches the seq128 probe-case strategy.",
            ],
            "s100p_adaptation": [
                "Use GGUF F16/Q4_0/Q4_K_M as reference-matrix rows when artifacts exist.",
                "Current local evidence has Q4_K_M only; F16 and Q4_0 remain missing artifacts.",
            ],
        },
    ]


def build_related_work_md() -> str:
    materials = source_materials()
    lines = [
        "# llada.cpp / llama.cpp-npu Inspired Replication Matrix",
        "",
        "Scope: this track borrows system design and validation methods only. It does not port Qualcomm Hexagon code to S100P, does not run generation quality, does not enable product routing, and does not touch port 18888.",
        "",
        "## Materials Read",
        "",
        "| Material | What is reused | S100P replication boundary |",
        "| --- | --- | --- |",
    ]
    for item in materials:
        lines.append(
            f"| [{item['title']}]({item['url']}) | "
            f"{'; '.join(item['usable_design_points'])} | "
            f"{'; '.join(item['s100p_adaptation'])} |"
        )
    lines.extend(
        [
            "",
            "## Replication Track",
            "",
            "| Upstream method | S100P diagnostic adaptation | Output |",
            "| --- | --- | --- |",
            "| llada.cpp CPU-side logits path | Run BPU segments 0..26, dump seg26 hidden, then compute final lm_head on CPU/HF when a verified Dream BF16 wrapper exists | `reports/220_hybrid_bpu_hidden_cpu_lmhead.json` |",
            "| llada.cpp graph-guided runtime validation | Treat seg26 hidden and seg27_28 final logits as a producer-consumer contract instead of a single black-box output | `reports/230_final_segment_input_contract_sweep.json` |",
            "| llama.cpp-npu quant/layout audit | Check official dequant, scalar/channel scale availability, signedness, byte order, and layout implications before making quality claims | `reports/240_s100p_dequant_layout_audit.json` |",
            "| llama.cpp/diffuse-cpp GGUF references | Compare the same seq128 token-id cases across BF16, GGUF F16, GGUF Q4_0, GGUF Q4_K_M, and S100P raw/dequant when artifacts exist | `reports/210_reference_matrix_logits_compare.json` |",
            "",
            "## Current Artifact Boundary",
            "",
            "- Available: GGUF Q4_K_M logits, S100P BPU raw/dequant final logits, S100P seg24..27 boundary dumps, final segment input sweep.",
            "- Unavailable in the current v3 evidence set: verified Dream BF16/PyTorch forward wrapper, HF seg26 boundary hidden, GGUF F16 logits, GGUF Q4_0 logits, CPU/HF lm_head logits.",
            "- Therefore, conclusions remain at logits numerical validity and root-cause localization. They are not generation-quality or product-route claims.",
            "",
        ]
    )
    return "\n".join(lines)


def case_lookup_by_id(cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {case.get("case_id"): case for case in cases if case.get("case_id")}


def build_reference_matrix(run_root: Path) -> dict[str, Any]:
    logits = opt_json(run_root / "reports/070_logits_probe_battery_triplet.json")
    s100p = opt_json(run_root / "reports/020_s100p_dump_logits_run.json")
    bf16 = opt_json(run_root / "reports/140_bf16_reference_status.json")

    s100p_cases = case_lookup_by_id(s100p.get("cases", []))
    rows = []
    for case in logits.get("cases", []):
        case_id = case.get("case_id")
        s100p_case = s100p_cases.get(case_id, {})
        final_meta = (s100p_case.get("final_tensor_metadata") or {})
        final_segment = (final_meta.get("final_segment") or {})
        gguf_cmp = (case.get("comparisons") or {}).get("gguf_vs_bpu")
        rows.append(
            {
                "case_id": case_id,
                "artifacts": {
                    "hf_pytorch_bf16": {"available": False, "reason": bf16.get("reason", "bf16_reference_unavailable")},
                    "gguf_f16": {"available": False, "reason": "no_gguf_f16_logits_or_model_artifact_in_current_v3_evidence"},
                    "gguf_q4_0": {"available": False, "reason": "no_gguf_q4_0_logits_or_model_artifact_in_current_v3_evidence"},
                    "gguf_q4_k_m": {"available": bool(case.get("has_gguf"))},
                    "s100p_bpu_raw": {"available": bool(final_segment.get("raw_stats"))},
                    "s100p_bpu_dequant": {"available": bool(case.get("has_bpu"))},
                },
                "available_compare": {
                    "gguf_q4_k_m_vs_s100p_bpu_dequant": compact_compare(gguf_cmp),
                },
                "gguf_q4_k_m_top5": top_values((gguf_cmp or {}).get("reference_top5")),
                "s100p_bpu_top5": top_values(final_meta.get("top5") or (gguf_cmp or {}).get("candidate_top5")),
                "s100p_raw_stats": small_stats(final_segment.get("raw_stats")),
                "s100p_dequant_stats": small_stats(final_segment.get("dequant_stats")),
            }
        )

    return {
        "schema_version": "dream7b_reference_matrix_logits_compare_v1",
        "created_at_utc": utc_now_iso(),
        "scope": "seq128 last-token logits numerical comparison only; generation quality not run",
        "source_reports": {
            "triplet_logits": str(run_root / "reports/070_logits_probe_battery_triplet.json"),
            "s100p_logits": str(run_root / "reports/020_s100p_dump_logits_run.json"),
            "bf16_status": str(run_root / "reports/140_bf16_reference_status.json"),
        },
        "backend_status": {
            "hf_pytorch_bf16": {
                "status": bf16.get("bf16_reference_status", "unavailable"),
                "reason": bf16.get("reason", "missing_bf16_status"),
                "no_bf16_ground_truth_claims_allowed": bf16.get("no_bf16_ground_truth_claims_allowed", True),
            },
            "gguf_f16": {"status": "unavailable", "reason": "not present in current v3 evidence set"},
            "gguf_q4_0": {"status": "unavailable", "reason": "not present in current v3 evidence set"},
            "gguf_q4_k_m": {"status": "available", "case_count": logits.get("case_count")},
            "s100p_bpu_raw_dequant": {
                "status": "available",
                "runtime_version": s100p.get("runtime_version"),
                "case_count": s100p.get("case_count"),
            },
        },
        "summary": {
            "case_count": logits.get("case_count", len(rows)),
            "gguf_q4_k_m_vs_s100p_bpu_mean_cosine": logits.get("gguf_vs_bpu_mean_cosine"),
            "s100p_all_cases_raw_final_constant_zero": all(
                ((row.get("s100p_raw_stats") or {}).get("nonzero_count") == 0) for row in rows
            )
            if rows
            else None,
            "matrix_verdict": "blocked_against_gguf_q4_k_m_bf16_f16_q4_0_unavailable",
        },
        "missing_artifacts": [
            "verified Dream-7B HF/PyTorch BF16 diffusion forward wrapper and logits",
            "GGUF F16 logits for the same seq128 token-id cases",
            "GGUF Q4_0 logits for the same seq128 token-id cases",
        ],
        "cases": rows,
    }


def find_segment(case: dict[str, Any], segment_id: int) -> dict[str, Any] | None:
    for segment in case.get("segments", []):
        if segment.get("segment") == segment_id:
            return segment
    return None


def build_hybrid_report(run_root: Path) -> dict[str, Any]:
    boundary = opt_json(run_root / "reports/130_s100p_boundary_dump_subprocess.json")
    bf16 = opt_json(run_root / "reports/140_bf16_reference_status.json")
    bf16_boundary = opt_json(run_root / "reports/140_bf16_boundary_status.json")
    sweep = opt_json(run_root / "reports/120_final_segment_input_sweep.json")

    case_rows = []
    for case in boundary.get("cases", []):
        seg26 = find_segment(case, 26)
        seg27 = find_segment(case, 27)
        case_rows.append(
            {
                "case_id": case.get("case_id"),
                "s100p_segments_0_26_dump_available": bool(seg26),
                "seg26_dequant_stats": small_stats((seg26 or {}).get("dequant_stats")),
                "seg26_raw_stats": small_stats((seg26 or {}).get("raw_stats")),
                "seg27_bpu_output_stats": small_stats((seg27 or {}).get("dequant_stats")),
                "seg27_raw_stats": small_stats((seg27 or {}).get("raw_stats")),
            }
        )

    cpu_available = bf16.get("bf16_reference_status") == "available" and bf16_boundary.get("bf16_boundary_status") == "available"
    return {
        "schema_version": "dream7b_hybrid_bpu_hidden_cpu_lmhead_v1",
        "created_at_utc": utc_now_iso(),
        "scope": "llada.cpp-inspired hybrid diagnostic; no generation and no product route",
        "source_reports": {
            "boundary_dump": str(run_root / "reports/130_s100p_boundary_dump_subprocess.json"),
            "bf16_status": str(run_root / "reports/140_bf16_reference_status.json"),
            "bf16_boundary_status": str(run_root / "reports/140_bf16_boundary_status.json"),
            "final_segment_sweep": str(run_root / "reports/120_final_segment_input_sweep.json"),
        },
        "hybrid_steps": {
            "run_s100p_bpu_segments_0_26": "available_from_boundary_dump",
            "dump_seg26_hidden_state": "available_from_boundary_dump",
            "compute_final_lm_head_on_cpu_hf_reference": "unavailable" if not cpu_available else "available",
            "compare_hybrid_logits_to_hf_full_logits": "blocked_cpu_lmhead_or_hf_full_logits_unavailable"
            if not cpu_available
            else "available",
            "compare_hybrid_logits_to_gguf_logits": "blocked_cpu_lmhead_unavailable" if not cpu_available else "available",
        },
        "decision_rule": {
            "if_hybrid_logits_recover": "seg27_28/lm_head/output contract likely fault",
            "if_hybrid_logits_fail": "earlier hidden path or input alignment likely fault",
            "current_outcome": "decision_rule_not_executed_cpu_hf_lmhead_unavailable" if not cpu_available else "executed",
        },
        "cpu_hf_reference_status": {
            "bf16_reference_status": bf16.get("bf16_reference_status", "unavailable"),
            "bf16_boundary_status": bf16_boundary.get("bf16_boundary_status", "unavailable"),
            "reason": bf16.get("reason", bf16_boundary.get("reason", "missing_reference")),
        },
        "cases": case_rows,
        "localization_from_non_hybrid_evidence": {
            "final_segment_input_sweep_verdict": sweep.get("final_segment_input_sweep_verdict"),
            "smallest_recovery_variant": sweep.get("smallest_recovery_variant"),
            "likely_issue_class": sweep.get("likely_issue_class"),
            "real_hidden_constant_output": sweep.get("real_hidden_constant_output"),
            "synthetic_controls_nonconstant": sweep.get("synthetic_controls_nonconstant"),
            "interpretation": (
                "The hybrid llada.cpp-style CPU lm_head test is blocked, but the existing final-segment sweep shows "
                "real BPU seg26 hidden produces all-zero logits at x and x/2, while x/4 and narrower clipped/normalized "
                "variants produce nonconstant logits. This localizes the current fault to the seg26 hidden range/scale "
                "or final-segment input contract, without proving BF16 ground-truth failure."
            ),
        },
        "missing_artifacts": [
            "verified Dream-7B HF/PyTorch BF16 full logits for the same seq128 cases",
            "verified HF/PyTorch lm_head path that accepts dumped seg26 hidden",
            "verified segment-to-PyTorch-layer mapping for seg26 hidden",
        ],
    }


def variant_by_id(sweep: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {v.get("variant_id"): v for v in sweep.get("variants", []) if v.get("variant_id")}


def compact_variant(v: dict[str, Any] | None, label: str | None = None) -> dict[str, Any]:
    if not isinstance(v, dict):
        return {"variant_id": label, "status": "missing"}
    out_stats = small_stats(v.get("dequant_output_stats"))
    raw_stats = small_stats(v.get("raw_output_stats"))
    return {
        "variant_id": v.get("variant_id", label),
        "status": v.get("run_status"),
        "runtime_exception": v.get("runtime_exception"),
        "why_included": v.get("why_included"),
        "input_stats": small_stats(v.get("input_stats")),
        "dequant_output_stats": out_stats,
        "raw_output_stats": raw_stats,
        "normalized_entropy": v.get("normalized_entropy"),
        "top1_probability": v.get("top1_probability"),
        "top20_head": top_values(v.get("top20_logits"), limit=5),
        "nonconstant_output": bool(out_stats and out_stats.get("constant") is False and (out_stats.get("nonzero_count") or 0) > 0),
    }


def build_input_contract_sweep(run_root: Path) -> dict[str, Any]:
    sweep = opt_json(run_root / "reports/120_final_segment_input_sweep.json")
    by_id = variant_by_id(sweep)
    required = [
        "real_x",
        "real_x_div_2",
        "real_x_div_4",
        "real_x_div_8",
        "real_x_div_16",
        "real_x_div_32",
        "real_x_clip_16",
        "real_x_clip_8",
        "real_x_clip_4",
        "real_x_clip_2",
        "real_x_clip_1",
        "real_x_z_normalized",
        "synthetic_match_mean_std_normal",
        "synthetic_match_min_max_uniform",
        "synthetic_zeros",
        "synthetic_ones",
        "synthetic_ramp",
        "synthetic_last_token_impulse",
        "real_raw_int16_as_input",
    ]
    variants = [compact_variant(by_id.get(v), v) for v in required]
    return {
        "schema_version": "dream7b_final_segment_input_contract_sweep_v1",
        "created_at_utc": utc_now_iso(),
        "scope": "seg27_28 final segment input-contract sweep; logits numerical validity only",
        "source_report": str(run_root / "reports/120_final_segment_input_sweep.json"),
        "hbm_path": sweep.get("hbm_path"),
        "model_name": sweep.get("model_name"),
        "input_cases": {
            "hf_seg26_hidden_to_bpu_seg27_28": {
                "status": "unavailable",
                "reason": "HF/PyTorch seg26 boundary hidden unavailable; verified segment-to-layer mapping unavailable",
            },
            "bpu_seg26_hidden_to_bpu_seg27_28": compact_variant(by_id.get("real_x"), "real_x"),
        },
        "summary": {
            "final_segment_input_sweep_verdict": sweep.get("final_segment_input_sweep_verdict"),
            "real_hidden_constant_output": sweep.get("real_hidden_constant_output"),
            "synthetic_controls_nonconstant": sweep.get("synthetic_controls_nonconstant"),
            "smallest_recovery_variant": sweep.get("smallest_recovery_variant"),
            "likely_issue_class": sweep.get("likely_issue_class"),
            "raw_int16_input_status": (by_id.get("real_raw_int16_as_input") or {}).get("run_status"),
            "raw_int16_input_exception": (by_id.get("real_raw_int16_as_input") or {}).get("runtime_exception"),
            "raw_uint16_input_status": "not_run_runtime_requires_float_input",
            "raw_uint16_input_reason": "HBRT rejected int16 direct input for _input_0 and reported expected numpy dtype format 'f'; uint16 direct input is not supported without a runtime override.",
        },
        "variant_groups": {
            "scaled_bpu_hidden": [compact_variant(by_id.get(v), v) for v in ["real_x_div_2", "real_x_div_4", "real_x_div_8", "real_x_div_16", "real_x_div_32"]],
            "clipped_bpu_hidden": [compact_variant(by_id.get(v), v) for v in ["real_x_clip_16", "real_x_clip_8", "real_x_clip_4", "real_x_clip_2", "real_x_clip_1"]],
            "normalized_bpu_hidden": [compact_variant(by_id.get("real_x_z_normalized"), "real_x_z_normalized")],
            "synthetic_matching_bpu_distribution": [
                compact_variant(by_id.get("synthetic_match_mean_std_normal"), "synthetic_match_mean_std_normal"),
                compact_variant(by_id.get("synthetic_match_min_max_uniform"), "synthetic_match_min_max_uniform"),
            ],
            "synthetic_controls": [
                compact_variant(by_id.get("synthetic_zeros"), "synthetic_zeros"),
                compact_variant(by_id.get("synthetic_ones"), "synthetic_ones"),
                compact_variant(by_id.get("synthetic_ramp"), "synthetic_ramp"),
                compact_variant(by_id.get("synthetic_last_token_impulse"), "synthetic_last_token_impulse"),
            ],
            "raw_reinterpretation_inputs": [
                compact_variant(by_id.get("real_raw_int16_as_input"), "real_raw_int16_as_input"),
                {
                    "variant_id": "real_raw_uint16_as_input",
                    "status": "not_run_runtime_requires_float_input",
                    "runtime_exception": "not attempted after int16 dtype rejection",
                },
            ],
        },
        "variants": variants,
        "interpretation": (
            "Real BPU seg26 hidden at original scale and /2 drives seg27_28 to all-zero logits. "
            "The first recovery is /4, and clip_4 / clip_2 / clip_1 / z-normalized variants are nonconstant. "
            "This is a diagnostic recovery only; it does not validate corrected logits against BF16 or GGUF. "
            "It points to input range/scale or final-segment input contract rather than generation quality."
        ),
    }


def build_dequant_layout_audit(run_root: Path) -> dict[str, Any]:
    audit = opt_json(run_root / "reports/060_dequant_audit.json")
    boundary = opt_json(run_root / "reports/130_s100p_boundary_dump_subprocess.json")

    cases = []
    for case in audit.get("cases", []):
        variants = {}
        for variant in case.get("variants", []):
            variants[variant.get("variant")] = {
                "stats": small_stats(variant.get("stats")),
                "compare_to_reference": compact_compare(variant.get("compare_to_reference")),
                "top5": top_values(variant.get("top5")),
            }
        cases.append(
            {
                "case_id": case.get("case_id"),
                "reference_type": case.get("reference_type"),
                "raw_stats": small_stats(case.get("raw_stats")),
                "scale": case.get("scale"),
                "zero_point": case.get("zero_point"),
                "official_variant": case.get("official_variant"),
                "official_entropy": case.get("official_entropy"),
                "best_variant": case.get("best_variant"),
                "variants": variants,
            }
        )

    seg26_cases = []
    for case in boundary.get("cases", []):
        seg26 = find_segment(case, 26)
        if seg26:
            seg26_cases.append(
                {
                    "case_id": case.get("case_id"),
                    "seg26_raw_stats": small_stats(seg26.get("raw_stats")),
                    "seg26_dequant_stats": small_stats(seg26.get("dequant_stats")),
                    "seg26_quant_metadata": seg26.get("quant_metadata"),
                }
            )

    return {
        "schema_version": "dream7b_s100p_dequant_layout_audit_v1",
        "created_at_utc": utc_now_iso(),
        "scope": "S100P final logits raw/dequant/layout audit inspired by llama.cpp-npu; logits only",
        "source_reports": {
            "dequant_audit": str(run_root / "reports/060_dequant_audit.json"),
            "boundary_dump": str(run_root / "reports/130_s100p_boundary_dump_subprocess.json"),
        },
        "audit_dimensions": {
            "official_dequant": {"status": "executed", "variant": "scale_x"},
            "per_tensor_scale": {"status": "available", "evidence": "HBRT output quant metadata exposes scalar scale and zero_point"},
            "per_channel_scale": {
                "status": "unavailable",
                "reason": "current HBRT metadata for final logits exposes scalar scale only; no per-channel vector scale was available",
            },
            "signed_unsigned_reinterpretation": {"status": "executed", "variants": ["identity_float", "uint16_reinterpret"]},
            "endian_swap": {"status": "executed", "variant": "byteswap_int16"},
            "stride_layout_variants": {
                "status": "logically_non_rescuing_for_final_logits",
                "reason": "final raw logits are all zero for all tested cases; stride or permutation cannot recover nonzero values from an all-zero vector",
            },
            "raw_int_stats": {"status": "available", "fields": ["min", "max", "mean", "std", "nonzero_count", "constant"]},
        },
        "summary": {
            "verdict": audit.get("verdict"),
            "case_count": audit.get("case_count"),
            "raw_constant_cases": audit.get("raw_constant_cases"),
            "all_final_raw_logits_zero": all((case.get("raw_stats") or {}).get("nonzero_count") == 0 for case in cases)
            if cases
            else None,
            "layout_dequant_rescue_found": False,
            "interpretation": (
                "All tested final raw logits are already constant all-zero. Official dequant, scalar scale, zero-point handling, "
                "uint16 reinterpretation, and endian swap cannot recover nonzero logits. Late hidden states are nonzero and often saturated, "
                "so the current failure is upstream of output dequant and at or before final segment execution/output emission."
            ),
        },
        "cases": cases,
        "seg26_hidden_audit": seg26_cases,
    }


def build_reference_matrix_md(matrix: dict[str, Any]) -> str:
    lines = [
        "# Dream-7B Reference Matrix Logits Compare",
        "",
        f"- scope: `{matrix['scope']}`",
        f"- verdict: `{matrix['summary']['matrix_verdict']}`",
        f"- case_count: `{matrix['summary']['case_count']}`",
        f"- gguf_q4_k_m_vs_s100p_bpu_mean_cosine: `{matrix['summary']['gguf_q4_k_m_vs_s100p_bpu_mean_cosine']}`",
        "",
        "## Backend Status",
        "",
        "| Backend | Status | Reason |",
        "| --- | --- | --- |",
    ]
    for name, status in matrix["backend_status"].items():
        lines.append(f"| `{name}` | `{status.get('status')}` | {status.get('reason', '')} |")
    lines.extend(
        [
            "",
            "## Cases",
            "",
            "| case | BF16 | F16 | Q4_0 | Q4_K_M | S100P raw nz | cosine Q4_K_M vs BPU | ref top1 | bpu top1 |",
            "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in matrix["cases"]:
        cmp = row["available_compare"]["gguf_q4_k_m_vs_s100p_bpu_dequant"]
        lines.append(
            f"| `{row['case_id']}` | "
            f"{row['artifacts']['hf_pytorch_bf16']['available']} | "
            f"{row['artifacts']['gguf_f16']['available']} | "
            f"{row['artifacts']['gguf_q4_0']['available']} | "
            f"{row['artifacts']['gguf_q4_k_m']['available']} | "
            f"{(row.get('s100p_raw_stats') or {}).get('nonzero_count')} | "
            f"{cmp.get('cosine')} | {cmp.get('ref_top1')} | {cmp.get('candidate_top1')} |"
        )
    lines.extend(["", "## Missing Artifacts", ""])
    lines.extend(f"- `{item}`" for item in matrix["missing_artifacts"])
    lines.append("")
    return "\n".join(lines)


def build_hybrid_md(report: dict[str, Any]) -> str:
    lines = [
        "# Hybrid BPU Hidden + CPU lm_head Diagnostic",
        "",
        f"- CPU/HF reference status: `{report['cpu_hf_reference_status']['bf16_reference_status']}`",
        f"- current outcome: `{report['decision_rule']['current_outcome']}`",
        "",
        "## Decision Rule",
        "",
        f"- If hybrid logits recover: `{report['decision_rule']['if_hybrid_logits_recover']}`",
        f"- If hybrid logits fail: `{report['decision_rule']['if_hybrid_logits_fail']}`",
        "",
        "## S100P Dumped Cases",
        "",
        "| case | seg26 available | seg26 abs_max | seg26 nonzero | seg27 nonzero |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for row in report["cases"]:
        lines.append(
            f"| `{row['case_id']}` | {row['s100p_segments_0_26_dump_available']} | "
            f"{row['seg26_dequant_stats'].get('abs_max')} | "
            f"{row['seg26_dequant_stats'].get('nonzero_count')} | "
            f"{row['seg27_bpu_output_stats'].get('nonzero_count')} |"
        )
    lines.extend(["", "## Current Non-Hybrid Localization", "", report["localization_from_non_hybrid_evidence"]["interpretation"], ""])
    return "\n".join(lines)


def build_sweep_md(report: dict[str, Any]) -> str:
    lines = [
        "# Final Segment Input-Contract Sweep",
        "",
        f"- verdict: `{report['summary']['final_segment_input_sweep_verdict']}`",
        f"- smallest_recovery_variant: `{report['summary']['smallest_recovery_variant']}`",
        f"- likely_issue_class: `{report['summary']['likely_issue_class']}`",
        f"- HF seg26 hidden input: `{report['input_cases']['hf_seg26_hidden_to_bpu_seg27_28']['status']}`",
        "",
        "## Required Variants",
        "",
        "| variant | status | input abs_max | output allzero | output nonzero | output std | top1 |",
        "| --- | --- | ---: | --- | ---: | ---: | ---: |",
    ]
    for variant in report["variants"]:
        out = variant.get("dequant_output_stats") or {}
        top = (variant.get("top20_head") or [{}])[0]
        lines.append(
            f"| `{variant.get('variant_id')}` | `{variant.get('status')}` | "
            f"{(variant.get('input_stats') or {}).get('abs_max')} | {out.get('allzero')} | "
            f"{out.get('nonzero_count')} | {out.get('std')} | {top.get('index')} |"
        )
    lines.extend(["", "## Interpretation", "", report["interpretation"], ""])
    return "\n".join(lines)


def build_audit_md(report: dict[str, Any]) -> str:
    lines = [
        "# S100P Dequant/Layout Audit",
        "",
        f"- verdict: `{report['summary']['verdict']}`",
        f"- all_final_raw_logits_zero: `{report['summary']['all_final_raw_logits_zero']}`",
        f"- layout_dequant_rescue_found: `{report['summary']['layout_dequant_rescue_found']}`",
        "",
        "## Audit Dimensions",
        "",
        "| dimension | status | note |",
        "| --- | --- | --- |",
    ]
    for name, item in report["audit_dimensions"].items():
        lines.append(f"| `{name}` | `{item.get('status')}` | {item.get('reason') or item.get('evidence') or item.get('variant') or item.get('variants') or ''} |")
    lines.extend(
        [
            "",
            "## Final Logits Cases",
            "",
            "| case | raw nonzero | raw min | raw max | best variant | best cosine |",
            "| --- | ---: | ---: | ---: | --- | ---: |",
        ]
    )
    for case in report["cases"]:
        best = case.get("best_variant") or {}
        raw = case.get("raw_stats") or {}
        lines.append(
            f"| `{case.get('case_id')}` | {raw.get('nonzero_count')} | {raw.get('min')} | {raw.get('max')} | "
            f"`{best.get('variant')}` | {best.get('cosine')} |"
        )
    lines.extend(["", "## Interpretation", "", report["summary"]["interpretation"], ""])
    return "\n".join(lines)


def build_gate_packet_v4(
    run_root: Path,
    matrix: dict[str, Any],
    hybrid: dict[str, Any],
    sweep: dict[str, Any],
    audit: dict[str, Any],
) -> dict[str, Any]:
    v3 = opt_json(run_root / "01_final_evidence/dream7b_s100p_gate_packet_v3.json")
    gate_status = {
        "compile_feasible": (v3.get("gate_status") or {}).get("compile_feasible", "pass"),
        "s100p_runtime_valid": (v3.get("gate_status") or {}).get("s100p_runtime_valid", "pass"),
        "reference_matrix_logits_compare": "partial_q4_k_m_and_s100p_available_bf16_f16_q4_0_missing",
        "logits_numerically_valid": "fail_against_gguf_q4_k_m_inconclusive_against_bf16_f16_q4_0",
        "hybrid_bpu_hidden_cpu_lmhead": "blocked_cpu_hf_lmhead_unavailable",
        "final_segment_input_contract_sweep": sweep["summary"].get("final_segment_input_sweep_verdict"),
        "s100p_dequant_layout_audit": "pass_no_dequant_or_layout_variant_rescues_all_zero_raw_final_logits",
        "generation_quality_valid": "not_run_by_design",
        "product_route_valid": "not_run_by_design",
        "route_safety": "pass_offline_artifact_synthesis_no_18888_no_product_route",
    }
    return {
        "schema_version": "dream7b_s100p_gate_packet_v4_llada_llamacpp_npu_track",
        "created_at_utc": utc_now_iso(),
        "track": "llada.cpp / llama.cpp-npu inspired replication track",
        "verdict": "logits_blocked_against_gguf_q4_k_m_localized_to_final_segment_input_range_or_scale_bf16_unresolved",
        "verdict_class": "logits_numerical_validity_root_cause_localization_only",
        "gate_status": gate_status,
        "source_materials": source_materials(),
        "generated_reports": {
            "related_work_reproduction_matrix": "reports/200_related_work_reproduction_matrix.md",
            "reference_matrix_logits_compare": "reports/210_reference_matrix_logits_compare.json",
            "hybrid_bpu_hidden_cpu_lmhead": "reports/220_hybrid_bpu_hidden_cpu_lmhead.json",
            "final_segment_input_contract_sweep": "reports/230_final_segment_input_contract_sweep.json",
            "s100p_dequant_layout_audit": "reports/240_s100p_dequant_layout_audit.json",
        },
        "key_findings": {
            "reference_matrix": matrix["summary"],
            "hybrid": {
                "current_outcome": hybrid["decision_rule"]["current_outcome"],
                "cpu_hf_reference_status": hybrid["cpu_hf_reference_status"],
            },
            "final_segment_sweep": sweep["summary"],
            "dequant_layout_audit": audit["summary"],
        },
        "blocking_issues": [
            "verified Dream-7B BF16/PyTorch forward and lm_head wrapper unavailable",
            "HF/PyTorch seg26 hidden boundary unavailable",
            "GGUF F16 and Q4_0 reference logits unavailable",
            "S100P final raw logits are all-zero for current seq128 probe cases",
            "real BPU seg26 hidden at original scale and /2 causes all-zero final logits; /4 is first diagnostic recovery",
        ],
        "root_cause_localization": {
            "most_likely_current_fault_class": "seg26_hidden_range_or_scale_vs_seg27_28_input_contract",
            "supported_by": [
                "seg24..26 boundary dumps are nonzero for completed cases",
                "seg27_28 output is all-zero for real seg26 hidden in full-chain and fresh-subprocess boundary dumps",
                "seg27_28 responds to synthetic controls and to scaled/clipped real hidden variants",
                "output dequant/layout variants cannot recover all-zero raw final logits",
            ],
            "not_proven": [
                "BF16/PyTorch ground-truth failure",
                "GGUF F16 or Q4_0 agreement/disagreement",
                "generation quality",
                "product-route readiness",
            ],
        },
        "safe_claim_boundary": (
            "Dream7B seq128 S100P segmented HBM remains blocked at logits numerical validity. "
            "The available Q4_K_M GGUF reference disagrees with S100P final logits because S100P raw final logits are all-zero for the tested cases. "
            "The llada.cpp-inspired hybrid CPU lm_head decision rule could not be executed without a verified HF/PyTorch Dream lm_head wrapper. "
            "Independent final-segment input sweeps localize the current anomaly to seg26 hidden range/scale or the seg27_28 input contract, not to generation quality or product routing."
        ),
        "next_minimal_experiments": [
            "Provide or build a verified Dream-7B HF/PyTorch BF16 forward wrapper and lm_head-only path for dumped seg26 hidden.",
            "Export GGUF F16 and GGUF Q4_0 logits for the same seq128 token-id cases.",
            "Obtain HBRT seg27_28 input tensor descriptors including dtype, layout, quantization, and accepted dynamic range.",
        ],
    }


def build_gate_md(packet: dict[str, Any]) -> str:
    lines = [
        "# Dream7B S100P Gate Packet V4",
        "",
        f"- verdict: `{packet['verdict']}`",
        f"- verdict_class: `{packet['verdict_class']}`",
        f"- track: `{packet['track']}`",
        "",
        "## Gate Status",
        "",
        "| Gate | Status |",
        "| --- | --- |",
    ]
    for key, value in packet["gate_status"].items():
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(["", "## Key Findings", ""])
    lines.append(f"- reference_matrix: `{packet['key_findings']['reference_matrix']}`")
    lines.append(f"- hybrid: `{packet['key_findings']['hybrid']}`")
    lines.append(f"- final_segment_sweep: `{packet['key_findings']['final_segment_sweep']}`")
    lines.append(f"- dequant_layout_audit: `{packet['key_findings']['dequant_layout_audit']}`")
    lines.extend(["", "## Root-Cause Localization", ""])
    lines.append(f"- most_likely_current_fault_class: `{packet['root_cause_localization']['most_likely_current_fault_class']}`")
    lines.extend(f"- supported_by: {item}" for item in packet["root_cause_localization"]["supported_by"])
    lines.extend(["", "## Blocking Issues", ""])
    lines.extend(f"- `{item}`" for item in packet["blocking_issues"])
    lines.extend(["", "## Safe Claim Boundary", "", packet["safe_claim_boundary"], "", "## Next Minimal Experiments", ""])
    lines.extend(f"- {item}" for item in packet["next_minimal_experiments"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build llada.cpp / llama.cpp-npu inspired Dream7B S100P replication reports.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--run-root", default=str(RUN_ROOT_DEFAULT))
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    run_root = (repo_root / args.run_root).resolve()
    reports_root = repo_root / "reports"

    matrix = build_reference_matrix(run_root)
    hybrid = build_hybrid_report(run_root)
    sweep = build_input_contract_sweep(run_root)
    audit = build_dequant_layout_audit(run_root)
    packet = build_gate_packet_v4(run_root, matrix, hybrid, sweep, audit)

    write_text(reports_root / "200_related_work_reproduction_matrix.md", build_related_work_md())
    write_json(reports_root / "210_reference_matrix_logits_compare.json", matrix)
    write_text(reports_root / "210_reference_matrix_logits_compare.md", build_reference_matrix_md(matrix))
    write_json(reports_root / "220_hybrid_bpu_hidden_cpu_lmhead.json", hybrid)
    write_text(reports_root / "220_hybrid_bpu_hidden_cpu_lmhead.md", build_hybrid_md(hybrid))
    write_json(reports_root / "230_final_segment_input_contract_sweep.json", sweep)
    write_text(reports_root / "230_final_segment_input_contract_sweep.md", build_sweep_md(sweep))
    write_json(reports_root / "240_s100p_dequant_layout_audit.json", audit)
    write_text(reports_root / "240_s100p_dequant_layout_audit.md", build_audit_md(audit))

    final_dir = run_root / "01_final_evidence"
    write_json(final_dir / "dream7b_s100p_gate_packet_v4.json", packet)
    write_text(final_dir / "dream7b_s100p_gate_packet_v4.md", build_gate_md(packet))
    write_json(reports_root / "dream7b_s100p_gate_packet_v4.json", packet)
    write_text(reports_root / "dream7b_s100p_gate_packet_v4.md", build_gate_md(packet))

    print(reports_root / "200_related_work_reproduction_matrix.md")
    print(reports_root / "210_reference_matrix_logits_compare.json")
    print(reports_root / "220_hybrid_bpu_hidden_cpu_lmhead.json")
    print(reports_root / "230_final_segment_input_contract_sweep.json")
    print(reports_root / "240_s100p_dequant_layout_audit.json")
    print(final_dir / "dream7b_s100p_gate_packet_v4.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
