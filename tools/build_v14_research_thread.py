#!/usr/bin/env python3
"""Build Dream7B/S100P v14 reports and GPT Pro evidence package.

v14 is evidence aggregation plus offline diagnostics. It does not run
generation and does not touch product routes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


CASE_IDS = ["zeros", "ramp", "short_chinese_prompt_padded"]
STRICT = {"relative_l2_max": 0.1, "pearson_min": 0.95, "cosine_min": 0.95}
SAFETY = {
    "generation_quality_run": False,
    "product_routes_18888_18889_touched": False,
    "dream7b_frontend_openclaw_traffic_touched": False,
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_jsonable(obj: Any) -> str:
    data = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
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
    return json.loads(path.read_text(encoding="utf-8"))


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return str(path)


def artifact(path: Path, root: Path, hash_large: bool = True) -> dict[str, Any]:
    row: dict[str, Any] = {"path": rel(path, root), "exists": path.exists()}
    if path.exists() and path.is_file():
        row["size_bytes"] = path.stat().st_size
        if hash_large or path.stat().st_size < 512 * 1024 * 1024:
            row["sha256"] = sha256_file(path)
        else:
            row["sha256"] = "skipped_large_file"
    return row


def git_status(root: Path) -> dict[str, Any]:
    try:
        proc = subprocess.run(["git", "status", "--short"], cwd=root, text=True, capture_output=True, timeout=10)
        return {"returncode": proc.returncode, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}
    except Exception as exc:
        return {"status": f"git_status_error:{type(exc).__name__}:{exc}"}


def common(root: Path, name: str, command: str, inputs: list[Path]) -> dict[str, Any]:
    return {
        "schema_version": f"dream7b_s100p_v14_{name}",
        "created_at_utc": now(),
        "run_commands": [command],
        "host_environment": {"local_platform": platform.platform(), "python": sys.version},
        "git": git_status(root),
        "input_artifacts": [artifact(p, root) for p in inputs],
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
    lines += [f"- {b}" for b in bullets]
    if report.get("blocking_or_failure_reasons"):
        lines += ["", "## Blocking or Failure Reasons"]
        lines += [f"- {x}" for x in report["blocking_or_failure_reasons"]]
    if report.get("next_minimal_experiments"):
        lines += ["", "## Next Minimal Experiments"]
        lines += [f"- {x}" for x in report["next_minimal_experiments"]]
    write_text(m, "\n".join(lines) + "\n")
    report["output_artifacts"] = [artifact(j, root), artifact(m, root)]
    write_json(j, report)
    return report


def tensor_stats(x: np.ndarray) -> dict[str, Any]:
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


def topk(x: np.ndarray, k: int = 10) -> list[dict[str, Any]]:
    v = np.asarray(x, dtype=np.float64).reshape(-1)
    idx = np.argsort(v)[-k:][::-1].astype(int)
    return [{"index": int(i), "value": float(v[i])} for i in idx]


def compare_arrays(ref: np.ndarray, cand: np.ndarray, topk_n: int = 5) -> dict[str, Any]:
    r = np.asarray(ref, dtype=np.float64).reshape(-1)
    c = np.asarray(cand, dtype=np.float64).reshape(-1)
    if r.shape != c.shape:
        return {"shape_match": False, "reference_shape": list(r.shape), "candidate_shape": list(c.shape)}
    rt = np.argsort(r)[-topk_n:][::-1].astype(int)
    ct = np.argsort(c)[-topk_n:][::-1].astype(int)
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
        "candidate_stats": tensor_stats(c.astype(np.float32)),
        "reference_stats": tensor_stats(r.astype(np.float32)),
    }


def strict_logits_valid(m: dict[str, Any]) -> bool:
    return bool(
        m.get("top1_agreement")
        and m.get("reference_top1_in_candidate_top5")
        and m.get("cosine") is not None
        and float(m["cosine"]) >= STRICT["cosine_min"]
        and m.get("pearson_centered") is not None
        and float(m["pearson_centered"]) >= STRICT["pearson_min"]
        and m.get("relative_l2") is not None
        and float(m["relative_l2"]) <= STRICT["relative_l2_max"]
        and not (m.get("candidate_stats") or {}).get("allzero")
        and not (m.get("candidate_stats") or {}).get("constant")
    )


def squeeze_hidden(x: np.ndarray) -> np.ndarray:
    arr = np.asarray(x)
    if arr.ndim == 3 and arr.shape[0] == 1:
        arr = arr[0]
    return arr.astype(np.float32)


def parse_zip_manifest(zip_path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {"path": str(zip_path), "exists": zip_path.exists()}
    if not zip_path.exists():
        return out
    out["size_bytes"] = zip_path.stat().st_size
    out["sha256"] = sha256_file(zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        out["testzip_bad_member"] = zf.testzip()
        names = set(zf.namelist())
        out["member_count"] = len(names)
        mf = json.loads(zf.read("MANIFEST.json"))
        out["manifest_entries"] = len(mf.get("files", []))
        missing, bad_size, bad_sha = [], [], []
        for item in mf.get("files", []):
            p = item["path"]
            if p not in names:
                missing.append(p)
                continue
            data = zf.read(p)
            if len(data) != item.get("size_bytes"):
                bad_size.append(p)
            if hashlib.sha256(data).hexdigest() != item.get("sha256"):
                bad_sha.append(p)
        out.update({"manifest_missing": missing, "manifest_bad_size": bad_size, "manifest_bad_sha256": bad_sha})
        out["contains_standalone_full_truth_arrays"] = any("full_truth" in x and x.endswith(".npy") for x in names)
        out["contains_exact_compiler_hbo_graph"] = any(x.endswith(".hbo") or x.endswith(".onnx") or x.endswith(".mlir") for x in names)
        out["contains_gguf_f16_logits_reference"] = any("gguf" in x.lower() and "f16" in x.lower() and x.endswith(".npy") for x in names)
    return out


def task1400(root: Path, command: str) -> dict[str, Any]:
    zip_path = root / "evidence_for_gptpro" / "dream7b_s100p_v13_for_gptpro_20260703_132614.zip"
    gate = load_json(root / "01_final_evidence" / "dream7b_s100p_gate_packet_v13.json", {})
    r1300 = load_json(root / "reports" / "1300_v13_baseline_lock.json", {})
    r1310 = load_json(root / "reports" / "1310_seg00_01_operator_mapping.json", {})
    r1320 = load_json(root / "reports" / "1320_seg00_01_decomposition_compare.json", {})
    r1340 = load_json(root / "reports" / "1340_bpu_island_reconstruction_matrix.json", {})
    z = parse_zip_manifest(zip_path)
    report = common(root, "1400_v14_baseline_lock", command, [zip_path])
    supported = [
        "current_full_bpu_path=falsified_against_HF_PyTorch_BF16_logits_truth",
        f"v13 verdict={gate.get('verdict')}",
        f"seg00_01 decomposition={r1320.get('verdict')}",
        f"bpu_islands={r1340.get('verdict')}",
        "generation_quality=not_run_by_design",
        "product_route=not_run_by_design",
    ]
    unsupported = [
        "deployment success",
        "generation failure or quality result",
        "18888/18889 product route result",
        "GGUF F16 truth row",
        "exact seg00_01 compiler source graph for seq128 B=1",
    ]
    report.update(
        {
            "v13_package": z,
            "v13_gate_packet": gate,
            "v13_key_reports": {
                "1300": r1300.get("schema_version"),
                "1310_verdict": r1310.get("verdict"),
                "1320_verdict": r1320.get("verdict"),
                "1340_verdict": r1340.get("verdict"),
            },
            "v13_supported_claims": supported,
            "v13_unsupported_claims": unsupported,
            "exact_remaining_blockers": [
                "standalone BF16 truth arrays must be first-class v14 evidence",
                "seg00_01 mul output and add position input are not directly dumped",
                "seq128 B=1 compiler/HBO source graph and quant tables are not yet available",
                "GGUF F16 logits reference is still unavailable",
            ],
            "required_v14_artifacts": [
                "full_truth_bf16_v14",
                "seg00_01_exact_graph_v14",
                "hf_remote_code_v14",
                "compiler_graph_artifact_search_v14",
                "gguf_f16_reference_v14",
                "bpu_island_diagnostic_calibration_v14",
            ],
            "standalone_bf16_truth_arrays_present_in_v13_zip": bool(z.get("contains_standalone_full_truth_arrays")),
            "exact_compiler_hbo_graph_present_in_v13_zip": bool(z.get("contains_exact_compiler_hbo_graph")),
            "gguf_f16_logits_reference_present_in_v13_zip": bool(z.get("contains_gguf_f16_logits_reference")),
        }
    )
    if not (z.get("exists") and z.get("testzip_bad_member") is None and not z.get("manifest_bad_sha256")):
        report["blocking_or_failure_reasons"].append("v13 zip manifest/hash validation is not clean")
    return save_report(root, "1400_v14_baseline_lock", report, "v14 Baseline Lock", [f"v13 zip sha256: `{z.get('sha256')}`", f"v13 verdict: `{gate.get('verdict')}`"])


def task1410(root: Path, command: str) -> dict[str, Any]:
    cases = {c["case_id"]: c for c in iter_jsonl(root / "cases" / "canonical_seq128_cases_v10.jsonl")}
    out_root = root / "evidence" / "full_truth_bf16_v14"
    rows = []
    for cid in CASE_IDS:
        src = root / "evidence" / "full_truth_repeat_v11" / cid / "repeat_full_truth_logits.npy"
        dst_dir = out_root / cid
        dst = dst_dir / "full_truth_logits.npy"
        dst_dir.mkdir(parents=True, exist_ok=True)
        if src.exists():
            shutil.copy2(src, dst)
        logits = np.load(dst)
        case = cases.get(cid, {})
        meta = {
            "case_id": cid,
            "model_path": case.get("model_path") or "/mnt/nas/openclaw/models/dream7b-hf",
            "model_class": "AutoModel trust_remote_code DreamForCausalLM/DreamModel",
            "dtype": "torch.bfloat16",
            "device": "cpu",
            "tokenizer_path": case.get("tokenizer_path"),
            "tokenizer_manifest_sha256": case.get("tokenizer_manifest_sha256") or case.get("tokenizer_manifest_sha256_v10"),
            "model_code_hashes": {p.name: sha256_file(p) for p in sorted((root / "evidence" / "hf_remote_code_v14").glob("*")) if p.is_file()},
            "token_ids_sha256": case.get("token_ids_sha256") or sha256_jsonable(case.get("token_ids")),
            "position_ids_sha256": sha256_jsonable(case.get("position_ids")),
            "last_token_index": case.get("last_token_index", 127),
            "semantic_or_diagnostic": case.get("semantic_or_diagnostic"),
            "logits_shape": list(logits.shape),
            "top10": topk(logits, 10),
            "stats": tensor_stats(logits),
            "sha256": sha256_file(dst),
            "source_repeat_v11_sha256": sha256_file(src) if src.exists() else None,
            "v10_sha256": sha256_file(root / "evidence" / "full_truth_v10" / cid / "full_truth_logits.npy") if (root / "evidence" / "full_truth_v10" / cid / "full_truth_logits.npy").exists() else None,
        }
        meta["matches_v10_sha256"] = bool(meta["v10_sha256"] and meta["v10_sha256"] == meta["sha256"])
        write_json(dst_dir / "metadata.json", meta)
        rows.append(meta)
    report = common(root, "1410_full_truth_packaging_gate", command, [root / "evidence" / "full_truth_repeat_v11"])
    report.update({"status": "pass" if len(rows) == 3 and all(not r["stats"]["allzero"] and not r["stats"]["constant"] for r in rows) else "fail", "rows": rows})
    return save_report(root, "1410_full_truth_packaging_gate", report, "Full Truth BF16 Packaging Gate", [f"packaged rows: `{len(rows)}/3`", f"status: `{report['status']}`"])


def task1420(root: Path, command: str) -> dict[str, Any]:
    ev = root / "evidence" / "seg00_01_exact_graph_v14"
    remote = load_json(root / "evidence" / "s100p_remote_v14_reports" / "1420_1440_v14_seg00_exact_graph_position_remote.json", {})
    rows = []
    required = [
        "input_0_tokens.npy",
        "input_1_positions.npy",
        "gathernd_output_raw.bin",
        "gathernd_output_interpreted.npy",
        "mul_input.npy",
        "add_input_embedding.npy",
        "add_output_raw.npy",
        "add_output_dequant.npy",
        "metadata.json",
    ]
    for cid in CASE_IDS:
        case_dir = ev / cid
        present = {name: artifact(case_dir / name, root) for name in required}
        rows.append(
            {
                "case_id": cid,
                "all_required_visible_files_present": all(v["exists"] for v in present.values()),
                "files": present,
                "limitations": [
                    "mul_output_raw.bin and mul_output_interpreted.npy are not available from HRT dump",
                    "add_input_position.npy is not available from HRT dump",
                ],
            }
        )
    report = common(root, "1420_seg00_01_exact_intermediate_dump", command, [ev, root / "evidence" / "s100p_remote_v14_reports" / "1420_1440_v14_seg00_exact_graph_position_remote.json"])
    report.update({"remote_status": remote.get("status"), "rows": rows, "status": "pass" if all(r["all_required_visible_files_present"] for r in rows) else "partial"})
    return save_report(root, "1420_seg00_01_exact_intermediate_dump", report, "seg00_01 Exact Intermediate Dump", [f"status: `{report['status']}`", "mul_output/add_input_position: `not_dumped_by_hrt`"])


def best_scalar_fit(source: np.ndarray, target: np.ndarray) -> tuple[float, np.ndarray]:
    s = source.astype(np.float64).reshape(-1)
    t = target.astype(np.float64).reshape(-1)
    denom = float(np.dot(s, s))
    scale = float(np.dot(s, t) / denom) if denom else 0.0
    return scale, (source.astype(np.float32) * scale).astype(np.float32)


def per_channel_affine_fit(source: np.ndarray, target: np.ndarray) -> tuple[dict[str, float], np.ndarray]:
    s = source.astype(np.float32)
    t = target.astype(np.float32)
    sx = s - s.mean(axis=0, keepdims=True)
    tx = t - t.mean(axis=0, keepdims=True)
    denom = np.sum(sx * sx, axis=0, keepdims=True)
    slope = np.sum(sx * tx, axis=0, keepdims=True) / np.maximum(denom, 1e-6)
    intercept = t.mean(axis=0, keepdims=True) - slope * s.mean(axis=0, keepdims=True)
    out = (s * slope + intercept).astype(np.float32)
    return {
        "slope_mean": float(np.mean(slope)),
        "slope_std": float(np.std(slope)),
        "intercept_mean": float(np.mean(intercept)),
        "intercept_std": float(np.std(intercept)),
    }, out


def symmetric_int8_dequant(hf: np.ndarray) -> tuple[float, np.ndarray]:
    scale = float(np.max(np.abs(hf)) / 127.0) if np.max(np.abs(hf)) else 1.0
    q = np.clip(np.round(hf / scale), -127, 127).astype(np.int8)
    return scale, (q.astype(np.float32) * scale).astype(np.float32)


def task1430(root: Path, command: str) -> dict[str, Any]:
    ev = root / "evidence" / "seg00_01_exact_graph_v14"
    rows = []
    deployable_matches = []
    affine_only = []
    for cid in CASE_IDS:
        g = np.load(ev / cid / "gathernd_output_interpreted.npy").astype(np.float32)
        hf = squeeze_hidden(np.load(root / "evidence" / "seg00_01_decomposition_v13" / cid / "hf" / "token_embedding_output.npy"))
        scalar, g_scaled = best_scalar_fit(g, hf)
        aff_stats, aff = per_channel_affine_fit(g, hf)
        q_scale, hf_qdq = symmetric_int8_dequant(hf)
        variants = {
            "raw_gathernd_int8_values_vs_hf_embedding": g,
            "gathernd_best_scalar_to_hf_embedding": g_scaled,
            "hf_embedding_symmetric_int8_dequant_candidate": hf_qdq,
            "gathernd_sign_flip_best_scalar": best_scalar_fit(-g, hf)[1],
            "gathernd_byteswap_unavailable_int8": g,
            "gathernd_transpose_not_shape_compatible": g,
            "per_channel_affine_fit_diagnostic": aff,
        }
        case_rows = []
        for name, cand in variants.items():
            m = compare_arrays(hf, cand)
            row = {"case_id": cid, "variant": name, "metrics": m}
            if "best_scalar" in name:
                row["candidate_scale_factor"] = scalar
            if name == "hf_embedding_symmetric_int8_dequant_candidate":
                row["candidate_scale_factor"] = q_scale
            if name == "per_channel_affine_fit_diagnostic":
                row["fit_stats"] = aff_stats
            case_rows.append(row)
        rows.extend(case_rows)
        if case_rows:
            best = min((r for r in case_rows if r["metrics"].get("shape_match")), key=lambda r: r["metrics"].get("relative_l2", 9))
            if best["variant"] == "per_channel_affine_fit_diagnostic" and (best["metrics"].get("relative_l2") or 9) < 0.1:
                affine_only.append(cid)
            if best["variant"] != "per_channel_affine_fit_diagnostic" and (best["metrics"].get("relative_l2") or 9) < 0.1 and (best["metrics"].get("pearson_centered") or 0) > 0.95:
                deployable_matches.append(cid)
    if len(deployable_matches) == 3:
        verdict = "gathernd_matches_hf_embedding_after_known_quant"
    elif affine_only:
        verdict = "gathernd_matches_hf_embedding_only_after_unacceptable_affine_fit"
    else:
        verdict = "inconclusive_missing_quant_metadata"
    report = common(root, "1430_gathernd_embedding_quant_audit", command, [ev, root / "evidence" / "seg00_01_decomposition_v13"])
    report.update({"verdict": verdict, "rows": rows, "deployable_match_cases": deployable_matches, "affine_only_cases": affine_only, "note": "Per-channel affine fit is diagnostic and non-deployable."})
    if verdict != "gathernd_matches_hf_embedding_after_known_quant":
        report["blocking_or_failure_reasons"].append("No known GatherND quant scale/metadata maps the dumped int8 GatherND output to HF token embeddings across all cases.")
    return save_report(root, "1430_gathernd_embedding_quant_audit", report, "GatherND Embedding Quant Audit", [f"verdict: `{verdict}`", f"rows: `{len(rows)}`"])


def task1440(root: Path, command: str) -> dict[str, Any]:
    remote = load_json(root / "evidence" / "s100p_remote_v14_reports" / "1420_1440_v14_seg00_exact_graph_position_remote.json", {})
    rows = []
    max_abs = 0.0
    max_norm = 0.0
    for case in remote.get("rows", []):
        cid = case.get("case_id")
        for row in ((case.get("position_audit") or {}).get("rows") or []):
            d = row.get("delta_vs_all_zero_positions", {}).get("stats", {})
            item = {
                "case_id": cid,
                "variant": row.get("variant"),
                "delta_abs_max": row.get("delta_abs_max"),
                "delta_std": row.get("delta_std"),
                "delta_norm": row.get("delta_norm"),
                "output_stats": row.get("dequant_output", {}).get("stats"),
            }
            rows.append(item)
            if item["delta_abs_max"] is not None:
                max_abs = max(max_abs, float(item["delta_abs_max"]))
            if item["delta_norm"] is not None:
                max_norm = max(max_norm, float(item["delta_norm"]))
    verdict = "position_input_contract_suspicious" if max_abs > 0.1 else "position_input_contract_consistent"
    report = common(root, "1440_seg00_01_position_input_audit", command, [root / "evidence" / "s100p_remote_v14_reports" / "1420_1440_v14_seg00_exact_graph_position_remote.json"])
    report.update(
        {
            "verdict": verdict,
            "rows": rows,
            "max_delta_abs": max_abs,
            "max_delta_norm": max_norm,
            "hf_source_interpretation": "DreamModel.forward uses embed_tokens(input_ids), then creates rotary position embeddings for decoder layers; no learned absolute position embedding is added at the embedding boundary.",
            "source_lines": {"modeling_dream.py": [615, 665, 677, 679, 682]},
        }
    )
    if verdict != "position_input_contract_consistent":
        report["blocking_or_failure_reasons"].append("Changing _input_1 position vectors produces material seg00_01 output deltas, but HF code does not expose a learned absolute position add at this boundary.")
    return save_report(root, "1440_seg00_01_position_input_audit", report, "seg00_01 Position Input Audit", [f"verdict: `{verdict}`", f"max_delta_abs: `{max_abs}`"])


def source_excerpt(path: Path, line_numbers: list[int], context: int = 2) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    out = {}
    for ln in line_numbers:
        start = max(1, ln - context)
        end = min(len(lines), ln + context)
        out[str(ln)] = "\n".join(f"{i}: {lines[i-1]}" for i in range(start, end + 1))
    return out


def task1450(root: Path, command: str) -> dict[str, Any]:
    ev = root / "evidence" / "seg00_01_exact_graph_v14"
    source = root / "evidence" / "hf_remote_code_v14" / "modeling_dream.py"
    candidates = ["token_embedding_output", "layer0_pre_attention_norm_output", "layer0_final_output"]
    rows = []
    for cid in CASE_IDS:
        bpu = np.load(ev / cid / "add_output_dequant.npy").astype(np.float32)
        gather = np.load(ev / cid / "gathernd_output_interpreted.npy").astype(np.float32)
        for cand in candidates:
            hp = root / "evidence" / "seg00_01_decomposition_v13" / cid / "hf" / f"{cand}.npy"
            if not hp.exists():
                continue
            hf = squeeze_hidden(np.load(hp))
            rows.append({"case_id": cid, "bpu_tensor": "add_output_dequant", "hf_candidate": cand, "metrics": compare_arrays(hf, bpu)})
            if cand == "token_embedding_output":
                rows.append({"case_id": cid, "bpu_tensor": "gathernd_output_interpreted_raw_int8", "hf_candidate": cand, "metrics": compare_arrays(hf, gather)})
    exact_buildable = False
    verdict = "exact_comparator_unresolved_missing_mul_position_constants"
    report = common(root, "1450_seg00_01_hf_equivalent_comparator", command, [source, ev])
    report.update(
        {
            "verdict": verdict,
            "exact_comparator_buildable": exact_buildable,
            "hf_boundary_interpretation": {
                "embedding": "self.embed_tokens(input_ids)",
                "position": "position_embeddings = self.rotary_emb(hidden_states, position_ids); consumed inside decoder attention, not a learned absolute add to embeddings",
                "seg00_01_visible_graph": "GatherND(token embedding-like int8 table) plus hidden hbir.mul/hbir.add path to int16 output",
            },
            "source_hashes": {p.name: sha256_file(p) for p in sorted((root / "evidence" / "hf_remote_code_v14").glob("*")) if p.is_file()},
            "source_excerpts": source_excerpt(source, [615, 665, 677, 679, 682, 809]) if source.exists() else {},
            "comparison_rows": rows,
        }
    )
    report["blocking_or_failure_reasons"].append("HRT did not dump mul_output or separate add_input_position/constants, so the exact HF equivalent of GatherND + position-derived term cannot be reconstructed from available evidence.")
    return save_report(root, "1450_seg00_01_hf_equivalent_comparator", report, "seg00_01 HF Equivalent Comparator", [f"verdict: `{verdict}`", f"comparison_rows: `{len(rows)}`"])


def task1460(root: Path, command: str) -> dict[str, Any]:
    search = load_json(root / "evidence" / "compiler_graph_artifact_search_v14" / "search_results.json", {"rows": []})
    rows = search.get("rows", [])
    hbo = [r for r in rows if str(r.get("path", "")).endswith(".hbo")]
    seq128_hbo = [r for r in hbo if "seq128" in str(r.get("path", "")).lower()]
    seq16_hbo = [r for r in hbo if "seq16" in str(r.get("path", "")).lower()]
    seg00_related = [r for r in rows if "seg00" in str(r.get("path", "")).lower() or "segment_0_1" in str(r.get("path", "")).lower()]
    verdict = "seq16_hbo_available_seq128_b1_source_graph_missing"
    if seq128_hbo:
        verdict = "seq128_hbo_available_needs_operator_extraction"
    report = common(root, "1460_compiler_graph_artifact_search", command, [root / "evidence" / "compiler_graph_artifact_search_v14" / "search_results.json"])
    report.update(
        {
            "verdict": verdict,
            "result_count": search.get("result_count"),
            "hbo_count": len(hbo),
            "seq16_hbo_count": len(seq16_hbo),
            "seq128_hbo_count": len(seq128_hbo),
            "seg00_related_count": len(seg00_related),
            "seq128_hbo_examples": seq128_hbo[:20],
            "seq16_hbo_examples": seq16_hbo[:20],
            "seg00_related_examples": seg00_related[:80],
        }
    )
    if not seq128_hbo:
        report["blocking_or_failure_reasons"].append("No seq128 B=1 seg00_01 HBO/source graph was found; seq16 HBO artifacts are not sufficient for corrected v14 recompile.")
    vendor = root / "vendor_request" / "SEG00_01_COMPILER_ARTIFACT_REQUEST.md"
    write_text(
        vendor,
        "\n".join(
            [
                "# SEG00_01 Compiler Artifact Request",
                "",
                "Please provide the exact artifacts required to close Dream7B seq128 B=1 `seg00_01` correctness:",
                "",
                "- source ONNX/HBIR/HBO for `seg00_01` used to build the tested HBM",
                "- quant scales and zero points for GatherND output and final add output",
                "- constants and dynamic ranges used by `hbir.mul_id_63`",
                "- separate tensors or formulas for `hbir.add_id_137` input-0 and input-1",
                "- exact op list, shapes, layout, and split metadata",
                "- calibration dataset, calibration command, and dynamic range tables",
                "- compiler/HBDK/HBRT versions and export command",
                "- mapping from HF source functions/layers to each exported segment",
                "",
                "Current limitation: HRT dump shows View, GatherND, BPU hbir.mul, and BPU hbir.add, but does not expose `mul_output` or `add_input_position`.",
            ]
        )
        + "\n",
    )
    report["vendor_request"] = artifact(vendor, root)
    return save_report(root, "1460_compiler_graph_artifact_search", report, "Compiler Graph Artifact Search", [f"verdict: `{verdict}`", f"hbo_count: `{len(hbo)}`", f"seq128_hbo_count: `{len(seq128_hbo)}`"])


def task1470(root: Path, command: str, r1460: dict[str, Any]) -> dict[str, Any]:
    verdict = "not_run_compiler_unavailable"
    if r1460.get("seq128_hbo_count"):
        verdict = "not_run_operator_extraction_pipeline_unavailable"
    report = common(root, "1470_seg00_01_corrected_recompile_candidates", command, [root / "reports" / "1460_compiler_graph_artifact_search.json"])
    report.update({"verdict": verdict, "executed_candidates": [], "reason": "No accessible seq128 B=1 compiler/export pipeline plus source graph and quant metadata was available for safe corrected recompile."})
    report["blocking_or_failure_reasons"].append("Corrected/recompiled seg00_01 candidates require compiler/vendor artifacts; no offline candidate was fabricated.")
    return save_report(root, "1470_seg00_01_corrected_recompile_candidates", report, "seg00_01 Corrected Recompile Candidates", [f"verdict: `{verdict}`"])


def task1480(root: Path, command: str) -> dict[str, Any]:
    remote = load_json(root / "evidence" / "bpu_island_diagnostic_calibration_v14" / "1480_v14_bpu_island_diagnostic_calibration_remote.json", None)
    if remote is None:
        remote = load_json(root / "evidence" / "s100p_remote_v14_reports" / "1480_v14_bpu_island_diagnostic_calibration_remote.json", None)
    if remote is None:
        remote = {"status": "remote_running_or_missing", "rows": [], "errors": []}
    rows = remote.get("rows", [])
    summary: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = f"{row.get('island')}::{row.get('variant')}"
        m = row.get("final_metrics") or {}
        s = summary.setdefault(key, {"rows": 0, "strict_logits_valid_rows": 0, "top1_agreement_rows": 0, "deployable": row.get("deployable")})
        s["rows"] += 1
        s["strict_logits_valid_rows"] += int(strict_logits_valid(m))
        s["top1_agreement_rows"] += int(bool(m.get("top1_agreement")))
    deployable_pass = [k for k, v in summary.items() if v.get("deployable") and v.get("rows") == 3 and v.get("strict_logits_valid_rows") == 3]
    diagnostic_pass = [k for k, v in summary.items() if not v.get("deployable") and v.get("rows") == 3 and v.get("strict_logits_valid_rows") == 3]
    if deployable_pass:
        verdict = "deployable_known_correction_passed_logits"
    elif diagnostic_pass:
        verdict = "diagnostic_fit_passed_non_deployable"
    elif rows:
        verdict = "no_calibration_variant_passed_strict_logits"
    elif remote.get("status") in {"model_loaded", "running"}:
        verdict = "runtime_timeout_no_rows_after_model_load"
    else:
        verdict = remote.get("status") or "remote_running_or_missing"
    report = common(root, "1480_bpu_island_diagnostic_calibration", command, [root / "evidence" / "bpu_island_diagnostic_calibration_v14", root / "evidence" / "s100p_remote_v14_reports"])
    report.update({"verdict": verdict, "remote_status": remote.get("status"), "rows": len(rows), "expected_rows": remote.get("expected_rows"), "errors": remote.get("errors", []), "summary": summary, "deployable_pass": deployable_pass, "diagnostic_pass": diagnostic_pass})
    if not deployable_pass:
        report["blocking_or_failure_reasons"].append("No deployable known-scale/no-fit early BPU island calibration passed strict logits validity across all three cases.")
    if verdict == "runtime_timeout_no_rows_after_model_load":
        report["blocking_or_failure_reasons"].append("The remote HF suffix calibration attempt loaded the model and started zeros island=[1], but produced no result rows before manual stop; v13 island suffix timing indicates the full 60-row v14 sweep is not practical in this runtime.")
    return save_report(root, "1480_bpu_island_diagnostic_calibration", report, "BPU Island Diagnostic Calibration", [f"verdict: `{verdict}`", f"rows: `{len(rows)}/{remote.get('expected_rows')}`"])


def task1490(root: Path, command: str) -> dict[str, Any]:
    log = root / "evidence" / "gguf_f16_reference_v14" / "gguf_f16_logits_runner_probe.log"
    text = log.read_text(encoding="utf-8", errors="ignore") if log.exists() else ""
    gguf_lines = [line.strip() for line in text.splitlines() if ".gguf" in line.lower()]
    f16 = [x for x in gguf_lines if "f16" in x.lower()]
    q4km = [x for x in gguf_lines if "q4km" in x.lower() or "q4_k_m" in x.lower()]
    historical = root / "evidence" / "gguf_f16_reference_v14" / "historical_q4km_control"
    hist_rows = [artifact(p, root) for p in sorted(historical.glob("*")) if p.is_file()]
    verdict = "gguf_f16_blocked_no_artifact"
    if f16:
        verdict = "gguf_f16_artifact_found_logits_runner_still_unverified"
    report = common(root, "1490_gguf_f16_logits_runner_closure", command, [log, historical])
    report.update(
        {
            "verdict": verdict,
            "gguf_artifacts": {"f16": f16, "q4_k_m": q4km, "all_probe_lines": gguf_lines},
            "diffuse_cli_help_status": "tokens_supported_generation_style_cli_no_logits_only_option",
            "historical_q4km_control": hist_rows,
            "truth_boundary": "Q4_K_M remains a deployment-control reference, not BF16 truth.",
        }
    )
    report["blocking_or_failure_reasons"].append("No GGUF F16 artifact or logits-only runner for all three canonical cases is available in v14.")
    return save_report(root, "1490_gguf_f16_logits_runner_closure", report, "GGUF F16 Logits Runner Closure", [f"verdict: `{verdict}`", f"q4_k_m_probe_lines: `{len(q4km)}`"])


def write_final_docs(root: Path, command: str, reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    r1480 = reports["1480"]
    if r1480.get("deployable_pass"):
        verdict = "D_bpu_island_candidate_logits_validated_generation_pending"
    else:
        verdict = "B_seg00_01_exact_comparator_still_unresolved_compiler_artifacts_required"
    gate = {
        "schema_version": "dream7b_s100p_gate_packet_v14",
        "created_at_utc": now(),
        "verdict": verdict,
        "generation_quality_run": False,
        "product_routes_18888_18889_touched": False,
        "dream7b_frontend_openclaw_traffic_touched": False,
        "current_full_bpu_path": "falsified_against_HF_PyTorch_BF16_logits_truth",
        "v13_verdict": reports["1400"].get("v13_gate_packet", {}).get("verdict"),
        "seg00_01": {
            "exact_dump": reports["1420"].get("status"),
            "gathernd_verdict": reports["1430"].get("verdict"),
            "position_verdict": reports["1440"].get("verdict"),
            "hf_comparator_verdict": reports["1450"].get("verdict"),
            "compiler_artifacts": reports["1460"].get("verdict"),
            "corrected_recompile": reports["1470"].get("verdict"),
        },
        "bpu_island_diagnostic_calibration": {"verdict": r1480.get("verdict"), "deployable_pass": r1480.get("deployable_pass"), "diagnostic_pass": r1480.get("diagnostic_pass")},
        "gguf_reference": reports["1490"].get("verdict"),
        "bf16_truth_hashes": {cid: artifact(root / "evidence" / "full_truth_bf16_v14" / cid / "full_truth_logits.npy", root) for cid in CASE_IDS},
        "claim_boundary": "The tested Dream7B S100P full-BPU and hybrid BPU-island routes remain logits-invalid. v14 closes evidence around seg00_01 but cannot build an exact comparator/recompile without compiler source graph and quant metadata.",
        "commands": [command],
        "strict_thresholds": STRICT,
    }
    write_json(root / "01_final_evidence" / "dream7b_s100p_gate_packet_v14.json", gate)
    write_text(
        root / "01_final_evidence" / "dream7b_s100p_gate_packet_v14.md",
        "\n".join(
            [
                "# Dream7B S100P Gate Packet v14",
                "",
                f"- verdict: `{verdict}`",
                "- generation_quality_run: `false`",
                "- product_routes_18888_18889_touched: `false`",
                "- dream7b_frontend_openclaw_traffic_touched: `false`",
                "- full-BPU path remains falsified against HF/PyTorch BF16 logits truth.",
                "- v14 identifies missing exact `seg00_01` compiler/quant metadata as the remaining closure blocker.",
            ]
        )
        + "\n",
    )
    write_text(
        root / "reports" / "ROOT_CAUSE_SUMMARY_V14.md",
        "# Root Cause Summary v14\n\nv14 strengthens the `seg00_01` root-cause locus with exact HRT-visible tensors: token ids, position ids, GatherND output, add input-0, and add output. The remaining unresolved part is the hidden `hbir.mul` output and add input-1/constant path. HF source shows token embedding followed by RoPE shared inside decoder layers, not a learned absolute-position add at the embedding boundary. Therefore the current evidence supports a `seg00_01` graph/input/quant contract problem, but exact operator-level attribution still requires compiler/HBO source graph and quant metadata.\n",
    )
    write_text(
        root / "reports" / "CANDIDATE_DEPLOYMENT_ROUTES_V14.md",
        "# Candidate Deployment Routes v14\n\nNo route is deployable on logits evidence yet. Candidate A is a corrected `seg00_01` re-export/recompile using vendor/compiler source graph and verified quant scales. Candidate B is a CPU/HF prefix plus BPU island plus HF suffix route only if a deployable no-fit or known-scale island correction passes strict logits validity. Candidate C is GGUF F16/logits reference, currently blocked by missing F16 artifact and logits-only runner. Generation remains locked.\n",
    )
    write_text(
        root / "reports" / "PAPER_EVIDENCE_DOSSIER_V14.md",
        "# Paper Evidence Dossier v14\n\nThe paper-safe result is negative for the tested full-BPU and hybrid BPU-island paths, not a general impossibility claim for Dream7B on S100P. BF16 full-truth arrays are packaged as standalone v14 evidence. The strongest root-cause locus remains `seg00_01`; HRT-visible intermediate dumps show the embedding-like GatherND path and position-sensitive BPU add output, while missing compiler source graph prevents final operator-level closure. No generation quality and no 18888/18889 product route tests were run.\n",
    )
    return gate


def copy_if_exists(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)


def package_v14(root: Path, command: str) -> dict[str, Any]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    staging = root / "tmp" / f"dream7b_s100p_v14_for_gptpro_{stamp}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    report_stems = [
        "1400_v14_baseline_lock",
        "1410_full_truth_packaging_gate",
        "1420_seg00_01_exact_intermediate_dump",
        "1430_gathernd_embedding_quant_audit",
        "1440_seg00_01_position_input_audit",
        "1450_seg00_01_hf_equivalent_comparator",
        "1460_compiler_graph_artifact_search",
        "1470_seg00_01_corrected_recompile_candidates",
        "1480_bpu_island_diagnostic_calibration",
        "1490_gguf_f16_logits_runner_closure",
        "ROOT_CAUSE_SUMMARY_V14",
        "CANDIDATE_DEPLOYMENT_ROUTES_V14",
        "PAPER_EVIDENCE_DOSSIER_V14",
    ]
    for stem in report_stems:
        for suffix in [".json", ".md"]:
            copy_if_exists(root / "reports" / f"{stem}{suffix}", staging / "reports" / f"{stem}{suffix}")
    for p in (root / "01_final_evidence").glob("*v14*"):
        copy_if_exists(p, staging / "01_final_evidence" / p.name)
    for sub in [
        "full_truth_bf16_v14",
        "seg00_01_exact_graph_v14",
        "hf_remote_code_v14",
        "compiler_graph_artifact_search_v14",
        "gguf_f16_reference_v14",
        "bpu_island_diagnostic_calibration_v14",
        "s100p_remote_v14_reports",
    ]:
        copy_if_exists(root / "evidence" / sub, staging / "evidence" / sub)
    copy_if_exists(root / "vendor_request" / "SEG00_01_COMPILER_ARTIFACT_REQUEST.md", staging / "vendor_request" / "SEG00_01_COMPILER_ARTIFACT_REQUEST.md")
    for tool in ["build_v14_research_thread.py", "run_v14_seg00_exact_graph_and_position.py", "run_v14_bpu_island_diagnostic_calibration.py"]:
        copy_if_exists(root / "tools" / tool, staging / "tools" / tool)
    inside_1500 = {
        "schema_version": "dream7b_s100p_v14_1500_final_v14_gate_packet_and_package",
        "created_at_utc": now(),
        "inside_package_report": True,
        "note": "This in-package 1500 report intentionally omits the enclosing zip SHA256 to avoid a circular self-reference. The workspace report contains the final zip hash.",
        "generation_quality_run": False,
        "product_routes_18888_18889_touched": False,
        "dream7b_frontend_openclaw_traffic_touched": False,
    }
    write_json(staging / "reports" / "1500_final_v14_gate_packet_and_package.json", inside_1500)
    write_text(
        staging / "reports" / "1500_final_v14_gate_packet_and_package.md",
        "# Final v14 Gate Packet and Package\n\nThis in-package report omits the enclosing zip SHA256 to avoid circular self-reference. See the workspace copy for the final zip hash.\n",
    )
    write_text(staging / "README.md", "Dream7B/S100P v14 evidence package. No generation quality and no 18888/18889 route interaction.\n")
    files = []
    for p in sorted(staging.rglob("*")):
        if p.is_file():
            files.append({"path": rel(p, staging), "size_bytes": p.stat().st_size, "sha256": sha256_file(p)})
    write_json(staging / "MANIFEST.json", {"schema_version": "dream7b_s100p_v14_manifest", "created_at_utc": now(), "file_count": len(files), "files": files})
    write_text(staging / "SHA256SUMS.txt", "\n".join(f"{f['sha256']}  {f['path']}" for f in files) + "\n")
    out = root / "evidence_for_gptpro" / f"dream7b_s100p_v14_for_gptpro_{stamp}.zip"
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
    report = common(root, "1500_final_v14_gate_packet_and_package", command, [out])
    report.update({"zip_path": rel(out, root), "zip_sha256": zip_sha, "zip_sha256_txt": rel(out.with_suffix(out.suffix + ".sha256.txt"), root), "zip_size_bytes": out.stat().st_size, "zip_member_count": count, "zip_testzip_bad_member": bad, "manifest_file_count": len(files)})
    save_report(root, "1500_final_v14_gate_packet_and_package", report, "Final v14 Gate Packet and Package", [f"zip_path: `{report['zip_path']}`", f"zip_sha256: `{report['zip_sha256']}`"])
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    command = " ".join([sys.executable, *sys.argv])
    reports: dict[str, dict[str, Any]] = {}
    reports["1400"] = task1400(root, command)
    reports["1410"] = task1410(root, command)
    reports["1420"] = task1420(root, command)
    reports["1430"] = task1430(root, command)
    reports["1440"] = task1440(root, command)
    reports["1450"] = task1450(root, command)
    reports["1460"] = task1460(root, command)
    reports["1470"] = task1470(root, command, reports["1460"])
    reports["1480"] = task1480(root, command)
    reports["1490"] = task1490(root, command)
    gate = write_final_docs(root, command, reports)
    package = package_v14(root, command)
    print(json.dumps({"verdict": gate["verdict"], "zip": package["zip_path"], "zip_sha256": package["zip_sha256"], "seg00_comparator": reports["1450"]["verdict"], "island_calibration": reports["1480"]["verdict"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
