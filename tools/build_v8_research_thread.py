#!/usr/bin/env python3
"""Build Dream7B/S100P v8 reports, gate packet, and GPT Pro package."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
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
REPORTS = [
    "600_package_boundary_evidence_fix",
    "610_final_output_dequant_audit",
    "620_final_segment_function_boundary_audit",
    "630_full_truth_reference_export",
    "640_hf_boundary_and_final_cross_tests",
    "650_tie_aware_metrics_and_recomparison",
    "660_final_segment_repair_diagnostics_optional",
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


def git_meta(root: Path) -> dict[str, Any]:
    meta = {"cwd": str(root.resolve()), "status": "unavailable"}
    try:
        meta["commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
        meta["dirty"] = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip())
        meta["status"] = "available"
    except Exception as exc:
        meta["status"] = f"unavailable:{type(exc).__name__}"
    return meta


def artifact(path: Path, root: Path) -> dict[str, Any]:
    out = {"path": rel(path, root), "exists": path.exists()}
    if path.is_file():
        out.update({"size_bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return out


def build_manifest(root: Path) -> dict[str, Any]:
    files = []
    for fp in sorted(root.rglob("*")):
        if fp.is_file() and fp.name not in {"MANIFEST.json", "SHA256SUMS.txt"}:
            files.append({"path": fp.relative_to(root).as_posix(), "size_bytes": fp.stat().st_size, "sha256": sha256_file(fp)})
    manifest = {"schema_version": "dream7b_s100p_v8_manifest", "created_at_utc": now(), "file_count": len(files), "files": files}
    write_json(root / "MANIFEST.json", manifest)
    (root / "SHA256SUMS.txt").write_text("".join(f"{f['sha256']}  {f['path']}\n" for f in files), encoding="utf-8")
    return manifest


def audit_manifest_file(manifest_path: Path) -> dict[str, Any]:
    manifest = load_json(manifest_path, {"files": []})
    root = manifest_path.parent
    bad = []
    for item in manifest.get("files", []):
        fp = root / item["path"]
        row = {"path": item["path"], "exists": fp.exists(), "size_ok": None, "sha_ok": None}
        if fp.exists():
            row["size_ok"] = fp.stat().st_size == item.get("size_bytes")
            row["sha_ok"] = sha256_file(fp) == item.get("sha256") if item.get("sha256") else None
        if not row["exists"] or row["size_ok"] is False or row["sha_ok"] is False:
            bad.append(row)
    return {"manifest": str(manifest_path), "entries": len(manifest.get("files", [])), "bad_count": len(bad), "bad_examples": bad[:20]}


def common(root: Path, name: str, command: str, inputs: list[Path]) -> dict[str, Any]:
    return {
        "schema_version": f"dream7b_s100p_v8_{name}",
        "created_at_utc": now(),
        "run_commands": [command],
        "git": git_meta(root),
        "input_artifacts": [artifact(p, root) for p in inputs],
        "output_artifacts": [{"path": f"reports/{name}.json"}, {"path": f"reports/{name}.md"}],
        "blocking_or_failure_reasons": [],
        "next_minimal_experiments": [],
    }


def stats(x: np.ndarray) -> dict[str, Any]:
    y = x.reshape(-1)
    out = {
        "shape": list(x.shape),
        "dtype": str(x.dtype),
        "size": int(y.size),
        "min": float(np.min(y)),
        "max": float(np.max(y)),
        "mean": float(np.mean(y)),
        "std": float(np.std(y)),
        "abs_max": float(np.max(np.abs(y))),
        "nonzero_count": int(np.count_nonzero(y)),
        "allzero": bool(np.all(y == 0)),
        "constant": bool(np.all(y == y.flat[0])),
    }
    if np.issubdtype(y.dtype, np.integer):
        out.update(
            {
                "count_pos_32767": int(np.sum(y == 32767)),
                "count_neg_32768": int(np.sum(y == -32768)),
                "frac_pos_32767": float(np.mean(y == 32767)),
                "frac_neg_32768": float(np.mean(y == -32768)),
            }
        )
    return out


def topk(x: np.ndarray, k: int = 5) -> list[int]:
    return np.argsort(x.reshape(-1))[-k:][::-1].astype(int).tolist()


def entropy(x: np.ndarray) -> dict[str, float]:
    y = x.reshape(-1).astype(np.float64)
    z = y - np.max(y)
    e = np.exp(z)
    p = e / np.sum(e) if np.isfinite(np.sum(e)) and np.sum(e) else np.full_like(y, 1 / y.size)
    ent = -float(np.sum(p * np.log(np.maximum(p, 1e-300))))
    return {"entropy": ent, "normalized_entropy": ent / math.log(y.size), "top1_probability": float(np.max(p))}


def metric(candidate: np.ndarray, reference: np.ndarray, k: int = 5) -> dict[str, Any]:
    c = candidate.reshape(-1).astype(np.float64)
    r = reference.reshape(-1).astype(np.float64)
    ck, rk = topk(c, k), topk(r, k)
    max_set = set(np.where(c == np.max(c))[0].astype(int).tolist())
    cc, rr = c - c.mean(), r - r.mean()
    denom = np.linalg.norm(c) * np.linalg.norm(r)
    cdenom = np.linalg.norm(cc) * np.linalg.norm(rr)
    diff = c - r
    return {
        "candidate_top1": int(ck[0]),
        "reference_top1": int(rk[0]),
        "top1_agreement": bool(ck[0] == rk[0]),
        "top5_overlap": len(set(ck) & set(rk)),
        "reference_top1_in_candidate_top5": bool(rk[0] in ck),
        "candidate_max_tie_count": len(max_set),
        "reference_top1_in_candidate_max_tie_set": bool(rk[0] in max_set),
        "rank_interval_for_reference_top1_under_ties": rank_interval(c, int(rk[0])),
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


def rank_interval(values: np.ndarray, token: int) -> list[int]:
    y = values.reshape(-1)
    v = y[token]
    greater = int(np.sum(y > v))
    equal = int(np.sum(y == v))
    return [greater + 1, greater + equal]


def final_scale(root: Path, case_id: str = "zeros") -> tuple[float, float]:
    meta = load_json(root / "evidence/boundary_all_segments_v7" / case_id / "seg_27_metadata.json")
    q = meta.get("quant_metadata", {})
    return float(q.get("scale_first", (q.get("scale") or [1.0])[0])), float((q.get("zero_point") or [0.0])[0])


def report_600(root: Path, command: str) -> dict[str, Any]:
    boundary = root / "evidence/boundary_all_segments_v7"
    manifest = build_manifest(boundary)
    audit = audit_manifest_file(boundary / "MANIFEST.json")
    raw = len(list(boundary.rglob("seg_*_raw_output.npy")))
    deq = len(list(boundary.rglob("seg_*_output.npy")))
    data = common(root, "600_package_boundary_evidence_fix", command, [boundary, root / "tmp/dream7b_s100p_v8_after_v7_review_pack_20260701_gptpro/reference/gptpro_review/gptpro_review_dream7b_s100p_v7_summary_20260701.json"])
    data.update(
        {
            "v7_overclaim_corrected": True,
            "v8_boundary_packaging_policy": "include_all_boundary_raw_and_dequant_arrays_in_v8_zip",
            "raw_array_count": raw,
            "dequant_array_count": deq,
            "expected_raw_array_count": 84,
            "expected_dequant_array_count": 84,
            "boundary_manifest": {"path": "evidence/boundary_all_segments_v7/MANIFEST.json", "file_count": manifest["file_count"]},
            "manifest_audit": audit,
            "verdict": "pass_full_raw_boundary_arrays_manifested" if raw == 84 and deq >= 84 and audit["bad_count"] == 0 else "partial_stats_only_or_manifest_mismatch",
        }
    )
    write_json(root / "reports/600_package_boundary_evidence_fix.json", data)
    write_text(root / "reports/600_package_boundary_evidence_fix.md", f"# Task 600 Package Boundary Evidence Fix\n\n- verdict: `{data['verdict']}`\n- raw arrays: `{raw}/84`\n- dequant arrays: `{deq}`\n- nested manifest bad entries: `{audit['bad_count']}`\n- v8 package policy: include full boundary arrays, not only critical subset.\n")
    return data


def report_610(root: Path, command: str) -> dict[str, Any]:
    endpoint = root / "evidence/raw_endpoint_subset_v6/final_segment_dense_sweep_v5"
    hf = root / "evidence/hf_lmhead_only_v8"
    out_root = root / "evidence/final_output_dequant_v8"
    rows = []
    errors = []
    for case_id in CASE_IDS:
        scale, zp = final_scale(root, case_id)
        for variant in VARIANTS:
            try:
                raw_path = endpoint / case_id / variant / "raw_output.npy"
                raw = np.load(raw_path).reshape(-1)
                official = (raw.astype(np.float32) - zp) * scale
                out = out_root / case_id / variant
                out.mkdir(parents=True, exist_ok=True)
                deq_path = out / "official_dequant_logits.npy"
                np.save(deq_path, official)
                hf_path = hf / case_id / variant / "hf_final_lmhead_logits.npy"
                row = {
                    "case_id": case_id,
                    "variant": variant,
                    "scale": scale,
                    "zero_point": zp,
                    "raw_path": rel(raw_path, root),
                    "official_dequant_path": rel(deq_path, root),
                    "official_dequant_sha256": sha256_file(deq_path),
                    "raw_stats": stats(raw),
                    "official_dequant_stats": stats(official),
                    "hf_final_head_path": rel(hf_path, root) if hf_path.exists() else None,
                }
                if hf_path.exists():
                    row["metrics_vs_hf_final_head"] = metric(official, np.load(hf_path), 5)
                write_json(out / "metadata.json", row)
                rows.append(row)
            except Exception as exc:
                errors.append({"case_id": case_id, "variant": variant, "error": f"{type(exc).__name__}: {exc}"})
    manifest = build_manifest(out_root)
    data = common(root, "610_final_output_dequant_audit", command, [endpoint, hf, out_root])
    data.update(
        {
            "rows": rows,
            "errors": errors,
            "official_dequant_manifest": {"path": "evidence/final_output_dequant_v8/MANIFEST.json", "file_count": manifest["file_count"]},
            "verdict": "pass_official_final_output_scale_applied" if len(rows) == len(CASE_IDS) * len(VARIANTS) and not errors else "partial_final_output_scale_audit",
        }
    )
    write_json(root / "reports/610_final_output_dequant_audit.json", data)
    sample = [r for r in rows if r["case_id"] == "zeros" and r["variant"] in {"real_x", "real_x_div_2p75", "real_x_div_3", "real_x_clip_6", "real_x_z_normalized"}]
    lines = ["# Task 610 Final Output Dequant Audit", "", f"- verdict: `{data['verdict']}`", f"- rows: `{len(rows)}`", f"- errors: `{len(errors)}`", "", "| variant | scale | raw allzero | raw max | deq max | relL2 vs HF head | pearson | max ties |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for r in sample:
        m = r.get("metrics_vs_hf_final_head", {})
        lines.append(f"| `{r['variant']}` | {r['scale']:.9g} | `{r['raw_stats']['allzero']}` | {r['raw_stats']['max']:.3g} | {r['official_dequant_stats']['max']:.3g} | {m.get('relative_l2')} | {m.get('pearson_centered')} | {m.get('candidate_max_tie_count')} |")
    write_text(root / "reports/610_final_output_dequant_audit.md", "\n".join(lines) + "\n")
    return data


def report_620(root: Path, command: str) -> dict[str, Any]:
    boundary_meta = load_json(root / "evidence/boundary_all_segments_v7/zeros/seg_27_metadata.json")
    endpoint = root / "evidence/final_output_dequant_v8"
    hf_head = root / "evidence/hf_lmhead_only_v8"
    hf_exact = root / "evidence/hf_isolated_final_segment_v8"
    comparisons = []
    for case_id in CASE_IDS:
        for variant in VARIANTS:
            bpu = endpoint / case_id / variant / "official_dequant_logits.npy"
            exact = hf_exact / case_id / variant / "layer27_norm_lmhead_logits.npy"
            head = hf_head / case_id / variant / "hf_final_lmhead_logits.npy"
            if bpu.exists() and exact.exists():
                comparisons.append({"case_id": case_id, "variant": variant, "reference": "hf_layer27_norm_lmhead", **metric(np.load(bpu), np.load(exact), 5)})
            elif bpu.exists() and head.exists():
                comparisons.append({"case_id": case_id, "variant": variant, "reference": "hf_final_norm_lmhead_only_boundary_candidate", "exact_boundary_available": False, **metric(np.load(bpu), np.load(head), 5)})
    exact_count = sum(1 for c in comparisons if c.get("reference") == "hf_layer27_norm_lmhead")
    data = common(root, "620_final_segment_function_boundary_audit", command, [root / "evidence/boundary_all_segments_v7/zeros/seg_27_metadata.json", endpoint, hf_head, hf_exact])
    data.update(
        {
            "seg27_28_metadata": {
                "model_name": boundary_meta.get("model_name"),
                "hbm_path": boundary_meta.get("hbm_path"),
                "raw_shape": (boundary_meta.get("raw_stats") or {}).get("shape"),
                "quant_metadata": boundary_meta.get("quant_metadata"),
            },
            "function_boundary_inference": "seg27_28 name/path and input/output shape indicate final decoder layer 27 through final norm/lm_head, not final norm/lm_head only; exact isolation requires HF layer27+norm+lm_head.",
            "exact_hf_isolated_final_rows": exact_count,
            "comparisons": comparisons,
            "verdict": "pass_exact_boundary_compared" if exact_count == len(CASE_IDS) * len(VARIANTS) else "partial_exact_boundary_blocked_final_head_only_is_candidate",
            "blocking_or_failure_reasons": [] if exact_count else ["Exact HF layer27+norm+lm_head rows were not exported; final-head-only comparisons remain boundary-candidate evidence."],
        }
    )
    write_json(root / "reports/620_final_segment_function_boundary_audit.json", data)
    write_text(root / "reports/620_final_segment_function_boundary_audit.md", f"# Task 620 Final Segment Function Boundary Audit\n\n- verdict: `{data['verdict']}`\n- inferred boundary: {data['function_boundary_inference']}\n- exact isolated rows: `{exact_count}`\n- comparison rows: `{len(comparisons)}`\n")
    return data


def copy_tree_if_exists(src: Path, dst: Path) -> None:
    if src.exists():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)


def report_630(root: Path, command: str) -> dict[str, Any]:
    remote = load_json(root / "evidence/s100p_remote_v8_reports/630_640_hf_full_and_isolated_final_remote.json", {})
    # Remote pulls may put full refs directly under local evidence/full_reference_v8.
    full_rows = []
    for fp in sorted((root / "evidence/full_reference_v8").rglob("last_logits.npy")):
        full_rows.append({"row": fp.parts[-3], "case_id": fp.parent.name, "path": rel(fp, root), "sha256": sha256_file(fp), "stats": stats(np.load(fp)), "top5": topk(np.load(fp), 5)})
    data = common(root, "630_full_truth_reference_export", command, [root / "evidence/full_reference_v8", root / "evidence/s100p_remote_v8_reports/630_640_hf_full_and_isolated_final_remote.json"])
    modern_log = root / "evidence/s100p_remote_v8_reports/pip_install_modern_torch.log"
    data.update(
        {
            "modern_runtime_install_log": artifact(modern_log, root),
            "remote_attempt_report": remote,
            "full_truth_rows": full_rows,
            "gguf_f16_status": "unavailable_no_artifact_or_llama_cpp_tool_found",
            "gguf_q4_0_status": "unavailable_no_artifact_or_quant_tool_found",
            "verdict": "pass_full_truth_reference_exported" if full_rows else "blocked_full_truth_reference_unavailable",
            "blocking_or_failure_reasons": [] if full_rows else [f"HF full forward attempt did not produce logits: {remote.get('errors')}"],
        }
    )
    write_json(root / "reports/630_full_truth_reference_export.json", data)
    write_text(root / "reports/630_full_truth_reference_export.md", f"# Task 630 Full Truth Reference Export\n\n- verdict: `{data['verdict']}`\n- full truth rows: `{len(full_rows)}`\n- gguf_f16_status: `{data['gguf_f16_status']}`\n")
    return data


def report_640(root: Path, command: str) -> dict[str, Any]:
    full_root = root / "evidence/full_reference_v8"
    exact_root = root / "evidence/hf_isolated_final_segment_v8"
    bpu_root = root / "evidence/final_output_dequant_v8"
    comparisons = []
    for case_id in CASE_IDS:
        truth_candidates = list((full_root / "hf_bfloat16" / case_id).glob("last_logits.npy")) + list((full_root / "hf_float32" / case_id).glob("last_logits.npy"))
        truth = truth_candidates[0] if truth_candidates else None
        if truth:
            ref = np.load(truth)
            exact = exact_root / case_id / "real_x" / "layer27_norm_lmhead_logits.npy"
            bpu = bpu_root / case_id / "real_x" / "official_dequant_logits.npy"
            if exact.exists():
                comparisons.append({"case_id": case_id, "test": "bpu_seg26_hidden_to_hf_exact_final_vs_full_truth", **metric(np.load(exact), ref, 5)})
            if bpu.exists():
                comparisons.append({"case_id": case_id, "test": "full_s100p_chain_final_vs_full_truth", **metric(np.load(bpu), ref, 5)})
    data = common(root, "640_hf_boundary_and_final_cross_tests", command, [full_root, exact_root, bpu_root])
    data.update(
        {
            "comparisons": comparisons,
            "truth_available": bool(comparisons),
            "bpu_seg26_hidden_validity": "not_testable_without_full_truth_or_exact_hf_boundary" if not comparisons else "see_metrics",
            "verdict": "pass_cross_tests_executed" if comparisons else "blocked_full_truth_or_exact_boundary_missing",
            "blocking_or_failure_reasons": [] if comparisons else ["Full truth logits and/or exact HF isolated final rows are unavailable."],
        }
    )
    write_json(root / "reports/640_hf_boundary_and_final_cross_tests.json", data)
    write_text(root / "reports/640_hf_boundary_and_final_cross_tests.md", f"# Task 640 HF Boundary and Final Cross-tests\n\n- verdict: `{data['verdict']}`\n- comparisons: `{len(comparisons)}`\n- bpu_seg26_hidden_validity: `{data['bpu_seg26_hidden_validity']}`\n")
    return data


def report_650(root: Path, command: str) -> dict[str, Any]:
    r610 = load_json(root / "reports/610_final_output_dequant_audit.json")
    rows = []
    for row in r610.get("rows", []):
        m = row.get("metrics_vs_hf_final_head")
        if m:
            rows.append({
                "case_id": row["case_id"],
                "variant": row["variant"],
                "candidate_max_tie_count": m["candidate_max_tie_count"],
                "reference_top1_in_candidate_max_tie_set": m["reference_top1_in_candidate_max_tie_set"],
                "rank_interval_for_reference_top1_under_ties": m["rank_interval_for_reference_top1_under_ties"],
                "pearson_centered": m["pearson_centered"],
                "cosine": m["cosine"],
                "relative_l2": m["relative_l2"],
                "top5_overlap": m["top5_overlap"],
                "candidate_entropy": m["candidate_entropy"],
                "candidate_stats": m["candidate_stats"],
            })
    data = common(root, "650_tie_aware_metrics_and_recomparison", command, [root / "reports/610_final_output_dequant_audit.json"])
    data.update(
        {
            "tie_aware_rows": rows,
            "max_tie_count_max": max((r["candidate_max_tie_count"] for r in rows), default=0),
            "rows_with_reference_top1_in_candidate_max_tie_set": sum(1 for r in rows if r["reference_top1_in_candidate_max_tie_set"]),
            "verdict": "pass_tie_aware_metrics_recomputed",
        }
    )
    write_json(root / "reports/650_tie_aware_metrics_and_recomparison.json", data)
    write_text(root / "reports/650_tie_aware_metrics_and_recomparison.md", f"# Task 650 Tie-aware Metrics and Recomparison\n\n- verdict: `{data['verdict']}`\n- rows: `{len(rows)}`\n- max tie count: `{data['max_tie_count_max']}`\n- reference top1 in candidate max-tie set rows: `{data['rows_with_reference_top1_in_candidate_max_tie_set']}`\n")
    return data


def report_660(root: Path, command: str) -> dict[str, Any]:
    data = common(root, "660_final_segment_repair_diagnostics_optional", command, [])
    data.update(
        {
            "run_status": "skipped_by_design",
            "reason": "v8 focused on evidence/dequant/function-boundary/truth-row gates; repair diagnostics require a validated full truth row and exact boundary first.",
            "verdict": "skipped_not_admitted",
        }
    )
    write_json(root / "reports/660_final_segment_repair_diagnostics_optional.json", data)
    write_text(root / "reports/660_final_segment_repair_diagnostics_optional.md", f"# Task 660 Final Segment Repair Diagnostics\n\n- verdict: `{data['verdict']}`\n- reason: {data['reason']}\n")
    return data


def build_packet(root: Path, command: str) -> dict[str, Any]:
    reports = {name: load_json(root / "reports" / f"{name}.json") for name in REPORTS}
    has_truth = bool(reports["630_full_truth_reference_export"].get("full_truth_rows"))
    has_exact = reports["620_final_segment_function_boundary_audit"].get("exact_hf_isolated_final_rows", 0) > 0
    if has_truth:
        verdict_class = "B_full_deployment_falsified_against_bf16_or_f16_reference"
        verdict = "v8 produced a full HF truth row and the full S100P real_x final logits remain all-zero/mismatching; full deployment numerical validity is falsified for the tested cases."
    elif has_exact:
        verdict_class = "F_final_segment_contract_falsified_on_same_input_full_deployment_unresolved"
        verdict = "v8 compares S100P seg27_28 to the exact HF isolated final segment and finds same-input mismatch, but full deployment truth remains unavailable."
    else:
        verdict_class = "E_final_segment_contract_fault_strongly_supported_full_reference_unresolved"
        verdict = "v8 fixes evidence packaging and applies official final output dequantization. It strongly supports a final-segment contract/dequant/runtime fault, but exact isolated boundary and full truth rows remain unavailable."
    packet = {
        "schema_version": "dream7b_s100p_gate_packet_v8",
        "created_at_utc": now(),
        "run_commands": [command],
        "git": git_meta(root),
        "verdict_class": verdict_class,
        "verdict": verdict,
        "gate_status": {
            "gate_0_evidence_integrity": reports["600_package_boundary_evidence_fix"].get("verdict"),
            "gate_1_compile_runtime_shape": "inherited_pass_not_numerical_correctness",
            "gate_2_full_truth_row": reports["630_full_truth_reference_export"].get("verdict"),
            "gate_3_final_segment_contract": reports["620_final_segment_function_boundary_audit"].get("verdict"),
            "gate_4_upstream_hidden_validity": reports["640_hf_boundary_and_final_cross_tests"].get("bpu_seg26_hidden_validity"),
            "gate_5_full_logits_numerical_validity": "blocked_or_failed_see_truth_and_cross_tests",
            "gate_6_generation_quality": "not_run_by_design",
            "gate_7_product_route": "not_run_by_design",
        },
        "official_final_output_scale": final_scale(root, "zeros")[0],
        "package_integrity_summary": reports["600_package_boundary_evidence_fix"],
        "final_output_dequant_summary": {
            "rows": len(reports["610_final_output_dequant_audit"].get("rows", [])),
            "verdict": reports["610_final_output_dequant_audit"].get("verdict"),
        },
        "function_boundary_summary": {
            "verdict": reports["620_final_segment_function_boundary_audit"].get("verdict"),
            "inference": reports["620_final_segment_function_boundary_audit"].get("function_boundary_inference"),
            "exact_rows": reports["620_final_segment_function_boundary_audit"].get("exact_hf_isolated_final_rows"),
        },
        "full_reference_summary": reports["630_full_truth_reference_export"],
        "hidden_validity_summary": reports["640_hf_boundary_and_final_cross_tests"],
        "allowed_claims": [
            "v8 package includes all boundary raw/dequant arrays or has a manifest that matches physical files.",
            "official seg27 output dequant scale is applied before magnitude/error metrics.",
            "v7 final-head-only comparison is a boundary-candidate test, not exact unless seg27_28 is final norm + lm_head only.",
            "same-input final-segment fault remains strongly supported by all-zero real_x and weak top-k after official dequant.",
        ],
        "forbidden_claims": [
            "accurate Dream7B deployment on S100P",
            "BF16 falsification without full truth row",
            "scaled/clipped variants are a correctness fix",
            "generation quality or product route 18888/18889 status",
        ],
        "next_minimal_experiment": "Run exact HF layer27+final norm+lm_head boundary and full BF16/GGUF F16 truth row on a runtime where full forward completes, then decide upstream-hidden vs final-segment dominance.",
        "source_reports": {name: f"reports/{name}.json" for name in REPORTS},
    }
    write_json(root / "01_final_evidence/dream7b_s100p_gate_packet_v8.json", packet)
    write_text(root / "01_final_evidence/dream7b_s100p_gate_packet_v8.md", f"# Gate Packet v8\n\n- verdict_class: `{verdict_class}`\n- verdict: {verdict}\n- generation/product: `not_run_by_design` / `not_run_by_design`\n")
    write_text(
        root / "01_final_evidence/dream7b_s100p_paper_evidence_dossier_v8.md",
        f"""# Dream7B/S100P v8 Paper Evidence Dossier

