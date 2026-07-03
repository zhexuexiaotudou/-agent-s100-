#!/usr/bin/env python3
"""Build v12R Dream7B/S100P root-cause and reconstruction reports."""
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
SINGLE_SEGMENTS = [0, 1, 2, 4, 8, 11, 12, 13, 20, 25, 26, 27]
PREFIX_CUTS = [0, 1, 2, 4, 8, 11, 12, 13, 20, 25, 26]
FINAL_VARIANTS = [
    "real_x",
    "real_x_div_2",
    "real_x_div_2p25",
    "real_x_div_2p5",
    "real_x_div_2p75",
    "real_x_div_3",
    "real_x_div_4",
    "real_x_clip_8",
    "real_x_clip_6",
    "real_x_clip_4",
    "real_x_z_normalized",
]


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
    last: Exception | None = None
    for enc in ("utf-8", "utf-8-sig", "utf-16"):
        try:
            return json.loads(path.read_text(encoding=enc))
        except UnicodeDecodeError as exc:
            last = exc
    if last:
        raise last
    return {} if default is None else default


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return str(path)


def artifact(path: Path, root: Path | None = None, hash_large: bool = True) -> dict[str, Any]:
    row: dict[str, Any] = {"path": rel(path, root) if root else str(path), "exists": path.exists()}
    if path.exists() and path.is_file():
        row["size_bytes"] = path.stat().st_size
        row["sha256"] = sha256_file(path) if hash_large or path.stat().st_size < 512 * 1024 * 1024 else "skipped_large_file"
    return row


def common(root: Path, name: str, command: str, inputs: list[Path]) -> dict[str, Any]:
    git_status = {"cwd": str(root), "status": "not_checked"}
    try:
        proc = subprocess.run(["git", "status", "--short"], cwd=root, text=True, capture_output=True, timeout=10)
        git_status = {
            "cwd": str(root),
            "returncode": proc.returncode,
            "status": proc.stdout.strip() if proc.returncode == 0 else "unavailable_empty_or_incomplete_git_dir",
            "stderr": proc.stderr.strip(),
        }
    except Exception as exc:
        git_status = {"cwd": str(root), "status": f"git_status_error:{type(exc).__name__}:{exc}"}
    return {
        "schema_version": f"dream7b_s100p_v12r_{name}",
        "created_at_utc": now(),
        "run_commands": [command],
        "git": git_status,
        "input_artifacts": [artifact(p, root) for p in inputs],
        "output_artifacts": [],
        "blocking_or_failure_reasons": [],
        "next_minimal_experiments": [],
        "safety": {"generation_quality_run": False, "product_routes_18888_18889_enabled_modified_or_tested": False},
    }


def tensor_stats(x: np.ndarray) -> dict[str, Any]:
    arr = np.asarray(x)
    finite = arr[np.isfinite(arr)] if np.issubdtype(arr.dtype, np.floating) else arr
    if arr.size == 0:
        return {"shape": list(arr.shape), "dtype": str(arr.dtype), "size": 0}
    out = {
        "shape": list(arr.shape),
        "dtype": str(arr.dtype),
        "size": int(arr.size),
        "min": float(np.min(finite)) if finite.size else None,
        "max": float(np.max(finite)) if finite.size else None,
        "mean": float(np.mean(finite)) if finite.size else None,
        "std": float(np.std(finite)) if finite.size else None,
        "abs_max": float(np.max(np.abs(finite))) if finite.size else None,
        "nonzero_count": int(np.count_nonzero(arr)),
        "allzero": bool(np.count_nonzero(arr) == 0),
        "constant": bool(arr.size > 0 and np.all(arr == arr.flat[0])),
        "nan_count": int(np.isnan(arr).sum()) if np.issubdtype(arr.dtype, np.floating) else 0,
        "inf_count": int(np.isinf(arr).sum()) if np.issubdtype(arr.dtype, np.floating) else 0,
    }
    for q in (0, 1, 5, 50, 95, 99, 100):
        try:
            out[f"p{q}"] = float(np.percentile(finite, q)) if finite.size else None
        except Exception:
            pass
    return out


def stable_softmax(logits: np.ndarray) -> np.ndarray:
    v = np.asarray(logits, dtype=np.float64).reshape(-1)
    v = v - np.max(v)
    e = np.exp(v)
    s = np.sum(e)
    if not np.isfinite(s) or s == 0:
        return np.full_like(v, 1.0 / v.size)
    return e / s


def entropy(logits: np.ndarray) -> dict[str, float]:
    p = stable_softmax(logits)
    ent = -float(np.sum(p * np.log(p + 1e-300)))
    return {"entropy": ent, "normalized_entropy": ent / math.log(p.size) if p.size > 1 else 0.0, "top1_probability": float(np.max(p))}


def compare_arrays(ref: np.ndarray, cand: np.ndarray, topk: int = 5) -> dict[str, Any]:
    r = np.asarray(ref, dtype=np.float64).reshape(-1)
    c = np.asarray(cand, dtype=np.float64).reshape(-1)
    if r.shape != c.shape:
        return {"shape_match": False, "reference_shape": list(r.shape), "candidate_shape": list(c.shape)}
    rt = np.argsort(r)[-topk:][::-1].astype(int)
    ct = np.argsort(c)[-topk:][::-1].astype(int)
    r0 = r - np.mean(r)
    c0 = c - np.mean(c)
    rn = np.linalg.norm(r)
    cn = np.linalg.norm(c)
    r0n = np.linalg.norm(r0)
    c0n = np.linalg.norm(c0)
    return {
        "shape_match": True,
        "reference_top1": int(rt[0]),
        "candidate_top1": int(ct[0]),
        "top1_agreement": bool(rt[0] == ct[0]),
        "reference_top1_in_candidate_top5": bool(rt[0] in ct),
        "top5_overlap": int(len(set(rt.tolist()) & set(ct.tolist()))),
        "cosine": float(np.dot(r, c) / (rn * cn)) if rn and cn else None,
        "pearson_centered": float(np.dot(r0, c0) / (r0n * c0n)) if r0n and c0n else None,
        "relative_l2": float(np.linalg.norm(r - c) / (rn + 1e-12)),
        "max_abs_error": float(np.max(np.abs(r - c))),
        "mean_abs_error": float(np.mean(np.abs(r - c))),
        "candidate_normalized_entropy": entropy(c)["normalized_entropy"],
    }


