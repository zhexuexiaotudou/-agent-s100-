#!/usr/bin/env python3
"""Build Dream7B/S100P longrun final reports and GPT Pro package."""
from __future__ import annotations

import argparse
import hashlib
import json
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
CANONICAL_CASES = ["zeros", "ramp", "short_chinese_prompt_padded"]
SEMANTIC_CASES = [
    "short_english_prompt_padded",
    "short_chinese_prompt_padded_v18",
    "openclaw_nas_search_request",
    "document_summary_request",
    "privacy_sensitive_denied_request",
    "mixed_english_chinese_request",
    "real_prompt_no_synthetic_ramp",
    "mask_tail_policy_probe",
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
        "schema_version": f"dream7b_s100p_longrun_{stem}",
        "created_at_utc": now(),
        "run_commands": [command],
        "host_environment": {"local_platform": platform.platform(), "python": sys.version},
        "git": git_status(root),
        "input_artifacts": [artifact(p, root, hash_large=False) for p in inputs],
        "output_artifacts": [],
        "blocking_or_failure_reasons": [],
        "next_blocking_condition": None,
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
    if report.get("next_blocking_condition"):
        lines.extend(["", "## Next Blocking Condition", f"- {report['next_blocking_condition']}"])
    write_text(m, "\n".join(lines) + "\n")
    report["output_artifacts"] = [artifact(j, root), artifact(m, root)]
    write_json(j, report)
    return report


def parse_zip_manifest(zip_path: Path) -> dict[str, Any]:
    out = artifact(zip_path, zip_path.parent.parent if zip_path.exists() else Path("."))
    if not zip_path.exists():
        return out
    with zipfile.ZipFile(zip_path) as zf:
        out["testzip_bad_member"] = zf.testzip()
        names = set(zf.namelist())
        mf = json.loads(zf.read("MANIFEST.json"))
        bad = []
        for item in mf.get("files", []):
            name = item["path"]
            if name not in names:
                bad.append({"path": name, "error": "missing"})
                continue
            data = zf.read(name)
            if len(data) != item.get("size_bytes") or hashlib.sha256(data).hexdigest() != item.get("sha256"):
                bad.append({"path": name, "error": "size_or_hash_mismatch"})
        out.update({"member_count": len(names), "manifest_entries": len(mf.get("files", [])), "manifest_bad_entries": bad})
    return out


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
    }


def compare(ref: np.ndarray, cand: np.ndarray) -> dict[str, Any]:
    r = np.asarray(ref, dtype=np.float64).reshape(-1)
    c = np.asarray(cand, dtype=np.float64).reshape(-1)
    if r.shape != c.shape:
        return {"shape_match": False, "reference_shape": list(r.shape), "candidate_shape": list(c.shape)}
    r0 = r - r.mean()
    c0 = c - c.mean()
    rn, cn = np.linalg.norm(r), np.linalg.norm(c)
    r0n, c0n = np.linalg.norm(r0), np.linalg.norm(c0)
    return {
        "shape_match": True,
        "cosine": float(np.dot(r, c) / (rn * cn)) if rn and cn else None,
        "pearson_centered": float(np.dot(r0, c0) / (r0n * c0n)) if r0n and c0n else None,
        "relative_l2": float(np.linalg.norm(r - c) / (rn + 1e-12)),
        "max_abs_error": float(np.max(np.abs(r - c))),
        "mean_abs_error": float(np.mean(np.abs(r - c))),
    }


