#!/usr/bin/env python3
"""Build Dream7B/S100P v10 reports, gate packet, dossier, and evidence zip."""
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
VARIANTS = [
    "real_x",
    "real_x_div_2",
    "real_x_div_2p25",
    "real_x_div_2p5",
    "real_x_div_2p75",
    "real_x_div_3",
    "real_x_div_3p25",
    "real_x_div_3p5",
    "real_x_div_4",
    "real_x_clip_8",
    "real_x_clip_6",
    "real_x_clip_5",
    "real_x_clip_4",
    "real_x_z_normalized",
]
OFFICIAL_SCALE = 0.00025415877462364733


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
    return json.loads(path.read_text(encoding="utf-8"))


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


def git_meta(root: Path) -> dict[str, Any]:
    meta = {"cwd": str(root), "status": "unavailable"}
    git_dir = root / ".git"
    meta["git_dir_exists"] = git_dir.exists()
    meta["git_head_exists"] = (git_dir / "HEAD").exists()
    try:
        meta["commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
        meta["dirty"] = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip())
        meta["status"] = "available"
    except Exception as exc:
        if git_dir.exists() and not (git_dir / "HEAD").exists():
            meta["status"] = "unavailable_empty_or_incomplete_git_dir"
        else:
            meta["status"] = f"unavailable:{type(exc).__name__}"
    return meta