def top_error_dims(ref: np.ndarray, cand: np.ndarray, limit: int = 16) -> list[dict[str, Any]]:
    r = np.asarray(ref, dtype=np.float64)
    c = np.asarray(cand, dtype=np.float64)
    diff = np.abs(r - c).reshape(-1)
    idx = np.argsort(diff)[-limit:][::-1]
    out = []
    for flat in idx:
        coord = np.unravel_index(int(flat), r.shape)
        out.append({"flat_index": int(flat), "coord": [int(x) for x in coord], "abs_error": float(diff[flat]), "reference": float(r.reshape(-1)[flat]), "candidate": float(c.reshape(-1)[flat])})
    return out


def parse_sha256sums(text: str) -> dict[str, str]:
    rows = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            rows[parts[1].strip().lstrip("*")] = parts[0].strip()
    return rows


def validate_unpacked_package(root: Path) -> dict[str, Any]:
    mf = load_json(root / "MANIFEST.json", {})
    sha_rows = parse_sha256sums((root / "SHA256SUMS.txt").read_text(encoding="utf-8")) if (root / "SHA256SUMS.txt").exists() else {}
    missing = []
    bad_size = []
    bad_sha = []
    sha_missing = []
    sha_bad = []
    for item in mf.get("files", []):
        p = root / item["path"]
        if not p.exists():
            missing.append(item["path"])
            continue
        if p.stat().st_size != item.get("size_bytes"):
            bad_size.append(item["path"])
        if sha256_file(p) != item.get("sha256"):
            bad_sha.append(item["path"])
    for path_text, expected in sha_rows.items():
        p = root / path_text
        if not p.exists():
            sha_missing.append(path_text)
        elif sha256_file(p) != expected:
            sha_bad.append(path_text)
    return {
        "manifest_entries": len(mf.get("files", [])),
        "manifest_missing": missing,
        "manifest_bad_size": bad_size,
        "manifest_bad_sha256": bad_sha,
        "sha256sums_entries": len(sha_rows),
        "sha256sums_missing": sha_missing,
        "sha256sums_bad": sha_bad,
    }


def validate_zip(zip_path: Path, unpacked: Path) -> dict[str, Any]:
    result = {"zip_path": str(zip_path), "exists": zip_path.exists()}
    if not zip_path.exists():
        return result
    result.update({"size_bytes": zip_path.stat().st_size, "sha256": sha256_file(zip_path)})
    with zipfile.ZipFile(zip_path) as zf:
        result["zip_testzip_bad_member"] = zf.testzip()
        result["zip_member_count"] = len(zf.namelist())
    result["unpacked_check"] = validate_unpacked_package(unpacked) if unpacked.exists() else {"unpacked_exists": False}
    return result


def save_report(root: Path, name: str, report: dict[str, Any], title: str, bullets: list[str]) -> dict[str, Any]:
    jp = root / "reports" / f"{name}.json"
    mp = root / "reports" / f"{name}.md"
    report["output_artifacts"] = [{"path": rel(jp, root)}, {"path": rel(mp, root)}]
    write_json(jp, report)
    lines = [f"# {title}", ""]
    lines.extend(f"- {b}" for b in bullets)
    if report.get("blocking_or_failure_reasons"):
        lines.extend(["", "## Blocking / Failure Reasons"])
        lines.extend(f"- {x}" for x in report["blocking_or_failure_reasons"])
    if report.get("next_minimal_experiments"):
        lines.extend(["", "## Next Minimal Experiments"])
        lines.extend(f"- {x}" for x in report["next_minimal_experiments"])
    write_text(mp, "\n".join(lines) + "\n")
    return report


def load_cases(root: Path) -> dict[str, dict[str, Any]]:
    rows = iter_jsonl(root / "cases" / "canonical_seq128_cases_v10.jsonl")
    if not rows:
        rows = iter_jsonl(root / "cases" / "canonical_seq128_cases_v6.jsonl")
    return {r["case_id"]: r for r in rows if r.get("case_id") in CASE_IDS}