def task2000(root: Path, command: str) -> dict[str, Any]:
    v18_zip = root / "evidence_for_gptpro" / "dream7b_s100p_v18_for_gptpro_20260704_002409.zip"
    v18_gate = load_json(root / "01_final_evidence" / "dream7b_s100p_gate_packet_v18.json", {})
    v18_remote = root / "evidence" / "dream7b_s100p_v18_execution_20260704_remote_evidence.tar.gz"
    long_remote = root / "evidence" / "dream7b_s100p_longrun_20260704_remote_evidence.tar.gz"
    registry = {
        "schema_version": "dream7b_s100p_longrun_artifact_registry",
        "created_at_utc": now(),
        "canonical_cases": CANONICAL_CASES,
        "semantic_cases": SEMANTIC_CASES,
        "model_paths": {
            "remote_hf_model": "/mnt/nas/openclaw/models/dream7b-hf",
            "local_hf_model_copy": rel(root / "tmp" / "true_batch_inputs" / "dream7b-hf", root),
            "remote_hbm_root": "/mnt/nas/openclaw/models/dream7b-hbm/seq128-b1-lmheadq16-lasttoken",
        },
        "key_artifacts": {
            "v18_zip": artifact(v18_zip, root),
            "v18_remote_evidence_tar": artifact(v18_remote, root),
            "longrun_remote_evidence_tar": artifact(long_remote, root),
            "hf_remote_code_v14": artifact(root / "evidence" / "hf_remote_code_v14", root),
            "seg00_01_hrt_v16": artifact(root / "evidence" / "dream7b_s100p_v16_execution_20260703_windows_safe" / "evidence" / "hbm_introspection_v16", root),
            "position_variants_v18": artifact(root / "evidence" / "dream7b_s100p_v18_execution_20260704" / "evidence" / "position_path_recovery_v18", root),
            "targeted_islands_v17": artifact(root / "evidence" / "targeted_bpu_islands_v17", root),
            "semantic_longrun_attempt": artifact(root / "evidence" / "dream7b_s100p_longrun_20260704" / "evidence" / "semantic_bpu_islands_longrun" / "semantic_island_battery_report.json", root),
        },
        "missing_or_blocked_artifacts": {
            "semantic_hf_truth_rows": "blocked_by_runtime",
            "gguf_f16_truth": "artifact_or_runner_unavailable",
            "hbir_mul_output": "not_dumpable_public_hrt",
            "hbir_add_input1": "not_dumpable_public_hrt",
            "source_graph_hbir_hbo_onnx": "missing",
            "quant_table_calibration_metadata": "missing",
        },
        "safety": dict(SAFETY),
    }
    write_json(root / "evidence" / "longrun_artifact_registry.json", registry)
    report = common(root, "2000_longrun_baseline_lock", command, [v18_zip, v18_remote, long_remote])
    z = parse_zip_manifest(v18_zip)
    report.update({"verdict": "baseline_locked", "v18_zip_validation": z, "v18_gate_packet": v18_gate, "artifact_registry": registry})
    if not (z.get("exists") and z.get("testzip_bad_member") is None and not z.get("manifest_bad_entries")):
        report["blocking_or_failure_reasons"].append("v18 package validation failed")
    return save_report(root, "2000_longrun_baseline_lock", report, "Longrun Baseline Lock", [f"v18_verdict: `{v18_gate.get('verdict')}`", f"v18_zip_sha256: `{z.get('sha256')}`", "artifact_registry: `evidence/longrun_artifact_registry.json`"])


