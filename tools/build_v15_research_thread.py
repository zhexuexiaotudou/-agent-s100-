#!/usr/bin/env python3
"""Build Dream7B/S100P v15 reports and GPT Pro evidence package."""
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


CASE_IDS = ["zeros", "ramp", "short_chinese_prompt_padded"]
SAFETY = {
    "generation_quality_run": False,
    "product_routes_18888_18889_touched": False,
    "dream7b_frontend_openclaw_traffic_touched": False,
}
STRICT = {"relative_l2_max": 0.1, "pearson_min": 0.95, "cosine_min": 0.95}


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


def git_status(root: Path) -> dict[str, Any]:
    try:
        p = subprocess.run(["git", "status", "--short"], cwd=root, text=True, capture_output=True, timeout=10)
        return {"returncode": p.returncode, "stdout": p.stdout.strip(), "stderr": p.stderr.strip()}
    except Exception as exc:
        return {"status": f"{type(exc).__name__}:{exc}"}


def common(root: Path, stem: str, command: str, inputs: list[Path]) -> dict[str, Any]:
    return {
        "schema_version": f"dream7b_s100p_v15_{stem}",
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


def compare_arrays(ref: np.ndarray, cand: np.ndarray, topk: int = 5) -> dict[str, Any]:
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
        "candidate_stats": tensor_stats(c.astype(np.float32)),
        "reference_stats": tensor_stats(r.astype(np.float32)),
    }


def strict_pass(m: dict[str, Any]) -> bool:
    return bool(
        m.get("shape_match")
        and (m.get("relative_l2") is not None and float(m["relative_l2"]) <= STRICT["relative_l2_max"])
        and (m.get("pearson_centered") is not None and float(m["pearson_centered"]) >= STRICT["pearson_min"])
        and (m.get("cosine") is not None and float(m["cosine"]) >= STRICT["cosine_min"])
    )


def squeeze_hidden(x: np.ndarray) -> np.ndarray:
    arr = np.asarray(x)
    if arr.ndim == 3 and arr.shape[0] == 1:
        arr = arr[0]
    return arr.astype(np.float32)


def parse_zip_manifest(zip_path: Path) -> dict[str, Any]:
    out = {"path": str(zip_path), "exists": zip_path.exists()}
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
        missing, bad_size, bad_hash = [], [], []
        for item in mf.get("files", []):
            p = item["path"]
            if p not in names:
                missing.append(p)
                continue
            data = zf.read(p)
            if len(data) != item.get("size_bytes"):
                bad_size.append(p)
            if hashlib.sha256(data).hexdigest() != item.get("sha256"):
                bad_hash.append(p)
        out.update({"manifest_missing": missing, "manifest_bad_size": bad_size, "manifest_bad_sha256": bad_hash})
    return out


def task1600(root: Path, command: str) -> dict[str, Any]:
    zip_path = root / "evidence_for_gptpro" / "dream7b_s100p_v14_for_gptpro_20260703_141021.zip"
    gate = load_json(root / "01_final_evidence" / "dream7b_s100p_gate_packet_v14.json", {})
    required = [
        "1420_seg00_01_exact_intermediate_dump",
        "1430_gathernd_embedding_quant_audit",
        "1440_seg00_01_position_input_audit",
        "1450_seg00_01_hf_equivalent_comparator",
        "1460_compiler_graph_artifact_search",
    ]
    report = common(root, "1600_v15_baseline_lock", command, [zip_path, root / "01_final_evidence" / "dream7b_s100p_gate_packet_v14.json"])
    z = parse_zip_manifest(zip_path)
    report.update(
        {
            "v14_zip": z,
            "v14_gate_packet": gate,
            "required_reports": {name: artifact(root / "reports" / f"{name}.json", root) for name in required},
            "baseline_facts": [
                "full-BPU path has been falsified against HF/PyTorch BF16 logits truth",
                "v14 narrowed the strongest root-cause locus to seg00_01 or its input/embedding/position/quant graph contract",
                "v14 still lacks hbir.mul output, add input-1, source graph, and quant table",
                "generation/product routes remain locked",
            ],
        }
    )
    if not (z.get("exists") and z.get("testzip_bad_member") is None and not z.get("manifest_bad_sha256")):
        report["blocking_or_failure_reasons"].append("v14 package validation is not clean")
    return save_report(root, "1600_v15_baseline_lock", report, "v15 Baseline Lock", [f"v14 verdict: `{gate.get('verdict')}`", f"v14 zip sha256: `{z.get('sha256')}`"])