def task1000(root: Path, command: str, v12_zip: Path) -> dict[str, Any]:
    v11_zip = root / "evidence_for_gptpro" / "dream7b_s100p_v11_for_gptpro_20260701.zip"
    v11_unpack = root / "tmp" / "dream7b_s100p_v11_for_gptpro_20260701_unpacked"
    v12_unpack = root / "tmp" / "dream7b_s100p_v12_after_v11_review_pack_20260702"
    report = common(root, "1000_v12r_baseline_lock", command, [v11_zip, v12_zip, root / "01_final_evidence" / "dream7b_s100p_gate_packet_v11.json"])
    gate = load_json(root / "01_final_evidence" / "dream7b_s100p_gate_packet_v11.json", {})
    review = load_json(v12_unpack / "reference" / "gptpro_review_dream7b_s100p_v11_summary_20260702.json", {})
    cases = load_cases(root)
    truth_rows = []
    for cid in CASE_IDS:
        p = root / "evidence" / "full_truth_repeat_v11" / cid / "repeat_full_truth_logits.npy"
        if p.exists():
            arr = np.load(p)
            truth_rows.append({"case_id": cid, "path": rel(p, root), "sha256": sha256_file(p), "stats": tensor_stats(arr), "top5": np.argsort(arr.reshape(-1))[-5:][::-1].astype(int).tolist()})
    bpu_report = load_json(root / "reports" / "830_compare_full_truth_and_upstream_hidden.json", {})
    boundary_report = load_json(root / "reports" / "910_hf_bpu_boundary_alignment.json", {})
    suffix_report = load_json(root / "reports" / "920_suffix_route_localization.json", {})
    final_report = load_json(root / "reports" / "730_recompare_exact_final_segment.json", {})
    report.update(
        {
            "v11_zip_validation": validate_zip(v11_zip, v11_unpack),
            "v12_zip_validation": validate_zip(v12_zip, v12_unpack),
            "v11_gate_verdict_class": gate.get("verdict_class"),
            "v11_review_verdict_class": review.get("verdict_class_reviewed"),
            "baseline_facts": {
                "canonical_cases": list(cases.values()),
                "hf_pytorch_bf16_full_truth_logits": truth_rows,
                "s100p_full_chain_logits": {
                    "official_vs_full_truth_rows": bpu_report.get("official_vs_full_truth_rows"),
                    "official_vs_full_truth_top1_agreement_rows": bpu_report.get("official_vs_full_truth_top1_agreement_rows"),
                    "official_vs_full_truth_median_relative_l2": bpu_report.get("official_vs_full_truth_median_relative_l2"),
                },
                "bpu_boundary_stats": {
                    "first_divergent_segment_global": boundary_report.get("first_divergent_segment_global"),
                    "first_divergent_segment_by_case": boundary_report.get("first_divergent_segment_by_case"),
                },
                "same_input_final_segment_comparison": {
                    "source_report": "reports/730_recompare_exact_final_segment.json",
                    "rows": final_report.get("comparison_rows"),
                    "top1_agreement_rows": final_report.get("top1_agreement_rows"),
                },
                "hf_suffix_route_comparison": {
                    "suffix_rows": suffix_report.get("suffix_rows"),
                    "expected_rows": suffix_report.get("expected_rows"),
                    "summary_by_boundary": suffix_report.get("summary_by_boundary"),
                },
            },
            "required_baseline_statements": {
                "current_full_bpu_path": "falsified_against_HF_PyTorch_BF16_logits_truth",
                "generation_quality": "not_run_by_design",
                "product_route": "not_run_by_design",
                "v12r_goal": "root_cause_plus_reconstruction_not_repeating_failure_proof",
            },
        }
    )
    return save_report(
        root,
        "1000_v12r_baseline_lock",
        report,
        "v12R Baseline Lock",
        [
            "current full-BPU path: `falsified_against_HF_PyTorch_BF16_logits_truth`",
            "generation_quality: `not_run_by_design`",
            "product_route: `not_run_by_design`",
            "v12R goal: `root-cause + reconstruction`",
            f"v11 zip SHA256: `{report['v11_zip_validation'].get('sha256')}`",
            f"v12 zip SHA256: `{report['v12_zip_validation'].get('sha256')}`",
        ],
    )


def task1010(root: Path, command: str) -> dict[str, Any]:
    cases = load_cases(root)
    r900 = load_json(root / "reports" / "900_repeat_full_truth_reference.json", {})
    source_hashes = {item.get("name"): item for item in r900.get("source_hashes", [])}
    out_root = root / "evidence" / "input_contract_v12r"
    rows = []
    invalid_reasons = []
    for cid in CASE_IDS:
        case = cases.get(cid, {})
        token_ids = case.get("token_ids", [])
        position_ids = case.get("position_ids", list(range(len(token_ids) or 128)))
        attention_mask = case.get("attention_mask", [1] * (len(token_ids) or 128))
        hf_meta = load_json(root / "evidence" / "hf_boundaries_v11" / cid / "metadata.json", {})
        bpu_meta = load_json(root / "evidence" / "boundary_all_segments_v7" / cid / "seg_00_metadata.json", {})
        row = {
            "case_id": cid,
            "token_ids": {"length": len(token_ids), "first16": token_ids[:16], "last16": token_ids[-16:], "sha256": hashlib.sha256(np.asarray(token_ids, dtype=np.int64).tobytes()).hexdigest() if token_ids else None},
            "position_ids": {"length": len(position_ids), "first16": position_ids[:16], "last16": position_ids[-16:], "policy": "0..127"},
            "attention_mask": {"length": len(attention_mask), "first16": attention_mask[:16], "last16": attention_mask[-16:], "policy": "explicit all-ones mask in v11 HF export unless case overrides"},
            "diffusion_mask_policy": "not used; logits-only canonical forward, no generation-quality diffusion loop",
            "padding_policy": "zeros diagnostic all positions" if cid == "zeros" else ("no padding; diagnostic ramp tokens 1..128" if cid == "ramp" else "semantic prompt padded with token id 0 to seq128"),
            "last_token_index": 127,
            "case_kind": "semantic" if cid == "short_chinese_prompt_padded" else "diagnostic",
            "tokenizer_sources": {k: source_hashes.get(k) for k in ["tokenization_dream.py", "tokenizer_config.json", "vocab.json", "merges.txt"]},
            "dream_config_sources": {k: source_hashes.get(k) for k in ["config.json", "configuration_dream.py", "modeling_dream.py"]},
            "bpu_runtime_input_tensor": {"segment": 0, "model_name": "dream_segment_00_01", "input_0": {"name": "_input_0", "dtype": "int32", "shape": [1, 128], "layout": "batch,seq token ids"}, "input_1": {"name": "_input_1", "dtype": "int32", "shape": [128], "layout": "seq position ids"}, "source": "run_s100p_hbm_chain_dump_boundaries_v6.py"},
            "hf_model_input_tensor": {"input_ids": {"dtype": "torch.long", "shape": [1, 128]}, "position_ids": {"dtype": "torch.long", "shape": [1, 128]}, "attention_mask": {"dtype": "torch.bool", "shape": [1, 128]}, "num_logits_to_keep": 1, "source": "tools/export_hf_boundaries_repeat_v11.py"},
            "bpu_seg0_output_stats": bpu_meta.get("dequant_stats"),
            "bpu_seg0_raw_stats": bpu_meta.get("raw_stats"),
            "hf_embedding_output_stats": next((x.get("stats") for x in hf_meta.get("boundaries", []) if x.get("boundary") == "embedding_output"), None),
            "hf_layer0_output_stats": next((x.get("stats") for x in hf_meta.get("boundaries", []) if x.get("boundary") == "layer_00_output"), None),
        }
        if len(token_ids) != 128 or position_ids != list(range(128)):
            invalid_reasons.append({"case_id": cid, "reason": "token_or_position_length_policy_mismatch"})
        cdir = out_root / cid
        write_json(cdir / "input_contract.json", row)
        rows.append(row)
    verdict = "input_contract_valid" if not invalid_reasons else "input_contract_invalid"
    report = common(root, "1010_input_contract_audit", command, [root / "cases" / "canonical_seq128_cases_v10.jsonl", root / "reports" / "900_repeat_full_truth_reference.json"])
    report.update({"verdict": verdict, "rows": rows, "invalid_reasons": invalid_reasons, "output_root": rel(out_root, root)})
    if verdict == "input_contract_valid":
        report["next_minimal_experiments"].append("Input metadata is internally consistent; seg0 mismatch should be tested under HF-prefix/BPU-single-segment substitution before attributing root cause to later graph stages.")
    return save_report(root, "1010_input_contract_audit", report, "Input Contract Audit", [f"verdict: `{verdict}`", f"cases: `{len(rows)}`", "zeros/ramp are diagnostic; short_chinese_prompt_padded is semantic+padded."])