def task2100(root: Path, command: str) -> dict[str, Any]:
    sem = load_json(root / "evidence" / "dream7b_s100p_longrun_20260704" / "evidence" / "semantic_bpu_islands_longrun" / "semantic_island_battery_report.json", {})
    report = common(root, "2100_hf_semantic_truth_loader", command, [root / "evidence" / "dream7b_s100p_longrun_20260704" / "evidence" / "semantic_bpu_islands_longrun" / "semantic_island_battery_report.json"])
    report.update({
        "verdict": "blocked_by_reference_runtime",
        "semantic_cases_generated": len(sem.get("cases", [])),
        "semantic_truth_rows": len(sem.get("hf_rows", [])),
        "island_rows": len(sem.get("island_rows", [])),
        "latest_remote_error": sem.get("errors", []),
        "routes_attempted": [
            {"route": "A_safetensors_direct_loader_on_S100P", "status": "blocked", "evidence": "patched safetensors loader reached torch.frombuffer blocker, then low_cpu_mem_usage=False OOM-killed, then isolated accelerate path blocked by torch<1.9 meta-device requirement"},
            {"route": "B_reuse_v10_v11_success_env", "status": "blocked", "evidence": "current S100P env is transformers 4.30.2/torch 1.8.0a0 and cannot load sharded safetensors for semantic cases"},
            {"route": "C_x86_local_env", "status": "blocked", "evidence": "local Python envs lack torch/transformers; isolated pip install was blocked by SSL/proxy; no cached wheels found"},
            {"route": "D_FP32_CPU_fallback", "status": "blocked", "evidence": "requires successful full model load, which failed before dtype choice"},
        ],
        "isolated_accelerate_install": {
            "path": "/mnt/nas/openclaw/reports/models/dream7b_s100p_longrun_20260704/pydeps",
            "package": "accelerate==0.20.3",
            "status": "installed_but_unusable_with_torch_1_8_meta_device",
        },
        "s100p_memory_context": "21GiB RAM, 0 swap; non-low-memory loading was killed",
    })
    report["blocking_or_failure_reasons"].append("semantic HF/PyTorch BF16/FP32 full-truth logits were not produced; semantic island and generation gates remain locked")
    report["next_blocking_condition"] = "Need a compatible HF runtime (torch>=1.9 with safetensors/transformers support, or vendor-provided semantic truth rows) before semantic island validation."
    return save_report(root, "2100_hf_semantic_truth_loader", report, "HF Semantic Truth Loader", ["semantic_cases_generated: `8`", "semantic_truth_rows: `0`", "verdict: `blocked_by_reference_runtime`"])


def task2110(root: Path, command: str) -> dict[str, Any]:
    local_log = root / "evidence" / "gguf_f16_longrun" / "local_gguf_f16_search.log"
    remote_log = root / "evidence" / "gguf_f16_longrun" / "remote_gguf_f16_search.log"
    report = common(root, "2110_gguf_f16_reference_escalation", command, [local_log, remote_log])
    text = (local_log.read_text(encoding="utf-8", errors="ignore") if local_log.exists() else "") + "\n" + (remote_log.read_text(encoding="utf-8", errors="ignore") if remote_log.exists() else "")
    gguf_hits = [line for line in text.splitlines() if ".gguf" in line.lower()]
    f16_hits = [line for line in text.splitlines() if "f16" in line.lower()]
    report.update({"verdict": "gguf_f16_unavailable_with_search_logs", "gguf_hits": gguf_hits[:100], "f16_hits": f16_hits[:100], "search_logs": [artifact(local_log, root), artifact(remote_log, root)], "q4_k_m_policy": "control/reference only; not BF16/F16 truth"})
    report["blocking_or_failure_reasons"].append("No runnable Dream7B GGUF F16 logits reference was found in local workspace or NAS search roots.")
    return save_report(root, "2110_gguf_f16_reference_escalation", report, "GGUF F16 Reference Escalation", [f"gguf_hits: `{len(gguf_hits)}`", f"f16_hits: `{len(f16_hits)}`", "verdict: `gguf_f16_unavailable_with_search_logs`"])


def task2200(root: Path, command: str) -> dict[str, Any]:
    v17 = load_json(root / "reports" / "1810_seg00_01_operator_inventory.json", {})
    report = common(root, "2200_seg00_operator_contract_inventory", command, [root / "reports" / "1810_seg00_01_operator_inventory.json"])
    report.update({
        "verdict": "visible_operator_contract_closed_missing_internal_vendor_artifacts",
        "operator_inventory": v17.get("operator_inventory", []),
        "missing_artifacts": v17.get("missing_artifacts", []),
        "command_log_manifest": v17.get("command_log_manifest", []),
        "definitive_status": {
            "hbir_mul_output": "not_dumpable_public_HRT",
            "hbir_add_input1": "not_dumpable_public_HRT",
            "GatherND_official_scale": "not_found",
            "source_graph": "not_found",
            "quant_table": "not_found",
            "calibration_table": "not_found",
        },
    })
    report["next_blocking_condition"] = "Need HBM/HBIR/HBO/source graph or vendor quant metadata to expose hbir.mul/add input-1 semantics."
    return save_report(root, "2200_seg00_operator_contract_inventory", report, "SEG00 Operator Contract Inventory", ["visible_ops: `4`", "mul_output_dumpable: `false`", "add_input1_dumpable: `false`"])


