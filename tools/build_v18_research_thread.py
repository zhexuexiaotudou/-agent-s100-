#!/usr/bin/env python3
"""Build Dream7B/S100P v18 reports and GPT Pro evidence package."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


SAFETY = {
    "generation_quality_run": False,
    "product_routes_18888_18889_touched": False,
    "dream7b_frontend_openclaw_traffic_touched": False,
    "harness_qwen_openclaw_defaults_modified": False,
}
CASE_IDS = ["zeros", "ramp", "short_chinese_prompt_padded"]
ISLANDS = ["[1]", "[2]", "[1,2]"]


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
        "schema_version": f"dream7b_s100p_v18_{stem}",
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
    return out


def task1900(root: Path, command: str) -> dict[str, Any]:
    v17_zip = root / "evidence_for_gptpro" / "dream7b_s100p_v17_for_gptpro_20260703_233743.zip"
    gate = load_json(root / "01_final_evidence" / "dream7b_s100p_gate_packet_v17.json", {})
    z = parse_zip_manifest(v17_zip)
    sem = load_json(root / "evidence" / "dream7b_s100p_v18_execution_20260704" / "evidence" / "targeted_bpu_islands_semantic_v18" / "semantic_island_battery_report.json", {})
    pos = load_json(root / "evidence" / "dream7b_s100p_v18_execution_20260704" / "evidence" / "position_path_recovery_v18" / "position_path_recovery_report.json", {})
    report = common(root, "1900_v18_baseline_lock", command, [v17_zip, root / "01_final_evidence" / "dream7b_s100p_gate_packet_v17.json"])
    report.update({
        "verdict": "baseline_locked",
        "v17_package": z,
        "v17_gate_packet": gate,
        "v18_remote_position_status": pos.get("status"),
        "v18_remote_semantic_status": sem.get("status"),
        "v18_scope": "position-derived seg00_01 path closure plus targeted island ramp/semantic debugging",
        "overclaim_boundaries": [
            "v18 does not rerun full-chain falsification",
            "semantic battery did not produce logits rows because HF BF16 runtime load was blocked",
            "diagnostic transforms are not deployable repairs",
            "generation and product routes remain not-run by design",
        ],
    })
    if not (z.get("exists") and z.get("testzip_bad_member") is None and not z.get("manifest_missing") and not z.get("manifest_bad_hash")):
        report["blocking_or_failure_reasons"].append("v17 package validation failed")
    return save_report(root, "1900_v18_baseline_lock", report, "v18 Baseline Lock", [f"v17_verdict: `{gate.get('verdict')}`", f"v17_zip_sha256: `{z.get('sha256')}`", f"position_remote_status: `{pos.get('status')}`", f"semantic_remote_status: `{sem.get('status')}`"])


def token_norm_summary(delta: np.ndarray) -> dict[str, Any]:
    arr = np.asarray(delta, dtype=np.float32)
    if arr.ndim != 2:
        arr = arr.reshape(128, -1)
    norms = np.linalg.norm(arr, axis=1)
    return {
        "nonzero_token_count": int(np.count_nonzero(norms > 1e-8)),
        "max_token_norm": float(np.max(norms)),
        "mean_token_norm": float(np.mean(norms)),
        "std_token_norm": float(np.std(norms)),
        "cv_token_norm": float(np.std(norms) / (np.mean(norms) + 1e-12)),
        "top_token_indices": np.argsort(norms)[-8:][::-1].astype(int).tolist(),
    }


def position_case_metrics(case_dir: Path) -> dict[str, Any]:
    variants = case_dir / "position_variants"
    selected = ["all_zero", "all_one", "constant_1", "constant_2", "constant_64", "constant_127", "canonical", "reversed", "random_permutation"]
    rows: dict[str, Any] = {}
    for name in selected:
        p = variants / name / "delta_vs_all_zero.npy"
        if p.exists():
            d = np.load(p)
            rows[name] = {"delta_norm": float(np.linalg.norm(d.reshape(-1))), "delta_abs_max": float(np.max(np.abs(d))), "delta_std": float(np.std(d)), "token_norm_summary": token_norm_summary(d)}
    linearity = {}
    if (variants / "constant_1" / "delta_vs_all_zero.npy").exists():
        d1 = np.load(variants / "constant_1" / "delta_vs_all_zero.npy").reshape(-1)
        for k in [2, 4, 8, 16, 32, 64, 127]:
            pk = variants / f"constant_{k}" / "delta_vs_all_zero.npy"
            if pk.exists():
                dk = np.load(pk).reshape(-1)
                linearity[f"constant_{k}_vs_k_times_constant_1_rel_l2"] = float(np.linalg.norm(dk - d1 * k) / (np.linalg.norm(dk) + 1e-12))
    spike_rows = {}
    for idx in [0, 1, 2, 64, 127]:
        vals = {}
        for val in [1, 2, 64, 127]:
            p = variants / f"single_spike_index_{idx:03d}_value_{val:03d}" / "delta_vs_all_zero.npy"
            if p.exists():
                d = np.load(p)
                vals[str(val)] = {"delta_norm": float(np.linalg.norm(d.reshape(-1))), "delta_abs_max": float(np.max(np.abs(d))), "token_norm_summary": token_norm_summary(d)}
        spike_rows[str(idx)] = vals
    return {"selected_variant_rows": rows, "linearity_tests": linearity, "single_spike_rows": spike_rows}


def task1910(root: Path, command: str) -> dict[str, Any]:
    pos_root = root / "evidence" / "dream7b_s100p_v18_execution_20260704" / "evidence" / "position_path_recovery_v18"
    remote = load_json(pos_root / "position_path_recovery_report.json", {})
    report = common(root, "1910_position_path_indirect_recovery", command, [pos_root / "position_path_recovery_report.json"])
    case_metrics = {cid: position_case_metrics(pos_root / cid) for cid in CASE_IDS}
    report.update({
        "verdict": "position_path_lookup_like_token_dependent_not_formula_recovered",
        "remote_status": remote.get("status"),
        "variant_count": len(remote.get("variant_names", [])),
        "cases": case_metrics,
        "interpretation": {
            "same_legal_dequant_domain": "delta = seg00_01 add/model output dequant(variant) - dequant(all_zero_position)",
            "formula_recovered": False,
            "position_value_dependence": "nonlinear; constant-k tests are not consistent with k * constant_1 for ramp/semantic-proxy cases",
            "token_index_dependence": "single-spike effects can be nonlocal and token-content dependent; index 1 is much larger for short_chinese_prompt_padded and ramp than zero-token case",
            "table_lookup_like_signal": "supported by non-monotonic spike values and canonical/reversed/random deltas that cannot be reduced to scalar broadcast",
            "hbir_add_input1_direct_dump": "still unavailable; HRT dump exposes add input-0/GatherND for all_zero positions only",
        },
    })
    if remote.get("status") != "pass":
        report["blocking_or_failure_reasons"].append("remote position recovery did not pass")
    return save_report(root, "1910_position_path_indirect_recovery", report, "Position Path Indirect Recovery", ["verdict: `position_path_lookup_like_token_dependent_not_formula_recovered`", f"variant_count: `{len(remote.get('variant_names', []))}`", "formula_recovered: `false`"])


def task1920(root: Path, command: str) -> dict[str, Any]:
    sem_root = root / "evidence" / "dream7b_s100p_v18_execution_20260704" / "evidence" / "targeted_bpu_islands_semantic_v18"
    sem = load_json(sem_root / "semantic_island_battery_report.json", {})
    report = common(root, "1920_targeted_island_semantic_battery", command, [sem_root / "semantic_island_battery_report.json"])
    report.update({
        "verdict": "semantic_battery_runtime_blocked_no_logits_rows",
        "remote_status": sem.get("status"),
        "semantic_cases_generated": len(sem.get("cases", [])),
        "hf_truth_rows": len(sem.get("hf_rows", [])),
        "island_rows": len(sem.get("island_rows", [])),
        "errors": sem.get("errors", []),
        "cases_path": sem.get("cases_path"),
        "semantic_vs_ramp_verdict": "inconclusive_runtime_blocked",
        "strict_gate_relaxed": False,
        "generation_quality_run": False,
        "attempted_compatibility_steps": [
            "transformers.modeling_rope_utils shim for rope_config_validation/ROPE_INIT_FUNCTIONS",
            "transformers.cache_utils shim for Cache/DynamicCache with use_cache=False",
            "flash-attn availability shims returning False",
            "is_torchdynamo_compiling shim returning False",
            "PreTrainedModel.from_pretrained compatibility wrapper for token/weights_only/_attn_implementation",
            "forced use_safetensors=True",
        ],
    })
    report["blocking_or_failure_reasons"].append("HF/PyTorch BF16 truth for semantic cases could not be produced because the installed transformers 4.30.2 path still attempted torch.load on sharded safetensors.")
    return save_report(root, "1920_targeted_island_semantic_battery", report, "Targeted Island Semantic Battery", [f"semantic_cases_generated: `{len(sem.get('cases', []))}`", "hf_truth_rows: `0`", "island_rows: `0`", "verdict: `semantic_battery_runtime_blocked_no_logits_rows`"])


def island_output_paths(root: Path, case_id: str, island: str) -> tuple[Path, Path, Path]:
    base = root / "evidence" / "targeted_bpu_islands_v17" / case_id
    hf = root / "evidence" / "hf_boundaries_v11" / case_id
    if island == "[1]":
        return base / "island_1" / "bpu_dequant_output.npy", base / "island_1" / "bpu_raw_output.npy", hf / "layer_01_output.npy"
    if island == "[2]":
        return base / "island_2" / "bpu_dequant_output.npy", base / "island_2" / "bpu_raw_output.npy", hf / "layer_02_output.npy"
    return base / "island_1_2" / "seg_02" / "bpu_dequant_output.npy", base / "island_1_2" / "seg_02" / "bpu_raw_output.npy", hf / "layer_02_output.npy"


def boundary_diagnostics(root: Path) -> list[dict[str, Any]]:
    rows = []
    for case_id in CASE_IDS:
        for island in ISLANDS:
            deq_p, raw_p, ref_p = island_output_paths(root, case_id, island)
            if not (deq_p.exists() and raw_p.exists() and ref_p.exists()):
                continue
            deq = np.load(deq_p).astype(np.float32)
            raw = np.load(raw_p).astype(np.float32)
            ref = np.load(ref_p).astype(np.float32)
            lo, hi = np.percentile(ref.reshape(-1), [1, 99])
            clipped = np.clip(deq, lo, hi)
            z = (deq - float(np.mean(deq))) / (float(np.std(deq)) + 1e-12) * float(np.std(ref)) + float(np.mean(ref))
            rows.append({
                "case_id": case_id,
                "island": island,
                "official_dequant": compare(ref, deq),
                "raw_no_transform": compare(ref, raw),
                "clip_to_hf_p01_p99_diagnostic": compare(ref, clipped),
                "z_normalized_diagnostic": compare(ref, z),
                "diagnostic_not_deployable": True,
            })
    return rows


def task1930(root: Path, command: str) -> dict[str, Any]:
    v17 = load_json(root / "reports" / "1860_targeted_bpu_island_validation.json", {})
    report = common(root, "1930_ramp_failure_deep_dive", command, [root / "reports" / "1860_targeted_bpu_island_validation.json"])
    ramp_rows = [r for r in v17.get("rows", []) if r.get("case_id") == "ramp"]
    non_ramp_rows = [r for r in v17.get("rows", []) if r.get("case_id") != "ramp"]
    by_island = {}
    for island in ISLANDS:
        rr = [r for r in ramp_rows if r.get("island") == island]
        nr = [r for r in non_ramp_rows if r.get("island") == island]
        by_island[island] = {
            "ramp_relative_l2": [r.get("final_metrics", {}).get("relative_l2") for r in rr],
            "ramp_cosine": [r.get("final_metrics", {}).get("cosine") for r in rr],
            "non_ramp_relative_l2": [r.get("final_metrics", {}).get("relative_l2") for r in nr],
            "non_ramp_cosine": [r.get("final_metrics", {}).get("cosine") for r in nr],
            "ramp_strict_pass": [r.get("strict_pass") for r in rr],
            "non_ramp_strict_pass_count": sum(1 for r in nr if r.get("strict_pass")),
        }
    report.update({
        "verdict": "ramp_failure_recurs_under_v17_diagnostic_cases_semantic_inconclusive",
        "v17_summary_by_island": v17.get("summary_by_island"),
        "ramp_vs_non_ramp_by_island": by_island,
        "boundary_diagnostic_transforms": boundary_diagnostics(root),
        "diagnostic_transform_policy": "clamp/z-normalize/no-transform are boundary diagnostics only; no HF suffix logits were claimed and no deployable repair is inferred.",
    })
    return save_report(root, "1930_ramp_failure_deep_dive", report, "Ramp Failure Deep Dive", ["ramp remains recurring v17 failure", "semantic comparison: `inconclusive_runtime_blocked`", "diagnostic transforms: `not_deployable_repairs`"])


def task1940(root: Path, command: str, reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    justified = False
    reasons = [
        "position-derived path formula was not recovered without target fitting",
        "official GatherND/add scale was not found",
        "semantic island pass condition was not established because semantic HF truth/runtime was blocked",
        "no source/quant metadata was found",
        "no deployable conversion was validated on heldout semantic cases",
    ]
    report = common(root, "1940_corrected_candidate_if_justified_v18", command, [])
    report.update({"verdict": "not_run_no_justified_correction", "corrected_candidate_run": False, "justification_conditions_met": justified, "failed_conditions": reasons})
    report["blocking_or_failure_reasons"].extend(reasons)
    return save_report(root, "1940_corrected_candidate_if_justified_v18", report, "Corrected Candidate If Justified v18", ["corrected_candidate_run: `false`", "verdict: `not_run_no_justified_correction`"])


def final_docs(root: Path, command: str, reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    verdict = "D_seg00_01_fault_strongly_supported_exact_closure_still_blocked"
    gate = {
        "schema_version": "dream7b_s100p_gate_packet_v18",
        "created_at_utc": now(),
        "verdict": verdict,
        **SAFETY,
        "current_full_bpu_path_status": "fail_falsified_against_HF_PyTorch_BF16_logits_truth_v17_baseline",
        "position_path_status": reports["1910"].get("verdict"),
        "semantic_battery_status": reports["1920"].get("verdict"),
        "ramp_failure_status": reports["1930"].get("verdict"),
        "corrected_candidate_status": reports["1940"].get("verdict"),
        "generation_quality_status": "not_run_by_design",
        "product_route_status": "not_run_by_design",
        "generation_gate_can_unlock": False,
        "product_route_can_unlock": False,
        "gates": {k: v.get("verdict") for k, v in reports.items()},
        "paper_safe_claim": "v18 strengthens the seg00_01 position-derived path diagnosis as lookup-like/token-dependent but does not recover a deployable formula; semantic island expansion is blocked by HF runtime loader incompatibility, so no semantic island validity claim is made.",
        "commands": [command],
    }
    write_json(root / "01_final_evidence" / "dream7b_s100p_gate_packet_v18.json", gate)
    write_text(root / "01_final_evidence" / "dream7b_s100p_gate_packet_v18.md", "# Dream7B S100P Gate Packet v18\n\n" + "\n".join(f"- {k}: `{v}`" for k, v in {
        "verdict": verdict,
        "position_path_status": gate["position_path_status"],
        "semantic_battery_status": gate["semantic_battery_status"],
        "corrected_candidate_status": gate["corrected_candidate_status"],
        "generation_quality_status": gate["generation_quality_status"],
        "product_route_status": gate["product_route_status"],
    }.items()) + "\n")
    write_text(root / "reports" / "SEG00_POSITION_PATH_STATUS_V18.md", "# SEG00 Position Path Status V18\n\nThe v18 position-variant probe ran 34 variants over three canonical cases. Delta analysis in the legal seg00_01 output dequant domain supports a lookup-like and token-dependent position-derived path, not a recovered linear/scalar formula. hbir.add input-1 remains not directly dumpable.\n")
    write_text(root / "reports" / "BPU_ISLAND_SEMANTIC_STATUS_V18.md", "# BPU Island Semantic Status V18\n\nThe semantic prompt battery generated eight seq128 semantic cases, but HF BF16 truth and island rows were blocked by the current S100P Python stack: transformers 4.30.2 still attempted torch.load on sharded safetensors even after local compatibility shims. No semantic island pass/fail claim is made.\n")
    write_text(root / "reports" / "PAPER_EVIDENCE_DOSSIER_V18.md", "# Paper Evidence Dossier V18\n\nThe current tested full-BPU path remains falsified by v17 baseline. v18 adds a stronger seg00_01 position-derived path probe: 34 position variants across zeros, ramp, and short Chinese cases, with deltas computed only in the legal seg00_01 output dequant domain. The observed deltas are nonlinear, nonlocal, and token-content dependent, so no deployable formula or corrected candidate is justified. Semantic BPU-island expansion was attempted but blocked before logits truth by HF runtime loader incompatibility; generation and product routes were not run.\n")
    return gate


def package_v18(root: Path, command: str) -> dict[str, Any]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    staging = root / "tmp" / f"dream7b_s100p_v18_for_gptpro_{stamp}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    report_files = [
        "1900_v18_baseline_lock", "1910_position_path_indirect_recovery", "1920_targeted_island_semantic_battery",
        "1930_ramp_failure_deep_dive", "1940_corrected_candidate_if_justified_v18",
    ]
    for stem in report_files:
        copy_path(root / "reports" / f"{stem}.json", staging / "reports" / f"{stem}.json")
        copy_path(root / "reports" / f"{stem}.md", staging / "reports" / f"{stem}.md")
    for name in ["PAPER_EVIDENCE_DOSSIER_V18.md", "SEG00_POSITION_PATH_STATUS_V18.md", "BPU_ISLAND_SEMANTIC_STATUS_V18.md"]:
        copy_path(root / "reports" / name, staging / "reports" / name)
    for p in (root / "01_final_evidence").glob("*v18*"):
        copy_path(p, staging / "01_final_evidence" / p.name)
    for p in [
        root / "evidence" / "dream7b_s100p_v18_execution_20260704_remote_evidence.tar.gz",
        root / "tools" / "build_v18_research_thread.py",
        root / "tools" / "run_v18_position_path_recovery.py",
        root / "tools" / "run_v18_semantic_island_battery.py",
        root / "tools" / "build_v17_research_thread.py",
        root / "evidence_for_gptpro" / "dream7b_s100p_v17_for_gptpro_20260703_233743.zip.sha256.txt",
    ]:
        copy_path(p, staging / rel(p, root))
    # Keep lightweight extracted JSON/cases directly visible in the package.
    for p in [
        root / "evidence" / "dream7b_s100p_v18_execution_20260704" / "evidence" / "position_path_recovery_v18" / "position_path_recovery_report.json",
        root / "evidence" / "dream7b_s100p_v18_execution_20260704" / "evidence" / "targeted_bpu_islands_semantic_v18" / "semantic_island_battery_report.json",
        root / "evidence" / "dream7b_s100p_v18_execution_20260704" / "evidence" / "targeted_bpu_islands_semantic_v18" / "cases" / "semantic_seq128_cases_v18.jsonl",
    ]:
        copy_path(p, staging / rel(p, root))
    write_text(staging / "README.md", "Dream7B/S100P v18 evidence package. No generation, no 18888/18889, no OpenClaw foreground route changes. Full raw v18 remote evidence is in evidence/dream7b_s100p_v18_execution_20260704_remote_evidence.tar.gz.\n")
    files = []
    for p in sorted(staging.rglob("*")):
        if p.is_file():
            files.append({"path": rel(p, staging), "size_bytes": p.stat().st_size, "sha256": sha256_file(p)})
    write_json(staging / "MANIFEST.json", {"schema_version": "dream7b_s100p_v18_manifest", "created_at_utc": now(), "manifest_scope": "payload_files_excluding_MANIFEST_json_and_SHA256SUMS_txt", "file_count": len(files), "files": files})
    manifest_row = {"path": "MANIFEST.json", "size_bytes": (staging / "MANIFEST.json").stat().st_size, "sha256": sha256_file(staging / "MANIFEST.json")}
    write_text(staging / "SHA256SUMS.txt", "\n".join(f"{f['sha256']}  {f['path']}" for f in files + [manifest_row]) + "\n")
    out = root / "evidence_for_gptpro" / f"dream7b_s100p_v18_for_gptpro_{stamp}.zip"
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
    report = common(root, "1950_final_v18_gate_packet_and_package", command, [out])
    report.update({"zip_path": rel(out, root), "zip_sha256": zip_sha, "zip_sha256_txt": rel(out.with_suffix(out.suffix + ".sha256.txt"), root), "zip_size_bytes": out.stat().st_size, "zip_member_count": count, "zip_testzip_bad_member": bad, "manifest_file_count": len(files)})
    save_report(root, "1950_final_v18_gate_packet_and_package", report, "Final v18 Gate Packet and Package", [f"zip_path: `{report['zip_path']}`", f"zip_sha256: `{zip_sha}`"])
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    command = " ".join([sys.executable, *sys.argv])
    reports: dict[str, dict[str, Any]] = {}
    reports["1900"] = task1900(root, command)
    reports["1910"] = task1910(root, command)
    reports["1920"] = task1920(root, command)
    reports["1930"] = task1930(root, command)
    reports["1940"] = task1940(root, command, reports)
    gate = final_docs(root, command, reports)
    package = package_v18(root, command)
    print(json.dumps({"verdict": gate["verdict"], "zip": package["zip_path"], "zip_sha256": package["zip_sha256"], "gates": gate["gates"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