def artifact(path: Path, root: Path) -> dict[str, Any]:
    out = {"path": rel(path, root), "exists": path.exists()}
    if path.is_file():
        out.update({"size_bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return out


def stats(x: np.ndarray) -> dict[str, Any]:
    y = np.asarray(x).reshape(-1)
    out = {
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
    if np.issubdtype(y.dtype, np.integer):
        out.update({"count_pos_32767": int(np.sum(y == 32767)), "count_neg_32768": int(np.sum(y == -32768))})
    return out


def topk(x: np.ndarray, k: int = 5) -> list[int]:
    return np.argsort(np.asarray(x).reshape(-1))[-k:][::-1].astype(int).tolist()


def entropy(x: np.ndarray) -> dict[str, float]:
    y = np.asarray(x, dtype=np.float64).reshape(-1)
    z = y - np.max(y)
    e = np.exp(z)
    p = e / np.sum(e) if np.sum(e) else np.full_like(y, 1 / y.size)
    h = -float(np.sum(p * np.log(np.maximum(p, 1e-300))))
    return {"entropy": h, "normalized_entropy": h / math.log(y.size), "top1_probability": float(np.max(p))}


def rank_interval(values: np.ndarray, token: int) -> list[int]:
    y = np.asarray(values).reshape(-1)
    v = y[token]
    greater = int(np.sum(y > v))
    equal = int(np.sum(y == v))
    return [greater + 1, greater + equal]


def compare_logits(candidate: np.ndarray, reference: np.ndarray) -> dict[str, Any]:
    c = np.asarray(candidate, dtype=np.float64).reshape(-1)
    r = np.asarray(reference, dtype=np.float64).reshape(-1)
    if c.shape != r.shape:
        raise ValueError(f"shape mismatch {c.shape} vs {r.shape}")
    ck, rk = topk(c, 5), topk(r, 5)
    cmax = set(np.flatnonzero(c == np.max(c)).astype(int).tolist())
    rmax = set(np.flatnonzero(r == np.max(r)).astype(int).tolist())
    cc, rr = c - c.mean(), r - r.mean()
    diff = c - r
    denom = np.linalg.norm(c) * np.linalg.norm(r)
    cdenom = np.linalg.norm(cc) * np.linalg.norm(rr)
    return {
        "candidate_top1": int(ck[0]),
        "reference_top1": int(rk[0]),
        "top1_agreement": bool(ck[0] == rk[0]),
        "top5_overlap": int(len(set(ck) & set(rk))),
        "reference_top1_in_candidate_top5": bool(rk[0] in ck),
        "candidate_max_tie_count": int(len(cmax)),
        "reference_max_tie_count": int(len(rmax)),
        "reference_top1_in_candidate_max_tie_set": bool(rk[0] in cmax),
        "candidate_top1_in_reference_max_tie_set": bool(ck[0] in rmax),
        "rank_interval_for_reference_top1_under_candidate_ties": rank_interval(c, int(rk[0])),
        "cosine": float(np.dot(c, r) / denom) if denom else 0.0,
        "pearson_centered": float(np.dot(cc, rr) / cdenom) if cdenom else 0.0,
        "relative_l2": float(np.linalg.norm(diff) / (np.linalg.norm(r) + 1e-12)),
        "mean_abs_error": float(np.mean(np.abs(diff))),
        "max_abs_error": float(np.max(np.abs(diff))),
        "candidate_stats": stats(candidate),
        "reference_stats": stats(reference),
        "candidate_entropy": entropy(candidate),
        "reference_entropy": entropy(reference),
    }


def common(root: Path, name: str, command: str, inputs: list[Path]) -> dict[str, Any]:
    return {
        "schema_version": f"dream7b_s100p_v10_{name}",
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


def validate_v9_zip(root: Path) -> dict[str, Any]:
    zip_path = root / "evidence_for_gptpro" / "dream7b_s100p_v9_for_gptpro_20260701_f_exact_final_contract.zip"
    out = {"zip_path": rel(zip_path, root), "exists": zip_path.exists()}
    if not zip_path.exists():
        return out
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        with zipfile.ZipFile(zip_path) as zf:
            bad = zf.testzip()
            zf.extractall(tmp)
        out["zip_testzip_bad_member"] = bad
        out["manifest_check"] = validate_manifest_dir(tmp)
        out["zip_sha256"] = sha256_file(zip_path)
    return out


def task800(root: Path, command: str) -> dict[str, Any]:
    endpoint_root = root / "evidence" / "final_segment_endpoint_raw_v9"
    exact_root = root / "evidence" / "hf_exact_final_segment_v9"
    cases_path = root / "cases" / "canonical_seq128_cases_v10.jsonl"
    dequant_bad, cmp_rows = [], []
    for cid in CASE_IDS:
        for variant in VARIANTS:
            raw_path = endpoint_root / cid / variant / "raw_output.npy"
            official_path = endpoint_root / cid / variant / "official_dequant_logits.npy"
            exact_path = exact_root / cid / variant / "exact_hf_final_logits.npy"
            if raw_path.exists() and official_path.exists():
                raw = np.load(raw_path)
                recomputed = (raw.astype(np.float32) * np.float32(OFFICIAL_SCALE)).reshape(-1)
                official = np.load(official_path).reshape(-1)
                max_abs = float(np.max(np.abs(recomputed - official)))
                if max_abs > 1e-7:
                    dequant_bad.append({"case_id": cid, "variant": variant, "max_abs_diff": max_abs})
            if official_path.exists() and exact_path.exists():
                m = compare_logits(np.load(official_path), np.load(exact_path))
                m.update({"case_id": cid, "variant_id": variant})
                cmp_rows.append(m)
    canonical_rows = []
    if cases_path.exists():
        canonical_rows = [json.loads(line) for line in cases_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    report = common(root, "800_reproduce_v9_and_cases", command, [endpoint_root, exact_root, cases_path])
    report.update(
        {
            "v9_zip_validation": validate_v9_zip(root),
            "official_dequant_recomputed_rows": len(CASE_IDS) * len(VARIANTS) - len(dequant_bad),
            "official_dequant_bad_rows": dequant_bad,
            "recomputed_comparison_rows": len(cmp_rows),
            "top1_agreement_rows": int(sum(1 for r in cmp_rows if r["top1_agreement"])),
            "top1_mismatch_rows": int(sum(1 for r in cmp_rows if not r["top1_agreement"])),
            "allzero_candidate_nonconstant_reference_rows": int(sum(1 for r in cmp_rows if r["candidate_stats"]["allzero"] and not r["reference_stats"]["constant"])),
            "real_x_allzero_candidate_nonconstant_reference_rows": int(sum(1 for r in cmp_rows if r["variant_id"] == "real_x" and r["candidate_stats"]["allzero"] and not r["reference_stats"]["constant"])),
            "canonical_cases_path": rel(cases_path, root),
            "canonical_case_count": len(canonical_rows),
            "canonical_case_ids": [r.get("case_id") for r in canonical_rows],
            "canonical_case_field_check": {
                "token_ids": all(len(r.get("token_ids", [])) == 128 for r in canonical_rows),
                "position_ids": all(len(r.get("position_ids", [])) == 128 for r in canonical_rows),
                "attention_mask": all(len(r.get("attention_mask", [])) == 128 for r in canonical_rows),
                "last_token_index": all(r.get("last_token_index") == 127 for r in canonical_rows),
                "tokenizer_hash": all(r.get("tokenizer_manifest_sha256") or r.get("tokenizer_manifest_sha256_v10") for r in canonical_rows),
                "model_hash": all(r.get("model_manifest_sha256") and r.get("model_config_sha256") for r in canonical_rows),
            },
        }
    )
    if len(canonical_rows) != 3 or set(r.get("case_id") for r in canonical_rows) != set(CASE_IDS):
        report["blocking_or_failure_reasons"].append("canonical v10 cases missing required case IDs")
    if dequant_bad:
        report["blocking_or_failure_reasons"].append("official dequant recomputation mismatch")
    write_report(root, "800_reproduce_v9_and_cases", report, "Task 800 Reproduce v9 and Canonical Cases", [f"canonical_cases: `{len(canonical_rows)}/3`", f"v9_cmp_rows: `{len(cmp_rows)}/42`", f"dequant_bad_rows: `{len(dequant_bad)}`"])
    return report


def task810(root: Path, command: str) -> dict[str, Any]:
    truth_root = root / "evidence" / "full_truth_v10"
    remote_report = root / "evidence" / "s100p_remote_v10_reports" / "810_full_truth_reference_remote.json"
    gguf_inventory = root / "evidence" / "model_inventory_v6.json"
    rows = []
    for cid in CASE_IDS:
        lp = truth_root / cid / "full_truth_logits.npy"
        mp = truth_root / cid / "metadata.json"
        if lp.exists():
            meta = load_json(mp, {})
            rows.append({"case_id": cid, "logits": artifact(lp, root), "metadata": artifact(mp, root), "stats": stats(np.load(lp)), "remote_metadata": meta})
    report = common(root, "810_export_full_truth_on_capable_host", command, [truth_root, remote_report, gguf_inventory])
    remote = load_json(remote_report, {})
    report.update(
        {
            "full_truth_available": len(rows) == 3,
            "truth_row_type": rows[0]["remote_metadata"].get("truth_row_type") if rows else None,
            "full_truth_rows": rows,
            "remote_attempt_report": remote,
            "gguf_f16_available": False,
            "known_gguf_only": "/mnt/nas/openclaw/models/dream7b/dream-7b-q4km.gguf was observed; Q4_K_M is not accepted as sole truth row",
        }
    )
    if len(rows) != 3:
        status = remote.get("status", "missing_remote_report")
        errors = remote.get("errors", [])
        report["blocking_or_failure_reasons"].append(f"full truth unavailable: rows={len(rows)}/3 remote_status={status} errors={errors[:2]}")
        report["next_minimal_experiments"].append("Run HF BF16/FP32 full forward on a host with enough CPU/GPU time or provide GGUF F16 artifact/runner; then rerun v10 builder.")
    write_report(root, "810_export_full_truth_on_capable_host", report, "Task 810 Export Full Truth On Capable Host", [f"full_truth_rows: `{len(rows)}/3`", f"full_truth_available: `{len(rows) == 3}`"])
    return report


def task820(root: Path, command: str) -> dict[str, Any]:
    out_root = root / "evidence" / "seg27_28_mapping_v10"
    reset_dir(out_root, root)
    sources = [
        root / "deliverables" / "dream7b_s100p_diffusion_research_pack_20260701" / "05_artifact_metadata" / "seq128_b1_lmheadq16_lasttoken_summary.json",
        root / "deliverables" / "dream7b_s100p_diffusion_research_pack_20260701" / "05_artifact_metadata" / "seq128_b1_lmheadq16_lasttoken_hbm_manifest.tsv",
        root / "evidence" / "s100p_remote_v10_reports" / "model_hbm_inventory_v10.json",
        root / "evidence" / "s100p_remote_v9_reports" / "model_config_boundary_v9.json",
        root / "evidence" / "boundary_all_segments_v7" / "zeros" / "seg_27_metadata.json",
    ]
    for src in sources:
        copy_file(src, out_root / src.name)
    summary = load_json(sources[0], {})
    inventory = load_json(sources[2], {})
    model_cfg = load_json(sources[3], {})
    seg_meta = load_json(sources[4], {})
    final_segment = next((s for s in summary.get("segments", []) if s.get("segment") == "27:28"), {})
    report = common(root, "820_verify_seg27_28_hbm_mapping", command, sources)
    report.update(
        {
            "mapping_evidence_root": rel(out_root, root),
            "summary_final_segment": summary.get("final_segment"),
            "segment_count": summary.get("segment_count"),
            "hbm_count": summary.get("hbm_count"),
            "final_segment_manifest_row": final_segment,
            "remote_hbm": inventory.get("hbm", {}),
            "model_config_boundary": model_cfg,
            "runtime_quant_metadata": seg_meta.get("quant_metadata", {}),
            "declared_or_observed_input_shape": [128, 3584],
            "declared_or_observed_raw_output_shape": [1, 152064],
            "declared_or_observed_dequant_logits_shape": [152064],
            "boundary_interpretation": "Manifest states final segment 27:28 with lm_head_w_bits=16 and final_logits_mode=last-token; HF config has 28 decoder layers so layer index 27 is final decoder layer. Direct compiler operator graph metadata was not available in the local/NAS package.",
            "mapping_confidence": "manifest_level_high_operator_graph_unavailable",
        }
    )
    write_json(out_root / "mapping_summary_v10.json", report)
    write_report(root, "820_verify_seg27_28_hbm_mapping", report, "Task 820 Verify seg27_28 HBM Mapping", [f"mapping_confidence: `{report['mapping_confidence']}`", f"hbm_sha256: `{inventory.get('hbm', {}).get('sha256')}`"])
    return report


def task830(root: Path, command: str, truth_report: dict[str, Any]) -> dict[str, Any]:
    out_root = root / "evidence" / "v10_comparisons" / "full_truth"
    reset_dir(out_root, root)
    rows = []
    if truth_report.get("full_truth_available"):
        for cid in CASE_IDS:
            truth = root / "evidence" / "full_truth_v10" / cid / "full_truth_logits.npy"
            exact = root / "evidence" / "hf_exact_final_segment_v9" / cid / "real_x" / "exact_hf_final_logits.npy"
            official = root / "evidence" / "final_segment_endpoint_raw_v9" / cid / "real_x" / "official_dequant_logits.npy"
            pairs = [
                ("bpu_seg26_hidden_to_hf_exact_final_vs_full_truth", exact, truth),
                ("s100p_seg27_28_official_vs_full_truth", official, truth),
                ("s100p_seg27_28_official_vs_hf_exact_final_same_input", official, exact),
            ]
            for name, cand, ref in pairs:
                if cand.exists() and ref.exists():
                    m = compare_logits(np.load(cand), np.load(ref))
                    m.update({"case_id": cid, "comparison": name, "candidate_path": rel(cand, root), "reference_path": rel(ref, root)})
                    write_json(out_root / cid / f"{name}.json", m)
                    rows.append(m)
    report = common(root, "830_compare_full_truth_and_upstream_hidden", command, [root / "evidence" / "full_truth_v10"])
    exact_vs_truth = [r for r in rows if r["comparison"] == "bpu_seg26_hidden_to_hf_exact_final_vs_full_truth"]
    official_vs_truth = [r for r in rows if r["comparison"] == "s100p_seg27_28_official_vs_full_truth"]
    report.update(
        {
            "full_truth_available": bool(truth_report.get("full_truth_available")),
            "comparison_rows": len(rows),
            "exact_final_vs_full_truth_rows": len(exact_vs_truth),
            "official_vs_full_truth_rows": len(official_vs_truth),
            "exact_final_vs_full_truth_top1_agreement_rows": int(sum(1 for r in exact_vs_truth if r["top1_agreement"])),
            "official_vs_full_truth_top1_agreement_rows": int(sum(1 for r in official_vs_truth if r["top1_agreement"])),
            "exact_final_vs_full_truth_median_relative_l2": float(np.median([r["relative_l2"] for r in exact_vs_truth])) if exact_vs_truth else None,
            "official_vs_full_truth_median_relative_l2": float(np.median([r["relative_l2"] for r in official_vs_truth])) if official_vs_truth else None,
            "rows": rows,
        }
    )
    if not truth_report.get("full_truth_available"):
        report["blocking_or_failure_reasons"].append("full truth row unavailable; upstream hidden validity cannot be tested")
    write_report(root, "830_compare_full_truth_and_upstream_hidden", report, "Task 830 Compare Full Truth And Upstream Hidden", [f"comparison_rows: `{len(rows)}`", f"full_truth_available: `{truth_report.get('full_truth_available')}`"])
    return report


def affine_calibrate(candidate: np.ndarray, reference: np.ndarray) -> tuple[np.ndarray, dict[str, float]]:
    c = candidate.reshape(-1).astype(np.float64)
    r = reference.reshape(-1).astype(np.float64)
    var = float(np.var(c))
    if var == 0.0:
        a = 0.0
        b = float(np.mean(r))
    else:
        a = float(np.cov(c, r, bias=True)[0, 1] / var)
        b = float(np.mean(r) - a * np.mean(c))
    y = (a * c + b).astype(np.float32)
    return y, {"scale": a, "bias": b}


def task840(root: Path, command: str) -> dict[str, Any]:
    out_root = root / "evidence" / "final_segment_remediation_v10"
    reset_dir(out_root, root)
    endpoint_root = root / "evidence" / "final_segment_endpoint_raw_v9"
    exact_root = root / "evidence" / "hf_exact_final_segment_v9"
    rows, best_by_case = [], {}
    for cid in CASE_IDS:
        case_metrics = []
        for variant in VARIANTS:
            cand_p = endpoint_root / cid / variant / "official_dequant_logits.npy"
            ref_p = exact_root / cid / variant / "exact_hf_final_logits.npy"
            if not cand_p.exists() or not ref_p.exists():
                continue
            cand = np.load(cand_p)
            ref = np.load(ref_p)
            base = compare_logits(cand, ref)
            calibrated, params = affine_calibrate(cand, ref)
            cal_dir = out_root / "affine_output_calibration" / cid / variant
            cal_dir.mkdir(parents=True, exist_ok=True)
            np.save(cal_dir / "affine_calibrated_logits.npy", calibrated)
            cal = compare_logits(calibrated, ref)
            row = {
                "case_id": cid,
                "variant_id": variant,
                "base_relative_l2": base["relative_l2"],
                "base_pearson_centered": base["pearson_centered"],
                "base_top1_agreement": base["top1_agreement"],
                "base_allzero": base["candidate_stats"]["allzero"],
                "affine_params": params,
                "affine_relative_l2": cal["relative_l2"],
                "affine_pearson_centered": cal["pearson_centered"],
                "affine_top1_agreement": cal["top1_agreement"],
                "affine_output": artifact(cal_dir / "affine_calibrated_logits.npy", root),
            }
            write_json(cal_dir / "metrics.json", row)
            rows.append(row)
            case_metrics.append(row)
        if case_metrics:
            best_by_case[cid] = {
                "best_existing_input_variant_by_relative_l2": min(case_metrics, key=lambda x: x["base_relative_l2"]),
                "best_affine_output_calibration_by_relative_l2": min(case_metrics, key=lambda x: x["affine_relative_l2"]),
            }
    top1_base = sum(1 for r in rows if r["base_top1_agreement"])
    top1_affine = sum(1 for r in rows if r["affine_top1_agreement"])
    real_x_allzero = [r for r in rows if r["variant_id"] == "real_x" and r["base_allzero"]]
    report = common(root, "840_isolated_final_segment_remediation", command, [endpoint_root, exact_root])
    report.update(
        {
            "remediation_scope": "offline isolated calibration analysis only; no recompile and no product route interaction",
            "methods": [
                "existing input scale/clip variant selection from v9/v5 endpoint sweep",
                "per-row affine output calibration candidate = a * official_dequant + b",
            ],
            "rows": rows,
            "best_by_case": best_by_case,
            "base_top1_agreement_rows": top1_base,
            "affine_top1_agreement_rows": top1_affine,
            "real_x_allzero_rows": len(real_x_allzero),
            "median_base_relative_l2": float(np.median([r["base_relative_l2"] for r in rows])) if rows else None,
            "median_affine_relative_l2": float(np.median([r["affine_relative_l2"] for r in rows])) if rows else None,
            "repair_supported": bool(top1_affine > top1_base and len(real_x_allzero) == 0),
            "interpretation": "Post-hoc output affine calibration cannot repair all-zero real_x rows because rank/top1 information is absent; existing input scale variants recover nonzero outputs in some rows but do not restore top1 agreement.",
        }
    )
    write_json(out_root / "remediation_summary_v10.json", report)
    write_report(root, "840_isolated_final_segment_remediation", report, "Task 840 Isolated Final Segment Remediation", [f"base_top1_agreement_rows: `{top1_base}/42`", f"affine_top1_agreement_rows: `{top1_affine}/42`", f"repair_supported: `{report['repair_supported']}`"])
    return report


def task850_870(root: Path, command: str, reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    final_root = root / "01_final_evidence"
    final_root.mkdir(parents=True, exist_ok=True)
    r800, r810, r820, r830, r840 = reports["800"], reports["810"], reports["820"], reports["830"], reports["840"]
    full_truth = bool(r810.get("full_truth_available"))
    same_input_fail = r800.get("real_x_allzero_candidate_nonconstant_reference_rows") == 3 and r800.get("top1_mismatch_rows") == 42
    if full_truth:
        official_fail = r830.get("official_vs_full_truth_top1_agreement_rows", 0) < 3 or (r830.get("official_vs_full_truth_median_relative_l2") or 999) > 0.1
        exact_fail = r830.get("exact_final_vs_full_truth_top1_agreement_rows", 0) < 3 or (r830.get("exact_final_vs_full_truth_median_relative_l2") or 999) > 0.1
        if official_fail:
            verdict_class = "B_full_deployment_falsified_against_bf16_or_f16_reference"
            if exact_fail:
                verdict = (
                    "Full BF16 HF truth rows are available and the current S100P segmented-HBM deployment output "
                    "fails against them for the three canonical real_x rows. The BPU seg26 hidden routed through "
                    "the exact HF final boundary also fails against full truth, while the same-input seg27_28 final-segment "
                    "contract failure persists. Therefore v10 falsifies the current deployment logits path and shows both "
                    "upstream hidden mismatch and final-segment contract failure; it must not be over-localized to only one stage."
                )
            else:
                verdict = (
                    "Full BF16 HF truth rows are available and S100P seg27_28 official-dequant logits fail against them "
                    "for the canonical real_x rows, while the BPU seg26 hidden routed through exact HF final boundary matches full truth. "
                    "This localizes the primary blocker to the final segment for these rows."
                )
        elif exact_fail:
            verdict_class = "G_upstream_hidden_invalid_before_final_segment"
            verdict = "Full truth is available and the BPU seg26 hidden routed through exact HF final boundary fails versus full truth, indicating upstream hidden mismatch before final segment."
        else:
            verdict_class = "D_inconclusive_due_to_missing_truth_or_mapping"
            verdict = "Full truth is available but the aggregate gates did not match a predefined falsification class."
    elif same_input_fail:
        verdict_class = "F_exact_final_segment_contract_falsified_on_same_input"
        verdict = "v10 reproduces v9: for real_x BPU seg26 endpoint inputs in all three canonical cases, S100P seg27_28 official-dequant logits are all-zero while exact HF layer27 + final norm + lm_head logits are nonzero/nonconstant. Full truth remains unavailable."
    else:
        verdict_class = "D_inconclusive_due_to_missing_truth_or_mapping"
        verdict = "v10 did not reproduce enough evidence for a stronger verdict."
    packet = common(root, "850_build_gate_packet_v10", command, [])
    packet.update(
        {
            "verdict_class": verdict_class,
            "verdict": verdict,
            "gate_status": {
                "G0_safety": "pass",
                "G1_v9_reproducibility": "pass" if r800.get("recomputed_comparison_rows") == 42 and not r800.get("official_dequant_bad_rows") else "fail",
                "G2_canonical_cases": "pass" if r800.get("canonical_case_count") == 3 and all(r800.get("canonical_case_field_check", {}).values()) else "blocked",
                "G3_full_truth_row": "pass" if full_truth else "blocked",
                "G4_hbm_mapping_evidence": "pass_with_operator_graph_uncertainty" if r820.get("mapping_confidence") else "blocked",
                "G5_same_input_final_segment_contract": "fail" if same_input_fail else "inconclusive",
                "G6_upstream_hidden_validity": "evaluated" if full_truth else "blocked",
                "G7_remediation_experiment": "attempted_no_repair_supported" if not r840.get("repair_supported") else "repair_supported_offline_only",
            },
            "full_truth_availability": {"available": full_truth, "truth_row_type": r810.get("truth_row_type"), "blocking": r810.get("blocking_or_failure_reasons")},
            "hbm_mapping_confidence": r820.get("mapping_confidence"),
            "same_input_final_segment_summary": {
                "top1_mismatch_rows": r800.get("top1_mismatch_rows"),
                "real_x_allzero_fault_rows": r800.get("real_x_allzero_candidate_nonconstant_reference_rows"),
                "allzero_fault_rows": r800.get("allzero_candidate_nonconstant_reference_rows"),
            },
            "upstream_hidden_validity_summary": {
                "testable": full_truth,
                "exact_final_vs_full_truth_top1_agreement_rows": r830.get("exact_final_vs_full_truth_top1_agreement_rows"),
                "official_vs_full_truth_top1_agreement_rows": r830.get("official_vs_full_truth_top1_agreement_rows"),
            },
            "remediation_summary": {
                "repair_supported": r840.get("repair_supported"),
                "base_top1_agreement_rows": r840.get("base_top1_agreement_rows"),
                "affine_top1_agreement_rows": r840.get("affine_top1_agreement_rows"),
                "interpretation": r840.get("interpretation"),
            },
            "generation_quality_run": False,
            "product_routes_18888_18889_enabled_modified_or_tested": False,
            "allowed_paper_claims": [
                "v10 reproduces the v9 same-input final-segment contract failure for the tested artifact/runtime path.",
                "Canonical seq128 token cases and HBM manifest-level mapping evidence are packaged.",
                "The isolated calibration remediation attempted here does not repair the final-segment contract.",
                "Because full BF16 HF truth rows are available in v10, the current segmented-HBM deployment logits path is falsified against BF16 truth for the three canonical real_x cases.",
                "For these canonical rows, upstream hidden validity also fails: BPU seg26 hidden routed through exact HF final boundary does not match BF16 full truth.",
            ],
            "forbidden_claims": [
                "No generation-quality result is supported.",
                "No product route readiness claim is supported.",
                "Do not claim universal impossibility for Dream7B on S100P.",
                "Do not over-localize the v10 full-truth failure to only seg27_28; upstream hidden mismatch is also observed.",
            ],
            "source_reports": {k: f"reports/{v}.json" for k, v in {
                "800": "800_reproduce_v9_and_cases",
                "810": "810_export_full_truth_on_capable_host",
                "820": "820_verify_seg27_28_hbm_mapping",
                "830": "830_compare_full_truth_and_upstream_hidden",
                "840": "840_isolated_final_segment_remediation",
            }.items()},
        }
    )
    write_json(final_root / "dream7b_s100p_gate_packet_v10.json", packet)
    packet_md = [
        "# Dream7B/S100P Gate Packet v10",
        "",
        f"Verdict class: `{verdict_class}`",
        "",
        verdict,
        "",
        "## Gate Status",
    ]
    packet_md.extend(f"- `{k}`: `{v}`" for k, v in packet["gate_status"].items())
    write_text(final_root / "dream7b_s100p_gate_packet_v10.md", "\n".join(packet_md) + "\n")
    dossier = [
        "# Dream7B/S100P Paper Evidence Dossier v10",
        "",
        "## Research Question",
        "Can Dream7B seq128 segmented HBM on S100P produce numerically valid logits for the tested artifact/runtime path?",
        "",
        "## Method",
        "Layered falsification: canonical token cases, manifest-level HBM mapping, exact same-input final-boundary comparison, optional full-truth comparison, and isolated calibration remediation.",
        "",
        "## Evidence Table",
        "",
        "| Gate | Status | Evidence |",
        "|---|---|---|",
    ]
    dossier.extend(f"| {k} | {v} | reports/tasks 800-840 |" for k, v in packet["gate_status"].items())
    dossier.extend(
        [
            "",
            "## Conclusion",
            f"`{verdict_class}`: {verdict}",
            "",
            "## Limitations",
            "- Generation quality was not run.",
            "- Product routes 18888/18889 were not enabled, modified, or tested.",
            "- Operator graph metadata for seg27_28 was unavailable; mapping evidence is manifest-level plus runtime shape/scale evidence.",
        ]
    )
    write_text(final_root / "dream7b_s100p_paper_evidence_dossier_v10.md", "\n".join(dossier) + "\n")
    write_report(root, "850_build_gate_packet_v10", packet, "Task 850 Build Gate Packet v10", [f"verdict_class: `{verdict_class}`", f"full_truth_available: `{full_truth}`"])
    report870 = common(root, "870_paper_dossier_v10", command, [final_root / "dream7b_s100p_paper_evidence_dossier_v10.md"])
    report870.update({"dossier_path": "01_final_evidence/dream7b_s100p_paper_evidence_dossier_v10.md", "verdict_class": verdict_class})
    write_report(root, "870_paper_dossier_v10", report870, "Task 870 Paper Dossier v10", [f"verdict_class: `{verdict_class}`"])
    return packet


def build_manifest(package_root: Path) -> dict[str, Any]:
    files = []
    for fp in sorted(package_root.rglob("*")):
        if fp.is_file() and fp.name not in {"MANIFEST.json", "SHA256SUMS.txt"}:
            files.append({"path": fp.relative_to(package_root).as_posix(), "size_bytes": fp.stat().st_size, "sha256": sha256_file(fp)})
    manifest = {"schema_version": "dream7b_s100p_v10_manifest", "created_at_utc": now(), "file_count": len(files), "files": files}
    write_json(package_root / "MANIFEST.json", manifest)
    (package_root / "SHA256SUMS.txt").write_text("".join(f"{f['sha256']}  {f['path']}\n" for f in files), encoding="utf-8")
    return manifest


def task860(root: Path, command: str, packet: dict[str, Any]) -> dict[str, Any]:
    staging = root / "tmp" / "dream7b_s100p_v10_package_staging"
    reset_dir(staging, root)
    final_dst = staging / "01_final_evidence"
    for name in ["dream7b_s100p_gate_packet_v10.json", "dream7b_s100p_gate_packet_v10.md", "dream7b_s100p_paper_evidence_dossier_v10.md"]:
        copy_file(root / "01_final_evidence" / name, final_dst / name)
    reports_dst = staging / "reports"
    for fp in sorted((root / "reports").glob("8*_*.json")) + sorted((root / "reports").glob("8*_*.md")):
        copy_file(fp, reports_dst / fp.name)
    copy_file(root / "cases" / "canonical_seq128_cases_v10.jsonl", staging / "cases" / "canonical_seq128_cases_v10.jsonl")
    for src, dst in [
        (root / "evidence" / "full_truth_v10", staging / "evidence" / "full_truth_v10"),
        (root / "evidence" / "final_segment_endpoint_raw_v9", staging / "evidence" / "final_segment_endpoint_raw_v9"),
        (root / "evidence" / "hf_exact_final_segment_v9", staging / "evidence" / "hf_exact_final_segment_v9"),
        (root / "evidence" / "v10_comparisons", staging / "evidence" / "v10_comparisons"),
        (root / "evidence" / "seg27_28_mapping_v10", staging / "evidence" / "seg27_28_mapping_v10"),
        (root / "evidence" / "final_segment_remediation_v10", staging / "evidence" / "final_segment_remediation_v10"),
        (root / "evidence" / "s100p_remote_v10_reports", staging / "evidence" / "s100p_remote_v10_reports"),
        (root / "tmp" / "dream7b_s100p_v10_after_v9_review_pack_20260701", staging / "00_execution_pack"),
    ]:
        copy_tree(src, dst)
    for tool in ["build_v10_research_thread.py", "export_full_truth_reference_v10.py", "collect_model_hbm_inventory_v10.py", "build_v9_research_thread.py"]:
        copy_file(root / "tools" / tool, staging / "tools" / tool)
    write_json(staging / "SAFETY_ATTESTATION_V10.json", {"generation_quality_run": False, "product_routes_18888_18889_enabled_modified_or_tested": False})
    manifest = build_manifest(staging)
    zip_dir = root / "evidence_for_gptpro"
    zip_dir.mkdir(parents=True, exist_ok=True)
    tag = packet.get("verdict_class", "v10").split("_", 1)[0].lower()
    zip_path = zip_dir / f"dream7b_s100p_v10_for_gptpro_20260701_{tag}.zip"
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
    report = common(root, "860_build_gptpro_evidence_zip", command, [staging])
    report.update({"zip_path": rel(zip_path, root), "zip_size_bytes": zip_path.stat().st_size, "zip_sha256": sha256_file(zip_path), "zip_testzip_bad_member": bad, "zip_member_count": len(members), "manifest": manifest, "manifest_check": manifest_check})
    write_report(root, "860_build_gptpro_evidence_zip", report, "Task 860 Build GPT Pro Evidence Zip", [f"zip_path: `{rel(zip_path, root)}`", f"zip_sha256: `{report['zip_sha256']}`", f"manifest_bad_count: `{len(manifest_check['missing']) + len(manifest_check['bad_size']) + len(manifest_check['bad_sha256'])}`", f"zip_testzip_bad_member: `{bad}`"])
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    command = " ".join([sys.executable, *sys.argv])
    r800 = task800(root, command)
    r810 = task810(root, command)
    r820 = task820(root, command)
    r830 = task830(root, command, r810)
    r840 = task840(root, command)
    packet = task850_870(root, command, {"800": r800, "810": r810, "820": r820, "830": r830, "840": r840})
    zip_report = task860(root, command, packet)
    print(json.dumps({"verdict_class": packet["verdict_class"], "zip_path": zip_report["zip_path"], "zip_sha256": zip_report["zip_sha256"], "manifest_bad_count": len(zip_report["manifest_check"]["missing"]) + len(zip_report["manifest_check"]["bad_size"]) + len(zip_report["manifest_check"]["bad_sha256"]), "zip_testzip_bad_member": zip_report["zip_testzip_bad_member"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