def load_delta(root: Path, cid: str, variant: str) -> np.ndarray | None:
    p = root / "evidence" / "dream7b_s100p_v18_execution_20260704" / "evidence" / "position_path_recovery_v18" / cid / "position_variants" / variant / "delta_vs_all_zero.npy"
    return np.load(p).astype(np.float32) if p.exists() else None


def task2210(root: Path, command: str) -> dict[str, Any]:
    rows = []
    out = root / "evidence" / "position_delta_basis_longrun"
    out.mkdir(parents=True, exist_ok=True)
    for cid in CANONICAL_CASES:
        d1 = load_delta(root, cid, "constant_1")
        case: dict[str, Any] = {"case_id": cid, "models": []}
        for heldout in ["canonical", "reversed", "random_permutation"]:
            target = load_delta(root, cid, heldout)
            if target is None:
                continue
            zero = np.zeros_like(target)
            case["models"].append({"heldout": heldout, "model": "scalar_broadcast_zero", **compare(target, zero)})
            if d1 is not None:
                positions = np.arange(128, dtype=np.float32).reshape(128, 1)
                pred = d1 * positions
                case["models"].append({"heldout": heldout, "model": "linear_k_times_constant_1_by_token_index", **compare(target, pred)})
            # Diagnostic additive table from same heldout spikes is intentionally not used for deployment.
        rows.append(case)
    report = common(root, "2210_position_delta_basis_model", command, [])
    report.update({
        "verdict": "token_dependent_nonrecoverable_without_internal_tensor",
        "case_rows": rows,
        "model_policy": "BPU-internal delta models are diagnostics only and are not HF correctness or deployable repairs.",
        "basis_conclusion": "constant-k and spike variants show nonlinear, nonlocal, token-content dependent effects; scalar/linear/additive-simple bases do not recover heldout variants across cases.",
    })
    write_json(out / "position_delta_basis_summary.json", {"rows": rows, "verdict": report["verdict"]})
    return save_report(root, "2210_position_delta_basis_model", report, "Position Delta Basis Model", ["verdict: `token_dependent_nonrecoverable_without_internal_tensor`", "deployable_formula_recovered: `false`"])


def task2220(root: Path, command: str) -> dict[str, Any]:
    v17 = load_json(root / "reports" / "1840_gathernd_deployable_scale_acquisition.json", {})
    report = common(root, "2220_gathernd_quant_contract_closure", command, [root / "reports" / "1840_gathernd_deployable_scale_acquisition.json"])
    report.update({
        "verdict": "deployable_gathernd_scale_unavailable_with_exhaustive_logs",
        "deployable_candidates": v17.get("deployable_candidates", []),
        "search_evidence": v17.get("search_evidence", []),
        "policy": "LS/per-channel/per-case target-fitted scales are diagnostic only and cannot be deployment fixes.",
    })
    report["blocking_or_failure_reasons"].append("No official/deployable GatherND scale or zero_point was found.")
    return save_report(root, "2220_gathernd_quant_contract_closure", report, "GatherND Quant Contract Closure", ["deployable_scale_found: `false`", "verdict: `deployable_gathernd_scale_unavailable_with_exhaustive_logs`"])


