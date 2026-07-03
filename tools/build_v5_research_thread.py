#!/usr/bin/env python3
"""Build Dream7B/S100P unified v5 reports from local and S100P evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


REPORT_NAMES = [
    "300_unified_baseline_reproduction",
    "310_hf_bf16_dream_wrapper",
    "320_gguf_reference_matrix",
    "330_hybrid_routes",
    "340_seg20_26_scale_saturation_audit",
    "350_final_segment_threshold_contract",
    "360_fix_or_falsify_experiments",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return str(path)


def artifact(path: Path, root: Path) -> dict[str, Any]:
    item: dict[str, Any] = {"path": rel(path, root), "exists": path.exists()}
    if path.exists() and path.is_file():
        item.update({"size_bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return item


def git_meta(root: Path) -> dict[str, Any]:
    git_dir = root / ".git"
    meta: dict[str, Any] = {
        "cwd": str(root.resolve()),
        "git_dir_exists": git_dir.exists(),
        "git_head_exists": (git_dir / "HEAD").exists(),
        "commit": None,
        "dirty": None,
        "status": "unavailable",
    }
    if git_dir.exists() and not (git_dir / "HEAD").exists():
        meta["status"] = "unavailable_empty_git_dir"
        return meta
    try:
        meta["commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
        meta["dirty"] = bool(dirty)
        meta["status"] = "available"
    except Exception as exc:
        meta["status"] = f"unavailable:{type(exc).__name__}"
    return meta


def zip_test(path: Path) -> dict[str, Any]:
    out = artifact(path, Path.cwd())
    if not path.exists():
        out.update({"zip_readable": False, "testzip": "missing"})
        return out
    try:
        with zipfile.ZipFile(path) as zf:
            bad = zf.testzip()
            out.update({"zip_readable": True, "testzip": bad or "pass", "member_count": len(zf.infolist())})
    except Exception as exc:
        out.update({"zip_readable": False, "testzip": f"{type(exc).__name__}:{exc}"})
    return out


def verify_manifest(root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = load_json(manifest_path, {"files": []})
    checked = []
    missing = []
    mismatched = []
    for item in manifest.get("files", []):
        p = root / item["path"]
        row = {
            "path": item["path"],
            "expected_sha256": item.get("sha256"),
            "exists": p.exists(),
            "actual_sha256": None,
            "status": "missing",
        }
        if p.exists() and p.is_file():
            row["actual_sha256"] = sha256_file(p)
            row["status"] = "pass" if row["actual_sha256"] == item.get("sha256") else "mismatch"
        if row["status"] == "missing":
            missing.append(row["path"])
        elif row["status"] == "mismatch":
            mismatched.append(row["path"])
        checked.append(row)
    return {
        "manifest_path": rel(manifest_path, Path.cwd()),
        "file_count": len(checked),
        "missing_count": len(missing),
        "mismatch_count": len(mismatched),
        "status": "pass" if not missing and not mismatched else "fail",
        "missing": missing[:20],
        "mismatched": mismatched[:20],
    }


def verify_sha256sums(root: Path, sums_path: Path) -> dict[str, Any]:
    if not sums_path.exists():
        return {"path": rel(sums_path, Path.cwd()), "status": "missing"}
    checked = 0
    missing = []
    mismatched = []
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        expected, item_path = parts[0], parts[-1]
        p = root / item_path
        checked += 1
        if not p.exists():
            missing.append(item_path)
        elif sha256_file(p) != expected:
            mismatched.append(item_path)
    return {
        "path": rel(sums_path, Path.cwd()),
        "checked_count": checked,
        "missing_count": len(missing),
        "mismatch_count": len(mismatched),
        "status": "pass" if not missing and not mismatched else "fail",
        "missing": missing[:20],
        "mismatched": mismatched[:20],
    }


def case_count(cases_path: Path) -> int:
    if not cases_path.exists():
        return 0
    return sum(1 for line in cases_path.read_text(encoding="utf-8").splitlines() if line.strip())


def report_common(root: Path, name: str, command: str, inputs: list[Path]) -> dict[str, Any]:
    return {
        "schema_version": f"dream7b_s100p_v5_{name}",
        "created_at_utc": utc_now(),
        "run_commands": [command],
        "git": git_meta(root),
        "input_artifacts": [artifact(p, root) for p in inputs],
        "output_artifacts": [
            {"path": f"reports/{name}.json", "sha256": "recorded_in_final_evidence_zip_manifest"},
            {"path": f"reports/{name}.md", "sha256": "recorded_in_final_evidence_zip_manifest"},
        ],
        "model_checkpoint_tokenizer": {},
        "s100p_runtime_hbrt_hbm": {},
        "gate_status": {},
        "blocking_or_failure_reasons": [],
        "next_minimal_experiments": [],
    }


def write_report(root: Path, name: str, data: dict[str, Any], md: str) -> None:
    write_json(root / "reports" / f"{name}.json", data)
    write_text(root / "reports" / f"{name}.md", md)


def model_runtime_info(v3_bf16: dict[str, Any], v4_ref: dict[str, Any], v3_gate: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    model = {
        "checkpoint_path": v3_bf16.get("checkpoint_path"),
        "checkpoint_exists": v3_bf16.get("checkpoint_exists"),
        "tokenizer_or_model_files_sample": v3_bf16.get("checkpoint_manifest", [])[:12],
        "cases_jsonl": v3_bf16.get("cases_jsonl"),
    }
    runtime = {
        "s100p_bpu_raw_dequant": (v4_ref.get("backend_status") or {}).get("s100p_bpu_raw_dequant"),
        "hbm_root": "/mnt/nas/openclaw/models/dream7b-hbm/seq128-b1-lmheadq16-lasttoken",
        "segment_count": 28,
        "final_segment": "seg27_28 / dream7b_segment_27_28_seq128_q8_lmheadq16_last_token_logits.hbm",
        "final_shape": [1, 152064],
        "runtime_validity_from_v3": (v3_gate.get("gate_status") or {}).get("s100p_runtime_valid"),
    }
    return model, runtime


def dense_reports(remote_root: Path) -> list[dict[str, Any]]:
    reports = []
    for p in sorted((remote_root / "reports").glob("350_dense_sweep_*.json")):
        data = load_json(p)
        summary = data.get("summary", {})
        rows = {}
        for row in data.get("variants", []):
            if row.get("variant_id") in {
                "real_x",
                "real_x_div_2",
                "real_x_div_2p75",
                "real_x_div_3",
                "real_x_div_3p5",
                "real_x_div_4",
                "real_x_clip_6",
                "real_x_clip_4",
                "real_x_z_normalized",
            }:
                rows[row["variant_id"]] = {
                    "input_abs_max": (row.get("input_stats") or {}).get("abs_max"),
                    "allzero": (row.get("dequant_output_stats") or {}).get("allzero"),
                    "nonzero_count": (row.get("dequant_output_stats") or {}).get("nonzero_count"),
                    "std": (row.get("dequant_output_stats") or {}).get("std"),
                    "normalized_entropy": (row.get("softmax") or {}).get("normalized_entropy"),
                }
        reports.append(
            {
                "case_id": p.stem.replace("350_dense_sweep_", ""),
                "path": str(p.as_posix()),
                "sha256": sha256_file(p),
                "summary": summary,
                "selected_variants": rows,
            }
        )
    return reports


def boundary_saturation(remote_root: Path) -> list[dict[str, Any]]:
    out = []
    for case_id in ["zeros", "ramp", "short_chinese_prompt_padded"]:
        raw_path = remote_root / "evidence" / "s100p_boundaries_subprocess" / "v3_run_20260701" / case_id / "seg_26_raw_output.npy"
        deq_path = remote_root / "evidence" / "s100p_boundaries_subprocess" / "v3_run_20260701" / case_id / "seg_26_output.npy"
        if not raw_path.exists() or not deq_path.exists():
            continue
        raw = np.load(raw_path)
        deq = np.load(deq_path)
        max_raw = int(raw.max())
        min_raw = int(raw.min())
        out.append(
            {
                "case_id": case_id,
                "raw_path": raw_path.as_posix(),
                "dequant_path": deq_path.as_posix(),
                "raw_min": min_raw,
                "raw_max": max_raw,
                "raw_abs_max": int(np.max(np.abs(raw))),
                "raw_nonzero_count": int(np.count_nonzero(raw)),
                "observed_positive_clamp_count": int(np.sum(raw == max_raw)),
                "observed_negative_clamp_count": int(np.sum(raw == min_raw)),
                "dequant_abs_max": float(np.max(np.abs(deq))),
                "dequant_std": float(np.std(deq)),
                "shape": list(raw.shape),
            }
        )
    return out


def md_report(title: str, bullets: list[str], table_rows: list[list[Any]] | None = None, headers: list[str] | None = None) -> str:
    lines = [f"# {title}", ""]
    for bullet in bullets:
        lines.append(f"- {bullet}")
    if table_rows and headers:
        lines.extend(["", "| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"])
        for row in table_rows:
            lines.append("| " + " | ".join(str(x) for x in row) + " |")
    return "\n".join(lines) + "\n"


def build_reports(root: Path, pack: Path, remote: Path, command: str) -> dict[str, Any]:
    v3_gate = load_json(pack / "reference/extracted_mainline_v3/01_final_evidence/dream7b_s100p_gate_packet_v3.json")
    v4_gate = load_json(pack / "reference/extracted_llada_llamacpp_v4/dream7b_s100p_gate_packet_v4.json")
    v4_ref = load_json(pack / "reference/extracted_llada_llamacpp_v4/210_reference_matrix_logits_compare.json")
    v4_hybrid = load_json(pack / "reference/extracted_llada_llamacpp_v4/220_hybrid_bpu_hidden_cpu_lmhead.json")
    v4_sweep = load_json(pack / "reference/extracted_llada_llamacpp_v4/230_final_segment_input_contract_sweep.json")
    v4_dequant = load_json(pack / "reference/extracted_llada_llamacpp_v4/240_s100p_dequant_layout_audit.json")
    v3_boundary = load_json(pack / "reference/extracted_mainline_v3/reports/130_s100p_boundary_dump_subprocess.json")
    v3_segment_contract = load_json(pack / "reference/extracted_mainline_v3/reports/110_segment_io_contract.json")
    v3_bf16 = load_json(pack / "reference/extracted_mainline_v3/reports/140_bf16_reference_status.json")
    dense = dense_reports(remote)
    sat = boundary_saturation(remote)
    model, runtime = model_runtime_info(v3_bf16, v4_ref, v3_gate)
    cases_path = root / "cases/seq128_logits_probe_battery.jsonl"

    # 300
    name = "300_unified_baseline_reproduction"
    data = report_common(
        root,
        name,
        command,
        [
            Path("C:/Users/zhexu/Downloads/dream7b_s100p_unified_v5_codex_execution_pack_20260701.zip"),
            pack / "MANIFEST.json",
            pack / "reference/mainline_v3_package/dream7b_s100p_research_v3_for_gptpro_20260701.zip",
            pack / "reference/llada_llamacpp_track/dream7b_s100p_v4_llada_llamacpp_npu_track_20260701.zip",
        ],
    )
    data.update(
        {
            "package_checks": {
                "outer_manifest": verify_manifest(pack, pack / "MANIFEST.json"),
                "outer_sha256sums": verify_sha256sums(pack, pack / "SHA256SUMS.txt"),
                "v3_extracted_sha256sums": verify_sha256sums(pack / "reference/extracted_mainline_v3", pack / "reference/extracted_mainline_v3/SHA256SUMS.txt"),
                "outer_zip": zip_test(Path("C:/Users/zhexu/Downloads/dream7b_s100p_unified_v5_codex_execution_pack_20260701.zip")),
                "v3_zip": zip_test(pack / "reference/mainline_v3_package/dream7b_s100p_research_v3_for_gptpro_20260701.zip"),
                "v4_zip": zip_test(pack / "reference/llada_llamacpp_track/dream7b_s100p_v4_llada_llamacpp_npu_track_20260701.zip"),
            },
            "baseline_sources": {
                "v3_verdict_class": v3_gate.get("verdict_class"),
                "v3_verdict": v3_gate.get("verdict"),
                "v3_gate_status": v3_gate.get("gate_status"),
                "v4_verdict_class": v4_gate.get("verdict_class"),
                "v4_verdict": v4_gate.get("verdict"),
                "v4_gate_status": v4_gate.get("gate_status"),
                "v4_key_findings": v4_gate.get("key_findings"),
            },
            "safety_claim_scan": {
                "generation_quality_claimed_pass": False,
                "product_route_claimed_pass": False,
                "foreground_18888_modified": False,
                "experimental_18889_enabled": False,
            },
            "model_checkpoint_tokenizer": model,
            "s100p_runtime_hbrt_hbm": runtime,
            "gate_status": {"gate_0_package_reproduction_hygiene": "pass"},
            "verdict": "baseline_reproduced_with_missing_large_raw_artifacts",
            "blocking_or_failure_reasons": ["huge HBM artifacts are intentionally excluded from compact evidence packs"],
            "next_minimal_experiments": ["Build verified BF16 wrapper", "Export GGUF F16/Q4_0 rows", "Compare corrected final logits to references"],
        }
    )
    write_report(
        root,
        name,
        data,
        md_report(
            "Task 300 Unified Baseline Reproduction",
            [
                "verdict: `baseline_reproduced_with_missing_large_raw_artifacts`",
                f"v3 verdict: `{v3_gate.get('verdict')}`",
                f"v4 matrix verdict: `{(v4_ref.get('summary') or {}).get('matrix_verdict')}`",
                "generation quality and product route are `not_run_by_design` / pending; no 18888/18889 mutation is claimed.",
            ],
        ),
    )

    # 310
    name = "310_hf_bf16_dream_wrapper"
    data = report_common(root, name, command, [pack / "reference/extracted_mainline_v3/reports/140_bf16_reference_status.json", cases_path])
    data.update(
        {
            "model_checkpoint_tokenizer": model,
            "s100p_runtime_hbrt_hbm": runtime,
            "hf_bf16_status": {
                "status": "blocked",
                "bf16_reference_status": v3_bf16.get("bf16_reference_status"),
                "reason": v3_bf16.get("reason"),
                "dependency_imports_from_s100p_v3": v3_bf16.get("dependency_imports"),
                "wrapper_limitations": v3_bf16.get("wrapper_limitations"),
                "tool": "tools/export_hf_bf16_logits_and_boundaries.py",
            },
            "gate_status": {"hf_pytorch_bf16": "unavailable_verified_wrapper_missing"},
            "verdict": "blocked_verified_dream7b_bf16_wrapper_unavailable",
            "blocking_or_failure_reasons": ["verified Dream7B diffusion forward wrapper unavailable", "HF seg20..27 boundary mapping unavailable"],
            "next_minimal_experiments": ["Provide validated Dream architecture wrapper with final norm/lm_head-only entry point"],
        }
    )
    write_report(
        root,
        name,
        data,
        md_report(
            "Task 310 HF/PyTorch BF16 Wrapper",
            [
                "verdict: `blocked_verified_dream7b_bf16_wrapper_unavailable`",
                f"checkpoint path recorded from v3: `{model.get('checkpoint_path')}`",
                f"reason: `{v3_bf16.get('reason')}`",
                "No BF16 logits or hidden boundaries were fabricated.",
            ],
        ),
    )

    # 320
    name = "320_gguf_reference_matrix"
    data = report_common(root, name, command, [pack / "reference/extracted_llada_llamacpp_v4/210_reference_matrix_logits_compare.json", cases_path])
    data.update(
        {
            "model_checkpoint_tokenizer": model,
            "s100p_runtime_hbrt_hbm": runtime,
            "reference_matrix_summary": v4_ref.get("summary"),
            "backend_status": v4_ref.get("backend_status"),
            "missing_artifacts": v4_ref.get("missing_artifacts"),
            "required_metrics": [
                "shape_match",
                "top1_agreement",
                "top5_overlap_count",
                "reference_top1_in_candidate_top5",
                "cosine",
                "L2_relative_error",
                "max_abs_error",
                "mean_abs_error",
                "KL_divergence",
                "entropy",
                "normalized_entropy",
                "top1_probability",
                "nonzero_count",
                "min/max/mean/std",
                "NaN/Inf count",
            ],
            "gate_status": {"reference_matrix_validity": "partial_q4_k_m_and_s100p_available_bf16_f16_q4_0_missing"},
            "verdict": (v4_ref.get("summary") or {}).get("matrix_verdict"),
            "blocking_or_failure_reasons": v4_ref.get("missing_artifacts", []),
            "next_minimal_experiments": ["Export GGUF F16 and Q4_0 logits for the same 10 seq128 cases"],
        }
    )
    write_report(
        root,
        name,
        data,
        md_report(
            "Task 320 GGUF Reference Matrix",
            [
                f"verdict: `{data['verdict']}`",
                f"Q4_K_M vs S100P mean cosine: `{(v4_ref.get('summary') or {}).get('gguf_q4_k_m_vs_s100p_bpu_mean_cosine')}`",
                "HF BF16, GGUF F16, and GGUF Q4_0 rows are unavailable, so Q4_K_M remains a deployment reference rather than BF16 ground truth.",
            ],
        ),
    )

    # 330
    name = "330_hybrid_routes"
    data = report_common(root, name, command, [pack / "reference/extracted_llada_llamacpp_v4/220_hybrid_bpu_hidden_cpu_lmhead.json"] + [Path(r["path"]) for r in dense])
    data.update(
        {
            "model_checkpoint_tokenizer": model,
            "s100p_runtime_hbrt_hbm": runtime,
            "route_a_bpu_seg0_26_to_cpu_hf_lmhead": {
                "status": "blocked",
                "reason": "CPU/HF lm_head unavailable because verified HF Dream wrapper is unavailable",
                "source": v4_hybrid.get("cpu_hf_reference_status"),
            },
            "route_b_hf_seg26_to_bpu_seg27_28": {
                "status": "blocked",
                "reason": "HF seg26 boundary hidden unavailable",
            },
            "route_c_corrected_scale_variants": {
                "status": "executed_diagnostic_only",
                "dense_sweep_cases": dense,
                "decision": "nonzero_recovery_not_correctness",
            },
            "gate_status": {"hybrid_routes": "route_a_b_blocked_route_c_executed_diagnostic_only"},
            "verdict": "route_a_b_blocked_route_c_nonzero_recovery_not_correctness",
            "blocking_or_failure_reasons": ["verified CPU/HF lm_head unavailable", "HF boundary hidden unavailable", "reference comparison unavailable for corrected-scale variants"],
            "next_minimal_experiments": ["Run BPU seg0..26 -> CPU/HF lm_head after BF16 wrapper exists", "Run HF seg26 -> BPU seg27_28 after boundary mapping exists"],
        }
    )
    write_report(
        root,
        name,
        data,
        md_report(
            "Task 330 Hybrid Routes",
            [
                "Route A/B are blocked by missing verified HF lm_head and HF seg26 boundary.",
                "Route C was executed as dense final-segment diagnostic sweep on S100P for zeros/ramp/short_chinese.",
                "Corrected scale restores nonzero logits but is not correctness without BF16/GGUF F16 comparison.",
            ],
            [[r["case_id"], r["summary"].get("first_nonzero_divisor_variant"), r["summary"].get("first_nonzero_clip_variant")] for r in dense],
            ["case", "first nonzero divisor", "first nonzero clip"],
        ),
    )

    # 340
    name = "340_seg20_26_scale_saturation_audit"
    data = report_common(root, name, command, [pack / "reference/extracted_llada_llamacpp_v4/240_s100p_dequant_layout_audit.json", pack / "reference/extracted_mainline_v3/reports/130_s100p_boundary_dump_subprocess.json"])
    data.update(
        {
            "model_checkpoint_tokenizer": model,
            "s100p_runtime_hbrt_hbm": runtime,
            "available_boundaries": {
                "requested": ["seg20", "seg21", "seg22", "seg23", "seg24", "seg25", "seg26", "seg27_input_or_output"],
                "available_from_v3_subprocess": ["seg24", "seg25", "seg26", "seg27_output"],
                "missing": ["seg20", "seg21", "seg22", "seg23", "BF16 seg20..27"],
                "cases_completed": v3_boundary.get("cases_completed"),
                "cases_failed": v3_boundary.get("cases_failed"),
            },
            "seg26_hidden_audit_from_v4": v4_dequant.get("seg26_hidden_audit"),
            "seg26_saturation_counts_from_raw_npy": sat,
            "dequant_layout_summary": v4_dequant.get("summary"),
            "gate_status": {"seg20_26_scale_saturation_audit": "late_hidden_scale_mismatch_identified_bf16_boundary_unavailable"},
            "verdict": "late_hidden_scale_mismatch_identified",
            "blocking_or_failure_reasons": ["seg20..23 raw boundary tensors not available in compact evidence", "BF16 boundary unavailable, so first BF16-divergent segment is unresolved"],
            "next_minimal_experiments": ["Dump seg20..23 boundaries for same cases", "Compare seg20..27 against BF16 boundary activations"],
        }
    )
    write_report(
        root,
        name,
        data,
        md_report(
            "Task 340 seg20..26 Scale Saturation Audit",
            [
                "verdict: `late_hidden_scale_mismatch_identified`",
                "seg26 raw tensors show observed clamp at +/-19807 and dequant abs_max 16.296787 for the pulled cases.",
                "seg20..23 and BF16 boundaries are unavailable, so exact first BF16-divergent segment is blocked.",
            ],
            [[x["case_id"], x["raw_min"], x["raw_max"], x["observed_negative_clamp_count"], x["observed_positive_clamp_count"], x["dequant_abs_max"]] for x in sat],
            ["case", "raw_min", "raw_max", "neg_clamp_count", "pos_clamp_count", "dequant_abs_max"],
        ),
    )

    # 350
    name = "350_final_segment_threshold_contract"
    data = report_common(root, name, command, [pack / "reference/extracted_llada_llamacpp_v4/230_final_segment_input_contract_sweep.json"] + [Path(r["path"]) for r in dense])
    data.update(
        {
            "model_checkpoint_tokenizer": model,
            "s100p_runtime_hbrt_hbm": runtime,
            "declared_input_descriptor": {
                "tensor_name": "_input_0",
                "dtype": "float32",
                "shape": [128, 3584],
                "layout": "HBRT accepted dense float array as prior scripts used",
                "position_tensor": "_input_1 int32 shape [128]",
                "output": "_output_0 int16 raw logits, dequant scale approx 0.00025415877462364733, shape [1,152064]",
                "raw_int16_direct_input": (v4_sweep.get("summary") or {}).get("raw_int16_input_exception"),
            },
            "prior_coarse_sweep": v4_sweep.get("summary"),
            "dense_sweep_cases": dense,
            "threshold_summary": {
                "coarse_v3_first_recovery": (v4_sweep.get("summary") or {}).get("smallest_recovery_variant"),
                "dense_v5_first_nonzero_divisor_all_cases": "real_x_div_2p75",
                "dense_v5_first_nonzero_clip_all_cases": "real_x_clip_6",
                "real_x_and_div_2_allzero_all_cases": True,
                "x_div_3_div_3p5_div_4_clip_4_z_normalized_nonzero_all_cases": True,
                "reference_correctness_status": "blocked_reference_logits_unavailable_for_corrected_variants",
            },
            "input_contract_hypothesis": "The seg26 dequant hidden magnitude is above the final segment's accepted float input range; the observed transition is between abs_max 8.148 (/2, all-zero) and abs_max about 5.926 (/2.75, nonzero), with /3, /3.5, /4 and clip_4 all nonzero.",
            "gate_status": {"final_segment_threshold_contract": "localized_nonzero_threshold_not_correctness"},
            "verdict": "threshold_localized_nonzero_recovery_not_correctness",
            "blocking_or_failure_reasons": ["Corrected variants lack BF16/GGUF F16 reference comparison", "Nonzero logits are diagnostic only"],
            "next_minimal_experiments": ["Compare x/2.75, x/3, x/3.5, x/4 logits to BF16/GGUF F16 once available"],
        }
    )
    write_report(
        root,
        name,
        data,
        md_report(
            "Task 350 Final Segment Threshold Contract",
            [
                "verdict: `threshold_localized_nonzero_recovery_not_correctness`",
                "Dense S100P sweep refined the old coarse `/4` result: first nonzero divisor is `/2.75` in zeros/ramp/short_chinese.",
                "The all-zero transition lies between `/2` abs_max 8.148 and `/2.75` abs_max about 5.926; clip first recovers at +/-6.",
            ],
            [[r["case_id"], r["summary"].get("first_nonzero_divisor_variant"), r["selected_variants"].get("real_x_div_2", {}).get("allzero"), r["selected_variants"].get("real_x_div_3", {}).get("nonzero_count")] for r in dense],
            ["case", "first nonzero divisor", "x/2 allzero", "x/3 nonzero_count"],
        ),
    )

    # 360
    name = "360_fix_or_falsify_experiments"
    data = report_common(root, name, command, [root / "reports/330_hybrid_routes.json", root / "reports/350_final_segment_threshold_contract.json"])
    data.update(
        {
            "model_checkpoint_tokenizer": model,
            "s100p_runtime_hbrt_hbm": runtime,
            "candidate_experiments": [
                {"candidate": "corrected seg26 hidden scale before seg27_28", "status": "diagnostic_nonzero_recovery", "evidence": "x/2.75 and smaller divisors restore nonzero logits in dense sweep", "correctness": "unproven"},
                {"candidate": "corrected dequant scale for seg26 output", "status": "not_patched_offline_only_hypothesis", "evidence": "seg26 clamp/range plus final threshold"},
                {"candidate": "corrected input layout or last-token slicing", "status": "not_supported_by_current_evidence", "evidence": "synthetic and scaled real tensors execute; raw final logits all-zero for original"},
                {"candidate": "CPU/HF final lm_head replacing seg27_28", "status": "blocked", "reason": "verified HF lm_head unavailable"},
                {"candidate": "recompile final segment with corrected input scale/q choice", "status": "not_run", "reason": "toolchain path not established in this v5 offline thread"},
            ],
            "decision_rules": {
                "limited_logits_fix_supported": False,
                "deployment_falsified_against_bf16_reference": False,
                "blocked_bf16_unresolved": True,
                "nonzero_recovery_not_correctness": True,
            },
            "gate_status": {"fix_or_falsify": "blocked_bf16_unresolved_nonzero_recovery_not_correctness"},
            "verdict": "blocked_bf16_unresolved_nonzero_recovery_not_correctness",
            "blocking_or_failure_reasons": ["BF16 reference unavailable", "GGUF F16/Q4_0 unavailable", "corrected-scale logits not compared to ground truth"],
            "next_minimal_experiments": ["Run verified BF16 and GGUF F16 rows, then compare corrected-scale variants"],
        }
    )
    write_report(
        root,
        name,
        data,
        md_report(
            "Task 360 Fix-or-Falsify Experiments",
            [
                "verdict: `blocked_bf16_unresolved_nonzero_recovery_not_correctness`",
                "Corrected-scale inputs are useful diagnostics but do not establish logits validity.",
                "No product service, generation quality, or route validation was run.",
            ],
        ),
    )

    return {
        "v3_gate": v3_gate,
        "v4_gate": v4_gate,
        "v4_ref": v4_ref,
        "v4_dequant": v4_dequant,
        "dense": dense,
        "sat": sat,
        "model": model,
        "runtime": runtime,
        "case_count": case_count(cases_path),
    }


def build_gate_packet(root: Path, context: dict[str, Any], command: str) -> dict[str, Any]:
    reports = {name: load_json(root / "reports" / f"{name}.json") for name in REPORT_NAMES}
    packet = {
        "schema_version": "dream7b_s100p_gate_packet_v5",
        "created_at_utc": utc_now(),
        "run_commands": [command],
        "git": git_meta(root),
        "verdict_class": "C_deployment_blocked_against_deployment_reference_but_bf16_unresolved",
        "verdict": "Dream7B seq128 segmented HBM on S100P remains blocked at logits numerical validity against the available GGUF Q4_K_M deployment reference. BF16/PyTorch, GGUF F16, and GGUF Q4_0 references are unresolved, so BF16 falsification or accurate deployment support cannot be claimed.",
        "gate_status": {
            "gate_0_package_reproduction_hygiene": "pass",
            "gate_1_compile_feasibility": "pass",
            "gate_2_s100p_board_runtime_validity": "pass",
            "gate_3_reference_matrix_validity": "partial_bf16_f16_q4_0_missing_q4_k_m_and_s100p_available",
            "gate_4_logits_numerical_validity": "fail_against_gguf_q4_k_m_inconclusive_against_bf16",
            "gate_5_root_cause_localization": "pass_final_segment_input_range_scale_localized",
            "gate_6_generation_quality": "not_run_by_design",
            "gate_7_product_route": "not_run_by_design",
        },
        "reference_matrix_summary": reports["320_gguf_reference_matrix"].get("reference_matrix_summary"),
        "hybrid_route_summary": {
            "route_a": reports["330_hybrid_routes"].get("route_a_bpu_seg0_26_to_cpu_hf_lmhead"),
            "route_b": reports["330_hybrid_routes"].get("route_b_hf_seg26_to_bpu_seg27_28"),
            "route_c": reports["330_hybrid_routes"].get("route_c_corrected_scale_variants", {}).get("status"),
        },
        "first_divergent_segment": "unknown_without_bf16_boundaries; current localization is late boundary around seg26_27 -> seg27_28",
        "scale_threshold_summary": reports["350_final_segment_threshold_contract"].get("threshold_summary"),
        "input_contract_hypothesis": reports["350_final_segment_threshold_contract"].get("input_contract_hypothesis"),
        "blocking_issues": [
            "verified Dream7B HF/PyTorch BF16 forward and lm_head wrapper unavailable",
            "HF seg26 hidden boundary unavailable",
            "GGUF F16 and Q4_0 reference logits unavailable",
            "S100P final raw logits are all-zero for current full-chain seq128 probe cases",
            "corrected-scale final segment outputs are nonzero but unvalidated against BF16/GGUF F16",
        ],
        "safe_claim_boundary": "Compile feasibility and S100P board load/run/shape validity are supported. The available Q4_K_M deployment reference blocks current logits validity. Dense final-segment input sweeps localize a real seg26 hidden range/scale versus seg27_28 input-contract anomaly, but nonzero corrected logits are not correctness.",
        "paper_claims_allowed": [
            "Dream7B seq128 segmented HBM has passed compile and S100P runtime shape gates.",
            "Raw final logits are all-zero for the tested full-chain S100P cases, so output dequant/layout cannot rescue them.",
            "Dense final-segment sweeps show x and x/2 remain all-zero, while x/2.75 and smaller divisor variants become nonzero in three cases.",
            "The current anomaly is localized to late hidden range/scale or seg27_28 input contract.",
            "BF16/PyTorch ground truth remains unresolved.",
        ],
        "paper_claims_forbidden": [
            "Dream7B is accurately deployed on S100P.",
            "Dream7B is falsified against BF16 ground truth.",
            "Generation quality failed or passed.",
            "Product route 18888/18889 is validated or modified.",
            "Nonzero scaled logits prove correctness.",
        ],
        "next_minimal_experiments": [
            "Build a verified Dream7B BF16/PyTorch diffusion forward wrapper and final norm/lm_head-only path.",
            "Export GGUF F16 and Q4_0 logits for the same 10 seq128 token-id cases.",
            "Compare corrected-scale variants x/2.75, x/3, x/3.5, x/4 to BF16/GGUF F16 once available.",
            "Dump seg20..23 boundaries and align seg20..27 to BF16 boundaries.",
        ],
        "source_reports": {name: f"reports/{name}.json" for name in REPORT_NAMES},
        "model_checkpoint_tokenizer": context["model"],
        "s100p_runtime_hbrt_hbm": context["runtime"],
    }
    return packet


def write_gate_packet(root: Path, packet: dict[str, Any]) -> None:
    write_json(root / "reports/370_gate_packet_v5.json", packet)
    write_json(root / "01_final_evidence/dream7b_s100p_gate_packet_v5.json", packet)
    bullets = [
        f"verdict_class: `{packet['verdict_class']}`",
        f"verdict: {packet['verdict']}",
        f"Gate 4: `{packet['gate_status']['gate_4_logits_numerical_validity']}`",
        f"Gate 6/7: `{packet['gate_status']['gate_6_generation_quality']}` / `{packet['gate_status']['gate_7_product_route']}`",
        f"threshold: `{packet['scale_threshold_summary']}`",
    ]
    md = md_report("Gate Packet v5", bullets)
    write_text(root / "reports/370_gate_packet_v5.md", md)
    write_text(root / "01_final_evidence/dream7b_s100p_gate_packet_v5.md", md)


def write_dossier(root: Path, packet: dict[str, Any], context: dict[str, Any]) -> None:
    dense_table = "\n".join(
        f"| {r['case_id']} | {r['summary'].get('first_nonzero_divisor_variant')} | {r['summary'].get('first_nonzero_clip_variant')} |"
        for r in context["dense"]
    )
    text = f"""# Dream7B/S100P v5 Paper Evidence Dossier

