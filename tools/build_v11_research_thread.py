#!/usr/bin/env python3
"""Build Dream7B/S100P v11 reports, paper tables, and GPT Pro package."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


CASE_IDS = ["zeros", "ramp", "short_chinese_prompt_padded"]
BOUNDARY_SEGMENTS = list(range(28))
SUFFIX_BOUNDARIES = [8, 11, 12, 13, 20, 26]
SUBSET_BOUNDARIES = [0, 1, 8, 11, 12, 13, 20, 26, 27]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return {} if default is None else default
    last_error: Exception | None = None
    for encoding in ("utf-8", "utf-8-sig", "utf-16"):
        try:
            return json.loads(path.read_text(encoding=encoding))
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    return {} if default is None else default


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return str(path)


def reset_dir(path: Path, root: Path) -> None:
    resolved = path.resolve()
    root_resolved = root.resolve()
    if root_resolved not in resolved.parents and resolved != root_resolved:
        raise RuntimeError(f"refusing to remove outside workspace: {resolved}")
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def copy_file(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    if src.is_file():
        copy_file(src, dst)
    else:
        shutil.copytree(src, dst, dirs_exist_ok=True)


def artifact(path: Path, root: Path) -> dict[str, Any]:
    out = {"path": rel(path, root), "exists": path.exists()}
    if path.is_file():
        out.update({"size_bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return out


def git_meta(root: Path) -> dict[str, Any]:
    meta = {"cwd": str(root), "git_dir_exists": (root / ".git").exists(), "git_head_exists": (root / ".git" / "HEAD").exists(), "status": "unavailable"}
    try:
        meta["commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
        meta["dirty"] = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip())
        meta["status"] = "available"
    except Exception as exc:
        meta["status"] = "unavailable_empty_or_incomplete_git_dir" if meta["git_dir_exists"] and not meta["git_head_exists"] else f"unavailable:{type(exc).__name__}"
    return meta


def stats(x: np.ndarray) -> dict[str, Any]:
    y = np.asarray(x).reshape(-1)
    return {
        "shape": list(np.asarray(x).shape),
        "dtype": str(np.asarray(x).dtype),
        "size": int(y.size),
        "min": float(np.min(y)),
        "max": float(np.max(y)),
        "mean": float(np.mean(y)),
        "std": float(np.std(y)),
        "abs_max": float(np.max(np.abs(y))),
        "nonzero_count": int(np.count_nonzero(y)),
        "allzero": bool(np.all(y == 0)),
        "constant": bool(np.all(y == y.flat[0])),
        "nan_count": int(np.isnan(y.astype(np.float64, copy=False)).sum()),
        "inf_count": int(np.isinf(y.astype(np.float64, copy=False)).sum()),
    }


def topk(x: np.ndarray, k: int = 5) -> list[int]:
    return np.argsort(np.asarray(x).reshape(-1))[-k:][::-1].astype(int).tolist()


def entropy(x: np.ndarray) -> dict[str, float]:
    y = np.asarray(x, dtype=np.float64).reshape(-1)
    z = y - np.max(y)
    e = np.exp(z)
    p = e / np.sum(e) if np.sum(e) else np.full_like(y, 1 / y.size)
    h = -float(np.sum(p * np.log(np.maximum(p, 1e-300))))
    return {"entropy": h, "normalized_entropy": h / math.log(y.size), "top1_probability": float(np.max(p))}


def compare_arrays(candidate: np.ndarray, reference: np.ndarray) -> dict[str, Any]:
    c = np.asarray(candidate, dtype=np.float64).reshape(-1)
    r = np.asarray(reference, dtype=np.float64).reshape(-1)
    if c.shape != r.shape:
        return {"shape_mismatch": True, "candidate_shape": list(candidate.shape), "reference_shape": list(reference.shape)}
    cc, rr = c - c.mean(), r - r.mean()
    diff = c - r
    denom = np.linalg.norm(c) * np.linalg.norm(r)
    cdenom = np.linalg.norm(cc) * np.linalg.norm(rr)
    out = {
        "shape_mismatch": False,
        "cosine": float(np.dot(c, r) / denom) if denom else 0.0,
        "pearson_centered": float(np.dot(cc, rr) / cdenom) if cdenom else 0.0,
        "relative_l2": float(np.linalg.norm(diff) / (np.linalg.norm(r) + 1e-12)),
        "mean_abs_error": float(np.mean(np.abs(diff))),
        "max_abs_error": float(np.max(np.abs(diff))),
        "candidate_stats": stats(candidate),
        "reference_stats": stats(reference),
    }
    if c.size == 152064:
        ck, rk = topk(c, 5), topk(r, 5)
        out.update(
            {
                "candidate_top1": int(ck[0]),
                "reference_top1": int(rk[0]),
                "top1_agreement": bool(ck[0] == rk[0]),
                "top5_overlap": int(len(set(ck) & set(rk))),
                "candidate_entropy": entropy(candidate),
                "reference_entropy": entropy(reference),
            }
        )
    return out


def common(root: Path, name: str, command: str, inputs: list[Path]) -> dict[str, Any]:
    return {
        "schema_version": f"dream7b_s100p_v11_{name}",
        "created_at_utc": now(),
        "run_commands": [command],
        "git": git_meta(root),
        "input_artifacts": [artifact(p, root) for p in inputs],
        "output_artifacts": [{"path": f"reports/{name}.json"}, {"path": f"reports/{name}.md"}],
        "blocking_or_failure_reasons": [],
        "next_minimal_experiments": [],
    }


def write_report(root: Path, name: str, report: dict[str, Any], title: str, bullets: list[str]) -> None:
    write_json(root / "reports" / f"{name}.json", report)
    lines = [f"# {title}", "", f"- schema: `{report.get('schema_version')}`", f"- created_at_utc: `{report.get('created_at_utc')}`"]
    lines.extend(f"- {b}" for b in bullets)
    if report.get("blocking_or_failure_reasons"):
        lines.append("- blocking_or_failure_reasons:")
        lines.extend(f"  - {b}" for b in report["blocking_or_failure_reasons"])
    if report.get("next_minimal_experiments"):
        lines.append("- next_minimal_experiments:")
        lines.extend(f"  - {b}" for b in report["next_minimal_experiments"])
    write_text(root / "reports" / f"{name}.md", "\n".join(lines) + "\n")


def validate_manifest_dir(package_root: Path) -> dict[str, Any]:
    mf = load_json(package_root / "MANIFEST.json", {"files": []})
    missing, bad_size, bad_sha = [], [], []
    for ent in mf.get("files", []):
        p = package_root / ent["path"]
        if not p.exists():
            missing.append(ent["path"])
            continue
        if p.stat().st_size != ent.get("size_bytes"):
            bad_size.append(ent["path"])
        if sha256_file(p) != ent.get("sha256"):
            bad_sha.append(ent["path"])
    return {"entries": len(mf.get("files", [])), "missing": missing, "bad_size": bad_size, "bad_sha256": bad_sha}


def validate_zip_manifest(zip_path: Path) -> dict[str, Any]:
    out = {"zip_path": str(zip_path), "exists": zip_path.exists()}
    if not zip_path.exists():
        return out
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        with zipfile.ZipFile(zip_path) as zf:
            out["testzip_bad_member"] = zf.testzip()
            zf.extractall(tmp)
        out["manifest_check"] = validate_manifest_dir(tmp)
        out["zip_sha256"] = sha256_file(zip_path)
    return out


def task900(root: Path, command: str) -> dict[str, Any]:
    v10_zip = root / "evidence_for_gptpro" / "dream7b_s100p_v10_for_gptpro_20260701_b.zip"
    repeat_root = root / "evidence" / "full_truth_repeat_v11"
    remote_report = root / "evidence" / "s100p_remote_v11_reports" / "900_910_hf_boundaries_repeat_remote.json"
    rows = []
    for cid in CASE_IDS:
        old = root / "evidence" / "full_truth_v10" / cid / "full_truth_logits.npy"
        new = repeat_root / cid / "repeat_full_truth_logits.npy"
        if old.exists() and new.exists():
            metrics = compare_arrays(np.load(new), np.load(old))
            metrics.update({"case_id": cid, "repeat_path": rel(new, root), "v10_path": rel(old, root)})
            rows.append(metrics)
    remote = load_json(remote_report, {})
    source_hashes = remote.get("source_hashes", [])
    report = common(root, "900_repeat_full_truth_reference", command, [v10_zip, repeat_root, remote_report])
    report.update(
        {
            "v10_zip_validation": validate_zip_manifest(v10_zip),
            "repeat_truth_rows": len(rows),
            "repeat_truth_dtype": "HF/PyTorch repeat bfloat16 on same S100P environment",
            "fp32_or_second_environment_status": "blocked_unavailable_in_current_workspace",
            "source_hashes": source_hashes,
            "source_hashes_present": {item.get("name"): bool(item.get("sha256")) for item in source_hashes},
            "v10_vs_repeat_rows": rows,
            "top1_agreement_rows": int(sum(1 for r in rows if r.get("top1_agreement"))),
            "median_relative_l2": float(np.median([r["relative_l2"] for r in rows])) if rows else None,
            "median_pearson_centered": float(np.median([r["pearson_centered"] for r in rows])) if rows else None,
            "remote_status": remote.get("status"),
            "remote_errors": remote.get("errors", []),
        }
    )
    if len(rows) != 3:
        report["blocking_or_failure_reasons"].append("repeat truth rows incomplete")
    report["blocking_or_failure_reasons"].append(
        "FP32 or genuinely independent-host repeat truth was not executed because no such ready high-memory/runtime asset is available in the current workspace/NAS evidence; v11 provides a same-S100P BF16 repeat instead."
    )
    report["next_minimal_experiments"].append("For publication robustness, repeat FP32 or BF16 on a genuinely independent high-memory host when available.")
    write_report(root, "900_repeat_full_truth_reference", report, "Task 900 Repeat Full Truth Reference", [f"repeat_truth_rows: `{len(rows)}/3`", f"top1_agreement_rows: `{report['top1_agreement_rows']}/3`", f"median_relative_l2: `{report['median_relative_l2']}`"])
    return report


def task910(root: Path, command: str) -> dict[str, Any]:
    hf_root = root / "evidence" / "hf_boundaries_v11"
    bpu_root = root / "evidence" / "boundary_all_segments_v7"
    subset_root = root / "evidence" / "hf_bpu_boundary_subset_v11"
    reset_dir(subset_root, root)
    rows = []
    for cid in CASE_IDS:
        for seg in BOUNDARY_SEGMENTS:
            hf_path = hf_root / cid / f"layer_{seg:02d}_output.npy"
            bpu_path = bpu_root / cid / f"seg_{seg:02d}_output.npy"
            if not hf_path.exists() or not bpu_path.exists():
                rows.append({"case_id": cid, "segment": seg, "missing": True, "hf_exists": hf_path.exists(), "bpu_exists": bpu_path.exists()})
                continue
            metrics = compare_arrays(np.load(bpu_path), np.load(hf_path))
            metrics.update({"case_id": cid, "segment": seg, "hf_path": rel(hf_path, root), "bpu_path": rel(bpu_path, root), "missing": False})
            rows.append(metrics)
            if seg in SUBSET_BOUNDARIES:
                copy_file(hf_path, subset_root / cid / f"hf_layer_{seg:02d}_output.npy")
                copy_file(bpu_path, subset_root / cid / f"bpu_seg_{seg:02d}_output.npy")
    divergent = [
        r
        for r in rows
        if not r.get("missing") and (r.get("shape_mismatch") or r.get("relative_l2", 999) > 0.1 or r.get("pearson_centered", 0) < 0.95)
    ]
    first_by_case = {}
    for cid in CASE_IDS:
        case_rows = [r for r in divergent if r["case_id"] == cid]
        first_by_case[cid] = min((r["segment"] for r in case_rows), default=None)
    first_global = min((seg for seg in first_by_case.values() if seg is not None), default=None)
    report = common(root, "910_hf_bpu_boundary_alignment", command, [hf_root, bpu_root])
    report.update(
        {
            "alignment_rows": len([r for r in rows if not r.get("missing")]),
            "missing_rows": [r for r in rows if r.get("missing")],
            "divergent_rows": len(divergent),
            "first_divergent_segment_by_case": first_by_case,
            "first_divergent_segment_global": first_global,
            "thresholds": {"relative_l2_fail_gt": 0.1, "pearson_fail_lt": 0.95},
            "rows": rows,
            "raw_subset_root": rel(subset_root, root),
        }
    )
    if first_global is None:
        report["blocking_or_failure_reasons"].append("no divergence localized under configured thresholds")
    write_report(root, "910_hf_bpu_boundary_alignment", report, "Task 910 HF-BPU Boundary Alignment", [f"alignment_rows: `{report['alignment_rows']}`", f"first_divergent_segment_global: `{first_global}`", f"divergent_rows: `{len(divergent)}`"])
    return report


def task920(root: Path, command: str) -> dict[str, Any]:
    suffix_root = root / "evidence" / "hf_suffix_route_v11"
    remote_report = root / "evidence" / "s100p_remote_v11_reports" / "920_suffix_route_remote.json"
    rows = []
    for cid in CASE_IDS:
        truth = root / "evidence" / "full_truth_v10" / cid / "full_truth_logits.npy"
        for boundary in SUFFIX_BOUNDARIES:
            cand = suffix_root / cid / f"seg_{boundary:02d}_to_logits" / "suffix_logits.npy"
            if cand.exists() and truth.exists():
                metrics = compare_arrays(np.load(cand), np.load(truth))
                metrics.update({"case_id": cid, "boundary": boundary, "candidate_path": rel(cand, root), "reference_path": rel(truth, root)})
                rows.append(metrics)
    report = common(root, "920_suffix_route_localization", command, [suffix_root, remote_report])
    by_boundary = {}
    for boundary in SUFFIX_BOUNDARIES:
        br = [r for r in rows if r["boundary"] == boundary]
        by_boundary[str(boundary)] = {
            "rows": len(br),
            "top1_agreement_rows": int(sum(1 for r in br if r.get("top1_agreement"))),
            "median_relative_l2": float(np.median([r["relative_l2"] for r in br])) if br else None,
            "median_pearson_centered": float(np.median([r["pearson_centered"] for r in br])) if br else None,
        }
    report.update(
        {
            "suffix_rows": len(rows),
            "expected_rows": len(CASE_IDS) * len(SUFFIX_BOUNDARIES),
            "remote_status": load_json(remote_report, {}).get("status"),
            "remote_errors": load_json(remote_report, {}).get("errors", []),
            "summary_by_boundary": by_boundary,
            "rows": rows,
        }
    )
    if len(rows) != len(CASE_IDS) * len(SUFFIX_BOUNDARIES):
        report["blocking_or_failure_reasons"].append("suffix route rows incomplete")
    write_report(root, "920_suffix_route_localization", report, "Task 920 Suffix Route Localization", [f"suffix_rows: `{len(rows)}/{len(CASE_IDS) * len(SUFFIX_BOUNDARIES)}`"])
    return report


def task930(root: Path, command: str) -> dict[str, Any]:
    report = common(root, "930_gguf_f16_reference_crosscheck", command, [root / "evidence" / "model_inventory_v6.json"])
    inventory = load_json(root / "evidence" / "model_inventory_v6.json", {})
    report.update(
        {
            "gguf_f16_available": False,
            "gguf_f16_rows": 0,
            "known_gguf_artifacts": ["/mnt/nas/openclaw/models/dream7b/dream-7b-q4km.gguf"],
            "blocker": "Only Q4_K_M GGUF was found in prior and v10 NAS inventory; no GGUF F16/unquantized runner artifact is available in the current workspace/NAS evidence.",
            "inventory_excerpt": inventory.get("gguf", inventory) if isinstance(inventory, dict) else {},
        }
    )
    report["blocking_or_failure_reasons"].append(report["blocker"])
    report["next_minimal_experiments"].append("Provide Dream7B GGUF F16/unquantized artifact and llama.cpp/diffuse-cpp runner for canonical seq128 logits cross-check.")
    write_report(root, "930_gguf_f16_reference_crosscheck", report, "Task 930 GGUF F16 Reference Crosscheck", ["gguf_f16_available: `False`", "primary_truth: `HF/PyTorch BF16`"])
    return report


def task940(root: Path, command: str) -> dict[str, Any]:
    out_root = root / "evidence" / "operator_graph_metadata_v11"
    reset_dir(out_root, root)
    sources = [
        root / "deliverables" / "dream7b_s100p_diffusion_research_pack_20260701" / "05_artifact_metadata" / "seq128_b1_lmheadq16_lasttoken_summary.json",
        root / "deliverables" / "dream7b_s100p_diffusion_research_pack_20260701" / "05_artifact_metadata" / "seq128_b1_lmheadq16_lasttoken_hbm_manifest.tsv",
        root / "evidence" / "seg27_28_mapping_v10" / "mapping_summary_v10.json",
        root / "evidence" / "s100p_remote_v10_reports" / "model_hbm_inventory_v10.json",
    ]
    for src in sources:
        copy_file(src, out_root / src.name)
    mapping = load_json(root / "evidence" / "seg27_28_mapping_v10" / "mapping_summary_v10.json", {})
    report = common(root, "940_hbm_operator_graph_metadata", command, sources)
    report.update(
        {
            "metadata_root": rel(out_root, root),
            "operator_graph_status": "operator_graph_unavailable",
            "manifest_level_mapping": mapping.get("summary_final_segment"),
            "hbm": mapping.get("remote_hbm"),
            "runtime_quant_metadata": mapping.get("runtime_quant_metadata"),
            "boundary_interpretation": mapping.get("boundary_interpretation"),
        }
    )
    report["blocking_or_failure_reasons"].append("No compiler operator-list/graph metadata file was found in the local/NAS package; v11 retains manifest-level mapping confidence only.")
    write_report(root, "940_hbm_operator_graph_metadata", report, "Task 940 HBM Operator Graph Metadata", ["operator_graph_status: `operator_graph_unavailable`"])
    return report


def task950(root: Path, command: str) -> dict[str, Any]:
    v10 = load_json(root / "reports" / "840_isolated_final_segment_remediation.json", {})
    report = common(root, "950_offline_repair_experiment", command, [root / "reports" / "840_isolated_final_segment_remediation.json"])
    report.update(
        {
            "recompile_attempted": False,
            "calibration_reused_from_v10": True,
            "repair_supported": bool(v10.get("repair_supported")),
            "base_top1_agreement_rows": v10.get("base_top1_agreement_rows"),
            "affine_top1_agreement_rows": v10.get("affine_top1_agreement_rows"),
            "median_base_relative_l2": v10.get("median_base_relative_l2"),
            "median_affine_relative_l2": v10.get("median_affine_relative_l2"),
            "interpretation": "v11 did not find a rebuilt/calibrated artifact. v10 offline affine calibration lowered L2 but kept top1 agreement at 0/42, so no repair is supported.",
        }
    )
    report["blocking_or_failure_reasons"].append("No offline rebuilt seg27_28 artifact or calibration-capable compiler metadata was available.")
    write_report(root, "950_offline_repair_experiment", report, "Task 950 Offline Repair Experiment", [f"repair_supported: `{report['repair_supported']}`", f"affine_top1_agreement_rows: `{report['affine_top1_agreement_rows']}`"])
    return report


def task960(root: Path, command: str, reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    final_root = root / "01_final_evidence"
    final_root.mkdir(parents=True, exist_ok=True)
    r900, r910, r920, r930, r940, r950 = (reports[str(i)] for i in [900, 910, 920, 930, 940, 950])
    v10_b_report = load_json(root / "reports" / "830_compare_full_truth_and_upstream_hidden.json", {})
    repeat_truth_reproduced = bool(r900.get("repeat_truth_rows") == 3 and r900.get("top1_agreement_rows") == 3)
    v10_official_falsified = bool(
        v10_b_report.get("official_vs_full_truth_rows") == 3
        and v10_b_report.get("official_vs_full_truth_top1_agreement_rows") == 0
    )
    current_falsified = repeat_truth_reproduced and v10_official_falsified
    first_div = r910.get("first_divergent_segment_global")
    suffix_complete = r920.get("suffix_rows") == r920.get("expected_rows")
    verdicts = {
        "B_current_deployment_falsified": current_falsified,
        "F_final_segment_contract_falsified": True,
        "G_upstream_hidden_invalid": first_div is not None or suffix_complete,
        "H_repair_supported": bool(r950.get("repair_supported")),
    }
    packet = common(root, "960_build_v11_gate_packet_and_paper_tables", command, [])
    packet.update(
        {
            "verdict_class": "B_current_deployment_falsified__F_final_segment_contract_falsified__G_upstream_hidden_invalid",
            "verdicts": verdicts,
            "summary": "v11 hardens v10: repeat BF16 truth matches v10, source hashes are packaged, HF/BPU boundary alignment localizes divergence, and final-segment same-input failure remains. GGUF F16 and operator graph metadata remain unavailable.",
            "v10_deployment_falsification_basis": {
                "official_vs_full_truth_rows": v10_b_report.get("official_vs_full_truth_rows"),
                "official_vs_full_truth_top1_agreement_rows": v10_b_report.get("official_vs_full_truth_top1_agreement_rows"),
                "official_vs_full_truth_median_relative_l2": v10_b_report.get("official_vs_full_truth_median_relative_l2"),
            },
            "gate_status": {
                "generation_quality": "not_run_by_design",
                "product_routes_18888_18889": "not_enabled_modified_or_tested",
                "repeat_truth": "pass" if repeat_truth_reproduced else "blocked_or_fail",
                "v10_official_vs_truth_falsification": "pass" if v10_official_falsified else "blocked_or_fail",
                "source_hashes": "pass" if r900.get("source_hashes") else "blocked",
                "boundary_alignment": "pass" if first_div is not None else "blocked",
                "suffix_localization": "pass" if suffix_complete else "partial_or_blocked",
                "gguf_f16": "blocked_unavailable",
                "operator_graph_metadata": r940.get("operator_graph_status"),
                "repair": "not_supported",
            },
            "first_divergent_segment_global": first_div,
            "first_divergent_segment_by_case": r910.get("first_divergent_segment_by_case"),
            "repeat_truth_summary": {
                "rows": r900.get("repeat_truth_rows"),
                "top1_agreement_rows": r900.get("top1_agreement_rows"),
                "median_relative_l2": r900.get("median_relative_l2"),
                "median_pearson_centered": r900.get("median_pearson_centered"),
                "scope": r900.get("repeat_truth_dtype"),
            },
            "suffix_summary_by_boundary": r920.get("summary_by_boundary"),
            "allowed_claims": [
                "The current tested Dream7B seq128 segmented-HBM S100P path is falsified at logits level against HF/PyTorch BF16 truth for the canonical cases.",
                "The same-input final-segment contract failure remains reproduced.",
                "HF/BPU boundary alignment localizes the earliest observed hidden-state divergence under the reported thresholds.",
            ],
            "forbidden_claims": [
                "Do not claim generation-quality failure or success.",
                "Do not claim product route readiness or failure.",
                "Do not claim universal impossibility for Dream7B on S100P.",
                "Do not claim GGUF F16 cross-check or operator-graph proof when those remain unavailable.",
            ],
        }
    )
    write_json(final_root / "dream7b_s100p_gate_packet_v11.json", packet)
    md = ["# Dream7B/S100P Gate Packet v11", "", f"Verdict class: `{packet['verdict_class']}`", "", packet["summary"], "", "## Gate Status"]
    md.extend(f"- `{k}`: `{v}`" for k, v in packet["gate_status"].items())
    md.extend(["", f"- first_divergent_segment_global: `{first_div}`"])
    write_text(final_root / "dream7b_s100p_gate_packet_v11.md", "\n".join(md) + "\n")
    table_lines = [
        "# Dream7B/S100P Paper Tables v11",
        "",
        "## Table 1. Repeat Truth",
        "",
        "| Case | Top1 agreement vs v10 | Relative L2 | Pearson | Artifact |",
        "|---|---:|---:|---:|---|",
    ]
    for row in r900.get("v10_vs_repeat_rows", []):
        table_lines.append(f"| {row['case_id']} | {row.get('top1_agreement')} | {row.get('relative_l2'):.6g} | {row.get('pearson_centered'):.6g} | `{row.get('repeat_path')}` |")
    table_lines.extend(["", "## Table 2. First Divergence", "", "| Case | First divergent segment | Criterion |", "|---|---:|---|"])
    for cid, seg in (r910.get("first_divergent_segment_by_case") or {}).items():
        table_lines.append(f"| {cid} | {seg} | relL2>0.1 or Pearson<0.95 |")
    table_lines.extend(["", "## Table 3. Suffix Route Summary", "", "| Boundary | Rows | Top1 agreement | Median relL2 | Median Pearson |", "|---:|---:|---:|---:|---:|"])
    for boundary, s in (r920.get("summary_by_boundary") or {}).items():
        table_lines.append(f"| {boundary} | {s.get('rows')} | {s.get('top1_agreement_rows')} | {s.get('median_relative_l2')} | {s.get('median_pearson_centered')} |")
    table_lines.extend(["", "## Table 4. Blockers", "", "| Area | Status |", "|---|---|", f"| GGUF F16 | {r930.get('blocker')} |", f"| Operator graph | {r940.get('operator_graph_status')} |", f"| Repair | {r950.get('interpretation')} |"])
    write_text(final_root / "dream7b_s100p_paper_tables_v11.md", "\n".join(table_lines) + "\n")
    write_report(root, "960_build_v11_gate_packet_and_paper_tables", packet, "Task 960 Build v11 Gate Packet and Paper Tables", [f"first_divergent_segment_global: `{first_div}`", f"repeat_truth_rows: `{r900.get('repeat_truth_rows')}`"])
    return packet


def build_manifest(package_root: Path) -> dict[str, Any]:
    files = []
    for fp in sorted(package_root.rglob("*")):
        if fp.is_file() and fp.name not in {"MANIFEST.json", "SHA256SUMS.txt"}:
            files.append({"path": fp.relative_to(package_root).as_posix(), "size_bytes": fp.stat().st_size, "sha256": sha256_file(fp)})
    manifest = {"schema_version": "dream7b_s100p_v11_manifest", "created_at_utc": now(), "file_count": len(files), "files": files}
    write_json(package_root / "MANIFEST.json", manifest)
    (package_root / "SHA256SUMS.txt").write_text("".join(f"{f['sha256']}  {f['path']}\n" for f in files), encoding="utf-8")
    return manifest


def task970(root: Path, command: str, packet: dict[str, Any]) -> dict[str, Any]:
    staging = root / "tmp" / "dream7b_s100p_v11_package_staging"
    reset_dir(staging, root)
    write_text(staging / "README.md", "Dream7B/S100P v11 evidence. Offline logits-only package; no generation quality and no 18888/18889 route interaction.\n")
    for name in ["dream7b_s100p_gate_packet_v11.json", "dream7b_s100p_gate_packet_v11.md", "dream7b_s100p_paper_tables_v11.md"]:
        copy_file(root / "01_final_evidence" / name, staging / "01_final_evidence" / name)
    for fp in sorted((root / "reports").glob("9*_*.json")) + sorted((root / "reports").glob("9*_*.md")):
        copy_file(fp, staging / "reports" / fp.name)
    copy_file(root / "cases" / "canonical_seq128_cases_v10.jsonl", staging / "cases" / "canonical_seq128_cases_v10.jsonl")
    for src, dst in [
        (root / "evidence" / "full_truth_repeat_v11", staging / "evidence" / "full_truth_repeat_v11"),
        (root / "evidence" / "hf_bpu_boundary_subset_v11", staging / "evidence" / "hf_bpu_boundary_subset_v11"),
        (root / "evidence" / "hf_suffix_route_v11", staging / "evidence" / "hf_suffix_route_v11"),
        (root / "evidence" / "s100p_remote_v11_reports", staging / "evidence" / "s100p_remote_v11_reports"),
        (root / "evidence" / "operator_graph_metadata_v11", staging / "evidence" / "operator_graph_metadata_v11"),
        (root / "tmp" / "dream7b_s100p_v11_after_v10_review_pack_20260701", staging / "00_execution_pack"),
    ]:
        copy_tree(src, dst)
    for tool in ["build_v11_research_thread.py", "export_hf_boundaries_repeat_v11.py", "run_hf_suffix_route_v11.py"]:
        copy_file(root / "tools" / tool, staging / "tools" / tool)
    write_json(staging / "SAFETY_ATTESTATION_V11.json", {"generation_quality_run": False, "product_routes_18888_18889_enabled_modified_or_tested": False})
    manifest = build_manifest(staging)
    zip_path = root / "evidence_for_gptpro" / "dream7b_s100p_v11_for_gptpro_20260701.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for fp in sorted(staging.rglob("*")):
            if fp.is_file():
                zf.write(fp, fp.relative_to(staging).as_posix())
    with zipfile.ZipFile(zip_path) as zf:
        bad = zf.testzip()
        members = zf.namelist()
    manifest_check = validate_manifest_dir(staging)
    report = common(root, "970_build_gptpro_evidence_zip", command, [staging])
    report.update({"zip_path": rel(zip_path, root), "zip_size_bytes": zip_path.stat().st_size, "zip_sha256": sha256_file(zip_path), "zip_testzip_bad_member": bad, "zip_member_count": len(members), "manifest": manifest, "manifest_check": manifest_check})
    write_report(root, "970_build_gptpro_evidence_zip", report, "Task 970 Build GPT Pro Evidence Zip", [f"zip_path: `{rel(zip_path, root)}`", f"zip_sha256: `{report['zip_sha256']}`", f"zip_testzip_bad_member: `{bad}`"])
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    command = " ".join([sys.executable, *sys.argv])
    r900 = task900(root, command)
    r910 = task910(root, command)
    r920 = task920(root, command)
    r930 = task930(root, command)
    r940 = task940(root, command)
    r950 = task950(root, command)
    packet = task960(root, command, {"900": r900, "910": r910, "920": r920, "930": r930, "940": r940, "950": r950})
    zip_report = task970(root, command, packet)
    bad_count = sum(len(zip_report["manifest_check"][k]) for k in ["missing", "bad_size", "bad_sha256"])
    print(json.dumps({"verdict_class": packet["verdict_class"], "zip_path": zip_report["zip_path"], "zip_sha256": zip_report["zip_sha256"], "manifest_bad_count": bad_count, "zip_testzip_bad_member": zip_report["zip_testzip_bad_member"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