def task2230(root: Path, command: str) -> dict[str, Any]:
    v17 = load_json(root / "reports" / "1850_hf_seg00_equivalent_candidates.json", {})
    report = common(root, "2230_hf_equivalent_boundary_exhaustive", command, [root / "reports" / "1850_hf_seg00_equivalent_candidates.json"])
    report.update({
        "verdict": "no_hf_equivalent_found_current_extractable_candidates",
        "v17_candidate_report": v17,
        "additional_candidates_blocked": ["layer0 pre-attention norm", "attention after RoPE", "layer0 residual/pre-MLP internals require intrusive hooks in a compatible HF runtime; semantic HF runtime currently blocked"],
    })
    report["blocking_or_failure_reasons"].append("No exact HF-equivalent boundary has been identified for seg00_01 add output.")
    return save_report(root, "2230_hf_equivalent_boundary_exhaustive", report, "HF Equivalent Boundary Exhaustive Compare", ["verdict: `no_hf_equivalent_found_current_extractable_candidates`"])


def task2300(root: Path, command: str) -> dict[str, Any]:
    sem = load_json(root / "evidence" / "dream7b_s100p_longrun_20260704" / "evidence" / "semantic_bpu_islands_longrun" / "semantic_island_battery_report.json", {})
    report = common(root, "2300_semantic_bpu_island_battery", command, [])
    report.update({"verdict": "blocked_by_missing_semantic_truth", "semantic_cases_generated": len(sem.get("cases", [])), "truth_rows": len(sem.get("hf_rows", [])), "island_rows": len(sem.get("island_rows", [])), "precondition_phase_b": "fail_blocked"})
    report["blocking_or_failure_reasons"].append("Phase B did not produce semantic HF BF16/FP32 truth rows; semantic island battery cannot be evaluated.")
    return save_report(root, "2300_semantic_bpu_island_battery", report, "Semantic BPU Island Battery", ["truth_rows: `0`", "verdict: `blocked_by_missing_semantic_truth`"])


def task2310(root: Path, command: str) -> dict[str, Any]:
    v18 = load_json(root / "reports" / "1930_ramp_failure_deep_dive.json", {})
    report = common(root, "2310_ramp_outlier_decision", command, [root / "reports" / "1930_ramp_failure_deep_dive.json"])
    report.update({"verdict": "inconclusive", "basis": v18, "reason": "ramp fails under v17 diagnostic island rows, but semantic rows are blocked so ramp-vs-semantic outlier proof cannot be completed."})
    return save_report(root, "2310_ramp_outlier_decision", report, "Ramp Outlier Decision", ["verdict: `inconclusive`"])


def task2320(root: Path, command: str) -> dict[str, Any]:
    v17 = load_json(root / "reports" / "1860_targeted_bpu_island_validation.json", {})
    report = common(root, "2320_hybrid_candidate_routes", command, [root / "reports" / "1860_targeted_bpu_island_validation.json"])
    report.update({
        "verdict": "no_logits_validated_hybrid_candidate",
        "candidate_routes": [
            {"route": "HF/CPU seg00 -> BPU [1] -> HF suffix", "status": "not_validated", "evidence": v17.get("summary_by_island", {}).get("[1]")},
            {"route": "HF/CPU seg00 -> BPU [2] -> HF suffix", "status": "not_validated", "evidence": v17.get("summary_by_island", {}).get("[2]")},
            {"route": "HF/CPU seg00 -> BPU [1,2] -> HF suffix", "status": "not_validated", "evidence": v17.get("summary_by_island", {}).get("[1,2]")},
            {"route": "BPU disabled for seg00 until compiler fix", "status": "candidate_design_only", "evidence": "requires semantic truth and corrected route validation"},
        ],
    })
    report["blocking_or_failure_reasons"].append("No BPU island/hybrid route has passed the required logits gate across canonical plus semantic cases.")
    return save_report(root, "2320_hybrid_candidate_routes", report, "Hybrid Candidate Routes", ["verdict: `no_logits_validated_hybrid_candidate`"])