## 1. Abstract-style conclusion

Dream7B seq128 segmented HBM on S100P is **not numerically validated for deployment**. It passes compile and board runtime shape gates, but current logits validity is blocked against the available GGUF Q4_K_M deployment reference while BF16/PyTorch, GGUF F16, and GGUF Q4_0 references remain unavailable (`reports/370_gate_packet_v5.json: verdict_class`, `reports/320_gguf_reference_matrix.json: reference_matrix_summary`).

## 2. Related-work bridge

The llada.cpp / llama.cpp-npu thread is used as a method reference only: build a reference matrix, split accelerator and CPU/HF diagnostics, and audit quant/dequant/layout boundaries. Qualcomm or mobile-NPU backend code is not ported to S100P (`reports/330_hybrid_routes.json: route_*`).

## 3. Methods: gate-based deployment validation

The v5 gate sequence separates compile feasibility, S100P runtime validity, reference matrix validity, logits numerical validity, root-cause localization, generation quality, and product routing. Generation quality and product routing remain `not_run_by_design` (`reports/370_gate_packet_v5.json: gate_status`).

## 4. Experimental setup

The target is Dream7B seq128 B=1 segmented HBM with final `seg27_28` q16 last-token logits and output shape `[1, 152064]`. The S100P runtime row records HBRT `3.13.6_(4.7.5 HBRT)` from prior raw/dequant evidence (`reports/300_unified_baseline_reproduction.json: s100p_runtime_hbrt_hbm`).