def task1610(root: Path, command: str) -> dict[str, Any]:
    search = load_json(root / "evidence" / "compiler_source_graph_v15" / "targeted_search_results.json", {"rows": []})
    rows = search.get("rows", [])
    seq128_hbm = [r for r in rows if "seq128" in str(r.get("path", "")).lower() and str(r.get("path", "")).endswith(".hbm")]
    seq128_source = [r for r in rows if "seq128" in str(r.get("path", "")).lower() and str(r.get("suffix")) in {".hbo", ".onnx", ".mlir", ".bc"}]
    quant_meta = [r for r in rows if any(k in str(r.get("path", "")).lower() for k in ["quant", "calib", "scale", "range"]) and "seq128" in str(r.get("path", "")).lower()]
    verdict = "compiler_artifacts_missing_vendor_required" if not seq128_source and not quant_meta else "partial_artifacts_found_not_enough_for_exact_repair"
    report = common(root, "1610_seg00_01_compiler_source_graph_acquisition", command, [root / "evidence" / "compiler_source_graph_v15" / "targeted_search_results.json"])
    report.update(
        {
            "verdict": verdict,
            "result_count": search.get("result_count"),
            "seq128_hbm_count": len(seq128_hbm),
            "seq128_source_graph_count": len(seq128_source),
            "seq128_quant_metadata_count": len(quant_meta),
            "seq128_hbm_examples": seq128_hbm[:30],
            "seq128_source_graph_examples": seq128_source[:30],
            "seq128_quant_metadata_examples": quant_meta[:30],
            "historical_seq16_only_note": "seq16 HBO artifacts from v14/v15 searches are historical references and are not acceptable for exact seq128 B=1 repair.",
        }
    )
    vendor = root / "vendor_request" / "SEG00_01_COMPILER_ARTIFACT_REQUEST_V15.md"
    write_text(
        vendor,
        "# SEG00_01 Compiler Artifact Request V15\n\n"
        "Required for Dream7B seq128 B=1 tested `seg00_01` HBM closure:\n\n"
        "- source ONNX/HBIR/HBO matching `/mnt/nas/openclaw/models/dream7b-hbm/seq128-b1-lmheadq16-lasttoken/seg00_01/dream7b_segment_0_1_seq128_q8.hbm`\n"
        "- HBDK/HBRT compiler metadata, export command, compiler version, and split metadata\n"
        "- quantization table: GatherND output scale/zero point/layout, add output scale/zero point/layout\n"
        "- calibration dataset and dynamic ranges for embedding table, `hbir.mul_id_63`, and `hbir.add_id_137`\n"
        "- constants/formulas for `hbir.mul_id_63`, `hbir.add_id_137` input-0/input-1, and qnt.const_fake_quant nodes\n"
        "- exact op list with tensor names, dtypes, shapes, scales, zero points, and layouts\n",
    )
    report["vendor_request"] = artifact(vendor, root)
    if verdict == "compiler_artifacts_missing_vendor_required":
        report["blocking_or_failure_reasons"].append("Only seq128 HBM runtime artifacts were found; no matching source graph/HBO/quant metadata was found for exact repair.")
    return save_report(root, "1610_seg00_01_compiler_source_graph_acquisition", report, "seg00_01 Compiler Source Graph Acquisition", [f"verdict: `{verdict}`", f"seq128_hbm_count: `{len(seq128_hbm)}`", f"seq128_source_graph_count: `{len(seq128_source)}`"])