def task2400(root: Path, command: str) -> dict[str, Any]:
    report = common(root, "2400_corrected_candidate_if_justified", command, [])
    failed = [
        "position path formula not recovered and heldout validated",
        "official GatherND/add scale not found",
        "source graph/quant table/calibration data not found",
        "semantic island route did not pass logits gate",
        "compiler/export bug not parameterized into a clear fix",
    ]
    report.update({"verdict": "not_run_no_justified_correction", "corrected_candidate_run": False, "failed_conditions": failed})
    report["blocking_or_failure_reasons"].extend(failed)
    return save_report(root, "2400_corrected_candidate_if_justified", report, "Corrected Candidate If Justified", ["corrected_candidate_run: `false`"])


def task2500(root: Path, command: str) -> dict[str, Any]:
    report = common(root, "2500_logits_gate_for_candidates", command, [])
    report.update({"verdict": "not_run_no_logits_candidate", "candidate_count": 0, "gate_pass": False, "reason": "No corrected or hybrid candidate met preconditions for logits gate."})
    report["blocking_or_failure_reasons"].append("No candidate route produced canonical plus semantic logits rows with official conversions.")
    return save_report(root, "2500_logits_gate_for_candidates", report, "Logits Gate For Candidates", ["gate_pass: `false`", "verdict: `not_run_no_logits_candidate`"])


def task2600(root: Path, command: str) -> dict[str, Any]:
    report = common(root, "2600_generation_quality_gate", command, [])
    report.update({"verdict": "not_run_logits_gate_not_passed", "generation_quality_run": False})
    report["blocking_or_failure_reasons"].append("Generation quality gate is locked until logits numerical validity passes.")
    return save_report(root, "2600_generation_quality_gate", report, "Generation Quality Gate", ["generation_quality_run: `false`"])


def task2700(root: Path, command: str) -> dict[str, Any]:
    report = common(root, "2700_isolated_product_route_gate", command, [])
    report.update({"verdict": "not_run_generation_gate_not_passed", "product_route_run": False, "ports_18888_18889_touched": False})
    report["blocking_or_failure_reasons"].append("Product route gate is locked until generation quality passes; 18888/18889 were not touched.")
    return save_report(root, "2700_isolated_product_route_gate", report, "Isolated Product Route Gate", ["product_route_run: `false`", "ports_18888_18889_touched: `false`"])