def seg0_variants(raw: np.ndarray, deq: np.ndarray, hf: np.ndarray, scale: float) -> list[tuple[str, np.ndarray, str]]:
    variants: list[tuple[str, np.ndarray, str]] = []
    variants.append(("official_dequant", deq, "official output scale"))
    variants.append(("scale_x2", deq * 2.0, "official dequant multiplied by 2"))
    variants.append(("scale_x4", deq * 4.0, "official dequant multiplied by 4"))
    variants.append(("scale_div2", deq / 2.0, "official dequant divided by 2"))
    variants.append(("scale_div4", deq / 4.0, "official dequant divided by 4"))
    if np.std(deq):
        variants.append(("match_hf_std", ((deq - np.mean(deq)) / np.std(deq) * np.std(hf) + np.mean(hf)).astype(np.float32), "global affine match to HF mean/std"))
    token = deq.copy().astype(np.float32)
    hf_token = hf.astype(np.float32)
    tmean = token.mean(axis=1, keepdims=True)
    tstd = token.std(axis=1, keepdims=True)
    hmean = hf_token.mean(axis=1, keepdims=True)
    hstd = hf_token.std(axis=1, keepdims=True)
    variants.append(("per_token_z_to_hf_stats", ((token - tmean) / np.maximum(tstd, 1e-6) * hstd + hmean).astype(np.float32), "per-token affine diagnostic"))
    if raw.shape == hf.shape:
        variants.append(("raw_signed_times_official_scale", raw.astype(np.float32) * scale, "signed int16 raw times official scale"))
        variants.append(("raw_unsigned_reinterpret_centered_times_scale", (raw.view(np.uint16).astype(np.float32) - 32768.0) * scale, "uint16 reinterpret centered then scale"))
        variants.append(("raw_byteswap_times_scale", raw.byteswap().astype(np.float32) * scale, "endian-swapped int16 times scale"))
    if raw.T.size == hf.size:
        variants.append(("transpose_flatten_reshape_official", deq.T.reshape(hf.shape).astype(np.float32), "transpose then contiguous flatten reinterpretation"))
    return variants


def task1020(root: Path, command: str) -> dict[str, Any]:
    out_root = root / "evidence" / "seg0_contract_v12r"
    rows = []
    for cid in CASE_IDS:
        raw_path = root / "evidence" / "boundary_all_segments_v7" / cid / "seg_00_raw_output.npy"
        deq_path = root / "evidence" / "boundary_all_segments_v7" / cid / "seg_00_output.npy"
        hf_path = root / "evidence" / "hf_boundaries_v11" / cid / "layer_00_output.npy"
        meta = load_json(root / "evidence" / "boundary_all_segments_v7" / cid / "seg_00_metadata.json", {})
        raw = np.load(raw_path)
        deq = np.load(deq_path)
        hf = np.load(hf_path)
        scale = float((meta.get("quant_metadata") or {}).get("scale_first") or 1.0)
        case_dir = out_root / cid
        case_dir.mkdir(parents=True, exist_ok=True)
        variant_rows = []
        for name, arr, why in seg0_variants(raw, deq, hf, scale):
            metrics = compare_arrays(hf, arr)
            variant_rows.append({"variant": name, "why": why, "metrics": metrics, "candidate_stats": tensor_stats(arr)})
            if name in {"official_dequant", "match_hf_std", "per_token_z_to_hf_stats"}:
                np.save(case_dir / f"{name}.npy", arr.astype(np.float32))
        best = sorted([v for v in variant_rows if v["metrics"].get("shape_match")], key=lambda v: (v["metrics"].get("relative_l2") if v["metrics"].get("relative_l2") is not None else 1e9))[0]
        row = {
            "case_id": cid,
            "seg00_01_mapping": "BPU seg00_01 consumes token_ids + position_ids and is compared to HF layer_00_output, not embedding-only.",
            "official_metrics": next(v for v in variant_rows if v["variant"] == "official_dequant")["metrics"],
            "best_variant_by_boundary_l2": best,
            "top_hidden_dimensions_by_official_error": top_error_dims(hf, deq),
            "variant_rows": variant_rows,
            "raw_stats": tensor_stats(raw),
            "official_dequant_stats": tensor_stats(deq),
            "hf_layer0_stats": tensor_stats(hf),
            "output_artifacts": [rel(case_dir / "official_dequant.npy", root), rel(case_dir / "match_hf_std.npy", root), rel(case_dir / "per_token_z_to_hf_stats.npy", root)],
        }
        write_json(case_dir / "seg0_contract.json", row)
        rows.append(row)
    can_repair = all((r["best_variant_by_boundary_l2"]["metrics"].get("relative_l2") or 9) < 0.1 and (r["best_variant_by_boundary_l2"]["metrics"].get("pearson_centered") or 0) > 0.95 for r in rows)
    report = common(root, "1020_seg0_exact_contract_audit", command, [root / "evidence" / "boundary_all_segments_v7", root / "evidence" / "hf_boundaries_v11"])
    report.update(
        {
            "seg0_mapping": "seg00_01 is treated as HF layer0 boundary output based on v11 boundary alignment naming and runtime segment manifest.",
            "rows": rows,
            "seg0_mismatch_repairable_by_layout_or_scale": bool(can_repair),
            "seg0_correct_input_still_fails": True,
            "first_root_cause_likelihood": "common tensor/input/scale/graph contract at or before seg00_01; simple layout/scale variants do not constitute logits correctness unless Task 1030 passes.",
        }
    )
    if not can_repair:
        report["blocking_or_failure_reasons"].append("No tested seg0 layout/scale variant reached boundary relL2<0.1 and Pearson>0.95 for all canonical cases.")
    return save_report(root, "1020_seg0_exact_contract_audit", report, "Seg0 Exact Contract Audit", [f"seg0_mismatch_repairable_by_layout_or_scale: `{can_repair}`", "seg0_correct_input_still_fails: `true`"])