def task1620(root: Path, command: str) -> dict[str, Any]:
    ev = root / "evidence" / "seg00_01_mul_add_input1_v15"
    manifest = load_json(ev / "WINDOWS_SAFE_MANIFEST.json", {"files": []})
    files = manifest.get("files", [])
    names = [f.get("original_path", "") for f in files]
    mul_output = [n for n in names if "hbir.mul" in n and "output" in n]
    add_input1 = [n for n in names if "hbir.add" in n and ("input-1" in n or "input_1" in n)]
    add_input0 = [n for n in names if "hbir.add" in n and "input-0" in n]
    add_output = [n for n in names if "hbir.add" in n and "output" in n]
    report = common(root, "1620_hbir_mul_add_input1_recovery", command, [ev])
    verdict = "runtime_dump_does_not_expose_mul_output_or_add_input1" if not mul_output and not add_input1 else "mul_add_input1_partially_recovered"
    report.update(
        {
            "verdict": verdict,
            "hrt_capability": "hrt_model_exec supports dump_intermediate plus bin/txt/npy dump formats, but no public node-select or deeper BPU internal tensor flag was found.",
            "safe_manifest": manifest,
            "recovered": {
                "mul_input": [n for n in names if "hbir.mul" in n and "input" in n],
                "mul_output": mul_output,
                "add_input0": add_input0,
                "add_input1": add_input1,
                "add_output": add_output,
            },
            "inference_status": "position-variant finite difference remains inference only; not original tensor evidence.",
        }
    )
    if verdict != "mul_add_input1_partially_recovered":
        report["blocking_or_failure_reasons"].append("HRT dump variants still expose only hbir.mul input and hbir.add input-0/output; hbir.mul output and add input-1 remain vendor/runtime blockers.")
    return save_report(root, "1620_hbir_mul_add_input1_recovery", report, "hbir.mul and add input-1 Recovery", [f"verdict: `{verdict}`", f"file_count: `{manifest.get('file_count')}`"])


def task1630(root: Path, command: str) -> dict[str, Any]:
    v14 = load_json(root / "reports" / "1430_gathernd_embedding_quant_audit.json", {"rows": []})
    search = load_json(root / "evidence" / "compiler_source_graph_v15" / "targeted_search_results.json", {"rows": []})
    quant_candidates = [r for r in search.get("rows", []) if any(k in str(r.get("path", "")).lower() for k in ["quant", "calib", "scale", "range", "hbir"]) and "seq128" in str(r.get("path", "")).lower()]
    rows = v14.get("rows", [])
    by_variant: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_variant.setdefault(row.get("variant", ""), []).append(row.get("metrics", {}))
    summary = {}
    for variant, metrics in by_variant.items():
        vals = [m for m in metrics if m.get("shape_match")]
        summary[variant] = {
            "rows": len(vals),
            "strict_rows": sum(1 for m in vals if strict_pass(m)),
            "median_relative_l2": float(np.median([m["relative_l2"] for m in vals if m.get("relative_l2") is not None])) if vals else None,
            "mean_pearson": float(np.mean([m["pearson_centered"] for m in vals if m.get("pearson_centered") is not None])) if vals else None,
        }
    official_available = bool(quant_candidates)
    verdict = "official_scale_missing_reexport_recalibration_required" if not official_available else "official_metadata_candidates_found_not_closed"
    report = common(root, "1630_gathernd_official_quant_scale_closure", command, [root / "reports" / "1430_gathernd_embedding_quant_audit.json", root / "evidence" / "compiler_source_graph_v15" / "targeted_search_results.json"])
    report.update(
        {
            "verdict": verdict,
            "official_scale_available": official_available,
            "quant_metadata_candidates": quant_candidates[:30],
            "variant_summary": summary,
            "deployable_known_scale": [],
            "diagnostic_only_variants": ["gathernd_best_scalar_to_hf_embedding", "per_channel_affine_fit_diagnostic", "hf_embedding_symmetric_int8_dequant_candidate"],
        }
    )
    report["blocking_or_failure_reasons"].append("No official GatherND output scale/zero point was found for the tested seq128 B=1 artifact; diagnostic fits are not deployable repairs.")
    return save_report(root, "1630_gathernd_official_quant_scale_closure", report, "GatherND Official Quant Scale Closure", [f"verdict: `{verdict}`", f"official_scale_available: `{official_available}`"])