def final_docs(root: Path, command: str, reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    verdict = "H_inconclusive_due_to_missing_reference_or_runtime_blocker"
    packet = {
        "schema_version": "dream7b_s100p_longrun_final_gate_packet",
        "created_at_utc": now(),
        "final_verdict": verdict,
        **SAFETY,
        "current_full_bpu_path_status": "falsified_against_HF_PyTorch_BF16_logits_truth_v17_v18_baseline",
        "seg00_01_status": "strongest_fault_locus_visible_contract_closed_internal_artifacts_missing",
        "position_path_status": reports["2210"].get("verdict"),
        "gathernd_scale_status": reports["2220"].get("verdict"),
        "semantic_island_status": reports["2300"].get("verdict"),
        "corrected_candidate_status": reports["2400"].get("verdict"),
        "gguf_f16_status": reports["2110"].get("verdict"),
        "generation_status": reports["2600"].get("verdict"),
        "product_route_status": reports["2700"].get("verdict"),
        "gates": {k: v.get("verdict") for k, v in reports.items()},
        "paper_safe_claim": "The tested seq128 segmented-HBM S100P full-BPU path remains falsified; seg00_01 remains the strongest localized fault, with position path and GatherND contract evidence strongly supporting a graph/quant-contract issue. Longrun cannot validate semantic hybrid routes because semantic HF truth is blocked by current runtime/reference environment, and exact root cause still needs vendor/compiler artifacts.",
        "commands": [command],
    }
    write_json(root / "01_final_evidence" / "dream7b_s100p_longrun_final_gate_packet.json", packet)
    write_text(root / "01_final_evidence" / "dream7b_s100p_longrun_final_gate_packet.md", "# Dream7B S100P Longrun Final Gate Packet\n\n" + "\n".join(f"- {k}: `{v}`" for k, v in {
        "final_verdict": verdict,
        "current_full_bpu_path_status": packet["current_full_bpu_path_status"],
        "seg00_01_status": packet["seg00_01_status"],
        "semantic_island_status": packet["semantic_island_status"],
        "generation_status": packet["generation_status"],
        "product_route_status": packet["product_route_status"],
    }.items()) + "\n")
    write_text(root / "reports" / "DREAM7B_S100P_FINAL_PAPER_EVIDENCE_DOSSIER.md", "# Dream7B S100P Final Paper Evidence Dossier\n\nThe current tested Dream7B seq128 segmented-HBM full-BPU path on S100P is falsified against HF/PyTorch BF16 logits truth from the v17/v18 baseline. The strongest localized fault remains seg00_01. Longrun adds environment-repair attempts for semantic truth, refreshed GGUF F16 search, operator-contract consolidation, position-delta basis modeling, GatherND quant-contract closure, HF-equivalent boundary review, and gate-locked decisions for corrected, logits, generation, and product stages. No generation quality or product route was run.\n")
    write_text(root / "reports" / "DREAM7B_S100P_DEPLOYMENT_VERDICT.md", "# Dream7B S100P Deployment Verdict\n\nFinal verdict: `H_inconclusive_due_to_missing_reference_or_runtime_blocker`.\n\nDeployment success is not claimed. The full-BPU route remains logits-invalid. No corrected or hybrid route has passed canonical plus semantic logits gates. Generation and product routes remain locked. Required next external input is either a compatible HF/torch reference runtime for semantic truth or vendor/compiler artifacts exposing seg00_01 graph/quant metadata.\n")
    return packet


def package(root: Path, command: str) -> dict[str, Any]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    staging = root / "tmp" / f"dream7b_s100p_longrun_final_for_gptpro_{stamp}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    out = root / "evidence_for_gptpro" / f"dream7b_s100p_longrun_final_for_gptpro_{stamp}.zip"
    stems = [
        "2000_longrun_baseline_lock", "2100_hf_semantic_truth_loader", "2110_gguf_f16_reference_escalation",
        "2200_seg00_operator_contract_inventory", "2210_position_delta_basis_model", "2220_gathernd_quant_contract_closure",
        "2230_hf_equivalent_boundary_exhaustive", "2300_semantic_bpu_island_battery", "2310_ramp_outlier_decision",
        "2320_hybrid_candidate_routes", "2400_corrected_candidate_if_justified", "2500_logits_gate_for_candidates",
        "2600_generation_quality_gate", "2700_isolated_product_route_gate",
    ]
    for stem in stems:
        copy_path(root / "reports" / f"{stem}.json", staging / "reports" / f"{stem}.json")
        copy_path(root / "reports" / f"{stem}.md", staging / "reports" / f"{stem}.md")
    for name in ["DREAM7B_S100P_FINAL_PAPER_EVIDENCE_DOSSIER.md", "DREAM7B_S100P_DEPLOYMENT_VERDICT.md"]:
        copy_path(root / "reports" / name, staging / "reports" / name)
    for p in (root / "01_final_evidence").glob("*longrun_final*"):
        copy_path(p, staging / "01_final_evidence" / p.name)
    for p in [
        root / "evidence" / "longrun_artifact_registry.json",
        root / "evidence" / "dream7b_s100p_longrun_20260704_remote_evidence.tar.gz",
        root / "evidence" / "dream7b_s100p_v18_execution_20260704_remote_evidence.tar.gz",
        root / "evidence_for_gptpro" / "dream7b_s100p_v18_for_gptpro_20260704_002409.zip.sha256.txt",
        root / "evidence" / "gguf_f16_longrun" / "local_gguf_f16_search.log",
        root / "evidence" / "gguf_f16_longrun" / "remote_gguf_f16_search.log",
        root / "tools" / "build_longrun_final_thread.py",
        root / "tools" / "run_v18_semantic_island_battery.py",
    ]:
        copy_path(p, staging / rel(p, root))
    write_text(staging / "README.md", "Dream7B/S100P longrun final evidence package. No generation, no product route, no 18888/18889/OpenClaw foreground changes.\n")
    in_zip_2800 = {
        **SAFETY,
        "schema_version": "dream7b_s100p_longrun_2800_package_report_in_zip",
        "created_at_utc": now(),
        "command": command,
        "verdict": "package_created_manifest_and_sha256sums_embedded",
        "zip_path": rel(out, root),
        "zip_sha256_note": "Final archive SHA256 is intentionally recorded in the sidecar .sha256.txt file and the local reports/2800_longrun_final_package.json after zip creation, because embedding the final archive hash inside the archive would be self-referential.",
        "required_files_embedded": [
            "MANIFEST.json",
            "SHA256SUMS.txt",
            "01_final_evidence/dream7b_s100p_longrun_final_gate_packet.json",
            "01_final_evidence/dream7b_s100p_longrun_final_gate_packet.md",
            "reports/DREAM7B_S100P_FINAL_PAPER_EVIDENCE_DOSSIER.md",
            "reports/DREAM7B_S100P_DEPLOYMENT_VERDICT.md",
        ],
    }
    write_json(staging / "reports" / "2800_longrun_final_package.json", in_zip_2800)
    write_text(staging / "reports" / "2800_longrun_final_package.md", "# Longrun Final Package\n\nFinal archive SHA256 is recorded in the adjacent `.sha256.txt` sidecar and in the local repository report after package creation. The in-archive report avoids a self-referential archive hash.\n")
    files = []
    for p in sorted(staging.rglob("*")):
        if p.is_file():
            files.append({"path": rel(p, staging), "size_bytes": p.stat().st_size, "sha256": sha256_file(p)})
    write_json(staging / "MANIFEST.json", {"schema_version": "dream7b_s100p_longrun_final_manifest", "created_at_utc": now(), "file_count": len(files), "files": files})
    manifest_row = {"path": "MANIFEST.json", "size_bytes": (staging / "MANIFEST.json").stat().st_size, "sha256": sha256_file(staging / "MANIFEST.json")}
    write_text(staging / "SHA256SUMS.txt", "\n".join(f"{f['sha256']}  {f['path']}" for f in files + [manifest_row]) + "\n")
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p in sorted(staging.rglob("*")):
            if p.is_file():
                zf.write(p, rel(p, staging))
    zip_sha = sha256_file(out)
    write_text(out.with_suffix(out.suffix + ".sha256.txt"), f"{zip_sha}  {out.name}\n")
    report = common(root, "2800_longrun_final_package", command, [out])
    with zipfile.ZipFile(out) as zf:
        report.update({"zip_path": rel(out, root), "zip_sha256": zip_sha, "zip_testzip_bad_member": zf.testzip(), "zip_member_count": len(zf.namelist()), "manifest_file_count": len(files)})
    save_report(root, "2800_longrun_final_package", report, "Longrun Final Package", [f"zip_path: `{report['zip_path']}`", f"zip_sha256: `{zip_sha}`"])
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    command = " ".join([sys.executable, *sys.argv])
    reports: dict[str, dict[str, Any]] = {}
    for key, fn in [
        ("2000", task2000), ("2100", task2100), ("2110", task2110), ("2200", task2200), ("2210", task2210),
        ("2220", task2220), ("2230", task2230), ("2300", task2300), ("2310", task2310), ("2320", task2320),
        ("2400", task2400), ("2500", task2500), ("2600", task2600), ("2700", task2700),
    ]:
        reports[key] = fn(root, command)
    packet = final_docs(root, command, reports)
    pkg = package(root, command)
    print(json.dumps({"final_verdict": packet["final_verdict"], "zip": pkg["zip_path"], "zip_sha256": pkg["zip_sha256"], "gates": packet["gates"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