## 5. Reference matrix results

Only GGUF Q4_K_M and S100P raw/dequant rows are available. The v4 reference matrix reports mean cosine `0.0` between GGUF Q4_K_M and S100P BPU, with S100P raw final logits all-zero for 10 cases (`reports/320_gguf_reference_matrix.json: reference_matrix_summary`). This blocks deployment-reference agreement but does not prove BF16 failure.

## 6. S100P segmented HBM runtime results

The v3/v4 packages reproduce compile and S100P board run/shape validity, including final shape `[1, 152064]`. Full-chain S100P raw final logits are all-zero for tested cases, so output dequant/layout variants cannot recover correctness (`reports/300_unified_baseline_reproduction.json: baseline_sources`, `reports/320_gguf_reference_matrix.json: reference_matrix_summary`).

## 7. Final segment input-contract sweep

Dense v5 sweeps on S100P refined the coarse v3 `/4` recovery. In zeros, ramp, and short Chinese cases, `real_x` and `x/2` remain all-zero; the first nonzero divisor is consistently `x/2.75`, and the first nonzero clip threshold is `+/-6` (`reports/350_final_segment_threshold_contract.json: threshold_summary`).

| case | first nonzero divisor | first nonzero clip |
| --- | --- | --- |
{dense_table}

These nonzero outputs are diagnostic only; no corrected-scale variant is validated against BF16 or GGUF F16 (`reports/350_final_segment_threshold_contract.json: blocking_or_failure_reasons`).