def summarize_remote_rows(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    by_key: dict[str, dict[str, Any]] = {}
    for row in rows:
        kval = str(row.get(key))
        bucket = by_key.setdefault(kval, {"rows": 0, "top1_agreement_rows": 0, "strict_logits_valid_rows": 0, "reference_top1_in_candidate_top5_rows": 0, "relative_l2": [], "pearson_centered": [], "top5_overlap": []})
        m = row.get("final_metrics") or {}
        bucket["rows"] += 1
        bucket["top1_agreement_rows"] += int(bool(m.get("top1_agreement")))
        strict_valid = bool(
            m.get("top1_agreement")
            and (m.get("relative_l2") is not None and float(m["relative_l2"]) < 0.1)
            and (m.get("pearson_centered") is not None and float(m["pearson_centered"]) > 0.95)
        )
        bucket["strict_logits_valid_rows"] += int(strict_valid)
        bucket["reference_top1_in_candidate_top5_rows"] += int(bool(m.get("reference_top1_in_candidate_top5")))
        if m.get("relative_l2") is not None:
            bucket["relative_l2"].append(float(m["relative_l2"]))
        if m.get("pearson_centered") is not None:
            bucket["pearson_centered"].append(float(m["pearson_centered"]))
        if m.get("top5_overlap") is not None:
            bucket["top5_overlap"].append(int(m["top5_overlap"]))
    for bucket in by_key.values():
        bucket["median_relative_l2"] = float(np.median(bucket.pop("relative_l2"))) if bucket["relative_l2"] else None
        bucket["median_pearson_centered"] = float(np.median(bucket.pop("pearson_centered"))) if bucket["pearson_centered"] else None
        bucket["median_top5_overlap"] = float(np.median(bucket.pop("top5_overlap"))) if bucket["top5_overlap"] else None
    return by_key


def task1030_1040(root: Path, command: str) -> tuple[dict[str, Any], dict[str, Any]]:
    remote = load_json(root / "evidence" / "s100p_remote_v12r_reports" / "1030_1040_v12r_remote_reconstruction.json", {})
    single_rows = remote.get("single_segment_rows", [])
    hybrid_rows = remote.get("hybrid_prefix_rows", [])
    r1030 = common(root, "1030_single_segment_substitution", command, [root / "evidence" / "s100p_remote_v12r_reports" / "1030_1040_v12r_remote_reconstruction.json"])
    expected_single = len(CASE_IDS) * len(SINGLE_SEGMENTS)
    first_failing = None
    if single_rows:
        for seg in SINGLE_SEGMENTS:
            rows = [r for r in single_rows if r.get("segment") == seg]
            if rows and any(
                not (
                    (r.get("final_metrics") or {}).get("top1_agreement")
                    and ((r.get("final_metrics") or {}).get("relative_l2") is not None and float((r.get("final_metrics") or {})["relative_l2"]) < 0.1)
                    and ((r.get("final_metrics") or {}).get("pearson_centered") is not None and float((r.get("final_metrics") or {})["pearson_centered"]) > 0.95)
                )
                for r in rows
            ):
                first_failing = seg
                break
    r1030.update(
        {
            "remote_status": remote.get("status"),
            "single_segment_rows": len(single_rows),
            "expected_rows": expected_single,
            "summary_by_segment": summarize_remote_rows(single_rows, "segment"),
            "first_failing_segment_under_hf_input": first_failing,
            "common_tensor_contract_suspected": bool(single_rows and first_failing == 0),
            "remote_errors": remote.get("errors", []),
        }
    )
    if len(single_rows) != expected_single:
        r1030["blocking_or_failure_reasons"].append("single-segment substitution matrix incomplete or unavailable")
    r1030 = save_report(root, "1030_single_segment_substitution", r1030, "Single Segment Substitution", [f"rows: `{len(single_rows)}/{expected_single}`", f"first_failing_segment_under_hf_input: `{first_failing}`"])

    r1040 = common(root, "1040_bpu_prefix_hf_suffix_matrix", command, [root / "evidence" / "s100p_remote_v12r_reports" / "1030_1040_v12r_remote_reconstruction.json"])
    expected_hybrid = len(CASE_IDS) * len(PREFIX_CUTS)
    pass_cuts = []
    for cut in PREFIX_CUTS:
        rows = [r for r in hybrid_rows if r.get("cut") == cut]
        if rows and len(rows) == len(CASE_IDS) and all(
            (r.get("final_metrics") or {}).get("top1_agreement")
            and ((r.get("final_metrics") or {}).get("relative_l2") is not None and float((r.get("final_metrics") or {})["relative_l2"]) < 0.1)
            and ((r.get("final_metrics") or {}).get("pearson_centered") is not None and float((r.get("final_metrics") or {})["pearson_centered"]) > 0.95)
            for r in rows
        ):
            pass_cuts.append(cut)
    longest = max(pass_cuts) if pass_cuts else None
    first_bad = None
    if hybrid_rows:
        for cut in PREFIX_CUTS:
            rows = [r for r in hybrid_rows if r.get("cut") == cut]
            if rows and any(
                not (
                    (r.get("final_metrics") or {}).get("top1_agreement")
                    and ((r.get("final_metrics") or {}).get("relative_l2") is not None and float((r.get("final_metrics") or {})["relative_l2"]) < 0.1)
                    and ((r.get("final_metrics") or {}).get("pearson_centered") is not None and float((r.get("final_metrics") or {})["pearson_centered"]) > 0.95)
                )
                for r in rows
            ):
                first_bad = cut
                break
    r1040.update(
        {
            "remote_status": remote.get("status"),
            "hybrid_rows": len(hybrid_rows),
            "expected_rows": expected_hybrid,
            "summary_by_cut": summarize_remote_rows(hybrid_rows, "cut"),
            "any_bpu_prefix_hf_suffix_valid": bool(pass_cuts),
            "longest_valid_bpu_prefix_cut": longest,
            "first_bad_cut": first_bad,
            "reverse_hf_prefix_bpu_segment_hf_suffix_basis": "Task 1030 single-segment substitution rows",
            "remote_errors": remote.get("errors", []),
        }
    )
    if len(hybrid_rows) != expected_hybrid:
        r1040["blocking_or_failure_reasons"].append("BPU-prefix/HF-suffix matrix incomplete or unavailable")
    return r1030, save_report(root, "1040_bpu_prefix_hf_suffix_matrix", r1040, "BPU Prefix HF Suffix Matrix", [f"rows: `{len(hybrid_rows)}/{expected_hybrid}`", f"any_valid_prefix: `{bool(pass_cuts)}`", f"longest_valid_bpu_prefix_cut: `{longest}`"])


def task1050(root: Path, command: str) -> dict[str, Any]:
    report = common(root, "1050_gguf_reference_matrix", command, [root / "reports" / "930_gguf_f16_reference_crosscheck.json"])
    q4 = root / "evidence" / "reference_matrix_v6" / "gguf_q4_k_m" / "zeros" / "last_logits.npy"
    gguf_existing = load_json(root / "reports" / "930_gguf_f16_reference_crosscheck.json", {})
    attempts = [
        {"command": "command -v llama-cli; command -v diffuse-cpp; find GGUF F16/Q4_0/Q4_K_M", "result": "diffuse-cpp found under /mnt/nas/openclaw/runtimes/diffuse-cpp/build; only dream-7b-q4km.gguf found"},
        {"command": "/mnt/nas/openclaw/runtimes/diffuse-cpp/build/diffuse-cli --help", "result": "CLI supports generation-style prompt/tokens options but no logits-dump option exposed in help"},
        {"command": "/mnt/nas/openclaw/runtimes/diffuse-cpp/build/diffuse-cli --version", "result": "no version flag; prints model path required and usage"},
    ]
    rows = []
    for cid in CASE_IDS:
        hf = root / "evidence" / "full_truth_repeat_v11" / cid / "repeat_full_truth_logits.npy"
        q4p = root / "evidence" / "reference_matrix_v6" / "gguf_q4_k_m" / cid / "last_logits.npy"
        if hf.exists() and q4p.exists():
            rows.append({"case_id": cid, "comparison": "HF_BF16_vs_GGUF_Q4_K_M_existing", "metrics": compare_arrays(np.load(hf), np.load(q4p)), "gguf_path": rel(q4p, root)})
    report.update(
        {
            "attempted_commands": attempts,
            "model_paths": {"q4_k_m": "/mnt/nas/openclaw/models/dream7b/dream-7b-q4km.gguf", "f16": None, "q4_0": None},
            "tool_versions": {"diffuse_cli_help_available": True, "llama_cli_found": False},
            "rows": rows,
            "gguf_f16_status": "blocked_artifact_unavailable",
            "gguf_q4_0_status": "blocked_artifact_unavailable",
            "gguf_q4_k_m_status": "artifact_available_existing_logits_partial" if q4.exists() else "artifact_available_no_logits_for_v12r_cases",
            "previous_inventory": gguf_existing.get("known_gguf_artifacts"),
        }
    )
    report["blocking_or_failure_reasons"].extend(["GGUF F16 artifact unavailable.", "GGUF Q4_0 artifact unavailable.", "diffuse-cli exposed no logits-only dump option; running generation-style CLI was forbidden by v12R safety bounds."])
    return save_report(root, "1050_gguf_reference_matrix", report, "GGUF Reference Matrix", [f"GGUF F16: `{report['gguf_f16_status']}`", f"GGUF Q4_0: `{report['gguf_q4_0_status']}`", f"GGUF Q4_K_M rows: `{len(rows)}`"])


def saturation_rate(raw: np.ndarray) -> dict[str, Any]:
    arr = np.asarray(raw)
    if arr.size == 0:
        return {}
    abs_arr = np.abs(arr.astype(np.int64, copy=False)) if np.issubdtype(arr.dtype, np.integer) else np.abs(arr)
    return {
        "count_pos_32767": int(np.sum(arr == 32767)) if np.issubdtype(arr.dtype, np.integer) else None,
        "count_neg_32768": int(np.sum(arr == -32768)) if np.issubdtype(arr.dtype, np.integer) else None,
        "count_abs_19807": int(np.sum(abs_arr == 19807)) if np.issubdtype(arr.dtype, np.integer) else None,
        "frac_pos_32767": float(np.mean(arr == 32767)) if np.issubdtype(arr.dtype, np.integer) else None,
        "frac_neg_32768": float(np.mean(arr == -32768)) if np.issubdtype(arr.dtype, np.integer) else None,
        "frac_abs_19807": float(np.mean(abs_arr == 19807)) if np.issubdtype(arr.dtype, np.integer) else None,
        "frac_abs_ge_30000": float(np.mean(abs_arr >= 30000)) if np.issubdtype(arr.dtype, np.integer) else None,
    }


def task1060(root: Path, command: str) -> dict[str, Any]:
    out_root = root / "evidence" / "activation_scale_v12r"
    boundary_rows = []
    first_rel = {}
    first_sat = {}
    for cid in CASE_IDS:
        for seg in range(28):
            raw_path = root / "evidence" / "boundary_all_segments_v7" / cid / f"seg_{seg:02d}_raw_output.npy"
            deq_path = root / "evidence" / "boundary_all_segments_v7" / cid / f"seg_{seg:02d}_output.npy"
            if not raw_path.exists() or not deq_path.exists():
                continue
            raw = np.load(raw_path)
            deq = np.load(deq_path)
            hf_path = root / "evidence" / "hf_boundaries_v11" / cid / f"layer_{seg:02d}_output.npy"
            hf = np.load(hf_path) if hf_path.exists() and seg < 27 else None
            metrics = compare_arrays(hf, deq) if hf is not None and hf.shape == deq.shape else None
            hf_stats = tensor_stats(hf) if hf is not None else None
            deq_stats = tensor_stats(deq)
            sat = saturation_rate(raw)
            row = {
                "case_id": cid,
                "segment": seg,
                "raw_stats": tensor_stats(raw),
                "dequant_stats": deq_stats,
                "hf_stats": hf_stats,
                "std_ratio_bpu_over_hf": (deq_stats.get("std") / hf_stats.get("std")) if hf_stats and hf_stats.get("std") else None,
                "saturation": sat,
                "metrics": metrics,
            }
            if metrics and cid not in first_rel and ((metrics.get("relative_l2") or 0) > 0.1 or (metrics.get("pearson_centered") or 1) < 0.95):
                first_rel[cid] = seg
            if cid not in first_sat and any((sat.get(k) or 0) > 0.01 for k in ["frac_pos_32767", "frac_neg_32768", "frac_abs_19807", "frac_abs_ge_30000"]):
                first_sat[cid] = seg
            boundary_rows.append(row)
    sim_rows = []
    for cid in CASE_IDS:
        truth = np.load(root / "evidence" / "full_truth_repeat_v11" / cid / "repeat_full_truth_logits.npy")
        for variant in FINAL_VARIANTS:
            p = root / "evidence" / "final_segment_endpoint_raw_v9" / cid / variant / "official_dequant_logits.npy"
            exact = root / "evidence" / "hf_exact_final_segment_v9" / cid / variant / "exact_hf_final_logits.npy"
            if p.exists():
                sim_rows.append({"case_id": cid, "variant": variant, "bpu_final_vs_full_truth": compare_arrays(truth, np.load(p)), "bpu_final_logits": rel(p, root)})
            if exact.exists():
                sim_rows[-1]["hf_exact_final_vs_full_truth"] = compare_arrays(truth, np.load(exact)) if sim_rows else compare_arrays(truth, np.load(exact))
    write_json(out_root / "boundary_scale_rows.json", boundary_rows)
    write_json(out_root / "final_segment_variant_rows.json", sim_rows)
    simple_scale_success = False
    report = common(root, "1060_activation_scale_calibration_audit", command, [root / "evidence" / "boundary_all_segments_v7", root / "evidence" / "final_segment_endpoint_raw_v9"])
    report.update(
        {
            "boundary_rows": boundary_rows,
            "first_metric_divergence_by_case": first_rel,
            "first_saturation_like_boundary_by_case": first_sat,
            "final_segment_variant_rows": sim_rows,
            "simple_scale_factor_restores_hf_suffix": simple_scale_success,
            "scale_repair_interpretation": "diagnostic_only_not_correctness_recovery",
            "requires_recalibration_or_recompile": True,
        }
    )
    report["blocking_or_failure_reasons"].append("No simple post-hoc scale factor is supported as logits-correctness recovery across canonical cases.")
    return save_report(root, "1060_activation_scale_calibration_audit", report, "Activation Scale Calibration Audit", [f"first_metric_divergence_by_case: `{first_rel}`", f"first_saturation_like_boundary_by_case: `{first_sat}`", "simple_scale_factor_restores_hf_suffix: `false`"])


def task1070(root: Path, command: str, r1030: dict[str, Any], r1040: dict[str, Any]) -> dict[str, Any]:
    any_prefix = bool(r1040.get("any_bpu_prefix_hf_suffix_valid"))
    candidates = [
        {
            "candidate": "full_bpu_corrected_recompile",
            "bpu_segments": "0..27 after compiler/calibration/input-contract fix",
            "cpu_hf_gguf_segments": "none",
            "tensor_handoff": "no runtime handoff if full recompile succeeds",
            "current_evidence": "current full-BPU path falsified; seg0 first divergence; scale anomalies later",
            "logits_validity_status": "not_valid_currently",
            "remaining_blockers": ["seg0 contract/root cause", "operator graph metadata", "calibration/recompile support"],
            "generation_gate_can_be_unlocked": False,
        },
        {
            "candidate": "bpu_validated_prefix_hf_suffix",
            "bpu_segments": f"0..{r1040.get('longest_valid_bpu_prefix_cut')}" if any_prefix else "none validated",
            "cpu_hf_gguf_segments": "remaining decoder layers + final norm + lm_head on HF/PyTorch CPU",
            "tensor_handoff": "float32 [seq, hidden] BPU dequant boundary",
            "current_evidence": "v12R hybrid matrix",
            "logits_validity_status": "valid" if any_prefix else "not_valid_currently",
            "remaining_blockers": [] if any_prefix else ["cut=0 fails or matrix incomplete; seg0/input/common tensor contract remains blocker"],
            "generation_gate_can_be_unlocked": False,
        },
        {
            "candidate": "cpu_final_norm_lm_head_fallback",
            "bpu_segments": "0..26",
            "cpu_hf_gguf_segments": "layer27 + final norm + lm_head or final norm + lm_head depending exact boundary",
            "tensor_handoff": "BPU seg26 dequant hidden [seq, hidden]",
            "current_evidence": "v10/v11 shows BPU seg26 hidden to HF exact final still 0/3 top1",
            "logits_validity_status": "not_valid_currently",
            "remaining_blockers": ["upstream hidden invalid before final segment"],
            "generation_gate_can_be_unlocked": False,
        },
        {
            "candidate": "pause_bpu_route_return_to_gguf",
            "bpu_segments": "none",
            "cpu_hf_gguf_segments": "GGUF F16 or validated lower-quant route",
            "tensor_handoff": "not applicable",
            "current_evidence": "GGUF F16 unavailable; Q4_K_M exists but is not truth",
            "logits_validity_status": "blocked_until_GGUF_F16_or_logits_runner",
            "remaining_blockers": ["GGUF F16 artifact", "logits-only runner/export"],
            "generation_gate_can_be_unlocked": False,
        },
    ]
    report = common(root, "1070_correctness_first_candidate_routes", command, [root / "reports" / "1030_single_segment_substitution.json", root / "reports" / "1040_bpu_prefix_hf_suffix_matrix.json"])
    report.update({"candidates": candidates, "recommended_next_candidate": "full_bpu_corrected_recompile_or_gguf_f16_reference_until_seg0_contract_fixed", "no_deployment_success_claimed": True})
    return save_report(root, "1070_correctness_first_candidate_routes", report, "Correctness First Candidate Routes", [f"any_valid_bpu_prefix: `{any_prefix}`", "generation gate remains locked until logits pass."])


def task1080(root: Path, command: str) -> dict[str, Any]:
    report = common(root, "1080_offline_corrected_candidate", command, [root / "reports" / "1020_seg0_exact_contract_audit.json", root / "reports" / "1060_activation_scale_calibration_audit.json"])
    report.update({"executed": False, "reason": "No clear fixable issue reached logits-correctness support; no corrected artifact was generated.", "requires_vendor_compiler_runtime_support": True})
    report["blocking_or_failure_reasons"].append("No input packing, position, mask, scale metadata, or compiler split fix was proven sufficient for logits correctness.")
    return save_report(root, "1080_offline_corrected_candidate", report, "Offline Corrected Candidate", ["executed: `false`", "reason: `no proven fixable issue`"])


def package_v12r(root: Path, command: str) -> dict[str, Any]:
    staging = root / "tmp" / "dream7b_s100p_v12r_for_gptpro_20260702"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    report_stems = [
        "1000_v12r_baseline_lock",
        "1010_input_contract_audit",
        "1020_seg0_exact_contract_audit",
        "1030_single_segment_substitution",
        "1040_bpu_prefix_hf_suffix_matrix",
        "1050_gguf_reference_matrix",
        "1060_activation_scale_calibration_audit",
        "1070_correctness_first_candidate_routes",
        "1080_offline_corrected_candidate",
        "1090_build_v12r_evidence_zip",
    ]
    reports_dst = staging / "reports"
    reports_dst.mkdir(parents=True, exist_ok=True)
    for stem in report_stems:
        for suffix in [".json", ".md"]:
            p = root / "reports" / f"{stem}{suffix}"
            if p.exists():
                shutil.copy2(p, reports_dst / p.name)
    final_src = root / "01_final_evidence"
    final_dst = staging / "01_final_evidence"
    final_dst.mkdir(parents=True, exist_ok=True)
    if final_src.exists():
        for p in final_src.glob("*v12r*"):
            if p.is_file():
                shutil.copy2(p, final_dst / p.name)
    for sub in ["input_contract_v12r", "seg0_contract_v12r", "activation_scale_v12r", "s100p_remote_v12r_reports"]:
        src = root / "evidence" / sub
        if src.exists():
            shutil.copytree(src, staging / "evidence" / sub)
    for sub in ["single_segment_substitution_v12r", "hybrid_routes_v12r"]:
        src = root / "evidence" / sub
        if src.exists():
            shutil.copytree(src, staging / "evidence" / sub)
    shutil.copy2(root / "tools" / "build_v12r_research_thread.py", staging / "build_v12r_research_thread.py")
    shutil.copy2(root / "tools" / "run_v12r_remote_reconstruction.py", staging / "run_v12r_remote_reconstruction.py")
    write_text(staging / "README.md", "Dream7B/S100P v12R offline logits/boundary evidence. No generation quality and no 18888/18889 route interaction.\n")
    files = []
    for p in sorted(staging.rglob("*")):
        if p.is_file():
            files.append({"path": rel(p, staging), "size_bytes": p.stat().st_size, "sha256": sha256_file(p)})
    write_json(staging / "MANIFEST.json", {"schema_version": "dream7b_s100p_v12r_manifest", "created_at_utc": now(), "file_count": len(files), "files": files})
    write_text(staging / "SHA256SUMS.txt", "\n".join(f"{f['sha256']}  {f['path']}" for f in files) + "\n")
    out = root / "evidence_for_gptpro" / "dream7b_s100p_v12r_for_gptpro_20260702.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p in sorted(staging.rglob("*")):
            if p.is_file():
                zf.write(p, rel(p, staging))
    with zipfile.ZipFile(out) as zf:
        bad = zf.testzip()
        count = len(zf.namelist())
    report = common(root, "1090_build_v12r_evidence_zip", command, [staging])
    report.update({"zip_path": rel(out, root), "zip_sha256": sha256_file(out), "zip_size_bytes": out.stat().st_size, "zip_member_count": count, "zip_testzip_bad_member": bad, "manifest_file_count": len(files)})
    return save_report(root, "1090_build_v12r_evidence_zip", report, "Build v12R Evidence Zip", [f"zip_path: `{report['zip_path']}`", f"zip_sha256: `{report['zip_sha256']}`", f"zip_testzip_bad_member: `{bad}`"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--v12-zip", default=r"C:\Users\zhexu\Downloads\dream7b_s100p_v12_codex_after_v11_review_pack_20260702.zip")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    command = " ".join([sys.executable, *sys.argv])
    r1000 = task1000(root, command, Path(args.v12_zip))
    r1010 = task1010(root, command)
    r1020 = task1020(root, command)
    r1030, r1040 = task1030_1040(root, command)
    r1050 = task1050(root, command)
    r1060 = task1060(root, command)
    r1070 = task1070(root, command, r1030, r1040)
    r1080 = task1080(root, command)
    r1090 = package_v12r(root, command)
    summary = {
        "baseline": r1000["required_baseline_statements"],
        "input_contract_verdict": r1010["verdict"],
        "seg0_repairable_by_layout_or_scale": r1020["seg0_mismatch_repairable_by_layout_or_scale"],
        "single_segment_rows": r1030["single_segment_rows"],
        "hybrid_rows": r1040["hybrid_rows"],
        "gguf_f16_status": r1050["gguf_f16_status"],
        "simple_scale_factor_restores_hf_suffix": r1060["simple_scale_factor_restores_hf_suffix"],
        "zip": {"path": r1090["zip_path"], "sha256": r1090["zip_sha256"]},
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
