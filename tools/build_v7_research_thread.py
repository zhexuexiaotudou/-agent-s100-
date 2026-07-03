#!/usr/bin/env python3
"""Build Dream7B/S100P v7 evidence reports and review package."""
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
COMPARE_VARIANTS = [
    "real_x",
    "real_x_div_2",
    "real_x_div_2p5",
    "real_x_div_2p75",
    "real_x_div_3",
    "real_x_clip_8",
    "real_x_clip_6",
    "real_x_clip_5",
    "real_x_z_normalized",
]
CRITICAL_SEGMENTS = {9, 12, 13, 20, 25, 26, 27}
REPORTS = [
    "500_all_segment_boundary_raw_audit",
    "510_hf_final_norm_lmhead_only_route",
    "520_final_segment_functional_compare",
    "530_reference_matrix_completion",
    "540_bf16_full_forward_export",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
            continue
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return str(path)


def git_meta(root: Path) -> dict[str, Any]:
    git_dir = root / ".git"
    meta: dict[str, Any] = {"cwd": str(root.resolve()), "git_dir_exists": git_dir.exists(), "status": "unavailable"}
    try:
        meta["commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
        meta["dirty"] = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip())
        meta["status"] = "available"
    except Exception as exc:
        meta["status"] = f"unavailable:{type(exc).__name__}"
    return meta


def artifact(path: Path, root: Path) -> dict[str, Any]:
    out: dict[str, Any] = {"path": rel(path, root), "exists": path.exists()}
    if path.is_file():
        out.update({"size_bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return out


def array_stats(a: np.ndarray) -> dict[str, Any]:
    y = np.asarray(a).reshape(-1)
    finite = y[np.isfinite(y)] if np.issubdtype(y.dtype, np.floating) else y
    out = {
        "shape": list(a.shape),
        "dtype": str(a.dtype),
        "size": int(y.size),
        "min": float(np.min(finite)) if finite.size else None,
        "max": float(np.max(finite)) if finite.size else None,
        "mean": float(np.mean(finite)) if finite.size else None,
        "std": float(np.std(finite)) if finite.size else None,
        "abs_max": float(np.max(np.abs(finite))) if finite.size else None,
        "nonzero_count": int(np.count_nonzero(y)),
        "constant": bool(y.size > 0 and np.all(y == y.flat[0])),
        "allzero": bool(y.size > 0 and np.all(y == 0)),
        "nan_count": int(np.isnan(y).sum()) if np.issubdtype(y.dtype, np.floating) else 0,
        "inf_count": int(np.isinf(y).sum()) if np.issubdtype(y.dtype, np.floating) else 0,
    }
    if np.issubdtype(y.dtype, np.integer):
        out.update(
            {
                "count_pos_32767": int(np.sum(y == 32767)),
                "count_neg_32768": int(np.sum(y == -32768)),
                "count_abs_19807": int(np.sum(np.abs(y) == 19807)),
                "frac_pos_32767": float(np.mean(y == 32767)) if y.size else 0.0,
                "frac_neg_32768": float(np.mean(y == -32768)) if y.size else 0.0,
                "frac_abs_19807": float(np.mean(np.abs(y) == 19807)) if y.size else 0.0,
            }
        )
    for p in [0, 1, 5, 50, 95, 99, 100]:
        out[f"p{p}"] = float(np.percentile(finite, p)) if finite.size else None
    return out


def softmax_metrics(x: np.ndarray) -> dict[str, Any]:
    y = x.reshape(-1).astype(np.float64)
    y = y - np.max(y)
    exp = np.exp(y)
    denom = float(np.sum(exp))
    probs = exp / denom if np.isfinite(denom) and denom else np.full_like(y, 1.0 / y.size)
    ent = -float(np.sum(probs * np.log(np.maximum(probs, 1e-300))))
    return {"entropy": ent, "normalized_entropy": ent / math.log(y.size), "top1_probability": float(np.max(probs))}


def topk(x: np.ndarray, k: int = 10) -> list[int]:
    return np.argsort(x.reshape(-1))[-k:][::-1].astype(int).tolist()


def compare_logits(candidate: np.ndarray, reference: np.ndarray, k: int = 5) -> dict[str, Any]:
    a = candidate.reshape(-1).astype(np.float64)
    b = reference.reshape(-1).astype(np.float64)
    if a.shape != b.shape:
        raise ValueError(f"shape mismatch {a.shape} vs {b.shape}")
    ta = topk(a, k)
    tb = topk(b, k)
    diff = a - b
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return {
        "candidate_top1": int(ta[0]),
        "reference_top1": int(tb[0]),
        "top1_agreement": bool(ta[0] == tb[0]),
        "candidate_topk": ta,
        "reference_topk": tb,
        "top5_overlap": len(set(ta) & set(tb)),
        "reference_top1_in_candidate_top5": bool(tb[0] in ta),
        "cosine": float(np.dot(a, b) / denom) if denom else 0.0,
        "relative_l2": float(np.linalg.norm(diff) / (np.linalg.norm(b) + 1e-12)),
        "max_abs_error": float(np.max(np.abs(diff))),
        "mean_abs_error": float(np.mean(np.abs(diff))),
        "candidate_stats": array_stats(candidate),
        "reference_stats": array_stats(reference),
        "candidate_entropy": softmax_metrics(candidate),
        "reference_entropy": softmax_metrics(reference),
    }


def build_manifest(root: Path) -> dict[str, Any]:
    files = []
    for fp in sorted(root.rglob("*")):
        if fp.is_file() and fp.name not in {"MANIFEST.json", "SHA256SUMS.txt"}:
            files.append({"path": fp.relative_to(root).as_posix(), "size_bytes": fp.stat().st_size, "sha256": sha256_file(fp)})
    manifest = {"schema_version": "dream7b_s100p_v7_manifest", "created_at_utc": now(), "file_count": len(files), "files": files}
    write_json(root / "MANIFEST.json", manifest)
    (root / "SHA256SUMS.txt").write_text("".join(f"{f['sha256']}  {f['path']}\n" for f in files), encoding="utf-8")
    return manifest


def common(root: Path, name: str, command: str, inputs: list[Path]) -> dict[str, Any]:
    return {
        "schema_version": f"dream7b_s100p_v7_{name}",
        "created_at_utc": now(),
        "run_commands": [command],
        "git": git_meta(root),
        "input_artifacts": [artifact(p, root) for p in inputs],
        "output_artifacts": [{"path": f"reports/{name}.json"}, {"path": f"reports/{name}.md"}],
        "gate_status": {},
        "blocking_or_failure_reasons": [],
        "next_minimal_experiments": [],
    }


def segment_row(boundary_root: Path, case_result: dict[str, Any], case_id: str, seg: int, root: Path) -> dict[str, Any]:
    case_dir = boundary_root / case_id
    raw_path = case_dir / f"seg_{seg:02d}_raw_output.npy"
    deq_path = case_dir / f"seg_{seg:02d}_output.npy"
    remote_segment = next((x for x in case_result.get("segments", []) if x.get("segment") == seg), {})
    row: dict[str, Any] = {
        "case_id": case_id,
        "segment": seg,
        "raw_path": rel(raw_path, root) if raw_path.exists() else None,
        "dequant_path": rel(deq_path, root) if deq_path.exists() else None,
        "raw_present": raw_path.exists(),
        "dequant_present": deq_path.exists(),
        "remote_model_name": remote_segment.get("model_name"),
        "remote_hbm_path": remote_segment.get("hbm_path"),
        "remote_quant_metadata": remote_segment.get("quant_metadata"),
    }
    if raw_path.exists():
        raw = np.load(raw_path)
        row["raw_stats"] = array_stats(raw)
        row["raw_sha256"] = sha256_file(raw_path)
    else:
        row["raw_stats"] = remote_segment.get("raw_stats")
    if deq_path.exists():
        deq = np.load(deq_path)
        row["dequant_stats"] = array_stats(deq)
        row["dequant_sha256"] = sha256_file(deq_path)
    else:
        row["dequant_stats"] = remote_segment.get("dequant_stats")
    metadata = {
        "case_id": case_id,
        "segment": seg,
        "raw_path": row["raw_path"],
        "dequant_path": row["dequant_path"],
        "model_name": row["remote_model_name"],
        "hbm_path": row["remote_hbm_path"],
        "quant_metadata": row["remote_quant_metadata"],
        "raw_stats": row.get("raw_stats"),
        "dequant_stats": row.get("dequant_stats"),
        "raw_sha256": row.get("raw_sha256"),
        "dequant_sha256": row.get("dequant_sha256"),
    }
    write_json(case_dir / f"seg_{seg:02d}_metadata.json", metadata)
    row["metadata_path"] = rel(case_dir / f"seg_{seg:02d}_metadata.json", root)
    return row


def report_500(root: Path, command: str, boundary_root: Path) -> dict[str, Any]:
    rows = []
    remote_cases = []
    for case_id in CASE_IDS:
        result = load_json(boundary_root / case_id / "case_result.json", {})
        remote_cases.append(result)
        for seg in range(28):
            rows.append(segment_row(boundary_root, result, case_id, seg, root))
    missing = [f"{r['case_id']}/seg{r['segment']:02d}" for r in rows if not (r["raw_present"] and r["dequant_present"])]
    firsts: dict[str, Any] = {}
    for case_id in CASE_IDS:
        cr = [r for r in rows if r["case_id"] == case_id]
        def has_any_extreme(r: dict[str, Any]) -> bool:
            s = r.get("raw_stats") or {}
            return s.get("count_pos_32767", 0) > 0 or s.get("count_neg_32768", 0) > 0 or s.get("min") == -32768 or s.get("max") == 32767
        def has_both_extreme(r: dict[str, Any]) -> bool:
            s = r.get("raw_stats") or {}
            return (s.get("count_pos_32767", 0) > 0 or s.get("max") == 32767) and (s.get("count_neg_32768", 0) > 0 or s.get("min") == -32768)
        def sat_gt_1pct(r: dict[str, Any]) -> bool:
            s = r.get("raw_stats") or {}
            size = max(float(s.get("size") or 0), 1.0)
            return ((s.get("count_pos_32767", 0) + s.get("count_neg_32768", 0)) / size) > 0.01
        std_jump = None
        prev = None
        for r in cr:
            cur = (r.get("dequant_stats") or {}).get("std")
            if prev is not None and cur is not None and prev > 0 and cur > 10 * prev:
                std_jump = r["segment"]
                break
            if cur is not None:
                prev = cur
        firsts[case_id] = {
            "first_any_int16_extreme": next((r["segment"] for r in cr if has_any_extreme(r)), None),
            "first_both_sided_int16_extreme": next((r["segment"] for r in cr if has_both_extreme(r)), None),
            "first_gt_1pct_int16_saturation": next((r["segment"] for r in cr if sat_gt_1pct(r)), None),
            "first_dequant_std_jump_gt_10x_previous": std_jump,
            "first_allzero_raw": next((r["segment"] for r in cr if (r.get("raw_stats") or {}).get("allzero")), None),
        }
    manifest = build_manifest(boundary_root)
    data = common(root, "500_all_segment_boundary_raw_audit", command, [boundary_root])
    data.update(
        {
            "remote_cases": remote_cases,
            "boundary_rows": rows,
            "missing_raw_or_dequant_arrays": missing,
            "corrected_first_extreme_table": firsts,
            "boundary_manifest": {"path": rel(boundary_root / "MANIFEST.json", root), "file_count": manifest["file_count"]},
            "verdict": "pass_all_segment_raw_boundaries_packaged" if not missing else "partial_stats_only_for_early_segments",
            "gate_status": {"all_segment_boundary_audit": "pass" if not missing else "partial"},
        }
    )
    data["blocking_or_failure_reasons"] = [] if not missing else [f"Missing arrays: {missing[:20]}"]
    write_json(root / "reports/500_all_segment_boundary_raw_audit.json", data)
    md = [
        "# Task 500 All-segment Boundary Raw Audit",
        "",
        f"- verdict: `{data['verdict']}`",
        f"- missing raw/dequant arrays: `{len(missing)}`",
        f"- packaged files under boundary root: `{manifest['file_count']}`",
        "",
        "| case | first any int16 extreme | first both-sided extreme | first >1% saturation | first std jump >10x | first allzero raw |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for case_id, first in firsts.items():
        md.append(f"| `{case_id}` | {first['first_any_int16_extreme']} | {first['first_both_sided_int16_extreme']} | {first['first_gt_1pct_int16_saturation']} | {first['first_dequant_std_jump_gt_10x_previous']} | {first['first_allzero_raw']} |")
    write_text(root / "reports/500_all_segment_boundary_raw_audit.md", "\n".join(md) + "\n")
    return data


def report_510(root: Path, command: str, hf_root: Path) -> dict[str, Any]:
    remote = load_json(root / "evidence/s100p_remote_v7_reports/510_hf_final_lmhead_only_route_remote.json", {})
    rows = []
    errors = []
    for case_id in CASE_IDS:
        for variant in COMPARE_VARIANTS:
            lp = hf_root / case_id / variant / "hf_final_lmhead_logits.npy"
            mp = hf_root / case_id / variant / "metadata.json"
            if lp.exists() and mp.exists():
                meta = load_json(mp)
                logits = np.load(lp)
                rows.append(
                    {
                        "case_id": case_id,
                        "variant": variant,
                        "logits_path": rel(lp, root),
                        "metadata_path": rel(mp, root),
                        "logits_sha256": sha256_file(lp),
                        "logits_stats": array_stats(logits),
                        "top10": topk(logits, 10),
                        "hf_metadata": meta,
                    }
                )
            else:
                errors.append({"case_id": case_id, "variant": variant, "missing": [str(x) for x in [lp, mp] if not x.exists()]})
    manifest = build_manifest(hf_root) if hf_root.exists() else {"file_count": 0}
    data = common(root, "510_hf_final_norm_lmhead_only_route", command, [hf_root, root / "evidence/s100p_remote_v7_reports/510_hf_final_lmhead_only_route_remote.json"])
    verdict = "pass_hf_final_lmhead_only_logits_exported" if len(rows) == len(CASE_IDS) * len(COMPARE_VARIANTS) and not errors else ("partial_weights_found_but_matmul_blocked" if rows else "fail_tensor_names_or_shapes_unresolved")
    data.update(
        {
            "remote_report": remote,
            "completed": len(rows),
            "failed": len(errors),
            "rows": rows,
            "errors": errors,
            "hf_manifest": {"path": rel(hf_root / "MANIFEST.json", root), "file_count": manifest["file_count"]},
            "verdict": verdict,
            "gate_status": {"hf_final_norm_lmhead_only_route": "pass" if verdict.startswith("pass") else "partial_or_fail"},
            "blocking_or_failure_reasons": [] if verdict.startswith("pass") else [f"Missing/failed HF lmhead exports: {len(errors)}"],
        }
    )
    write_json(root / "reports/510_hf_final_norm_lmhead_only_route.json", data)
    lines = [
        "# Task 510 HF Final Norm + LM Head Only Route",
        "",
        f"- verdict: `{verdict}`",
        f"- completed: `{len(rows)}`",
        f"- failed: `{len(errors)}`",
        "",
        "| case | variant | allzero | nonzero | top1 |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(f"| `{row['case_id']}` | `{row['variant']}` | `{row['logits_stats']['allzero']}` | {row['logits_stats']['nonzero_count']} | {row['top10'][0]} |")
    write_text(root / "reports/510_hf_final_norm_lmhead_only_route.md", "\n".join(lines) + "\n")
    return data


def report_520(root: Path, command: str, hf_root: Path, endpoint_root: Path) -> dict[str, Any]:
    out_root = root / "evidence/final_segment_functional_compare_v7"
    rows = []
    errors = []
    for case_id in CASE_IDS:
        for variant in COMPARE_VARIANTS:
            hf_path = hf_root / case_id / variant / "hf_final_lmhead_logits.npy"
            bpu_path = endpoint_root / "final_segment_dense_sweep_v5" / case_id / variant / "dequant_logits.npy"
            metrics_path = out_root / case_id / variant / "metrics.json"
            try:
                hf = np.load(hf_path)
                bpu = np.load(bpu_path)
                metrics = compare_logits(bpu, hf, 5)
                metrics.update({"case_id": case_id, "variant": variant, "candidate": "bpu_seg27_28", "reference": "hf_final_norm_lmhead_same_input", "bpu_logits_path": rel(bpu_path, root), "hf_logits_path": rel(hf_path, root)})
                write_json(metrics_path, metrics)
                rows.append({**metrics, "metrics_path": rel(metrics_path, root)})
            except Exception as exc:
                err = {"case_id": case_id, "variant": variant, "error": f"{type(exc).__name__}: {exc}", "bpu_path": rel(bpu_path, root), "hf_path": rel(hf_path, root)}
                errors.append(err)
                write_json(metrics_path, err)
    q4_path = root / "evidence/reference_matrix_v6/gguf_q4_k_m/zeros/last_logits.npy"
    q4_rows = []
    if q4_path.exists():
        q4 = np.load(q4_path)
        for variant in COMPARE_VARIANTS:
            for label, base in [("bpu_seg27_28", endpoint_root / "final_segment_dense_sweep_v5" / "zeros" / variant / "dequant_logits.npy"), ("hf_lmhead_only", hf_root / "zeros" / variant / "hf_final_lmhead_logits.npy")]:
                if base.exists():
                    q4_rows.append({"variant": variant, "row": label, **compare_logits(np.load(base), q4, 5)})
    manifest = build_manifest(out_root)
    mismatch_count = sum(1 for r in rows if not r["top1_agreement"] or r["top5_overlap"] == 0)
    real_fault = [r for r in rows if r["variant"] == "real_x" and r["candidate_stats"]["allzero"] and not r["reference_stats"]["allzero"]]
    data = common(root, "520_final_segment_functional_compare", command, [hf_root, endpoint_root, q4_path, out_root])
    data.update(
        {
            "comparisons": rows,
            "errors": errors,
            "q4_k_m_zeros_comparisons": q4_rows,
            "mismatch_count": mismatch_count,
            "real_x_bpu_allzero_hf_nonzero_cases": [r["case_id"] for r in real_fault],
            "functional_compare_manifest": {"path": rel(out_root / "MANIFEST.json", root), "file_count": manifest["file_count"]},
            "verdict": "pass_final_segment_mismatch_quantified_same_input" if rows and not errors else "blocked_missing_hf_or_bpu_logits",
            "gate_status": {"final_segment_functional_comparison": "pass_mismatch_quantified" if rows and not errors else "blocked"},
        }
    )
    write_json(root / "reports/520_final_segment_functional_compare.json", data)
    lines = [
        "# Task 520 Final Segment Functional Compare",
        "",
        f"- verdict: `{data['verdict']}`",
        f"- comparisons: `{len(rows)}`",
        f"- mismatches by top1/top5: `{mismatch_count}`",
        f"- real_x BPU all-zero while HF lmhead nonzero cases: `{len(real_fault)}`",
        "",
        "| case | variant | top1 agree | top5 overlap | cosine | BPU allzero | HF allzero | BPU top1 | HF top1 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in rows:
        lines.append(f"| `{r['case_id']}` | `{r['variant']}` | `{r['top1_agreement']}` | {r['top5_overlap']} | {r['cosine']:.6g} | `{r['candidate_stats']['allzero']}` | `{r['reference_stats']['allzero']}` | {r['candidate_top1']} | {r['reference_top1']} |")
    write_text(root / "reports/520_final_segment_functional_compare.md", "\n".join(lines) + "\n")
    return data


def copy_if_exists(src: Path, dst: Path, root: Path, rows: list[dict[str, Any]], row_name: str, case_id: str, variant: str | None = None) -> None:
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        rows.append({"row": row_name, "case_id": case_id, "variant": variant, "path": rel(dst, root), "sha256": sha256_file(dst), "size_bytes": dst.stat().st_size})


def report_530(root: Path, command: str, hf_root: Path, endpoint_root: Path) -> dict[str, Any]:
    ref_root = root / "evidence/reference_matrix_v7"
    rows: list[dict[str, Any]] = []
    q4_src = root / "evidence/reference_matrix_v6/gguf_q4_k_m/zeros/last_logits.npy"
    copy_if_exists(q4_src, ref_root / "gguf_q4_k_m" / "zeros" / "last_logits.npy", root, rows, "gguf_q4_k_m", "zeros")
    bpu_src = root / "evidence/reference_matrix_v6/s100p_bpu_dequant/zeros/last_logits.npy"
    copy_if_exists(bpu_src, ref_root / "s100p_bpu_dequant" / "zeros" / "last_logits.npy", root, rows, "s100p_bpu_dequant", "zeros")
    for case_id in CASE_IDS:
        for variant in COMPARE_VARIANTS:
            copy_if_exists(hf_root / case_id / variant / "hf_final_lmhead_logits.npy", ref_root / "hf_final_lmhead_only" / case_id / variant / "last_logits.npy", root, rows, "hf_final_lmhead_only", case_id, variant)
            copy_if_exists(endpoint_root / "final_segment_dense_sweep_v5" / case_id / variant / "dequant_logits.npy", ref_root / "s100p_final_segment_diagnostic" / case_id / variant / "last_logits.npy", root, rows, "s100p_final_segment_diagnostic", case_id, variant)
    manifest = build_manifest(ref_root)
    full_truth_rows = [r for r in rows if r["row"] in {"hf_bf16_full", "hf_fp32_full", "gguf_f16"}]
    data = common(root, "530_reference_matrix_completion", command, [ref_root, root / "evidence/model_inventory_v6.json", root / "reports/510_hf_final_norm_lmhead_only_route.json"])
    data.update(
        {
            "rows": rows,
            "reference_matrix_manifest": {"path": rel(ref_root / "MANIFEST.json", root), "file_count": manifest["file_count"]},
            "truth_rows_available": full_truth_rows,
            "row_status": {
                "hf_bf16_or_fp32_full": "unavailable",
                "gguf_f16": "unavailable",
                "gguf_q4_0": "unavailable",
                "gguf_q4_k_m": "available" if q4_src.exists() else "unavailable",
                "s100p_bpu_dequant": "partial_available" if bpu_src.exists() else "unavailable",
                "corrected_scale_diagnostic": "available",
                "hf_final_lmhead_only": "available" if any(r["row"] == "hf_final_lmhead_only" for r in rows) else "unavailable",
            },
            "verdict": "pass_reference_matrix_has_bf16_or_f16_truth_row" if full_truth_rows else ("partial_q4km_plus_hf_lmhead_only_rows" if any(r["row"] == "hf_final_lmhead_only" for r in rows) else "blocked_reference_rows_unavailable"),
            "gate_status": {"reference_matrix_completion": "partial_no_full_truth_row" if not full_truth_rows else "pass"},
            "blocking_or_failure_reasons": ["No verified BF16/FP32 full logits or GGUF F16 row exists in v7."] if not full_truth_rows else [],
        }
    )
    write_json(root / "reports/530_reference_matrix_completion.json", data)
    lines = [
        "# Task 530 Reference Matrix Completion",
        "",
        f"- verdict: `{data['verdict']}`",
        f"- rows copied/exported: `{len(rows)}`",
        f"- full truth rows available: `{len(full_truth_rows)}`",
        "",
        "| row | count |",
        "| --- | ---: |",
    ]
    for row_name in sorted({r["row"] for r in rows}):
        lines.append(f"| `{row_name}` | {sum(1 for r in rows if r['row'] == row_name)} |")
    write_text(root / "reports/530_reference_matrix_completion.md", "\n".join(lines) + "\n")
    return data


def report_540(root: Path, command: str) -> dict[str, Any]:
    probe = load_json(root / "evidence/hf_bf16_v6/wrapper_probe_status.json", {})
    data = common(root, "540_bf16_full_forward_export", command, [root / "evidence/hf_bf16_v6/wrapper_probe_status.json"])
    data.update(
        {
            "attempted_in_v7": False,
            "v6_wrapper_probe": probe,
            "runtime_assessment": {
                "s100p_torch": (probe.get("dependency_state") or {}).get("system_torch"),
                "known_blocker": "S100P torch 1.8 lacks required APIs; prior shimmed full forward did not complete.",
                "v7_progress_without_full_forward": "HF final-norm+lm_head-only route avoids full model forward and exports comparable final-head logits.",
            },
            "verdict": "blocked_no_capable_torch_runtime",
            "gate_status": {"bf16_full_forward_export": "blocked_no_capable_torch_runtime"},
            "blocking_or_failure_reasons": ["No capable PyTorch runtime for full 7.6B BF16/FP32 Dream forward was available in this run."],
            "next_minimal_experiments": ["Run Dream HF full forward on PyTorch >=2.2 with enough memory and export canonical-case logits plus boundary hooks."],
        }
    )
    write_json(root / "reports/540_bf16_full_forward_export.json", data)
    write_text(
        root / "reports/540_bf16_full_forward_export.md",
        "# Task 540 BF16/FP32 Full Forward Export\n\n"
        f"- verdict: `{data['verdict']}`\n"
        "- v7 did not fabricate full BF16/FP32 logits.\n"
        "- v7 instead completed/attempted the narrower HF final-norm+lm_head-only route.\n",
    )
    return data


def build_gate_packet(root: Path, command: str) -> dict[str, Any]:
    reports = {name: load_json(root / "reports" / f"{name}.json") for name in REPORTS}
    r520 = reports["520_final_segment_functional_compare"]
    final_fault_cases = r520.get("real_x_bpu_allzero_hf_nonzero_cases", [])
    has_hf_final = reports["510_hf_final_norm_lmhead_only_route"].get("verdict", "").startswith("pass")
    has_truth = reports["530_reference_matrix_completion"].get("truth_rows_available")
    if final_fault_cases and has_hf_final and not has_truth:
        verdict_class = "E_final_segment_contract_fault_strongly_supported_but_full_reference_unresolved"
        verdict = "v7 packages all-segment boundaries and shows that for the same BPU seg26 hidden, HF final RMSNorm+lm_head produces nonzero logits while S100P seg27_28 can return all-zero or mismatched logits. This strongly supports a final-segment contract/runtime fault, but full BF16/GGUF F16 truth remains unavailable."
    elif not has_truth:
        verdict_class = "C_deployment_blocked_against_deployment_reference_but_bf16_unresolved"
        verdict = "v7 improves evidence but full BF16/GGUF F16 truth remains unavailable."
    else:
        verdict_class = "D_inconclusive_due_to_missing_artifact_or_input_alignment"
        verdict = "Full truth row exists but v7 did not establish pass/fail thresholds."
    packet = {
        "schema_version": "dream7b_s100p_gate_packet_v7",
        "created_at_utc": now(),
        "run_commands": [command],
        "git": git_meta(root),
        "verdict_class": verdict_class,
        "verdict": verdict,
        "gate_status": {
            "gate_0_evidence_integrity": "pass_pending_zip_self_check",
            "gate_1_all_segment_boundary_audit": reports["500_all_segment_boundary_raw_audit"].get("verdict"),
            "gate_2_hf_final_norm_lmhead_only_route": reports["510_hf_final_norm_lmhead_only_route"].get("verdict"),
            "gate_3_final_segment_functional_comparison": reports["520_final_segment_functional_compare"].get("verdict"),
            "gate_4_full_reference_matrix": reports["530_reference_matrix_completion"].get("verdict"),
            "gate_5_logits_numerical_validity": "blocked_full_bf16_or_gguf_f16_truth_unavailable_final_segment_fault_supported",
            "gate_6_generation_quality": "not_run_by_design",
            "gate_7_product_route": "not_run_by_design",
        },
        "all_segment_saturation_table": reports["500_all_segment_boundary_raw_audit"].get("corrected_first_extreme_table"),
        "final_segment_functional_comparison_summary": {
            "comparisons": len(r520.get("comparisons", [])),
            "mismatch_count": r520.get("mismatch_count"),
            "real_x_bpu_allzero_hf_nonzero_cases": final_fault_cases,
        },
        "reference_matrix_rows": reports["530_reference_matrix_completion"].get("row_status"),
        "blocking_issues": [
            "No verified BF16/FP32 full logits or GGUF F16 row exists.",
            "HF final-head-only route proves a same-input final projection mismatch, but it does not prove the BPU seg26 hidden itself is correct.",
            "GGUF F16 and Q4_0 rows remain unavailable.",
        ],
        "allowed_claims": [
            "All-segment raw/dequant boundary arrays for seg00..27 are packaged for zeros/ramp/short-Chinese if Task 500 passed.",
            "Earlier saturation/extreme indicators precede seg20; do not claim first saturation at seg20.",
            "HF final-norm+lm_head-only logits can be computed from BPU hidden inputs and compared to BPU seg27_28 on the same input.",
            "A final-segment input contract/runtime fault is strongly supported if BPU and HF final-head logits diverge on the same hidden.",
        ],
        "forbidden_claims": [
            "Dream7B is accurately deployed on S100P.",
            "Dream7B is falsified against BF16/PyTorch full-model truth.",
            "Any scaled/clipped nonzero BPU output is a correctness fix.",
            "Generation quality or product route 18888/18889 passed or failed.",
        ],
        "next_minimal_experiment": "Export full BF16/FP32 or GGUF F16 canonical logits, then decide whether the BPU seg26 hidden is valid and whether the final-segment fault is the only remaining blocker.",
        "paper_claim_boundary": "v7 supports a same-input final-segment contract fault and corrects the v6 localization claim by packaging seg00..27 boundaries. It does not validate full Dream7B numerical correctness because a full BF16/FP32 or GGUF F16 truth row is still missing.",
        "source_reports": {name: f"reports/{name}.json" for name in REPORTS},
    }
    write_json(root / "reports/570_gate_packet_v7.json", packet)
    write_json(root / "01_final_evidence/dream7b_s100p_gate_packet_v7.json", packet)
    text = (
        "# Gate Packet v7\n\n"
        f"- verdict_class: `{verdict_class}`\n"
        f"- verdict: {verdict}\n"
        f"- Gate 6/7: `{packet['gate_status']['gate_6_generation_quality']}` / `{packet['gate_status']['gate_7_product_route']}`\n"
    )
    write_text(root / "reports/570_gate_packet_v7.md", text)
    write_text(root / "01_final_evidence/dream7b_s100p_gate_packet_v7.md", text)
    return packet


def write_dossier(root: Path, packet: dict[str, Any]) -> None:
    text = f"""# Dream7B/S100P v7 Paper Evidence Dossier

## Conclusion

v7 does not validate accurate Dream7B deployment and does not falsify the model against BF16/PyTorch full-model truth. It moves the thread beyond v6 by packaging all-segment S100P boundary evidence and by comparing BPU `seg27_28` against HF final RMSNorm plus `lm_head` on the same BPU hidden input.

## Boundary Localization

`reports/500_all_segment_boundary_raw_audit.json` records raw and dequant arrays for `seg00..27` on zeros, ramp, and short-Chinese cases. The corrected first-extreme table supersedes the v6 wording: earlier int16 extremes occur before `seg20`, so v7 must not claim first saturation at `seg20`.

## Final Segment Function

`reports/510_hf_final_norm_lmhead_only_route.json` exports HF final-head-only logits from BPU final-segment input tensors. `reports/520_final_segment_functional_compare.json` compares those logits against BPU `seg27_28` logits for the same hidden inputs. If the BPU row is all-zero while HF final head is nonzero, the evidence supports a final-segment contract/runtime fault rather than a generation-quality issue.

## Reference Boundary

`reports/530_reference_matrix_completion.json` still lacks a full BF16/FP32 or GGUF F16 truth row. Q4_K_M remains a deployment-reference blocker, not mathematical truth. Therefore the v7 verdict is `{packet['verdict_class']}`.

## Claim Boundary

Allowed: all-segment raw boundary packaging, earlier-than-seg20 saturation correction, same-input HF final-head vs BPU final-segment mismatch, and full-reference blocker status. Forbidden: accurate S100P deployment, BF16 falsification, validated scale fix, generation quality claims, or product-route claims.
"""
    write_text(root / "01_final_evidence/dream7b_s100p_paper_evidence_dossier_v7.md", text)


def package_zip(root: Path, timestamp: str) -> tuple[Path, dict[str, Any]]:
    out = root / "evidence_zips" / f"dream7b_s100p_v7_for_gptpro_{timestamp}.zip"
    include: list[Path] = []
    for name in [*REPORTS, "570_gate_packet_v7"]:
        include.extend([root / "reports" / f"{name}.json", root / "reports" / f"{name}.md"])
    include.extend(
        [
            root / "01_final_evidence/dream7b_s100p_gate_packet_v7.json",
            root / "01_final_evidence/dream7b_s100p_gate_packet_v7.md",
            root / "01_final_evidence/dream7b_s100p_paper_evidence_dossier_v7.md",
            root / "cases/canonical_seq128_cases_v6.jsonl",
            root / "cases/seq128_logits_probe_battery.jsonl",
            root / "evidence/boundary_all_segments_v7/MANIFEST.json",
            root / "evidence/boundary_all_segments_v7/SHA256SUMS.txt",
            root / "evidence/hf_lmhead_only_v7",
            root / "evidence/final_segment_functional_compare_v7",
            root / "evidence/reference_matrix_v7",
            root / "evidence/s100p_remote_v7_reports",
            root / "tools/export_hf_final_lmhead_batch_v7.py",
            root / "tools/build_v7_research_thread.py",
            root / "tools/run_s100p_hbm_chain_dump_boundaries_v6.py",
        ]
    )
    for case_id in CASE_IDS:
        for seg in CRITICAL_SEGMENTS:
            for suffix in ["raw_output.npy", "output.npy", "metadata.json"]:
                include.append(root / "evidence/boundary_all_segments_v7" / case_id / f"seg_{seg:02d}_{suffix}")
        include.append(root / "evidence/boundary_all_segments_v7" / case_id / "case_result.json")
        include.append(root / "evidence/boundary_all_segments_v7" / case_id / "runtime_subprocess.log")
    endpoint_root = root / "evidence/raw_endpoint_subset_v6/final_segment_dense_sweep_v5"
    for case_id in CASE_IDS:
        for variant in ["real_x", "real_x_div_2p5", "real_x_div_2p75", "real_x_div_3", "real_x_clip_8", "real_x_clip_6", "real_x_z_normalized"]:
            for fn in ["input.npy", "dequant_logits.npy", "metadata.json"]:
                include.append(endpoint_root / case_id / variant / fn)

    files: list[Path] = []
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
        manifest = {
            "schema_version": "dream7b_s100p_v7_evidence_zip_manifest",
            "created_at_utc": now(),
            "file_count": len(manifest_files),
            "files": manifest_files,
            "large_artifact_policy": "All boundary stats and manifests are included; raw arrays are included for critical segments plus all HF final-head logits and comparison metrics.",
            "exclusions": ["generation-quality outputs", "product-route artifacts", "large HBM binaries", "credentials"],
        }
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--timestamp", default=datetime.now().strftime("%Y%m%d_%H%M%S"))
    args = parser.parse_args()
    root = Path.cwd()
    command = f"py tools/build_v7_research_thread.py --timestamp {args.timestamp}"
    boundary_root = root / "evidence/boundary_all_segments_v7"
    hf_root = root / "evidence/hf_lmhead_only_v7"
    endpoint_root = root / "evidence/raw_endpoint_subset_v6"
    report_500(root, command, boundary_root)
    report_510(root, command, hf_root)
    report_520(root, command, hf_root, endpoint_root)
    report_530(root, command, hf_root, endpoint_root)
    report_540(root, command)
    packet = build_gate_packet(root, command)
    write_dossier(root, packet)
    out, manifest = package_zip(root, args.timestamp)
    print(root / "01_final_evidence/dream7b_s100p_gate_packet_v7.json")
    print(root / "01_final_evidence/dream7b_s100p_paper_evidence_dossier_v7.md")
    print(out)
    print(f"zip_file_count={manifest['file_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