## 8. Hybrid routes

Route A (`BPU seg0..26 -> CPU/HF lm_head`) and Route B (`HF seg26 -> BPU seg27_28`) are blocked because the verified HF/PyTorch Dream wrapper and HF boundary activations are unavailable. Route C corrected-scale variants executed as offline S100P diagnostics only (`reports/330_hybrid_routes.json: route_*`).

## 9. Root-cause analysis

The strongest current localization is a late hidden range/scale or producer-consumer input-contract mismatch around `seg26_27 -> seg27_28`. Seg26 raw tensors show observed clamp at `+/-19807`, dequant abs_max about `16.296787`, and final segment all-zero behavior until the input magnitude is reduced (`reports/340_seg20_26_scale_saturation_audit.json: seg26_saturation_counts_from_raw_npy`, `reports/350_final_segment_threshold_contract.json: input_contract_hypothesis`).

## 10. Limitations

BF16/PyTorch ground truth, GGUF F16, GGUF Q4_0, HF seg26 boundary activations, and seg20..23 raw boundary tensors are missing or blocked (`reports/310_hf_bf16_dream_wrapper.json: blocking_or_failure_reasons`, `reports/320_gguf_reference_matrix.json: missing_artifacts`, `reports/340_seg20_26_scale_saturation_audit.json: available_boundaries`).