def position_variant_comparisons(root: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    ev = root / "evidence" / "seg00_01_exact_graph_v14"
    candidates = {
        "token_embedding_output": "token_embedding_output.npy",
        "layer0_pre_attention_norm_output": "layer0_pre_attention_norm_output.npy",
        "layer0_final_output": "layer0_final_output.npy",
    }
    for cid in CASE_IDS:
        rows = []
        vroot = ev / cid / "position_variants"
        if not vroot.exists():
            continue
        for variant_dir in sorted(p for p in vroot.iterdir() if p.is_dir()):
            cand_path = variant_dir / "dequant_output.npy"
            if not cand_path.exists():
                continue
            bpu = np.load(cand_path).astype(np.float32)
            for hname, fname in candidates.items():
                hp = root / "evidence" / "seg00_01_decomposition_v13" / cid / "hf" / fname
                if hp.exists():
                    rows.append({"case_id": cid, "position_variant": variant_dir.name, "hf_candidate": hname, "metrics": compare_arrays(squeeze_hidden(np.load(hp)), bpu)})
        valid = [r for r in rows if r["metrics"].get("shape_match")]
        out[cid] = {
            "rows": rows,
            "best": min(valid, key=lambda r: r["metrics"].get("relative_l2", 9)) if valid else None,
        }
    return out


def task1640(root: Path, command: str) -> dict[str, Any]:
    v14 = load_json(root / "reports" / "1440_seg00_01_position_input_audit.json", {})
    comp = position_variant_comparisons(root)
    verdict = "position_input_contract_fault_suspected"
    report = common(root, "1640_position_contract_closure", command, [root / "reports" / "1440_seg00_01_position_input_audit.json", root / "evidence" / "hf_remote_code_v14" / "modeling_dream.py"])
    report.update(
        {
            "verdict": verdict,
            "hf_source_interpretation": v14.get("hf_source_interpretation"),
            "hf_source_lines": v14.get("source_lines"),
            "position_variant_audit": {
                "max_delta_abs": v14.get("max_delta_abs"),
                "max_delta_norm": v14.get("max_delta_norm"),
                "rows": v14.get("rows", []),
            },
            "position_variant_comparisons_to_hf_candidates": comp,
            "all_zero_position_note": "all-zero position changes the boundary for some cases but does not constitute a repair without an exact comparator and logits gate.",
        }
    )
    report["blocking_or_failure_reasons"].append("HF source has no learned absolute embedding add at this boundary, while BPU seg00_01 output is position-sensitive; source graph is required to prove legality or fix export/input contract.")
    return save_report(root, "1640_position_contract_closure", report, "Position Contract Closure", [f"verdict: `{verdict}`", f"max_delta_abs: `{v14.get('max_delta_abs')}`"])


def top_errors(ref: np.ndarray, cand: np.ndarray, k: int = 10) -> list[dict[str, Any]]:
    r = np.asarray(ref, dtype=np.float64).reshape(-1)
    c = np.asarray(cand, dtype=np.float64).reshape(-1)
    idx = np.argsort(np.abs(r - c))[-k:][::-1]
    return [{"flat_index": int(i), "reference": float(r[i]), "candidate": float(c[i]), "abs_error": float(abs(r[i] - c[i]))} for i in idx]


def task1650(root: Path, command: str) -> dict[str, Any]:
    rows = []
    for cid in CASE_IDS:
        bpu = np.load(root / "evidence" / "seg00_01_exact_graph_v14" / cid / "add_output_dequant.npy").astype(np.float32)
        for hname in ["token_embedding_output", "layer0_pre_attention_norm_output", "layer0_final_output"]:
            hp = root / "evidence" / "seg00_01_decomposition_v13" / cid / "hf" / f"{hname}.npy"
            if not hp.exists():
                continue
            hf = squeeze_hidden(np.load(hp))
            rows.append({"case_id": cid, "candidate": "S100P_seg00_01_official_dequant", "hf_candidate": hname, "metrics": compare_arrays(hf, bpu), "top_hidden_errors": top_errors(hf, bpu, 10)})
    verdict = "exact_comparator_blocked_missing_mul_add_input1_source_graph_quant_table"
    report = common(root, "1650_exact_seg00_01_comparator", command, [root / "evidence" / "seg00_01_exact_graph_v14", root / "evidence" / "seg00_01_mul_add_input1_v15"])
    report.update(
        {
            "verdict": verdict,
            "exact_comparator_built": False,
            "available_surrogate_comparisons": rows,
            "missing_tensors_and_metadata": [
                "hbir.mul_id_63 output",
                "hbir.add_id_137 input-1",
                "qnt.const_fake_quant/GatherND official scale and zero point",
                "seq128 B=1 source graph/HBIR/HBO",
                "calibration dynamic ranges and layout metadata",
            ],
        }
    )
    report["blocking_or_failure_reasons"].append("No target-fitted affine or inferred finite-difference term was used as exact comparator; exact comparator remains blocked by missing artifacts.")
    return save_report(root, "1650_exact_seg00_01_comparator", report, "Exact seg00_01 Comparator", [f"verdict: `{verdict}`", f"surrogate_rows: `{len(rows)}`"])


def task1660(root: Path, command: str) -> dict[str, Any]:
    ev = root / "evidence" / "corrected_seg00_01_candidate_v15"
    ev.mkdir(parents=True, exist_ok=True)
    write_json(ev / "not_run_reason.json", {"reason": "No deployable known-scale/position/source-graph correction was found; corrected candidate was not triggered.", "safety": SAFETY})
    verdict = "not_run_no_justified_correction"
    report = common(root, "1660_corrected_seg00_01_candidate", command, [root / "reports" / "1610_seg00_01_compiler_source_graph_acquisition.json", root / "reports" / "1630_gathernd_official_quant_scale_closure.json"])
    report.update({"verdict": verdict, "trigger_condition_met": False, "executed_candidates": [], "evidence_root": rel(ev, root)})
    report["blocking_or_failure_reasons"].append("A corrected seg00_01 candidate would require official scale/zero point, position formula, source graph, or compiler support; none was available.")
    return save_report(root, "1660_corrected_seg00_01_candidate", report, "Corrected seg00_01 Candidate", [f"verdict: `{verdict}`"])


def task1670(root: Path, command: str) -> dict[str, Any]:
    log = root / "evidence" / "gguf_f16_reference_v15" / "gguf_f16_reference_probe.log"
    text = log.read_text(encoding="utf-8", errors="ignore") if log.exists() else ""
    ggufs = [line.strip() for line in text.splitlines() if ".gguf" in line.lower()]
    f16 = [x for x in ggufs if "f16" in x.lower()]
    q4km = [x for x in ggufs if "q4km" in x.lower() or "q4_k_m" in x.lower()]
    hist = root / "evidence" / "gguf_f16_reference_v14" / "historical_q4km_control"
    verdict = "gguf_f16_blocked_no_artifact_no_logits_runner" if not f16 else "gguf_f16_artifact_found_runner_unverified"
    report = common(root, "1670_gguf_f16_reference_closure", command, [log, hist])
    report.update(
        {
            "verdict": verdict,
            "gguf_artifacts": {"f16": f16, "q4_k_m": q4km, "all": ggufs},
            "probe_log_excerpt": text[:6000],
            "historical_q4km_control": [artifact(p, root) for p in sorted(hist.glob("*")) if p.is_file()] if hist.exists() else [],
            "truth_boundary": "Q4_K_M historical outputs are deployment-control references only, not BF16 truth.",
        }
    )
    report["blocking_or_failure_reasons"].append("No Dream7B GGUF F16 artifact and no all-case logits-only F16 runner were available.")
    return save_report(root, "1670_gguf_f16_reference_closure", report, "GGUF F16 Reference Closure", [f"verdict: `{verdict}`", f"q4_k_m_lines: `{len(q4km)}`"])


def write_final_docs(root: Path, command: str, reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    verdict = "C_seg00_01_contract_fault_strongly_supported_but_vendor_artifacts_required"
    gate = {
        "schema_version": "dream7b_s100p_gate_packet_v15",
        "created_at_utc": now(),
        "verdict": verdict,
        **SAFETY,
        "current_full_bpu_path": "falsified_against_HF_PyTorch_BF16_logits_truth",
        "v14_verdict": reports["1600"].get("v14_gate_packet", {}).get("verdict"),
        "seg00_01": {
            "compiler_source_graph": reports["1610"].get("verdict"),
            "mul_add_input1": reports["1620"].get("verdict"),
            "gathernd_official_scale": reports["1630"].get("verdict"),
            "position_contract": reports["1640"].get("verdict"),
            "exact_comparator": reports["1650"].get("verdict"),
            "corrected_candidate": reports["1660"].get("verdict"),
        },
        "gguf_f16": reports["1670"].get("verdict"),
        "bf16_truth_hashes": {cid: artifact(root / "evidence" / "full_truth_bf16_v14" / cid / "full_truth_logits.npy", root) for cid in CASE_IDS},
        "claim_boundary": "The current tested seq128 B=1 segmented-HBM S100P path remains logits-invalid. v15 strongly supports a seg00_01 contract/export/quant/position fault but cannot close exact root cause or produce a corrected candidate without vendor/compiler artifacts.",
        "commands": [command],
    }
    write_json(root / "01_final_evidence" / "dream7b_s100p_gate_packet_v15.json", gate)
    write_text(
        root / "01_final_evidence" / "dream7b_s100p_gate_packet_v15.md",
        "# Dream7B S100P Gate Packet v15\n\n"
        f"- verdict: `{verdict}`\n"
        "- generation_quality_run: `false`\n"
        "- product_routes_18888_18889_touched: `false`\n"
        "- dream7b_frontend_openclaw_traffic_touched: `false`\n"
        "- no corrected seg00_01 candidate was run because no deployable known-scale/source-graph fix was available.\n",
    )
    write_text(
        root / "reports" / "ROOT_CAUSE_SUMMARY_V15.md",
        "# Root Cause Summary v15\n\n"
        "v15 strengthens the seg00_01 contract-fault hypothesis. Targeted NAS/compiler-cache search found the seq128 B=1 HBM artifacts but no matching source ONNX/HBIR/HBO or quant table. HRT dump variants in bin/txt/npy expose hbir.mul input, GatherND output, hbir.add input-0, and hbir.add output, but still do not expose hbir.mul output or add input-1. HF source shows token embedding followed by RoPE usage inside decoder attention rather than a learned absolute-position add at the embedding boundary. The exact operator-level root cause remains vendor-artifact blocked.\n",
    )
    write_text(
        root / "reports" / "PAPER_EVIDENCE_DOSSIER_V15.md",
        "# Paper Evidence Dossier v15\n\n"
        "The paper-safe conclusion is that the tested Dream7B seq128 B=1 segmented-HBM S100P path and tested BPU/hybrid routes remain logits-invalid against HF/PyTorch BF16 truth. v15 does not claim Dream7B is impossible on S100P. It identifies the minimal missing artifacts needed for closure: source graph, quant table, hbir.mul output/add input-1, and calibration ranges. Generation quality and product routes were not run.\n",
    )
    write_text(
        root / "reports" / "CANDIDATE_DEPLOYMENT_ROUTES_V15.md",
        "# Candidate Deployment Routes v15\n\n"
        "No route is deployment-valid on logits evidence. The next viable route is a corrected seg00_01 re-export/recompile using official source graph and quant metadata, followed by seg00_01 boundary gate and HF suffix logits gate. BPU-island and GGUF F16 routes remain blocked: no deployable island correction passed, and no GGUF F16 logits reference is available.\n",
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


def package_v15(root: Path, command: str) -> dict[str, Any]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    staging = root / "tmp" / f"dream7b_s100p_v15_for_gptpro_{stamp}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    stems = [
        "1600_v15_baseline_lock",
        "1610_seg00_01_compiler_source_graph_acquisition",
        "1620_hbir_mul_add_input1_recovery",
        "1630_gathernd_official_quant_scale_closure",
        "1640_position_contract_closure",
        "1650_exact_seg00_01_comparator",
        "1660_corrected_seg00_01_candidate",
        "1670_gguf_f16_reference_closure",
        "ROOT_CAUSE_SUMMARY_V15",
        "PAPER_EVIDENCE_DOSSIER_V15",
        "CANDIDATE_DEPLOYMENT_ROUTES_V15",
    ]
    for stem in stems:
        for suffix in [".json", ".md"]:
            copy_if_exists(root / "reports" / f"{stem}{suffix}", staging / "reports" / f"{stem}{suffix}")
    for p in (root / "01_final_evidence").glob("*v15*"):
        copy_if_exists(p, staging / "01_final_evidence" / p.name)
    for sub in [
        "compiler_source_graph_v15",
        "seg00_01_mul_add_input1_v15",
        "gguf_f16_reference_v15",
        "corrected_seg00_01_candidate_v15",
        "full_truth_bf16_v14",
        "seg00_01_exact_graph_v14",
        "hf_remote_code_v14",
    ]:
        copy_if_exists(root / "evidence" / sub, staging / "evidence" / sub)
    copy_if_exists(root / "evidence" / "gguf_f16_reference_v14" / "historical_q4km_control", staging / "evidence" / "gguf_f16_reference_v14" / "historical_q4km_control")
    for p in (root / "vendor_request").glob("*V15.md"):
        copy_if_exists(p, staging / "vendor_request" / p.name)
    for tool in ["build_v15_research_thread.py", "build_v14_research_thread.py", "run_v14_seg00_exact_graph_and_position.py"]:
        copy_if_exists(root / "tools" / tool, staging / "tools" / tool)
    inside = {
        "schema_version": "dream7b_s100p_v15_1680_final_package_inside",
        "created_at_utc": now(),
        "inside_package_report": True,
        "note": "The enclosing zip SHA256 is intentionally omitted here to avoid circular self-reference. See workspace report 1680 for the final zip hash.",
        **SAFETY,
    }
    write_json(staging / "reports" / "1680_final_v15_gate_packet_and_package.json", inside)
    write_text(staging / "reports" / "1680_final_v15_gate_packet_and_package.md", "# Final v15 Gate Packet and Package\n\nIn-package non-circular package report.\n")
    write_text(staging / "README.md", "Dream7B/S100P v15 evidence package. No generation quality and no 18888/18889 route interaction.\n")
    files = []
    for p in sorted(staging.rglob("*")):
        if p.is_file():
            files.append({"path": rel(p, staging), "size_bytes": p.stat().st_size, "sha256": sha256_file(p)})
    write_json(staging / "MANIFEST.json", {"schema_version": "dream7b_s100p_v15_manifest", "created_at_utc": now(), "file_count": len(files), "files": files})
    write_text(staging / "SHA256SUMS.txt", "\n".join(f"{f['sha256']}  {f['path']}" for f in files) + "\n")
    out = root / "evidence_for_gptpro" / f"dream7b_s100p_v15_for_gptpro_{stamp}.zip"
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
    report = common(root, "1680_final_v15_gate_packet_and_package", command, [out])
    report.update({"zip_path": rel(out, root), "zip_sha256": zip_sha, "zip_sha256_txt": rel(out.with_suffix(out.suffix + ".sha256.txt"), root), "zip_size_bytes": out.stat().st_size, "zip_member_count": count, "zip_testzip_bad_member": bad, "manifest_file_count": len(files)})
    save_report(root, "1680_final_v15_gate_packet_and_package", report, "Final v15 Gate Packet and Package", [f"zip_path: `{report['zip_path']}`", f"zip_sha256: `{zip_sha}`"])
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    command = " ".join([sys.executable, *sys.argv])
    reports: dict[str, dict[str, Any]] = {}
    reports["1600"] = task1600(root, command)
    reports["1610"] = task1610(root, command)
    reports["1620"] = task1620(root, command)
    reports["1630"] = task1630(root, command)
    reports["1640"] = task1640(root, command)
    reports["1650"] = task1650(root, command)
    reports["1660"] = task1660(root, command)
    reports["1670"] = task1670(root, command)
    gate = write_final_docs(root, command, reports)
    package = package_v15(root, command)
    print(json.dumps({"verdict": gate["verdict"], "zip": package["zip_path"], "zip_sha256": package["zip_sha256"], "compiler": reports["1610"]["verdict"], "exact_comparator": reports["1650"]["verdict"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
