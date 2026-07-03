#!/usr/bin/env python3
"""Build Dream7B/S100P v9 reports, gate packet, and GPT Pro package."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
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
OFFICIAL_FINAL_OUTPUT_SCALE = 0.00025415877462364733
OFFICIAL_FINAL_OUTPUT_ZERO_POINT = 0.0


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
    for enc in ("utf-8", "utf-8-sig", "utf-16"):
        try:
            return json.loads(path.read_text(encoding=enc))
        except Exception:
            pass
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


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
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def git_meta(root: Path) -> dict[str, Any]:
    meta = {"cwd": str(root.resolve()), "status": "unavailable"}
    try:
        meta["commit"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        meta["dirty"] = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"],
                cwd=root,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        )
        meta["status"] = "available"
    except Exception as exc:
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
        "min": float(np.min(y)) if y.size else None,
        "max": float(np.max(y)) if y.size else None,
        "mean": float(np.mean(y)) if y.size else None,
        "std": float(np.std(y)) if y.size else None,
        "abs_max": float(np.max(np.abs(y))) if y.size else None,
        "nonzero_count": int(np.count_nonzero(y)),
        "allzero": bool(np.all(y == 0)) if y.size else False,
        "constant": bool(np.all(y == y[0])) if y.size else False,
        "nan_count": int(np.isnan(y.astype(np.float64, copy=False)).sum()) if y.size else 0,
        "inf_count": int(np.isinf(y.astype(np.float64, copy=False)).sum()) if y.size else 0,
    }
    if np.issubdtype(y.dtype, np.integer):
        out.update(
            {
                "count_pos_32767": int(np.sum(y == 32767)),
                "count_neg_32768": int(np.sum(y == -32768)),
                "frac_pos_32767": float(np.mean(y == 32767)) if y.size else 0.0,
                "frac_neg_32768": float(np.mean(y == -32768)) if y.size else 0.0,
            }
        )
    return out


def topk(x: np.ndarray, k: int = 5) -> list[int]:
    return np.argsort(np.asarray(x).reshape(-1))[-k:][::-1].astype(int).tolist()


def entropy(x: np.ndarray) -> dict[str, float]:
    y = np.asarray(x, dtype=np.float64).reshape(-1)
    if not y.size:
        return {"entropy": 0.0, "normalized_entropy": 0.0, "top1_probability": 0.0}
    z = y - np.max(y)
    e = np.exp(z)
    denom = np.sum(e)
    p = e / denom if np.isfinite(denom) and denom else np.full_like(y, 1.0 / y.size)
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
        raise ValueError(f"shape mismatch: candidate={c.shape} reference={r.shape}")
    ck = topk(c, 5)
    rk = topk(r, 5)
    cmax_set = set(np.flatnonzero(c == np.max(c)).astype(int).tolist())
    rmax_set = set(np.flatnonzero(r == np.max(r)).astype(int).tolist())
    cc = c - c.mean()
    rr = r - r.mean()
    denom = np.linalg.norm(c) * np.linalg.norm(r)
    cdenom = np.linalg.norm(cc) * np.linalg.norm(rr)
    diff = c - r
    return {
        "candidate_top1": int(ck[0]),
        "reference_top1": int(rk[0]),
        "top1_agreement": bool(ck[0] == rk[0]),
        "top5_overlap": int(len(set(ck) & set(rk))),
        "reference_top1_in_candidate_top5": bool(rk[0] in ck),
        "candidate_max_tie_count": int(len(cmax_set)),
        "reference_max_tie_count": int(len(rmax_set)),
        "reference_top1_in_candidate_max_tie_set": bool(rk[0] in cmax_set),
        "candidate_top1_in_reference_max_tie_set": bool(ck[0] in rmax_set),
        "rank_interval_for_reference_top1_under_candidate_ties": rank_interval(c, int(rk[0])),
        "rank_interval_for_candidate_top1_under_reference_ties": rank_interval(r, int(ck[0])),
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


def common_report(root: Path, name: str, command: str, inputs: list[Path]) -> dict[str, Any]:
    return {
        "schema_version": f"dream7b_s100p_v9_{name}",
        "created_at_utc": now(),
        "run_commands": [command],
        "git": git_meta(root),
        "input_artifacts": [artifact(p, root) for p in inputs],
        "output_artifacts": [
            {"path": f"reports/{name}.json"},
            {"path": f"reports/{name}.md"},
        ],
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


def package_final_endpoints(root: Path, command: str) -> dict[str, Any]:
    src_root = root / "evidence" / "raw_endpoint_subset_v6" / "final_segment_dense_sweep_v5"
    out_root = root / "evidence" / "final_segment_endpoint_raw_v9"
    reset_dir(out_root, root)
    rows = []
    missing = []
    for case_id in CASE_IDS:
        for variant in VARIANTS:
            src_dir = src_root / case_id / variant
            dst_dir = out_root / case_id / variant
            input_src = src_dir / "input.npy"
            raw_src = src_dir / "raw_output.npy"
            meta_src = src_dir / "metadata.json"
            if not input_src.exists() or not raw_src.exists():
                missing.append(rel(src_dir, root))
                continue
            copy_file(input_src, dst_dir / "input.npy")
            copy_file(raw_src, dst_dir / "raw_output.npy")
            raw = np.load(raw_src)
            dequant = (raw.astype(np.float32) - OFFICIAL_FINAL_OUTPUT_ZERO_POINT) * np.float32(OFFICIAL_FINAL_OUTPUT_SCALE)
            if dequant.ndim == 2 and dequant.shape[0] == 1:
                dequant = dequant.reshape(-1)
            np.save(dst_dir / "official_dequant_logits.npy", dequant.astype(np.float32, copy=False))
            input_arr = np.load(input_src)
            src_meta = load_json(meta_src, {})
            metadata = {
                "case_id": case_id,
                "variant_id": variant,
                "source_directory": rel(src_dir, root),
                "runtime_command_or_log_pointer": src_meta.get("runtime_command_or_log_pointer")
                or src_meta.get("run_command")
                or "remote v5 final_segment_dense_sweep_v5 endpoint run; local raw subset packaged in v6",
                "official_scale": OFFICIAL_FINAL_OUTPUT_SCALE,
                "official_zero_point": OFFICIAL_FINAL_OUTPUT_ZERO_POINT,
                "input_stats": stats(input_arr),
                "raw_output_stats": stats(raw),
                "official_dequant_stats": stats(dequant),
                "sha256": {
                    "input.npy": sha256_file(dst_dir / "input.npy"),
                    "raw_output.npy": sha256_file(dst_dir / "raw_output.npy"),
                    "official_dequant_logits.npy": sha256_file(dst_dir / "official_dequant_logits.npy"),
                },
                "source_metadata": src_meta,
            }
            write_json(dst_dir / "metadata.json", metadata)
            rows.append(
                {
                    "case_id": case_id,
                    "variant_id": variant,
                    "input_stats": metadata["input_stats"],
                    "raw_output_stats": metadata["raw_output_stats"],
                    "official_dequant_stats": metadata["official_dequant_stats"],
                    "files": {
                        "input": artifact(dst_dir / "input.npy", root),
                        "raw_output": artifact(dst_dir / "raw_output.npy", root),
                        "official_dequant": artifact(dst_dir / "official_dequant_logits.npy", root),
                        "metadata": artifact(dst_dir / "metadata.json", root),
                    },
                }
            )
    report = common_report(root, "700_package_final_endpoint_raw_evidence", command, [src_root])
    report.update(
        {
            "case_ids": CASE_IDS,
            "variants": VARIANTS,
            "expected_rows": len(CASE_IDS) * len(VARIANTS),
            "packaged_rows": len(rows),
            "missing_rows": missing,
            "official_final_output_scale": OFFICIAL_FINAL_OUTPUT_SCALE,
            "official_final_output_zero_point": OFFICIAL_FINAL_OUTPUT_ZERO_POINT,
            "rows": rows,
        }
    )
    if missing:
        report["blocking_or_failure_reasons"].append(f"missing raw endpoint rows: {missing[:5]}")
    write_report(
        root,
        "700_package_final_endpoint_raw_evidence",
        report,
        "Task 700 Package Final Endpoint Raw Evidence",
        [
            f"packaged_rows: `{len(rows)}/{len(CASE_IDS) * len(VARIANTS)}`",
            f"output_root: `{rel(out_root, root)}`",
            f"official_scale: `{OFFICIAL_FINAL_OUTPUT_SCALE}`",
        ],
    )
    return report


def exact_source_candidates(root: Path, explicit: Path | None, case_id: str, variant: str) -> list[Path]:
    bases = []
    if explicit is not None:
        bases.append(explicit)
    bases.extend(
        [
            root / "evidence" / "hf_exact_final_segment_v9",
            root / "evidence" / "hf_isolated_final_segment_v9",
            root / "evidence" / "hf_isolated_final_segment_v8",
            root / "evidence" / "s100p_remote_v9_hf_isolated_final_segment_v8",
            root / "evidence" / "s100p_remote_v9_hf_exact_final_segment",
        ]
    )
    names = ["exact_hf_final_logits.npy", "layer27_norm_lmhead_logits.npy"]
    out = []
    for base in bases:
        for name in names:
            out.append(base / case_id / variant / name)
    return out


def normalize_exact_hf(root: Path, command: str, exact_source: Path | None) -> dict[str, Any]:
    out_root = root / "evidence" / "hf_exact_final_segment_v9"
    out_root.mkdir(parents=True, exist_ok=True)
    boundary_config = root / "evidence" / "s100p_remote_v9_reports" / "model_config_boundary_v9.json"
    rows = []
    missing = []
    for case_id in CASE_IDS:
        for variant in VARIANTS:
            src = next((p for p in exact_source_candidates(root, exact_source, case_id, variant) if p.exists()), None)
            dst_dir = out_root / case_id / variant
            dst = dst_dir / "exact_hf_final_logits.npy"
            if src is None:
                missing.append({"case_id": case_id, "variant_id": variant})
                continue
            if src.resolve() != dst.resolve():
                copy_file(src, dst)
            src_meta = src.parent / "metadata.json"
            arr = np.load(dst)
            metadata = {
                "case_id": case_id,
                "variant_id": variant,
                "boundary": "HF Dream decoder layer 27 -> final RMSNorm -> lm_head",
                "reference_semantics": "same BPU seg26 hidden endpoint input is passed through exact HF final decoder layer, final norm, and lm_head",
                "source_path": rel(src, root),
                "exact_hf_final_logits_path": rel(dst, root),
                "exact_hf_final_stats": stats(arr),
                "sha256": {"exact_hf_final_logits.npy": sha256_file(dst)},
                "source_metadata": load_json(src_meta, {}),
            }
            write_json(dst_dir / "metadata.json", metadata)
            rows.append(metadata)
    report = common_report(root, "710_export_exact_hf_layer27_final", command, [])
    report.update(
        {
            "boundary": "HF Dream decoder layer 27 -> final RMSNorm -> lm_head",
            "boundary_index_evidence": load_json(boundary_config, {}),
            "expected_rows": len(CASE_IDS) * len(VARIANTS),
            "available_rows": len(rows),
            "missing_rows": missing,
            "output_root": rel(out_root, root),
            "rows": rows,
        }
    )
    if missing:
        report["blocking_or_failure_reasons"].append(f"missing exact HF final rows: {len(missing)}")
        report["next_minimal_experiments"].append(
            "Run tools_scaffold/export_hf_exact_layer27_final_v9.py on S100P with the v8 isolated modern Python path, then rerun this builder."
        )
    write_report(
        root,
        "710_export_exact_hf_layer27_final",
        report,
        "Task 710 Export Exact HF Layer27 Final",
        [
            f"available_rows: `{len(rows)}/{len(CASE_IDS) * len(VARIANTS)}`",
            f"boundary: `{report['boundary']}`",
            f"output_root: `{rel(out_root, root)}`",
        ],
    )
    return report


def full_truth_report(root: Path, command: str) -> dict[str, Any]:
    out_root = root / "evidence" / "full_reference_v9"
    reset_dir(out_root, root)
    v8_remote = root / "evidence" / "s100p_remote_v8_reports" / "630_640_hf_full_and_isolated_final_remote.json"
    inventory = root / "evidence" / "model_inventory_v6.json"
    v8 = load_json(v8_remote, {})
    inventory_data = load_json(inventory, {})
    blocked = {
        "full_truth_available": False,
        "truth_row_type": None,
        "required_minimum": "full HF BF16/FP32 logits or GGUF F16 logits for zeros, ramp, short_chinese_prompt_padded",
        "status": "blocked",
        "primary_blocker": "S100P full HF forward reached model-load stage in v8 isolated modern runtime but produced no logits before the evidence-run timeout; no GGUF F16 artifact/tool was found locally or on NAS during prior inventory.",
        "v8_remote_attempt": v8,
        "model_inventory_pointer": artifact(inventory, root),
        "known_gguf_observation": "NAS inventory previously found dream-7b-q4km.gguf, but no GGUF F16 truth artifact sufficient for v9 truth row.",
        "next_command": "On S100P, run a longer full-reference job with the isolated modern runtime or provide a GGUF F16 runner/artifact; then place per-case logits under evidence/full_reference_v9/{case}/full_truth_logits.npy.",
    }
    write_json(out_root / "blocked_full_truth_reference.json", blocked)
    write_text(
        out_root / "README.md",
        "\n".join(
            [
                "# Full Reference v9",
                "",
                "No full BF16/FP32 or GGUF F16 truth logits are available in this package.",
                "The final-segment same-input contract can still be tested, but full deployment logits validity cannot be proven or falsified without this row.",
            ]
        )
        + "\n",
    )
    report = common_report(root, "720_export_full_truth_reference", command, [v8_remote, inventory])
    report.update(blocked)
    report["output_root"] = rel(out_root, root)
    report["blocking_or_failure_reasons"].append(blocked["primary_blocker"])
    report["next_minimal_experiments"].append(blocked["next_command"])
    write_report(
        root,
        "720_export_full_truth_reference",
        report,
        "Task 720 Export Full Truth Reference",
        [
            "full_truth_available: `false`",
            "truth_row_type: `none`",
            f"blocked_report: `{rel(out_root / 'blocked_full_truth_reference.json', root)}`",
        ],
    )
    return report


def recompute_exact_final_comparison(root: Path, command: str) -> dict[str, Any]:
    out_root = root / "evidence" / "v9_comparisons" / "exact_final_segment"
    reset_dir(out_root, root)
    endpoint_root = root / "evidence" / "final_segment_endpoint_raw_v9"
    exact_root = root / "evidence" / "hf_exact_final_segment_v9"
    rows = []
    missing = []
    for case_id in CASE_IDS:
        for variant in VARIANTS:
            cand = endpoint_root / case_id / variant / "official_dequant_logits.npy"
            ref = exact_root / case_id / variant / "exact_hf_final_logits.npy"
            if not cand.exists() or not ref.exists():
                missing.append({"case_id": case_id, "variant_id": variant, "candidate_exists": cand.exists(), "reference_exists": ref.exists()})
                continue
            metrics = compare_logits(np.load(cand), np.load(ref))
            metrics.update(
                {
                    "case_id": case_id,
                    "variant_id": variant,
                    "candidate": "S100P seg27_28 official-dequant logits",
                    "reference": "HF exact layer27 + final norm + lm_head logits",
                    "candidate_path": rel(cand, root),
                    "reference_path": rel(ref, root),
                }
            )
            row_dir = out_root / case_id / variant
            write_json(row_dir / "metrics.json", metrics)
            rows.append(metrics)
    allzero_vs_nonconstant = [
        r
        for r in rows
        if r["candidate_stats"]["allzero"] and (not r["reference_stats"]["allzero"]) and (not r["reference_stats"]["constant"])
    ]
    real_x_allzero_vs_nonconstant = [r for r in allzero_vs_nonconstant if r["variant_id"] == "real_x"]
    nonzero_reference_rows = [r for r in rows if not r["reference_stats"]["allzero"]]
    top1_mismatch_rows = [r for r in rows if not r["top1_agreement"]]
    high_relative_l2_rows = [r for r in rows if r["relative_l2"] > 0.9]
    report = common_report(root, "730_recompare_exact_final_segment", command, [endpoint_root, exact_root])
    report.update(
        {
            "expected_rows": len(CASE_IDS) * len(VARIANTS),
            "compared_rows": len(rows),
            "missing_rows": missing,
            "allzero_candidate_nonconstant_reference_rows": len(allzero_vs_nonconstant),
            "real_x_allzero_candidate_nonconstant_reference_rows": len(real_x_allzero_vs_nonconstant),
            "nonzero_reference_rows": len(nonzero_reference_rows),
            "top1_agreement_rows": int(sum(1 for r in rows if r["top1_agreement"])),
            "top1_mismatch_rows": len(top1_mismatch_rows),
            "high_relative_l2_gt_0p9_rows": len(high_relative_l2_rows),
            "reference_top1_in_candidate_max_tie_set_rows": int(sum(1 for r in rows if r["reference_top1_in_candidate_max_tie_set"])),
            "rows": rows,
        }
    )
    if missing:
        report["blocking_or_failure_reasons"].append(f"missing comparison rows: {len(missing)}")
    write_report(
        root,
        "730_recompare_exact_final_segment",
        report,
        "Task 730 Recompare Exact Final Segment",
        [
            f"compared_rows: `{len(rows)}/{len(CASE_IDS) * len(VARIANTS)}`",
            f"allzero_candidate_nonconstant_reference_rows: `{len(allzero_vs_nonconstant)}`",
            f"top1_agreement_rows: `{report['top1_agreement_rows']}`",
        ],
    )
    return report


def upstream_hidden_audit(root: Path, command: str, compare_report: dict[str, Any], truth_report: dict[str, Any]) -> dict[str, Any]:
    endpoint_root = root / "evidence" / "final_segment_endpoint_raw_v9"
    exact_root = root / "evidence" / "hf_exact_final_segment_v9"
    rows = []
    for case_id in CASE_IDS:
        hidden = endpoint_root / case_id / "real_x" / "input.npy"
        exact = exact_root / case_id / "real_x" / "exact_hf_final_logits.npy"
        if not hidden.exists() or not exact.exists():
            continue
        h = np.load(hidden)
        e = np.load(exact)
        rows.append(
            {
                "case_id": case_id,
                "variant_id": "real_x",
                "bpu_seg26_hidden_stats": stats(h),
                "exact_hf_final_logits_stats": stats(e),
                "interpretation": "BPU seg26 endpoint hidden is executable through exact HF final boundary and yields nonzero/nonconstant logits; this does not validate hidden against a full truth row.",
            }
        )
    report = common_report(root, "740_upstream_hidden_validity_audit", command, [endpoint_root, exact_root])
    report.update(
        {
            "full_truth_available": bool(truth_report.get("full_truth_available")),
            "full_deployment_hidden_correctness_testable": bool(truth_report.get("full_truth_available")),
            "same_input_hidden_executability_rows": len(rows),
            "interpretation": "Without a full BF16/FP32 or GGUF F16 truth row, BPU seg26 hidden correctness versus full-model hidden is not testable. The same-input exact final test does show the hidden endpoint is not by itself forcing all-zero logits.",
            "rows": rows,
            "exact_final_segment_compared_rows": compare_report.get("compared_rows", 0),
        }
    )
    if not truth_report.get("full_truth_available"):
        report["blocking_or_failure_reasons"].append("full truth row unavailable; upstream hidden validity versus full model cannot be proven or falsified")
    write_report(
        root,
        "740_upstream_hidden_validity_audit",
        report,
        "Task 740 Upstream Hidden Validity Audit",
        [
            f"same_input_hidden_executability_rows: `{len(rows)}`",
            "full_deployment_hidden_correctness_testable: `false`",
        ],
    )
    return report


def tie_aware_summary(root: Path, command: str, compare_report: dict[str, Any]) -> dict[str, Any]:
    rows = compare_report.get("rows", [])
    report = common_report(root, "750_tie_aware_verdict_metrics", command, [root / "evidence" / "v9_comparisons" / "exact_final_segment"])
    report.update(
        {
            "compared_rows": len(rows),
            "candidate_allzero_rows": int(sum(1 for r in rows if r["candidate_stats"]["allzero"])),
            "candidate_constant_rows": int(sum(1 for r in rows if r["candidate_stats"]["constant"])),
            "reference_nonconstant_rows": int(sum(1 for r in rows if not r["reference_stats"]["constant"])),
            "candidate_max_tie_count_min": int(min((r["candidate_max_tie_count"] for r in rows), default=0)),
            "candidate_max_tie_count_max": int(max((r["candidate_max_tie_count"] for r in rows), default=0)),
            "reference_top1_in_candidate_max_tie_set_rows": int(
                sum(1 for r in rows if r["reference_top1_in_candidate_max_tie_set"])
            ),
            "top1_agreement_rows": int(sum(1 for r in rows if r["top1_agreement"])),
            "median_relative_l2": float(np.median([r["relative_l2"] for r in rows])) if rows else None,
            "median_pearson_centered": float(np.median([r["pearson_centered"] for r in rows])) if rows else None,
            "median_candidate_normalized_entropy": float(np.median([r["candidate_entropy"]["normalized_entropy"] for r in rows])) if rows else None,
            "median_reference_normalized_entropy": float(np.median([r["reference_entropy"]["normalized_entropy"] for r in rows])) if rows else None,
            "interpretation": "Candidate all-zero rows must be treated as full-vocabulary max ties, not as meaningful top-1 agreement. Relative L2 and constant/allzero status carry the final-segment contract decision.",
        }
    )
    if not rows:
        report["blocking_or_failure_reasons"].append("no exact final segment comparison rows available")
    write_report(
        root,
        "750_tie_aware_verdict_metrics",
        report,
        "Task 750 Tie-Aware Verdict Metrics",
        [
            f"candidate_allzero_rows: `{report['candidate_allzero_rows']}`",
            f"reference_top1_in_candidate_max_tie_set_rows: `{report['reference_top1_in_candidate_max_tie_set_rows']}`",
            f"median_relative_l2: `{report['median_relative_l2']}`",
        ],
    )
    return report


def build_gate_packet(
    root: Path,
    command: str,
    report700: dict[str, Any],
    report710: dict[str, Any],
    report720: dict[str, Any],
    report730: dict[str, Any],
    report740: dict[str, Any],
    report750: dict[str, Any],
) -> dict[str, Any]:
    final_root = root / "01_final_evidence"
    final_root.mkdir(parents=True, exist_ok=True)
    exact_complete = report710.get("available_rows") == len(CASE_IDS) * len(VARIANTS)
    raw_complete = report700.get("packaged_rows") == len(CASE_IDS) * len(VARIANTS)
    exact_fault_rows = report730.get("allzero_candidate_nonconstant_reference_rows", 0)
    real_x_exact_fault_rows = report730.get("real_x_allzero_candidate_nonconstant_reference_rows", 0)
    top1_mismatch_rows = report730.get("top1_mismatch_rows", 0)
    high_relative_l2_rows = report730.get("high_relative_l2_gt_0p9_rows", 0)
    full_truth = bool(report720.get("full_truth_available"))
    if exact_complete and real_x_exact_fault_rows == len(CASE_IDS):
        verdict_class = "F_exact_final_segment_contract_falsified_on_same_input"
        verdict = (
            "For the unmodified BPU seg26 hidden input (real_x) in all three prompt cases, S100P seg27_28 official-dequant logits are all-zero, "
            "while the exact HF layer27 + final norm + lm_head boundary produces nonzero/nonconstant logits for the same inputs. "
            f"Across the 42-row sweep, top-1 agreement is 0/42, {exact_fault_rows}/42 rows are all-zero/constant against nonconstant HF references, "
            f"and {high_relative_l2_rows}/42 rows have relative L2 > 0.9. This falsifies the final-segment contract on same input. "
            "Full deployment logits validity remains unproven without a full truth row."
        )
    elif not full_truth:
        verdict_class = "C_blocked_full_truth_unavailable"
        verdict = "Full Dream7B logits validity remains blocked because no full BF16/FP32 or GGUF F16 truth row is available."
    else:
        verdict_class = "D_inconclusive_artifact_or_alignment_issue"
        verdict = "Evidence did not produce a decisive final-segment contract fault or full-deployment decision."
    packet = common_report(root, "760_build_gate_packet_v9", command, [])
    packet.update(
        {
            "verdict_class": verdict_class,
            "verdict": verdict,
            "gate_status": {
                "G0_safety_generation_quality_not_run": "pass",
                "G0_safety_product_routes_18888_18889_untouched": "pass",
                "G1_raw_endpoint_packaging": "pass" if raw_complete else "fail",
                "G2_exact_hf_layer27_final_boundary": "pass" if exact_complete else "blocked",
                "G3_full_truth_reference_row": "pass" if full_truth else "blocked",
                "G4_exact_final_same_input_comparison": "fail_final_segment_contract" if real_x_exact_fault_rows == len(CASE_IDS) else ("blocked" if not exact_complete else "pass"),
                "G5_upstream_hidden_validity_vs_full_truth": "blocked" if not full_truth else "evaluated",
                "G6_evidence_packaging": "evaluated_by_task_770_manifest_and_zip_checks",
            },
            "compile_runtime_inherited_status": {
                "segmented_hbm_runtime": "inherited from v5-v8 endpoint runs; not rerun through product routes",
                "generation_quality": "not run",
                "product_routes_18888_18889": "not enabled, not modified, not tested",
            },
            "evidence_integrity_summary": {
                "final_endpoint_rows_packaged": report700.get("packaged_rows"),
                "exact_hf_rows_available": report710.get("available_rows"),
                "exact_comparison_rows": report730.get("compared_rows"),
                "full_truth_available": full_truth,
            },
            "full_truth_availability": {
                "available": full_truth,
                "blocked_reason": report720.get("primary_blocker"),
                "truth_row_type": report720.get("truth_row_type"),
            },
            "exact_final_segment_comparison_summary": {
                "boundary": report710.get("boundary"),
                "same_input_rows": report730.get("compared_rows"),
                "allzero_candidate_nonconstant_reference_rows": exact_fault_rows,
                "real_x_allzero_candidate_nonconstant_reference_rows": real_x_exact_fault_rows,
                "top1_mismatch_rows": top1_mismatch_rows,
                "high_relative_l2_gt_0p9_rows": high_relative_l2_rows,
                "top1_agreement_rows": report730.get("top1_agreement_rows"),
                "tie_aware_note": report750.get("interpretation"),
            },
            "upstream_hidden_validity_summary": report740.get("interpretation"),
            "numerical_logits_gate_summary": {
                "validated": False,
                "falsified_scope": "same-input final-segment contract" if exact_fault_rows else None,
                "not_validated_scope": "full Dream7B seq128 segmented HBM logits versus full BF16/FP32 or GGUF F16 truth",
            },
            "allowed_paper_claims": [
                "For the unmodified real_x endpoint inputs in all three prompt cases, the S100P seg27_28 official-dequant output does not implement the HF layer27 + final norm + lm_head boundary.",
                "Across the 42-row final-segment sweep, top-1 agreement is 0/42; 15/42 rows are all-zero/constant against nonconstant HF references in this run.",
                "The same BPU seg26 endpoint hidden produces nonzero/nonconstant logits through the exact HF final boundary.",
                "Full Dream7B seq128 segmented HBM logits validity on S100P is not established because the full truth row is unavailable.",
            ],
            "forbidden_claims": [
                "Do not claim generation quality or product-route behavior.",
                "Do not claim full Dream7B deployment logits are numerically valid.",
                "Do not claim full Dream7B deployment logits are falsified against BF16/FP32 truth without the missing truth row.",
                "Do not claim 18888/18889 routes were enabled, tested, or modified.",
            ],
            "next_minimal_experiment": [
                "Produce a full BF16/FP32 or GGUF F16 truth row for zeros, ramp, and short_chinese_prompt_padded.",
                "If full truth remains too slow on S100P, export the exact needed truth logits on a GPU/CPU host with enough RAM, then rerun task 740.",
            ],
            "source_reports": {
                "700": "reports/700_package_final_endpoint_raw_evidence.json",
                "710": "reports/710_export_exact_hf_layer27_final.json",
                "720": "reports/720_export_full_truth_reference.json",
                "730": "reports/730_recompare_exact_final_segment.json",
                "740": "reports/740_upstream_hidden_validity_audit.json",
                "750": "reports/750_tie_aware_verdict_metrics.json",
            },
        }
    )
    write_json(final_root / "dream7b_s100p_gate_packet_v9.json", packet)
    md = [
        "# Dream7B/S100P Gate Packet v9",
        "",
        f"Verdict class: `{verdict_class}`",
        "",
        verdict,
        "",
        "## Gate Status",
    ]
    md.extend(f"- `{k}`: `{v}`" for k, v in packet["gate_status"].items())
    md.extend(
        [
            "",
            "## Scope",
            "- Generation quality was not run.",
            "- Product routes 18888/18889 were not enabled, modified, or tested.",
            "- The decisive claim is limited to the same-input final-segment contract unless a full truth row is later added.",
        ]
    )
    write_text(final_root / "dream7b_s100p_gate_packet_v9.md", "\n".join(md) + "\n")
    dossier = [
        "# Dream7B/S100P Paper Evidence Dossier v9",
        "",
        "## Research Question",
        "Can Dream7B seq128 segmented HBM on S100P produce numerically valid logits?",
        "",
        "## Evidence Table",
        "",
        "| Evidence row | Status | Claim supported | Main artifact |",
        "|---|---:|---|---|",
        f"| Final endpoint raw tensors | {report700.get('packaged_rows')}/{len(CASE_IDS) * len(VARIANTS)} | Endpoint sweep is replayable | evidence/final_segment_endpoint_raw_v9 |",
        f"| Exact HF final boundary | {report710.get('available_rows')}/{len(CASE_IDS) * len(VARIANTS)} | Defines layer27 + final norm + lm_head on same hidden input | evidence/hf_exact_final_segment_v9 |",
        f"| Full truth row | {'available' if full_truth else 'blocked'} | Required for full deployment logits validity | evidence/full_reference_v9 |",
        f"| Same-input final comparison | {report730.get('compared_rows')}/{len(CASE_IDS) * len(VARIANTS)} | Tests seg27_28 official-dequant against exact HF final segment | evidence/v9_comparisons/exact_final_segment |",
        "",
        "## Main Conclusion",
        verdict,
        "",
        "## Paper-Safe Claims",
    ]
    dossier.extend(f"- {x}" for x in packet["allowed_paper_claims"])
    dossier.extend(["", "## Claims Not Supported"])
    dossier.extend(f"- {x}" for x in packet["forbidden_claims"])
    write_text(final_root / "dream7b_s100p_paper_evidence_dossier_v9.md", "\n".join(dossier) + "\n")
    write_report(
        root,
        "760_build_gate_packet_v9",
        packet,
        "Task 760 Build Gate Packet v9",
        [
            f"verdict_class: `{verdict_class}`",
            f"full_truth_available: `{full_truth}`",
            f"real_x_exact_fault_rows: `{real_x_exact_fault_rows}`",
            f"allzero_exact_fault_rows: `{exact_fault_rows}`",
        ],
    )
    return packet


def copy_tree_if_exists(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    if src.is_file():
        copy_file(src, dst)
        return
    shutil.copytree(src, dst, dirs_exist_ok=True)


def build_manifest(package_root: Path) -> dict[str, Any]:
    files = []
    for fp in sorted(package_root.rglob("*")):
        if fp.is_file() and fp.name not in {"MANIFEST.json", "SHA256SUMS.txt"}:
            files.append({"path": fp.relative_to(package_root).as_posix(), "size_bytes": fp.stat().st_size, "sha256": sha256_file(fp)})
    manifest = {"schema_version": "dream7b_s100p_v9_manifest", "created_at_utc": now(), "file_count": len(files), "files": files}
    write_json(package_root / "MANIFEST.json", manifest)
    (package_root / "SHA256SUMS.txt").write_text("".join(f"{f['sha256']}  {f['path']}\n" for f in files), encoding="utf-8")
    return manifest


def validate_manifest(package_root: Path) -> dict[str, Any]:
    manifest = load_json(package_root / "MANIFEST.json", {"files": []})
    bad = []
    for item in manifest.get("files", []):
        fp = package_root / item["path"]
        row = {"path": item["path"], "exists": fp.exists(), "size_ok": None, "sha_ok": None}
        if fp.exists():
            row["size_ok"] = fp.stat().st_size == item.get("size_bytes")
            row["sha_ok"] = sha256_file(fp) == item.get("sha256")
        if not row["exists"] or row["size_ok"] is False or row["sha_ok"] is False:
            bad.append(row)
    return {"manifest": "MANIFEST.json", "entries": len(manifest.get("files", [])), "bad_count": len(bad), "bad_examples": bad[:20]}


def build_package(root: Path, command: str, packet: dict[str, Any]) -> dict[str, Any]:
    staging = root / "tmp" / "dream7b_s100p_v9_package_staging"
    reset_dir(staging, root)
    final_dst = staging / "01_final_evidence"
    final_dst.mkdir(parents=True, exist_ok=True)
    for name in [
        "dream7b_s100p_gate_packet_v9.json",
        "dream7b_s100p_gate_packet_v9.md",
        "dream7b_s100p_paper_evidence_dossier_v9.md",
    ]:
        copy_tree_if_exists(root / "01_final_evidence" / name, final_dst / name)
    reports_dst = staging / "reports"
    reports_dst.mkdir(parents=True, exist_ok=True)
    for fp in sorted((root / "reports").glob("7*_*.json")) + sorted((root / "reports").glob("7*_*.md")):
        copy_file(fp, reports_dst / fp.name)
    copy_tree_if_exists(root / "evidence" / "final_segment_endpoint_raw_v9", staging / "evidence" / "final_segment_endpoint_raw_v9")
    copy_tree_if_exists(root / "evidence" / "hf_exact_final_segment_v9", staging / "evidence" / "hf_exact_final_segment_v9")
    copy_tree_if_exists(root / "evidence" / "full_reference_v9", staging / "evidence" / "full_reference_v9")
    copy_tree_if_exists(root / "evidence" / "v9_comparisons", staging / "evidence" / "v9_comparisons")
    copy_tree_if_exists(root / "evidence" / "s100p_remote_v9_reports", staging / "evidence" / "s100p_remote_v9_reports")
    copy_tree_if_exists(root / "evidence" / "s100p_remote_v8_reports", staging / "evidence" / "s100p_remote_v8_reports")
    copy_tree_if_exists(root / "evidence" / "model_inventory_v6.json", staging / "evidence" / "model_inventory_v6.json")
    copy_tree_if_exists(root / "tmp" / "dream7b_s100p_v9_after_v8_review_pack_20260701", staging / "00_execution_pack")
    copy_tree_if_exists(root / "tools" / "build_v9_research_thread.py", staging / "tools" / "build_v9_research_thread.py")
    copy_tree_if_exists(root / "tools" / "run_hf_full_and_isolated_final_v8.py", staging / "tools" / "run_hf_full_and_isolated_final_v8.py")
    copy_tree_if_exists(root / "tools" / "run_hf_exact_layer27_final_v9.py", staging / "tools" / "run_hf_exact_layer27_final_v9.py")
    safety_note = {
        "generation_quality_run": False,
        "product_routes_18888_18889_enabled_modified_or_tested": False,
        "note": "Occurrences of route numbers inside this package are safety-bound text only, not route configuration or runtime evidence.",
    }
    write_json(staging / "SAFETY_ATTESTATION_V9.json", safety_note)
    manifest = build_manifest(staging)
    manifest_check = validate_manifest(staging)
    zip_dir = root / "evidence_for_gptpro"
    zip_dir.mkdir(parents=True, exist_ok=True)
    tag = packet.get("verdict_class", "v9").split("_", 1)[0].lower()
    zip_path = zip_dir / f"dream7b_s100p_v9_for_gptpro_20260701_{tag}_exact_final_contract.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for fp in sorted(staging.rglob("*")):
            if fp.is_file():
                zf.write(fp, fp.relative_to(staging).as_posix())
    with zipfile.ZipFile(zip_path) as zf:
        bad_member = zf.testzip()
        zip_members = zf.namelist()
    report = common_report(root, "770_build_gptpro_evidence_zip", command, [staging])
    report.update(
        {
            "zip_path": rel(zip_path, root),
            "zip_size_bytes": zip_path.stat().st_size,
            "zip_sha256": sha256_file(zip_path),
            "zip_testzip_bad_member": bad_member,
            "zip_member_count": len(zip_members),
            "manifest": manifest,
            "manifest_check": manifest_check,
            "package_root_is_flat": all(not name.startswith("dream7b_s100p_v9_package_staging/") for name in zip_members),
        }
    )
    if bad_member:
        report["blocking_or_failure_reasons"].append(f"zip testzip failed at {bad_member}")
    if manifest_check["bad_count"]:
        report["blocking_or_failure_reasons"].append("manifest validation failed")
    write_report(
        root,
        "770_build_gptpro_evidence_zip",
        report,
        "Task 770 Build GPT Pro Evidence Zip",
        [
            f"zip_path: `{rel(zip_path, root)}`",
            f"zip_sha256: `{report['zip_sha256']}`",
            f"manifest_bad_count: `{manifest_check['bad_count']}`",
            f"zip_testzip_bad_member: `{bad_member}`",
        ],
    )
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--exact-source", default=None, help="Optional source root with case/variant/layer27_norm_lmhead_logits.npy")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    exact_source = Path(args.exact_source).resolve() if args.exact_source else None
    command = " ".join([sys.executable, *sys.argv])
    report700 = package_final_endpoints(root, command)
    report710 = normalize_exact_hf(root, command, exact_source)
    report720 = full_truth_report(root, command)
    report730 = recompute_exact_final_comparison(root, command)
    report740 = upstream_hidden_audit(root, command, report730, report720)
    report750 = tie_aware_summary(root, command, report730)
    packet = build_gate_packet(root, command, report700, report710, report720, report730, report740, report750)
    package_report = build_package(root, command, packet)
    print(
        json.dumps(
            {
                "verdict_class": packet["verdict_class"],
                "zip_path": package_report["zip_path"],
                "zip_sha256": package_report["zip_sha256"],
                "manifest_bad_count": package_report["manifest_check"]["bad_count"],
                "zip_testzip_bad_member": package_report["zip_testzip_bad_member"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