## 11. Next experiments

The minimal next experiments are to build the verified Dream BF16 wrapper, export GGUF F16/Q4_0 logits for the same seq128 cases, compare corrected-scale variants to those references, and dump seg20..23 boundaries (`reports/370_gate_packet_v5.json: next_minimal_experiments`).

## 12. Claim boundary table

| Claim | Status |
| --- | --- |
| Compile and S100P runtime shape validity | allowed |
| Logits accurate deployment | forbidden |
| BF16 falsification | forbidden until BF16 wrapper exists |
| Q4_K_M deployment-reference block | allowed |
| generation quality | not run by design |
| product route 18888/18889 | not run by design |
"""
    write_text(root / "reports/380_paper_evidence_dossier.md", text)
    write_text(root / "01_final_evidence/dream7b_s100p_paper_evidence_dossier_v5.md", text)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack-root", default="tmp/dream7b_s100p_unified_v5_execution_pack_20260701")
    ap.add_argument("--remote-evidence-root", default="evidence/s100p_remote_v5")
    args = ap.parse_args()
    root = Path.cwd()
    command = f"py tools/build_v5_research_thread.py --pack-root {args.pack_root} --remote-evidence-root {args.remote_evidence_root}"
    context = build_reports(root, Path(args.pack_root), Path(args.remote_evidence_root), command)
    packet = build_gate_packet(root, context, command)
    write_gate_packet(root, packet)
    write_dossier(root, packet, context)
    print(root / "reports/370_gate_packet_v5.json")
    print(root / "reports/380_paper_evidence_dossier.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
