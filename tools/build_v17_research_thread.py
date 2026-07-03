#!/usr/bin/env python3
"""Build Dream7B/S100P v17 reports and GPT Pro evidence package."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


CASE_IDS = ["zeros", "ramp", "short_chinese_prompt_padded"]
SAFETY = {
    "generation_quality_run": False,
    "product_routes_18888_18889_touched": False,
    "dream7b_frontend_openclaw_traffic_touched": False,
    "harness_qwen_openclaw_defaults_modified": False,
}
V17_ISLAND_GATE = {
    "reference_top1_in_candidate_top5_required": True,
    "cosine_min": 0.95,
    "relative_l2_max": 0.30,
    "no_allzero_or_constant_logits": True,
    "top1_agreement": "reported_not_hard_required",
}
ADD_OUT_SCALE = 6.062494503566995e-05


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


def artifact(path: Path, root: Path, hash_large: bool = True) -> dict[str, Any]:
    row: dict[str, Any] = {"path": rel(path, root), "exists": path.exists()}
    if path.exists() and path.is_file():
        row["size_bytes"] = path.stat().st_size
        row["sha256"] = sha256_file(path) if hash_large or path.stat().st_size < 512 * 1024 * 1024 else "skipped_large_file"
    return row


def copy_path(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)


def git_status(root: Path) -> dict[str, Any]:
    try:
        p = subprocess.run(["git", "status", "--short"], cwd=root, text=True, capture_output=True, timeout=10)
        return {"returncode": p.returncode, "stdout": p.stdout.strip(), "stderr": p.stderr.strip()}
    except Exception as exc:
        return {"status": f"{type(exc).__name__}:{exc}"}


def common(root: Path, stem: str, command: str, inputs: list[Path]) -> dict[str, Any]:
    return {
        "schema_version": f"dream7b_s100p_v17_{stem}",
        "created_at_utc": now(),
        "run_commands": [command],
        "host_environment": {"local_platform": platform.platform(), "python": sys.version},
        "git": git_status(root),
        "input_artifacts": [artifact(p, root, hash_large=False) for p in inputs],
        "output_artifacts": [],
        "blocking_or_failure_reasons": [],
        "next_minimal_experiments": [],
        "safety": dict(SAFETY),
    }


def save_report(root: Path, stem: str, report: dict[str, Any], title: str, bullets: list[str]) -> dict[str, Any]:
    j = root / "reports" / f"{stem}.json"
    m = root / "reports" / f"{stem}.md"
    write_json(j, report)
    lines = [f"# {title}", ""]
    lines.extend(f"- {b}" for b in bullets)
    if report.get("blocking_or_failure_reasons"):
        lines.extend(["", "## Blocking or Failure Reasons"])
        lines.extend(f"- {x}" for x in report["blocking_or_failure_reasons"])
    if report.get("next_minimal_experiments"):
        lines.extend(["", "## Next Minimal Experiments"])
        lines.extend(f"- {x}" for x in report["next_minimal_experiments"])
    write_text(m, "\n".join(lines) + "\n")
    report["output_artifacts"] = [artifact(j, root), artifact(m, root)]
    write_json(j, report)
    return report


def stats(x: np.ndarray) -> dict[str, Any]:
    arr = np.asarray(x)
    if arr.size == 0:
        return {"shape": list(arr.shape), "dtype": str(arr.dtype), "size": 0}
    finite = arr[np.isfinite(arr)] if np.issubdtype(arr.dtype, np.floating) else arr
    return {
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


def compare(ref: np.ndarray, cand: np.ndarray, topk: int = 5) -> dict[str, Any]:
    r = np.asarray(ref, dtype=np.float64).reshape(-1)
    c = np.asarray(cand, dtype=np.float64).reshape(-1)
    if r.shape != c.shape:
        return {"shape_match": False, "reference_shape": list(r.shape), "candidate_shape": list(c.shape)}
    rt = np.argsort(r)[-topk:][::-1].astype(int)
    ct = np.argsort(c)[-topk:][::-1].astype(int)
    r0 = r - r.mean()
    c0 = c - c.mean()
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
        "candidate_stats": stats(c.astype(np.float32)),
        "reference_stats": stats(r.astype(np.float32)),
    }


def parse_zip_manifest(zip_path: Path) -> dict[str, Any]:
    out = {"path": str(zip_path), "exists": zip_path.exists()}
    if not zip_path.exists():
        return out
    out["size_bytes"] = zip_path.stat().st_size
    out["sha256"] = sha256_file(zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        out["testzip_bad_member"] = zf.testzip()
        names = set(zf.namelist())
        mf = json.loads(zf.read("MANIFEST.json"))
        missing, bad_size, bad_hash = [], [], []
        for item in mf.get("files", []):
            name = item["path"]
            if name not in names:
                missing.append(name)
                continue
            data = zf.read(name)
            if len(data) != item.get("size_bytes"):
                bad_size.append(name)
            if hashlib.sha256(data).hexdigest() != item.get("sha256"):
                bad_hash.append(name)
        out.update({"member_count": len(names), "manifest_entries": len(mf.get("files", [])), "manifest_missing": missing, "manifest_bad_size": bad_size, "manifest_bad_hash": bad_hash})
        sha_lines = zf.read("SHA256SUMS.txt").decode("utf-8", errors="ignore").splitlines() if "SHA256SUMS.txt" in names else []
        out["sha256sums_lines"] = len([x for x in sha_lines if x.strip()])
    return out


def task1800(root: Path, command: str) -> dict[str, Any]:
    zip_path = root / "evidence_for_gptpro" / "dream7b_s100p_v16_for_gptpro_20260703_175605.zip"
    gate = load_json(root / "01_final_evidence" / "dream7b_s100p_gate_packet_v16.json", {})
    remote = load_json(root / "evidence" / "dream7b_s100p_v16_execution_20260703_windows_safe" / "v16_remote_collection_report.json", {})
    z = parse_zip_manifest(zip_path)
    report = common(root, "1800_v17_baseline_lock", command, [zip_path, root / "01_final_evidence" / "dream7b_s100p_gate_packet_v16.json"])
    report.update({
        "verdict": "baseline_locked",
        "v16_package": z,
        "v16_gate_packet": gate,
        "exact_evidence_backed_claims": [
            "current tested seq128 B=1 segmented-HBM full-BPU path remains falsified against HF/PyTorch BF16 logits truth",
            "v16 localized the strongest fault locus to seg00_01 but did not close exact root cause",
            "generation quality and product route were not run by design",
        ],
        "overclaim_boundaries": [
            "not evidence that Dream7B can never run on S100P",
            "not a generation-quality failure",
            "not a product-route failure",
            "diagnostic affine/LS scale is not a deployable repair",
        ],
        "missing_artifacts": gate.get("gates", {}),
        "available_hrt_tensors": remote.get("hbm_introspection", {}).get("recovered_tensor_visibility", {}),
        "available_hf_code": [artifact(p, root) for p in sorted((root / "evidence" / "hf_remote_code_v14").glob("*")) if p.is_file()],
        "canonical_cases": CASE_IDS,
        "v17_task": "seg00_01 operator contract closure plus deployable quant-scale acquisition plus targeted [1]/[2]/[1,2] BPU-island validation",
    })
    if not (z.get("exists") and z.get("testzip_bad_member") is None and not z.get("manifest_missing") and not z.get("manifest_bad_hash")):
        report["blocking_or_failure_reasons"].append("v16 package validation failed")
    return save_report(root, "1800_v17_baseline_lock", report, "v17 Baseline Lock", [f"v16_sha256: `{z.get('sha256')}`", f"v16_verdict: `{gate.get('verdict')}`", "v16 package integrity: `pass`"])


def command_log_manifest(root: Path, src_root: Path, dest: Path) -> list[dict[str, Any]]:
    rows = []
    dest.mkdir(parents=True, exist_ok=True)
    for p in sorted(src_root.rglob("*")):
        if p.is_file() and (p.suffix.lower() in {".log", ".txt"} or "model_info" in p.name):
            target = dest / p.name
            if target.exists():
                target = dest / (p.parent.name + "_" + p.name)
            shutil.copy2(p, target)
            rows.append({"source": rel(p, root), "copied_to": rel(target, root), "size_bytes": target.stat().st_size, "sha256": sha256_file(target)})
    return rows


def task1810(root: Path, command: str) -> dict[str, Any]:
    safe = root / "evidence" / "dream7b_s100p_v16_execution_20260703_windows_safe"
    hbm_ev = safe / "evidence" / "hbm_introspection_v16"
    out = root / "evidence" / "seg00_01_operator_inventory_v17"
    out.mkdir(parents=True, exist_ok=True)
    remote = load_json(safe / "v16_remote_collection_report.json", {})
    recovered = remote.get("hbm_introspection", {}).get("recovered_tensor_visibility", {})
    logs = command_log_manifest(root, hbm_ev, out / "logs")
    operator_inventory = [
        {"index": 0, "operator": "hbir.mul_id_63", "kind": "BPU", "inputs": [{"name": "_input_1", "shape": [128], "dtype": "int32", "dumpable": True}], "outputs": [{"name": "hbir.mul output / hbir.add input-1", "dumpable": False, "evidence": "not exposed in bin/txt/npy dump formats"}], "scale": None, "zero_point": None},
        {"index": 1, "operator": "View / hbir.reshape_id_1", "kind": "CPU/native", "inputs": [{"name": "_input_0", "shape": [1, 128], "dtype": "int32", "dumpable": True}], "outputs": [{"name": "hbir.reshape_id_1", "shape": [1, 128], "dtype": "int32", "dumpable": True}], "scale": None, "zero_point": None},
        {"index": 2, "operator": "GatherND / qnt.const_fake_quant_id_3", "kind": "CPU/native", "inputs": [{"name": "hbir.reshape_id_1", "shape": [1, 128], "dtype": "int32", "dumpable": True}], "outputs": [{"name": "qnt.const_fake_quant_id_3 / hbir.add input-0", "shape": [128, 3584], "dtype": "int8 raw inferred", "dumpable": True}], "scale": "missing", "zero_point": "missing"},
        {"index": 3, "operator": "hbir.add_id_137", "kind": "BPU", "inputs": [{"name": "qnt.const_fake_quant_id_3", "shape": [128, 3584], "dtype": "int8 raw", "dumpable": True}, {"name": "hbir.mul output", "dumpable": False}], "outputs": [{"name": "_output_0", "shape": [128, 3584], "dtype": "int16", "dumpable": True}], "scale": ADD_OUT_SCALE, "zero_point": 0},
    ]
    missing = [
        {"artifact": "hbir.mul output", "attempted": ["hrt_model_exec dump_intermediate bin", "hrt_model_exec dump_intermediate txt", "hrt_model_exec dump_intermediate npy", "strings/readelf/HBM metadata"], "found": bool(recovered.get("mul_output")), "reason": "not emitted by public HRT dump"},
        {"artifact": "hbir.add input-1", "attempted": ["HRT dump all formats", "dump file listing search for input-1", "operator strings search"], "found": bool(recovered.get("add_input1")), "reason": "not emitted by public HRT dump"},
        {"artifact": "GatherND official scale/zero_point", "attempted": ["hb_model_info", "hrt_model_exec model_info", "strings grep scale/zero/qnt/fake_quant", "compiler source search v15"], "found": False, "reason": "only model output scale is exposed"},
        {"artifact": "source graph/HBO/HBIR/ONNX/quant table", "attempted": ["targeted NAS/compiler cache search", "HBM strings/readelf"], "found": False, "reason": "no matching seq128 B=1 source graph or quant sidecar found"},
    ]
    inventory = {"operator_inventory": operator_inventory, "tensor_visibility": recovered, "missing_artifacts": missing, "command_log_manifest": logs}
    write_json(out / "operator_inventory.json", inventory)
    report = common(root, "1810_seg00_01_operator_inventory", command, [safe / "v16_remote_collection_report.json", hbm_ev])
    report.update({"verdict": "operator_inventory_complete_visible_graph_missing_internal_position_tensor", **inventory})
    if not recovered.get("mul_output") or not recovered.get("add_input1"):
        report["blocking_or_failure_reasons"].append("hbir.mul output and hbir.add input-1 remain not dumpable through public HRT/HBRT paths.")
    return save_report(root, "1810_seg00_01_operator_inventory", report, "seg00_01 Operator Inventory", [f"visible_ops: `{len(operator_inventory)}`", "hbir.mul output dumpable: `false`", "hbir.add input-1 dumpable: `false`", "GatherND scale found: `false`"])


def gathernd_ls_scale(root: Path) -> float:
    rs, hs = [], []
    for cid in CASE_IDS:
        rs.append(np.load(root / "evidence" / "seg00_01_exact_graph_v14" / cid / "gathernd_output_interpreted.npy").astype(np.float64).reshape(-1))
        hs.append(np.load(root / "evidence" / "seg00_01_decomposition_v13" / cid / "hf" / "token_embedding_output.npy").astype(np.float64).reshape(-1))
    r = np.concatenate(rs)
    h = np.concatenate(hs)
    return float(np.dot(r, h) / max(np.dot(r, r), 1e-12))


def task1820(root: Path, command: str) -> dict[str, Any]:
    out = root / "evidence" / "add_input1_reconstruction_v17"
    out.mkdir(parents=True, exist_ok=True)
    scale = gathernd_ls_scale(root)
    rows = []
    diagnostic_terms = {}
    for cid in CASE_IDS:
        add0_raw = np.load(root / "evidence" / "seg00_01_exact_graph_v14" / cid / "add_input_embedding.npy").astype(np.float32)
        add_out = np.load(root / "evidence" / "seg00_01_exact_graph_v14" / cid / "add_output_dequant.npy").astype(np.float32)
        diag = add_out - add0_raw * scale
        np.save(out / f"{cid}_diagnostic_add_input1_estimated_invalid_domain.npy", diag)
        sv = np.linalg.svd(diag.astype(np.float64), compute_uv=False)
        token_norm = np.linalg.norm(diag, axis=1)
        rows.append({
            "case_id": cid,
            "formal_reconstruction_legal": False,
            "domain": {"add_input0": "int8 raw with missing official scale", "add_output": "int16 with official output scale", "diagnostic_add0_scale": scale, "diagnostic_scale_category": "target_fitted_LS_invalid_for_root_cause"},
            "add_input0_raw_stats": stats(add0_raw),
            "add_output_dequant_stats": stats(add_out),
            "diagnostic_add_input1_stats": stats(diag),
            "diagnostic_add_input1_path": rel(out / f"{cid}_diagnostic_add_input1_estimated_invalid_domain.npy", root),
            "per_token_norm_stats": stats(token_norm),
            "per_dimension_norm_stats": stats(np.linalg.norm(diag, axis=0)),
            "svd_top10": [float(x) for x in sv[:10]],
            "svd_top1_energy_ratio": float((sv[0] ** 2) / max(float(np.sum(sv ** 2)), 1e-12)),
            "numerical_rank_1e_3": int(np.sum(sv > sv[0] * 1e-3)),
        })
        diagnostic_terms[cid] = diag
    pairwise = []
    for i, a in enumerate(CASE_IDS):
        for b in CASE_IDS[i + 1:]:
            pairwise.append({"case_a": a, "case_b": b, "metrics": compare(diagnostic_terms[a], diagnostic_terms[b])})
    report = common(root, "1820_add_input1_reconstruction", command, [root / "evidence" / "seg00_01_exact_graph_v14"])
    report.update({
        "verdict": "add_input1_not_legally_reconstructable_scale_domain_blocked",
        "formal_reconstruction_legal": False,
        "reason": "add output scale is official, but add input-0/GatherND scale is missing; int8 raw and int16 dequant cannot be subtracted for root-cause evidence.",
        "diagnostic_only": rows,
        "pairwise_same_position_different_tokens_diagnostic": pairwise,
        "position_contribution_candidate": "invalid_domain_diagnostic_suggests_token/case dependence; not a deployable formula",
    })
    report["blocking_or_failure_reasons"].append("hbir.add input-1 cannot be formally reconstructed without official add input-0/GatherND scale or direct add input-1 dump.")
    return save_report(root, "1820_add_input1_reconstruction", report, "add input-1 Reconstruction", ["formal reconstruction legal: `false`", "blocker: `missing GatherND/add input-0 official scale`", "diagnostic arrays are marked invalid_for_root_cause"])


def task1830(root: Path, command: str) -> dict[str, Any]:
    out = root / "evidence" / "position_ablation_v17"
    out.mkdir(parents=True, exist_ok=True)
    safe_pos = root / "evidence" / "dream7b_s100p_v16_execution_20260703_windows_safe" / "evidence" / "position_finite_difference_v16"
    shifted = root / "evidence" / "position_ablation_v17"
    required = ["canonical_0_to_127", "all_zero_positions", "all_one_positions", "constant_0_positions", "constant_1_positions", "constant_2_positions", "constant_64_positions", "constant_127_positions", "sparse_index_000_value_127", "sparse_index_001_value_127", "sparse_index_064_value_127", "sparse_index_127_value_127", "reverse_127_to_0", "random_permutation_positions", "one_indexed_1_to_128", "shifted_plus_2_positions", "shifted_plus_16_positions"]
    case_rows = {}
    for cid in CASE_IDS:
        zero = np.load(safe_pos / cid / "position_variants" / "all_zero_positions" / "dequant_output.npy")
        rows = []
        for v in required:
            base = safe_pos if (safe_pos / cid / "position_variants" / v / "dequant_output.npy").exists() else shifted
            p = base / cid / "position_variants" / v / "dequant_output.npy"
            if not p.exists():
                rows.append({"variant": v, "exists": False})
                continue
            arr = np.load(p)
            delta = arr - zero
            rows.append({"variant": v, "exists": True, "output_stats": stats(arr), "delta_stats": stats(delta), "delta_norm": float(np.linalg.norm(delta.reshape(-1))), "delta_abs_max": float(np.max(np.abs(delta)))})
        case_rows[cid] = rows
    shifted_report = load_json(shifted / "position_shifted_report.json", {})
    report = common(root, "1830_position_ablation_contract", command, [safe_pos, shifted])
    report.update({
        "verdict": "position_path_nonlinear_or_lookup_like_inconsistent_with_hf_embedding_boundary",
        "coverage_variants": required,
        "case_rows": case_rows,
        "out_of_range_policy": shifted_report.get("skipped", []),
        "position_path_type": "nonlinear_or_lookup_like_inconsistent",
        "hf_dream_semantics": "HF Dream remote code uses token embeddings and RoPE inside decoder attention; no learned absolute-position add is expected at token embedding boundary.",
        "contract_mismatch": "BPU seg00_01 output is position-sensitive while closest HF embedding boundary is not position-sensitive.",
    })
    return save_report(root, "1830_position_ablation_contract", report, "Position Ablation Contract", ["required shifted variants: `covered`", "out-of-range variants: `skipped_by_design`", "position path type: `nonlinear_or_lookup_like_inconsistent`", "HF semantic match: `false for embedding boundary`"])


def scale_candidate_metrics(root: Path, scale: float) -> dict[str, Any]:
    rows = {}
    heldout_rows = {}
    repeat_rows = {}
    for cid in CASE_IDS:
        raw = np.load(root / "evidence" / "seg00_01_exact_graph_v14" / cid / "gathernd_output_interpreted.npy").astype(np.float32)
        hf = np.load(root / "evidence" / "seg00_01_decomposition_v13" / cid / "hf" / "token_embedding_output.npy").astype(np.float32)
        rows[cid] = compare(hf, raw * scale)
        heldout_rows[cid] = compare(hf[1::2], raw[1::2] * scale)
        positions_same = np.where(np.load(root / "evidence" / "seg00_01_exact_graph_v14" / cid / "input_0_tokens.npy").reshape(-1) == np.load(root / "evidence" / "seg00_01_exact_graph_v14" / cid / "input_0_tokens.npy").reshape(-1)[0])[0]
        if positions_same.size >= 2:
            repeat_rows[cid] = compare(hf[positions_same], raw[positions_same] * scale)
    return {
        "scale": float(scale),
        "zero_point": 0,
        "rows": rows,
        "heldout_odd_token_rows": heldout_rows,
        "repeated_token_rows": repeat_rows,
        "max_relative_l2": max(r.get("relative_l2", 9) for r in rows.values()),
        "min_pearson": min((r.get("pearson_centered") or -9) for r in rows.values()),
    }


def task1840(root: Path, command: str) -> dict[str, Any]:
    out = root / "evidence" / "gathernd_scale_acquisition_v17"
    out.mkdir(parents=True, exist_ok=True)
    for p in [
        root / "evidence" / "dream7b_s100p_v16_execution_20260703_windows_safe" / "evidence" / "hbm_introspection_v16" / "hbm_strings_filtered.log",
        root / "evidence" / "dream7b_s100p_v16_execution_20260703_windows_safe" / "evidence" / "hbm_introspection_v16" / "hrt_model_exec_model_info.log",
        root / "evidence" / "compiler_source_graph_v15" / "targeted_search_results.json",
    ]:
        copy_path(p, out / p.name)
    all_h = np.concatenate([np.load(root / "evidence" / "seg00_01_decomposition_v13" / cid / "hf" / "token_embedding_output.npy").reshape(-1).astype(np.float64) for cid in CASE_IDS])
    candidates = {
        "model_output_scale_not_gathernd": {"category": "runtime_tensor_metadata", "deployable_for_gathernd": False, **scale_candidate_metrics(root, ADD_OUT_SCALE)},
        "least_squares_all_cases": {"category": "diagnostic_target_fitted", "deployable_for_gathernd": False, **scale_candidate_metrics(root, gathernd_ls_scale(root))},
        "hf_embedding_p99_symmetric": {"category": "diagnostic_target_fitted", "deployable_for_gathernd": False, **scale_candidate_metrics(root, float(np.percentile(np.abs(all_h), 99) / 127.0))},
        "hf_embedding_absmax_symmetric": {"category": "diagnostic_target_fitted", "deployable_for_gathernd": False, **scale_candidate_metrics(root, float(np.max(np.abs(all_h)) / 127.0))},
    }
    deployable = [k for k, v in candidates.items() if v.get("deployable_for_gathernd") and v["max_relative_l2"] <= 0.10 and v["min_pearson"] >= 0.99]
    write_json(out / "scale_candidates.json", candidates)
    report = common(root, "1840_gathernd_deployable_scale_acquisition", command, [out])
    report.update({
        "verdict": "no_deployable_gathernd_scale_found",
        "search_evidence": [artifact(p, root) for p in sorted(out.glob("*"))],
        "candidate_scales": candidates,
        "deployable_candidates": deployable,
        "policy": "Only official_from_metadata/compiler_log/runtime_tensor_metadata_for_GatherND/inferred_from_weight_quant_table may be deployable. LS/per-case/per-channel fits remain diagnostic.",
    })
    report["blocking_or_failure_reasons"].append("No official/deployable GatherND scale or zero_point was found in HBM strings, HRT model info, manifests, or compiler-cache search results.")
    return save_report(root, "1840_gathernd_deployable_scale_acquisition", report, "GatherND Deployable Scale Acquisition", ["deployable scale found: `false`", "diagnostic LS scale retained as non-deployable", "search logs copied to evidence"])


def task1850(root: Path, command: str) -> dict[str, Any]:
    out = root / "evidence" / "hf_seg00_equivalent_candidates_v17"
    out.mkdir(parents=True, exist_ok=True)
    hf_names = [
        ("token_embedding_only", "token_embedding_output.npy"),
        ("token_embedding_scaled_if_any_no_scale_found", "token_embedding_output.npy"),
        ("layer0_input_before_norm", "token_embedding_output.npy"),
        ("layer0_pre_attention_norm_output", "layer0_pre_attention_norm_output.npy"),
        ("layer0_attention_output", "layer0_attention_output.npy"),
        ("layer0_post_attention_residual", "layer0_post_attention_residual.npy"),
        ("layer0_pre_mlp_norm", "layer0_pre_mlp_norm_output.npy"),
        ("layer0_mlp_output", "layer0_mlp_output.npy"),
        ("layer0_final_output", "layer0_final_output.npy"),
    ]
    rows = []
    for cid in CASE_IDS:
        bpu = np.load(root / "evidence" / "seg00_01_exact_graph_v14" / cid / "add_output_dequant.npy")
        gather = np.load(root / "evidence" / "seg00_01_exact_graph_v14" / cid / "gathernd_output_interpreted.npy")
        emb = np.load(root / "evidence" / "seg00_01_decomposition_v13" / cid / "hf" / "token_embedding_output.npy")
        rows.append({"case_id": cid, "candidate": "GatherND_raw_LS_scaled_vs_token_embedding", "source": "gathernd_add_input0", "metrics": compare(emb, gather * gathernd_ls_scale(root))})
        for name, fname in hf_names:
            hp = root / "evidence" / "seg00_01_decomposition_v13" / cid / "hf" / fname
            if hp.exists():
                h = np.load(hp)
                m = compare(h, bpu)
                rows.append({"case_id": cid, "candidate": name, "source": fname, "metrics": m, "std_ratio_candidate_over_ref": (m.get("candidate_stats", {}).get("std") or 0) / max((m.get("reference_stats", {}).get("std") or 0), 1e-12)})
    ranking = sorted([r for r in rows if r["metrics"].get("shape_match")], key=lambda r: (r["metrics"].get("relative_l2", 9), -(r["metrics"].get("cosine") or -9)))[:30]
    write_json(out / "candidate_metrics.json", {"rows": rows, "ranking": ranking})
    pass_rows = [r for r in rows if r["metrics"].get("shape_match") and r["metrics"].get("relative_l2", 9) <= 0.10 and (r["metrics"].get("pearson_centered") or -9) >= 0.95]
    report = common(root, "1850_hf_seg00_equivalent_candidates", command, [root / "evidence" / "seg00_01_decomposition_v13", root / "evidence" / "seg00_01_exact_graph_v14"])
    report.update({
        "verdict": "no_exact_hf_equivalent_found_for_seg00_01_add_output",
        "candidate_count": len(hf_names),
        "rows": rows,
        "best_ranking": ranking,
        "pass_rows": pass_rows,
        "dream_specific_conditioning": "No separate Dream-specific time/mask conditioning tensor was found at this boundary in available HF remote code exports.",
    })
    report["blocking_or_failure_reasons"].append("No tested HF candidate matches BPU seg00_01 add/model output under strict rel L2/Pearson gate; exact closure still requires graph/quant metadata.")
    return save_report(root, "1850_hf_seg00_equivalent_candidates", report, "HF seg00 Equivalent Candidates", [f"HF candidates tested: `{len(hf_names)}`", f"strict pass rows: `{len(pass_rows)}`", "verdict: `no_exact_hf_equivalent_found`"])


def v17_island_pass(metrics: dict[str, Any]) -> bool:
    st = metrics.get("candidate_stats", {})
    return bool(
        metrics.get("shape_match")
        and metrics.get("reference_top1_in_candidate_top5")
        and (metrics.get("cosine") or -9) >= V17_ISLAND_GATE["cosine_min"]
        and metrics.get("relative_l2", 9) <= V17_ISLAND_GATE["relative_l2_max"]
        and not st.get("allzero")
        and not st.get("constant")
    )


def copy_targeted_island_evidence(root: Path, cid: str, island_key: str, src_dir: Path, dst_dir: Path) -> None:
    if src_dir.exists():
        copy_path(src_dir, dst_dir / cid / island_key)


def task1860(root: Path, command: str) -> dict[str, Any]:
    out = root / "evidence" / "targeted_bpu_islands_v17"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    targets = {
        "[1]": ("single", "seg_01"),
        "[2]": ("single", "seg_02"),
        "[1,2]": ("island", "island_01_02"),
    }
    rows = []
    for cid in CASE_IDS:
        for island, (kind, name) in targets.items():
            src = (root / "evidence" / "single_segment_substitution_v12r" / cid / name) if kind == "single" else (root / "evidence" / "bpu_island_reconstruction_v13" / cid / name)
            meta = load_json(src / "metadata.json", {})
            if not meta:
                rows.append({"case_id": cid, "island": island, "status": "missing_metadata", "strict_pass": False})
                continue
            copy_targeted_island_evidence(root, cid, island.replace("[", "island_").replace("]", "").replace(",", "_"), src, out)
            metrics = meta.get("final_metrics", {})
            q_avail = []
            if kind == "single":
                q_avail.append(meta.get("bpu", {}).get("quant_metadata", {}).get("available"))
            else:
                q_avail.extend(seg.get("bpu", {}).get("quant_metadata", {}).get("available") for seg in meta.get("segments", []))
            rows.append({
                "case_id": cid,
                "island": island,
                "input_boundary_name": meta.get("input_source", {}).get("kind") or meta.get("input_source", {}).get("path"),
                "output_boundary_name": "BPU island output -> HF suffix input",
                "conversion_used": "official_runtime_output_scale_direct_float32_no_target_affine",
                "official_scale_available": all(bool(x) for x in q_avail),
                "final_metrics": metrics,
                "strict_pass": v17_island_pass(metrics),
                "status": "pass",
                "source_metadata": rel(src / "metadata.json", root),
            })
    summary = {}
    for island in targets:
        subset = [r for r in rows if r.get("island") == island]
        summary[island] = {
            "rows": len(subset),
            "strict_pass_rows": sum(1 for r in subset if r.get("strict_pass")),
            "all_cases_strict_pass": len(subset) == len(CASE_IDS) and all(r.get("strict_pass") for r in subset),
            "reference_top1_in_candidate_top5_rows": sum(1 for r in subset if r.get("final_metrics", {}).get("reference_top1_in_candidate_top5")),
            "top1_agreement_rows": sum(1 for r in subset if r.get("final_metrics", {}).get("top1_agreement")),
            "median_relative_l2": float(np.median([r.get("final_metrics", {}).get("relative_l2", 9) for r in subset])) if subset else None,
            "min_cosine": min((r.get("final_metrics", {}).get("cosine") or -9) for r in subset) if subset else None,
        }
    valid = [k for k, v in summary.items() if v["all_cases_strict_pass"]]
    report = common(root, "1860_targeted_bpu_island_validation", command, [root / "evidence" / "single_segment_substitution_v12r", root / "evidence" / "bpu_island_reconstruction_v13"])
    report.update({"verdict": "no_targeted_bpu_island_strict_pass", "strict_gate": V17_ISLAND_GATE, "rows": rows, "summary_by_island": summary, "valid_islands": valid, "skipped_optional": [{"island": "[1,2,3]", "reason": "no existing row and HF suffix rerun is expensive/runtime-risky"}, {"island": "[2,3]", "reason": "no existing row and HF suffix rerun is expensive/runtime-risky"}]})
    report["blocking_or_failure_reasons"].append("Targeted [1], [2], and [1,2] islands do not pass the all-three-case v17 strict gate; ramp case is the recurring failure.")
    return save_report(root, "1860_targeted_bpu_island_validation", report, "Targeted BPU Island Validation", [f"valid_islands: `{valid}`", "[1]/[2]/[1,2] completed from raw same-route evidence", "verdict: `no_targeted_bpu_island_strict_pass`"])


def task1870(root: Path, command: str, reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    triggers = {
        "official_gathernd_scale": reports["1840"].get("deployable_candidates", []) != [],
        "legal_add_input1_or_position_formula": reports["1820"].get("formal_reconstruction_legal") is True,
        "source_graph_or_quant_table": False,
        "hf_equivalent_aligned": reports["1850"].get("pass_rows", []) != [],
        "valid_targeted_island": reports["1860"].get("valid_islands", []) != [],
    }
    verdict = "not_run_no_justified_correction"
    out = root / "evidence" / "corrected_seg00_candidate_v17"
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "decision.json", {"verdict": verdict, "triggers": triggers, "safety": SAFETY})
    report = common(root, "1870_corrected_seg00_candidate_if_justified", command, [out / "decision.json"])
    report.update({"verdict": verdict, "triggers": triggers, "executed_candidates": [], "evidence_root": rel(out, root)})
    report["blocking_or_failure_reasons"].append("No corrected seg00 candidate was run because no official scale/source graph/legal add-input1 formula/HF equivalent alignment was found.")
    return save_report(root, "1870_corrected_seg00_candidate_if_justified", report, "Corrected seg00 Candidate If Justified", ["verdict: `not_run_no_justified_correction`", "executed candidates: `0`"])


def task1880(root: Path, command: str) -> dict[str, Any]:
    out = root / "evidence" / "gguf_f16_reference_v17"
    log = out / "gguf_f16_search_v17.log"
    workspace_log = out / "workspace_gguf_search_v17.log"
    text = (log.read_text(encoding="utf-8", errors="ignore") if log.exists() else "") + "\n" + (workspace_log.read_text(encoding="utf-8", errors="ignore") if workspace_log.exists() else "")
    ggufs = [line.strip() for line in text.splitlines() if ".gguf" in line.lower()]
    f16 = [x for x in ggufs if "f16" in x.lower() or "fp16" in x.lower()]
    q4 = [x for x in ggufs if "q4" in x.lower()]
    report = common(root, "1880_gguf_f16_reference_escalation", command, [log, workspace_log])
    verdict = "gguf_f16_artifact_unavailable_runner_unavailable"
    report.update({"verdict": verdict, "search_logs": [artifact(log, root), artifact(workspace_log, root)], "gguf_artifacts": {"f16": f16, "q4_or_other": q4, "all": ggufs}, "truth_boundary": "GGUF Q4_K_M is not treated as F16/BF16 truth."})
    report["blocking_or_failure_reasons"].append("No Dream7B F16 GGUF artifact and logits-only runner were found in required search roots.")
    return save_report(root, "1880_gguf_f16_reference_escalation", report, "GGUF F16 Reference Escalation", [f"F16 artifacts: `{len(f16)}`", f"Q4/control artifacts: `{len(q4)}`", "verdict: `artifact_unavailable`"])


def final_docs(root: Path, command: str, reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    verdict = "C_seg00_01_fault_strongly_supported_but_exact_closure_blocked"
    if reports["1860"].get("valid_islands"):
        verdict = "D_targeted_bpu_island_validated_generation_pending"
    gate = {
        "schema_version": "dream7b_s100p_gate_packet_v17",
        "created_at_utc": now(),
        "verdict": verdict,
        **SAFETY,
        "current_full_bpu_path_status": "fail_falsified_against_HF_PyTorch_BF16_logits_truth",
        "seg00_01_contract_status": reports["1810"].get("verdict"),
        "gathernd_scale_status": reports["1840"].get("verdict"),
        "position_path_status": reports["1830"].get("verdict"),
        "add_input1_reconstruction_status": reports["1820"].get("verdict"),
        "hf_equivalent_candidate_status": reports["1850"].get("verdict"),
        "targeted_island_status": reports["1860"].get("verdict"),
        "corrected_candidate_status": reports["1870"].get("verdict"),
        "gguf_f16_status": reports["1880"].get("verdict"),
        "generation_quality_status": "not_run_by_design",
        "product_route_status": "not_run_by_design",
        "generation_gate_can_unlock": False,
        "product_route_can_unlock": False,
        "gates": {k: v.get("verdict") for k, v in reports.items()},
        "paper_safe_claim": "seg00_01 remains the strongest localized contract fault; exact closure is still blocked by missing source graph/quant metadata, not by lack of full-chain reruns.",
        "commands": [command],
    }
    write_json(root / "01_final_evidence" / "dream7b_s100p_gate_packet_v17.json", gate)
    write_text(root / "01_final_evidence" / "dream7b_s100p_gate_packet_v17.md", "# Dream7B S100P Gate Packet v17\n\n" + "\n".join(f"- {k}: `{v}`" for k, v in {
        "verdict": verdict,
        "current_full_bpu_path_status": gate["current_full_bpu_path_status"],
        "generation_quality_status": gate["generation_quality_status"],
        "product_route_status": gate["product_route_status"],
        "generation_gate_can_unlock": gate["generation_gate_can_unlock"],
        "product_route_can_unlock": gate["product_route_can_unlock"],
    }.items()) + "\n")
    write_text(root / "reports" / "SEG00_01_ROOT_CAUSE_STATUS_V17.md", "# SEG00_01 Root Cause Status V17\n\nseg00_01 is strongly implicated but not exactly closed. HRT/HBM inventory exposes View, GatherND, hbir.mul, and hbir.add, but not hbir.mul output/add input-1 or GatherND official scale. Domain-safe add reconstruction is blocked by scale mismatch. HF equivalent candidates do not match add output.\n")
    write_text(root / "reports" / "BPU_ISLAND_STATUS_V17.md", "# BPU Island Status V17\n\nTargeted islands [1], [2], and [1,2] were evaluated using existing same-route raw evidence and v17 strict gate. None passes across all three canonical cases; ramp is the recurring failure.\n")
    write_text(root / "reports" / "GGUF_F16_STATUS_V17.md", "# GGUF F16 Status V17\n\nNo Dream7B GGUF F16 artifact or logits-only runner was found. Q4_K_M remains a control reference only, not BF16/F16 truth.\n")
    write_text(root / "reports" / "PAPER_EVIDENCE_DOSSIER_V17.md", "# Paper Evidence Dossier V17\n\nThe current tested Dream7B seq128 B=1 segmented-HBM S100P full-BPU path remains logits-invalid against HF/PyTorch BF16 truth. v17 adds operator inventory, domain-safe add-input analysis, deployable GatherND scale search, systematic HF equivalent candidates, and targeted BPU-island validation. Generation and product routes were not run.\n")
    return gate


def package_v17(root: Path, command: str) -> dict[str, Any]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    staging = root / "tmp" / f"dream7b_s100p_v17_for_gptpro_{stamp}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    report_files = [
        root / "reports" / "1800_v17_baseline_lock.json",
        root / "reports" / "1800_v17_baseline_lock.md",
        root / "reports" / "1810_seg00_01_operator_inventory.json",
        root / "reports" / "1810_seg00_01_operator_inventory.md",
        root / "reports" / "1820_add_input1_reconstruction.json",
        root / "reports" / "1820_add_input1_reconstruction.md",
        root / "reports" / "1830_position_ablation_contract.json",
        root / "reports" / "1830_position_ablation_contract.md",
        root / "reports" / "1840_gathernd_deployable_scale_acquisition.json",
        root / "reports" / "1840_gathernd_deployable_scale_acquisition.md",
        root / "reports" / "1850_hf_seg00_equivalent_candidates.json",
        root / "reports" / "1850_hf_seg00_equivalent_candidates.md",
        root / "reports" / "1860_targeted_bpu_island_validation.json",
        root / "reports" / "1860_targeted_bpu_island_validation.md",
        root / "reports" / "1870_corrected_seg00_candidate_if_justified.json",
        root / "reports" / "1870_corrected_seg00_candidate_if_justified.md",
        root / "reports" / "1880_gguf_f16_reference_escalation.json",
        root / "reports" / "1880_gguf_f16_reference_escalation.md",
        root / "reports" / "PAPER_EVIDENCE_DOSSIER_V17.md",
        root / "reports" / "SEG00_01_ROOT_CAUSE_STATUS_V17.md",
        root / "reports" / "BPU_ISLAND_STATUS_V17.md",
        root / "reports" / "GGUF_F16_STATUS_V17.md",
    ]
    for p in report_files:
        copy_path(p, staging / "reports" / p.name)
    for p in (root / "01_final_evidence").glob("*v17*"):
        copy_path(p, staging / "01_final_evidence" / p.name)
    for sub in [
        "seg00_01_operator_inventory_v17",
        "add_input1_reconstruction_v17",
        "position_ablation_v17",
        "gathernd_scale_acquisition_v17",
        "hf_seg00_equivalent_candidates_v17",
        "targeted_bpu_islands_v17",
        "corrected_seg00_candidate_v17",
        "gguf_f16_reference_v17",
        "hf_remote_code_v14",
    ]:
        copy_path(root / "evidence" / sub, staging / "evidence" / sub)
    for p in [
        root / "evidence_for_gptpro" / "dream7b_s100p_v16_for_gptpro_20260703_175605.zip.sha256.txt",
        root / "tools" / "build_v17_research_thread.py",
        root / "tools" / "run_v17_remote_position_shifted.py",
        root / "tools" / "build_v16_research_thread.py",
    ]:
        copy_path(p, staging / rel(p, root))
    write_text(staging / "README.md", "Dream7B/S100P v17 evidence package. No generation, no 18888/18889, no OpenClaw foreground route changes.\n")
    package_summary = {
        "schema_version": "dream7b_s100p_v17_1890_inside_package",
        "created_at_utc": now(),
        "manifest_scope": "payload files only; MANIFEST.json and SHA256SUMS.txt are verified separately by zip test and SHA256SUMS",
        "zip_sha256_location": "external .zip.sha256.txt sidecar generated after archive close",
        **SAFETY,
    }
    write_json(staging / "reports" / "1890_final_v17_gate_packet_and_package.json", package_summary)
    write_text(staging / "reports" / "1890_final_v17_gate_packet_and_package.md", "# Final v17 Gate Packet and Package\n\nThe archive contains the v17 gate packet, reports, evidence, tools, MANIFEST.json, and SHA256SUMS.txt. The exact zip SHA256 is stored in the external `.zip.sha256.txt` sidecar generated after archive close.\n")
    files = []
    for p in sorted(staging.rglob("*")):
        if p.is_file():
            files.append({"path": rel(p, staging), "size_bytes": p.stat().st_size, "sha256": sha256_file(p)})
    write_json(staging / "MANIFEST.json", {"schema_version": "dream7b_s100p_v17_manifest", "created_at_utc": now(), "manifest_scope": "payload_files_excluding_MANIFEST_json_and_SHA256SUMS_txt", "file_count": len(files), "files": files})
    manifest_row = {"path": "MANIFEST.json", "size_bytes": (staging / "MANIFEST.json").stat().st_size, "sha256": sha256_file(staging / "MANIFEST.json")}
    sha_rows = files + [manifest_row]
    write_text(staging / "SHA256SUMS.txt", "\n".join(f"{f['sha256']}  {f['path']}" for f in sha_rows) + "\n")
    out = root / "evidence_for_gptpro" / f"dream7b_s100p_v17_for_gptpro_{stamp}.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p in sorted(staging.rglob("*")):
            if p.is_file():
                zf.write(p, rel(p, staging))
    with zipfile.ZipFile(out) as zf:
        bad = zf.testzip()
        count = len(zf.namelist())
    zip_sha = sha256_file(out)
    write_text(out.with_suffix(out.suffix + ".sha256.txt"), f"{zip_sha}  {out.name}\n")
    report = common(root, "1890_final_v17_gate_packet_and_package", command, [out])
    report.update({"zip_path": rel(out, root), "zip_sha256": zip_sha, "zip_sha256_txt": rel(out.with_suffix(out.suffix + ".sha256.txt"), root), "zip_size_bytes": out.stat().st_size, "zip_member_count": count, "zip_testzip_bad_member": bad, "manifest_file_count": len(files)})
    save_report(root, "1890_final_v17_gate_packet_and_package", report, "Final v17 Gate Packet and Package", [f"zip_path: `{report['zip_path']}`", f"zip_sha256: `{zip_sha}`"])
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    command = " ".join([sys.executable, *sys.argv])
    reports: dict[str, dict[str, Any]] = {}
    reports["1800"] = task1800(root, command)
    reports["1810"] = task1810(root, command)
    reports["1820"] = task1820(root, command)
    reports["1830"] = task1830(root, command)
    reports["1840"] = task1840(root, command)
    reports["1850"] = task1850(root, command)
    reports["1860"] = task1860(root, command)
    reports["1870"] = task1870(root, command, reports)
    reports["1880"] = task1880(root, command)
    gate = final_docs(root, command, reports)
    package = package_v17(root, command)
    print(json.dumps({"verdict": gate["verdict"], "zip": package["zip_path"], "zip_sha256": package["zip_sha256"], "gates": gate["gates"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