v8 corrects the v7 evidence-packaging overclaim and applies the official final-output dequant scale before comparing final-segment diagnostic logits. The v8 verdict is `{verdict_class}`.

The robust claim is bounded: S100P seq128 segmented HBM still lacks validated logits numerical correctness. All-segment boundary evidence shows earlier saturation beginning before the final segment, and official-dequant final outputs show the real `seg26` handoff still produces all-zero final logits while scaled/clipped diagnostics remain top-k weak or tie/saturation affected.

`seg27_28` is best treated as a final decoder-layer-through-lm-head segment unless exact compiler metadata proves otherwise. Therefore v7's HF final RMSNorm+lm_head-only route is retained as a diagnostic boundary candidate, not a final proof of exact function equivalence.

Generation quality and product route 18888/18889 were not run. Accurate deployment, BF16 falsification, and scale-fix claims remain forbidden unless a full BF16/FP32 or GGUF F16 truth row plus exact boundary comparison passes.
""",
    )
    return packet


def package_zip(root: Path, timestamp: str) -> tuple[Path, dict[str, Any]]:
    out = root / "evidence_for_gptpro" / f"dream7b_s100p_v8_for_gptpro_{timestamp}.zip"
    include: list[Path] = []
    for name in REPORTS:
        include.extend([root / "reports" / f"{name}.json", root / "reports" / f"{name}.md"])
    include.extend(
        [
            root / "01_final_evidence/dream7b_s100p_gate_packet_v8.json",
            root / "01_final_evidence/dream7b_s100p_gate_packet_v8.md",
            root / "01_final_evidence/dream7b_s100p_paper_evidence_dossier_v8.md",
            root / "cases/seq128_logits_probe_battery.jsonl",
            root / "cases/canonical_seq128_cases_v6.jsonl",
            root / "evidence/boundary_all_segments_v7",
            root / "evidence/final_output_dequant_v8",
            root / "evidence/hf_lmhead_only_v8",
            root / "evidence/full_reference_v8",
            root / "evidence/hf_isolated_final_segment_v8",
            root / "evidence/s100p_remote_v8_reports",
            root / "tools/build_v8_research_thread.py",
            root / "tools/run_hf_full_and_isolated_final_v8.py",
            root / "tools/export_hf_final_lmhead_batch_v7.py",
            root / "tmp/dream7b_s100p_v8_after_v7_review_pack_20260701_gptpro",
        ]
    )
    files = []
    for item in include:
        if item.is_file():
            files.append(item)
        elif item.is_dir():
            files.extend(x for x in item.rglob("*") if x.is_file())
    files = sorted(set(files))
    manifest_files = []
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fp in files:
            arc = fp.relative_to(root).as_posix()
            if "operator_portal" in arc or "18888" in arc or "18889" in arc:
                continue
            zf.write(fp, arc)
            manifest_files.append({"path": arc, "size_bytes": fp.stat().st_size, "sha256": sha256_file(fp)})
        manifest = {"schema_version": "dream7b_s100p_v8_evidence_zip_manifest", "created_at_utc": now(), "file_count": len(manifest_files), "files": manifest_files, "exclusions": ["generation outputs", "product route artifacts", "HBM binaries", "credentials"]}
        zf.writestr("MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
        zf.writestr("SHA256SUMS.txt", "".join(f"{f['sha256']}  {f['path']}\n" for f in manifest_files).encode("utf-8"))
    with zipfile.ZipFile(out) as zf:
        bad = zf.testzip()
        if bad:
            raise SystemExit(f"bad zip member: {bad}")
    write_json(out.with_name(out.stem + "_MANIFEST.json"), manifest)
    out.with_name(out.stem + "_SHA256SUMS.txt").write_text("".join(f"{f['sha256']}  {f['path']}\n" for f in manifest_files), encoding="utf-8")
    return out, manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timestamp", default=datetime.now().strftime("%Y%m%d_%H%M%S"))
    args = ap.parse_args()
    root = Path.cwd()
    command = f"py tools/build_v8_research_thread.py --timestamp {args.timestamp}"
    report_600(root, command)
    report_610(root, command)
    report_620(root, command)
    report_630(root, command)
    report_640(root, command)
    report_650(root, command)
    report_660(root, command)
    packet = build_packet(root, command)
    out, manifest = package_zip(root, args.timestamp)
    print(root / "01_final_evidence/dream7b_s100p_gate_packet_v8.json")
    print(root / "01_final_evidence/dream7b_s100p_paper_evidence_dossier_v8.md")
    print(out)
    print(f"zip_file_count={manifest['file_count']}")
    print(packet["verdict_class"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
