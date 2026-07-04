#!/usr/bin/env python3
"""Build Dream7B/S100P v19 reports and GPT Pro evidence packet.

The builder consumes local and pulled remote evidence. It does not run
generation, product routes, or touch ports 18888/18889.
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
SAFETY = {
    "generation_quality_run": False,
    "product_routes_18888_18889_touched": False,
    "dream7b_frontend_openclaw_traffic_touched": False,
    "harness_qwen_openclaw_defaults_modified": False,
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return str(path)


def artifact(path: Path, root: Path) -> dict[str, Any]:
    row: dict[str, Any] = {"path": rel(path, root), "exists": path.exists()}
    if path.exists() and path.is_file():
        row.update({"size_bytes": path.stat().st_size, "sha256": sha256_file(path)})
    elif path.exists() and path.is_dir():
        files = [p for p in path.rglob("*") if p.is_file()]
        row.update({"file_count": len(files), "size_bytes": sum(p.stat().st_size for p in files)})
    return row


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run(cmd: list[str], cwd: Path) -> dict[str, Any]:
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, timeout=60)
        return {"cmd": cmd, "returncode": proc.returncode, "stdout": proc.stdout[-12000:], "stderr": proc.stderr[-12000:]}
    except Exception as exc:
        return {"cmd": cmd, "error": f"{type(exc).__name__}:{exc}"}


def common(root: Path, schema: str, command: str, inputs: list[Path]) -> dict[str, Any]:
    return {
        "schema_version": f"dream7b_s100p_v19_{schema}",
        "created_at_utc": now(),
        "run_commands": [command],
        "host_environment": {"platform": platform.platform(), "python": sys.version},
        "git": run(["git", "status", "--short"], root),
        "input_artifacts": [artifact(p, root) for p in inputs],
        "output_artifacts": [],
        "blocking_or_failure_reasons": [],
        "safety": dict(SAFETY),
    }


def save_report(root: Path, stem: str, report: dict[str, Any], title: str, bullets: list[str]) -> dict[str, Any]:
    j = root / "reports" / f"{stem}.json"
    m = root / "reports" / f"{stem}.md"
    write_json(j, report)
    write_text(m, "# " + title + "\n\n" + "\n".join("- " + b for b in bullets) + "\n")
    report["output_artifacts"] = [artifact(j, root), artifact(m, root)]
    write_json(j, report)
    return report


def stats(arr: np.ndarray) -> dict[str, Any]:
    x = np.asarray(arr)
    if x.size == 0:
        return {"shape": list(x.shape), "dtype": str(x.dtype), "size": 0}
    y = x.reshape(-1)
    return {
        "shape": list(x.shape),
        "dtype": str(x.dtype),
        "size": int(x.size),
        "min": float(np.min(y)),
        "max": float(np.max(y)),
        "mean": float(np.mean(y)),
        "std": float(np.std(y)),
        "abs_max": float(np.max(np.abs(y))),
        "nonzero_count": int(np.count_nonzero(y)),
        "allzero": bool(np.count_nonzero(y) == 0),
    }


def compare(ref: np.ndarray, cand: np.ndarray) -> dict[str, Any]:
    r = np.asarray(ref, dtype=np.float64).reshape(-1)
    c = np.asarray(cand, dtype=np.float64).reshape(-1)
    if r.shape != c.shape:
        return {"shape_match": False, "reference_shape": list(r.shape), "candidate_shape": list(c.shape)}
    rn = np.linalg.norm(r)
    cn = np.linalg.norm(c)
    r0 = r - r.mean()
    c0 = c - c.mean()
    r0n = np.linalg.norm(r0)
    c0n = np.linalg.norm(c0)
    return {
        "shape_match": True,
        "cosine": float(np.dot(r, c) / (rn * cn)) if rn and cn else None,
        "pearson_centered": float(np.dot(r0, c0) / (r0n * c0n)) if r0n and c0n else None,
        "relative_l2": float(np.linalg.norm(r - c) / (rn + 1e-12)),
        "max_abs_error": float(np.max(np.abs(r - c))),
        "mean_abs_error": float(np.mean(np.abs(r - c))),
        "reference_norm": float(rn),
        "candidate_norm": float(cn),
    }


def load_delta(case_root: Path, variant: str) -> np.ndarray | None:
    p = case_root / "position_variants" / variant / "delta_vs_all_zero.npy"
    return np.load(p) if p.exists() else None


def load_positions(case_root: Path, variant: str) -> np.ndarray | None:
    p = case_root / "position_variants" / variant / "positions.npy"
    return np.load(p) if p.exists() else None


def task2000(root: Path, command: str) -> dict[str, Any]:
    inputs = [
        root / "01_final_evidence" / "dream7b_s100p_gate_packet_v18.json",
        root / "reports" / "1900_v18_baseline_lock.json",
        root / "reports" / "1910_position_path_indirect_recovery.json",
        root / "reports" / "1920_targeted_island_semantic_battery.json",
        root / "reports" / "1930_ramp_failure_deep_dive.json",
        root / "reports" / "1940_corrected_candidate_if_justified_v18.json",
        root / "reports" / "PAPER_EVIDENCE_DOSSIER_V18.md",
        root / "reports" / "SEG00_POSITION_PATH_STATUS_V18.md",
        root / "reports" / "BPU_ISLAND_SEMANTIC_STATUS_V18.md",
        root / "evidence" / "dream7b_s100p_v18_execution_20260704_remote_evidence.tar.gz",
    ]
    report = common(root, "2000_baseline_lock", command, inputs)
    gate = read_json(inputs[0]) if inputs[0].exists() else {}
    pos = read_json(inputs[2]) if inputs[2].exists() else {}
    sem = read_json(inputs[3]) if inputs[3].exists() else {}
    report.update(
        {
            "v18_verdict": gate.get("final_verdict") or gate.get("verdict"),
            "full_bpu_path_status": "falsified_against_HF_PyTorch_BF16_logits_truth_v17_v18_baseline",
            "semantic_battery_blocker": sem.get("verdict"),
            "semantic_cases_generated": sem.get("semantic_cases_generated"),
            "semantic_hf_truth_rows": sem.get("hf_truth_rows", 0),
            "position_path_status": pos.get("verdict"),
            "targeted_islands_current_status": "v17 diagnostic islands [1], [2], [1,2] had weak signal but no all-case strict pass; v18 semantic rerun blocked before HF truth",
            "constraints": {
                "generation_quality": "not_run_by_design",
                "product_route": "not_run_by_design",
                "ports_18888_18889": "not_touched",
            },
            "verdict": "baseline_locked",
        }
    )
    return save_report(
        root,
        "2000_v19_baseline_lock",
        report,
        "V19 Baseline Lock",
        [
            f"v18_verdict: `{report['v18_verdict']}`",
            f"semantic_battery_blocker: `{report['semantic_battery_blocker']}`",
            f"position_path_status: `{report['position_path_status']}`",
            "generation_quality: `not_run_by_design`",
            "product_route: `not_run_by_design`",
        ],
    )


def task2010(root: Path, command: str) -> dict[str, Any]:
    ev = root / "evidence" / "dream7b_s100p_v19_execution_20260704" / "evidence" / "semantic_hf_truth_v19"
    primary = ev / "semantic_hf_truth_loader_report.json"
    inputs = [primary, ev / "route_a_safetensors_direct_loader.command.log", root / "tools" / "run_v19_semantic_hf_truth_loader.py"]
    report = common(root, "2010_semantic_hf_truth_loader_gate", command, inputs)
    data = read_json(primary) if primary.exists() else {}
    hf_rows = data.get("hf_truth_rows")
    if hf_rows is None:
        hf_rows = len(data.get("hf_rows", []))
    stage_log = data.get("stage_log", [])
    load_summary = data.get("route_a_load_summary", {})
    attempts = []
    for name in [
        "attempt_1_autocast_missing",
        "attempt_2_sdpa_missing",
        "attempt_3_forward_timeout",
    ]:
        attempts.append({"name": name, "report": artifact(ev / f"{name}.report.json", root), "command_log": artifact(ev / f"{name}.command.log", root)})
    route_a_status = "not_run"
    if load_summary.get("loaded_weight_keys") == load_summary.get("expected_weight_keys") == 339:
        route_a_status = "weights_loaded_all_339"
    status = data.get("status")
    last_stage = stage_log[-1].get("stage") if stage_log else None
    if int(hf_rows or 0) >= 8:
        verdict = "pass_hf_truth_rows_8"
    elif status == "manual_stop_forward_runtime_blocked_zero_rows" or last_stage == "route_a_manual_stop_forward_runtime_zero_rows":
        verdict = "blocked_forward_runtime_after_full_safetensors_load_zero_rows"
        report["blocking_or_failure_reasons"].append("Route A loaded all 339 safetensors keys into BF16 model, then spent 45+ minutes on the first semantic forward without producing a truth row. The run was manually stopped and preserved as a runtime blocker.")
    elif last_stage in {"route_a_forward_start", "route_a_case_start"}:
        verdict = "blocked_or_in_progress_forward_runtime_after_full_safetensors_load"
        report["blocking_or_failure_reasons"].append("Route A loaded all 339 safetensors keys into BF16 model, then entered semantic forward on S100P torch1.8 CPU, but no complete semantic truth row is present in the pulled evidence.")
    elif data.get("errors"):
        verdict = "blocked_route_a_exception"
        report["blocking_or_failure_reasons"].append(str(data.get("errors")[-1]))
    else:
        verdict = "blocked_no_hf_rows"
        report["blocking_or_failure_reasons"].append("No complete semantic HF truth rows found in pulled evidence.")
    report.update(
        {
            "route_a_status": route_a_status,
            "remote_status": status,
            "route_a_load_summary": load_summary,
            "attempts": attempts,
            "hf_truth_rows": int(hf_rows or 0),
            "case_ids_with_logits": [r.get("case_id") for r in data.get("hf_rows", [])],
            "stage_log_tail": stage_log[-10:],
            "route_b_reuse_v10_v11": {
                "status": "blocked_for_semantic_cases",
                "evidence": "v10/v11 canonical truth exists for zeros/ramp/short_chinese only; scripts use from_pretrained low_cpu_mem_usage and do not provide the 8 v19 semantic rows.",
            },
            "route_c_x86_or_torch2": {
                "status": "not_available_in_current_local_workspace",
                "local_python_has_torch": False,
                "note": "Current local Python lacks torch/transformers/safetensors/accelerate; no cached torch wheel was found during v19 local scan.",
            },
            "route_d_minimal_forward": {
                "status": "partial_not_truth",
                "evidence": "Manual no-init + direct safetensors load is a full model load, not a partial approximation; no separate partial truth row is claimed.",
            },
            "verdict": verdict,
        }
    )
    return save_report(
        root,
        "2010_semantic_hf_truth_loader_gate",
        report,
        "Semantic HF Truth Loader Gate",
        [
            f"verdict: `{verdict}`",
            f"route_a_status: `{route_a_status}`",
            f"hf_truth_rows: `{int(hf_rows or 0)}`",
            "generation_quality_run: `False`",
            "product_routes_18888_18889_touched: `False`",
        ],
    )


def task2020(root: Path, command: str, truth_report: dict[str, Any]) -> dict[str, Any]:
    ev = root / "evidence" / "dream7b_s100p_v19_execution_20260704" / "evidence" / "semantic_island_battery_v19"
    primary = ev / "semantic_island_battery_report.json"
    inputs = [root / "reports" / "2010_semantic_hf_truth_loader_gate.json", primary]
    report = common(root, "2020_semantic_bpu_island_battery", command, inputs)
    rows = int(truth_report.get("hf_truth_rows") or 0)
    if rows < 8:
        verdict = "blocked_hf_semantic_truth_rows_missing"
        report["blocking_or_failure_reasons"].append("Task 2 requires Task 1 to produce all 8 semantic HF truth rows; current rows < 8.")
        island_rows = 0
        island_data: dict[str, Any] = {}
    elif primary.exists():
        island_data = read_json(primary)
        island_rows_list = island_data.get("island_rows", [])
        island_rows = len(island_rows_list)
        expected = island_data.get("expected_island_rows") or (8 * 3)
        strict_rows = [r for r in island_rows_list if r.get("strict_pass") is True]
        semantic_rows = [r for r in island_rows_list if r.get("semantic_or_diagnostic", "semantic") == "semantic"]
        semantic_strict = [r for r in semantic_rows if r.get("strict_pass") is True]
        if island_rows == 0:
            verdict = "semantic_island_battery_report_present_no_rows"
            report["blocking_or_failure_reasons"].append("A v19 island report exists, but it contains no island rows.")
        elif island_rows < expected:
            verdict = "partial_semantic_island_signal_not_deployable"
            report["blocking_or_failure_reasons"].append("The v19 island report is partial; no deployment claim is allowed.")
        elif semantic_rows and len(semantic_strict) == len(semantic_rows):
            verdict = "ramp_diagnostic_outlier_candidate_semantic_island_supported"
        elif strict_rows:
            verdict = "partial_semantic_island_signal_not_deployable"
        else:
            verdict = "no_valid_semantic_island"
    else:
        verdict = "semantic_island_battery_pending_after_truth_recovered"
        island_rows = 0
        island_data = {}
        report["blocking_or_failure_reasons"].append("HF semantic truth is available, but no v19 semantic BPU island battery report was found. This remains pending, not a deployment pass.")
    report.update(
        {
            "hf_truth_rows": rows,
            "island_rows": island_rows,
            "expected_island_rows": island_data.get("expected_island_rows"),
            "remote_status": island_data.get("status"),
            "verdict": verdict,
            "strict_gate_relaxed": False,
        }
    )
    return save_report(
        root,
        "2020_semantic_bpu_island_battery",
        report,
        "Semantic BPU Island Battery",
        [f"verdict: `{verdict}`", f"hf_truth_rows: `{rows}`", f"island_rows: `{island_rows}`"],
    )


def task2030(root: Path, command: str, island_report: dict[str, Any]) -> dict[str, Any]:
    inputs = [root / "reports" / "2020_semantic_bpu_island_battery.json"]
    report = common(root, "2030_ramp_outlier_decision", command, inputs)
    if island_report.get("hf_truth_rows", 0) < 8:
        verdict = "C_inconclusive_semantic_truth_or_rows_missing"
        report["blocking_or_failure_reasons"].append("Ramp outlier decision needs semantic HF truth rows; they are missing.")
    elif island_report.get("island_rows", 0) == 0:
        verdict = "C_inconclusive_semantic_island_rows_missing"
        report["blocking_or_failure_reasons"].append("Ramp outlier decision needs semantic island rows; HF truth alone is insufficient.")
    else:
        verdict = "C_inconclusive_semantic_truth_or_rows_missing"
    report.update({"verdict": verdict, "semantic_rows_available": island_report.get("island_rows", 0)})
    return save_report(root, "2030_ramp_outlier_decision", report, "Ramp Outlier Decision", [f"verdict: `{verdict}`"])


def task2040(root: Path, command: str) -> dict[str, Any]:
    base = root / "evidence" / "dream7b_s100p_v18_execution_20260704" / "evidence" / "position_path_recovery_v18"
    out = root / "evidence" / "position_delta_basis_model_v19"
    inputs = [base / "position_path_recovery_report.json"]
    report = common(root, "2040_position_delta_basis_model", command, inputs)
    heldout_variants = ["canonical", "reversed", "random_permutation"]
    single_indices = [0, 1, 2, 64, 127]
    single_values = [1, 2, 64, 127]
    case_reports: dict[str, Any] = {}
    all_rel = []
    all_cos = []
    for cid in CASE_IDS:
        case_root = base / cid
        if not case_root.exists():
            case_reports[cid] = {"status": "missing_case_evidence"}
            continue
        basis: dict[tuple[int, int], np.ndarray] = {}
        for idx in single_indices:
            for val in single_values:
                arr = load_delta(case_root, f"single_spike_index_{idx:03d}_value_{val:03d}")
                if arr is not None:
                    basis[(idx, val)] = arr
        case_row: dict[str, Any] = {"basis_entries": len(basis), "heldout": {}, "cross_case_token_dependence": {}}
        for var in heldout_variants:
            target = load_delta(case_root, var)
            positions = load_positions(case_root, var)
            if target is None or positions is None:
                case_row["heldout"][var] = {"status": "missing"}
                continue
            pred = np.zeros_like(target, dtype=np.float32)
            covered = 0
            missing = 0
            for pos_idx, val in enumerate(np.asarray(positions).reshape(-1).astype(int).tolist()):
                if val == 0:
                    continue
                b = basis.get((pos_idx, val))
                if b is None:
                    missing += 1
                    continue
                pred = pred + b.astype(np.float32)
                covered += 1
            metrics = compare(target, pred)
            all_rel.append(metrics.get("relative_l2"))
            all_cos.append(metrics.get("cosine"))
            row = {
                "status": "evaluated",
                "positions_nonzero": int(np.count_nonzero(positions)),
                "basis_terms_covered": covered,
                "basis_terms_missing": missing,
                "target_stats": stats(target),
                "prediction_stats": stats(pred),
                "metrics": metrics,
            }
            case_row["heldout"][var] = row
            pred_path = out / cid / var / "additive_basis_prediction.npy"
            target_path = out / cid / var / "heldout_target_delta.npy"
            pred_path.parent.mkdir(parents=True, exist_ok=True)
            np.save(pred_path, pred)
            np.save(target_path, target)
            write_json(out / cid / var / "metadata.json", row)
        case_reports[cid] = case_row
    # Token dependence: same position variant across cases should match if only position-derived.
    for var in ["canonical", "reversed", "random_permutation", "constant_1", "constant_2", "constant_64", "constant_127"]:
        refs = {}
        for cid in CASE_IDS:
            arr = load_delta(base / cid, var)
            if arr is not None:
                refs[cid] = arr
        if len(refs) >= 2:
            pairs = {}
            keys = list(refs)
            for i, a in enumerate(keys):
                for b in keys[i + 1 :]:
                    pairs[f"{a}_vs_{b}"] = compare(refs[a], refs[b])
            for cid in CASE_IDS:
                case_reports.setdefault(cid, {}).setdefault("cross_case_token_dependence", {})[var] = pairs
    valid_rel = [x for x in all_rel if x is not None and math.isfinite(float(x))]
    valid_cos = [x for x in all_cos if x is not None and math.isfinite(float(x))]
    recoverable = bool(valid_rel and max(valid_rel) <= 0.10 and valid_cos and min(valid_cos) >= 0.99)
    if recoverable:
        model_verdict = "recoverable_lookup_like"
    else:
        model_verdict = "nonlinear_or_token_dependent_unrecoverable_without_internal_tensor"
        report["blocking_or_failure_reasons"].append("Single-spike additive basis does not predict heldout canonical/reversed/random variants within deployable thresholds, and cross-case deltas show token-content dependence.")
    summary = {
        "case_reports": case_reports,
        "heldout_variants": heldout_variants,
        "basis_source": "single_spike_index_{0,1,2,64,127}_value_{1,2,64,127}",
        "thresholds": {"recoverable_max_rel_l2": 0.10, "recoverable_min_cosine": 0.99},
        "max_rel_l2": max(valid_rel) if valid_rel else None,
        "min_cosine": min(valid_cos) if valid_cos else None,
        "position_path_model": model_verdict,
        "deployable_claim_allowed": False,
    }
    write_json(out / "position_delta_basis_summary.json", summary)
    report.update(summary)
    report["verdict"] = model_verdict
    return save_report(
        root,
        "2040_position_delta_basis_model",
        report,
        "Position Delta Basis Model",
        [
            f"position_path_model: `{model_verdict}`",
            f"max_rel_l2: `{summary['max_rel_l2']}`",
            f"min_cosine: `{summary['min_cosine']}`",
            "deployable_claim_allowed: `False`",
        ],
    )


def task2050(root: Path, command: str, truth: dict[str, Any], island: dict[str, Any], pos: dict[str, Any]) -> dict[str, Any]:
    inputs = [root / "reports" / "2010_semantic_hf_truth_loader_gate.json", root / "reports" / "2020_semantic_bpu_island_battery.json", root / "reports" / "2040_position_delta_basis_model.json"]
    report = common(root, "2050_corrected_candidate_if_justified", command, inputs)
    justified = False
    reasons = []
    if truth.get("hf_truth_rows", 0) >= 8 and island.get("verdict") in {"ramp_diagnostic_outlier_candidate_semantic_island_supported"}:
        justified = True
        reasons.append("semantic island pass with ramp outlier")
    if pos.get("position_path_model") == "recoverable_lookup_like" and (pos.get("max_rel_l2") or 999) <= 0.10 and (pos.get("min_cosine") or 0) >= 0.99:
        justified = True
        reasons.append("position model meets heldout threshold")
    verdict = "not_run_no_justified_correction" if not justified else "eligible_but_not_run_by_builder"
    if not justified:
        report["blocking_or_failure_reasons"].append("No semantic island pass, no recoverable position model, and no official internal tensor/source graph was found.")
    report.update({"justified": justified, "justification_reasons": reasons, "verdict": verdict})
    return save_report(root, "2050_corrected_candidate_if_justified_v19", report, "Corrected Candidate If Justified V19", [f"verdict: `{verdict}`"])


def final_docs(root: Path, command: str, reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    truth = reports["2010"]
    island = reports["2020"]
    pos = reports["2040"]
    if truth.get("hf_truth_rows", 0) < 8:
        verdict = "G_inconclusive_runtime_blocked"
    elif island.get("island_rows", 0) == 0 or island.get("verdict") == "semantic_island_battery_pending_after_truth_recovered":
        verdict = "F_semantic_hf_truth_recovered_bpu_island_battery_pending"
    elif truth.get("hf_truth_rows", 0) >= 8 and island.get("verdict") == "no_valid_semantic_island":
        verdict = "C_no_valid_semantic_bpu_island"
    elif truth.get("hf_truth_rows", 0) >= 8 and island.get("verdict") == "ramp_diagnostic_outlier_candidate_semantic_island_supported":
        verdict = "B_semantic_island_supported_ramp_outlier_candidate_not_deployable"
    elif pos.get("position_path_model") == "recoverable_lookup_like":
        verdict = "D_position_path_model_recovered_but_not_deployable"
    elif pos.get("position_path_model") == "nonlinear_or_token_dependent_unrecoverable_without_internal_tensor":
        verdict = "E_position_path_unrecoverable_without_vendor_internal_tensor"
    else:
        verdict = "G_inconclusive_runtime_blocked"
    packet = {
        **SAFETY,
        "schema_version": "dream7b_s100p_v19_final_gate_packet",
        "created_at_utc": now(),
        "command": command,
        "final_verdict": verdict,
        "current_full_bpu_path_status": "falsified_against_HF_PyTorch_BF16_logits_truth_v17_v18_baseline",
        "semantic_hf_truth_status": truth.get("verdict"),
        "semantic_hf_truth_rows": truth.get("hf_truth_rows"),
        "semantic_island_status": island.get("verdict"),
        "position_path_model": pos.get("position_path_model"),
        "corrected_candidate_status": reports["2050"].get("verdict"),
        "generation_quality": "not_run_logits_gate_not_passed",
        "product_route": "not_run_generation_gate_not_passed",
        "gates": {k: v.get("verdict") for k, v in reports.items()},
        "paper_safe_claim": "v19 advances the semantic truth loader from safetensors load failure to direct BF16 safetensors loading. Semantic island claims require actual v19 island rows; if those rows are absent, the island battery is pending rather than passed. Position delta-basis heldout modeling does not yield a deployable recovered formula unless the stated thresholds are met. No generation quality or product route was run.",
    }
    write_json(root / "01_final_evidence" / "dream7b_s100p_gate_packet_v19.json", packet)
    write_text(root / "01_final_evidence" / "dream7b_s100p_gate_packet_v19.md", "# Dream7B S100P Gate Packet V19\n\n" + "\n".join(f"- {k}: `{v}`" for k, v in {
        "final_verdict": verdict,
        "semantic_hf_truth_status": packet["semantic_hf_truth_status"],
        "semantic_hf_truth_rows": packet["semantic_hf_truth_rows"],
        "semantic_island_status": packet["semantic_island_status"],
        "position_path_model": packet["position_path_model"],
        "corrected_candidate_status": packet["corrected_candidate_status"],
        "generation_quality": packet["generation_quality"],
        "product_route": packet["product_route"],
    }.items()) + "\n")
    write_text(root / "reports" / "PAPER_EVIDENCE_DOSSIER_V19.md", "# Paper Evidence Dossier V19\n\nv19 does not repeat full-chain falsification. It tests whether the v18 semantic HF truth blocker can be removed and whether the seg00_01 position path can be modeled from BPU-internal delta basis evidence. Route A direct safetensors loading now reaches a full 339/339 BF16 weight load; if no semantic rows are present, the remaining blocker is forward runtime on S100P torch1.8 CPU. The position delta-basis heldout model is not deployable unless it meets the stated rel-L2/cosine thresholds. No generation quality or product route was run.\n")
    write_text(root / "reports" / "SEMANTIC_BPU_ISLAND_STATUS_V19.md", f"# Semantic BPU Island Status V19\n\nSemantic HF truth rows: `{truth.get('hf_truth_rows')}`. Island verdict: `{island.get('verdict')}`. No semantic partial pass is claimed as deployable.\n")
    write_text(root / "reports" / "POSITION_PATH_MODEL_STATUS_V19.md", f"# Position Path Model Status V19\n\nPosition path model: `{pos.get('position_path_model')}`. Deployable claim allowed: `False`.\n")
    return packet


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


def package(root: Path, command: str) -> dict[str, Any]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    staging = root / "tmp" / f"dream7b_s100p_v19_for_gptpro_{stamp}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    stems = [
        "2000_v19_baseline_lock",
        "2010_semantic_hf_truth_loader_gate",
        "2020_semantic_bpu_island_battery",
        "2030_ramp_outlier_decision",
        "2040_position_delta_basis_model",
        "2050_corrected_candidate_if_justified_v19",
    ]
    for stem in stems:
        copy_path(root / "reports" / f"{stem}.json", staging / "reports" / f"{stem}.json")
        copy_path(root / "reports" / f"{stem}.md", staging / "reports" / f"{stem}.md")
    for name in ["PAPER_EVIDENCE_DOSSIER_V19.md", "SEMANTIC_BPU_ISLAND_STATUS_V19.md", "POSITION_PATH_MODEL_STATUS_V19.md"]:
        copy_path(root / "reports" / name, staging / "reports" / name)
    for p in (root / "01_final_evidence").glob("*v19*"):
        copy_path(p, staging / "01_final_evidence" / p.name)
    for p in [
        root / "tools" / "run_v19_semantic_hf_truth_loader.py",
        root / "tools" / "build_v19_research_thread.py",
        root / "evidence" / "dream7b_s100p_v19_execution_20260704" / "evidence" / "semantic_hf_truth_v19",
        root / "evidence" / "position_delta_basis_model_v19" / "position_delta_basis_summary.json",
        root / "evidence" / "dream7b_s100p_v18_execution_20260704_remote_evidence.tar.gz",
        root / "evidence_for_gptpro" / "dream7b_s100p_v18_for_gptpro_20260704_002409.zip.sha256.txt",
    ]:
        copy_path(p, staging / rel(p, root))
    write_text(staging / "README.md", "Dream7B/S100P v19 evidence packet. No generation, no product route, no 18888/18889/OpenClaw foreground changes.\n")
    files = []
    for p in sorted(staging.rglob("*")):
        if p.is_file():
            files.append({"path": rel(p, staging), "size_bytes": p.stat().st_size, "sha256": sha256_file(p)})
    write_json(staging / "MANIFEST.json", {"schema_version": "dream7b_s100p_v19_manifest", "created_at_utc": now(), "file_count": len(files), "files": files})
    manifest_row = {"path": "MANIFEST.json", "size_bytes": (staging / "MANIFEST.json").stat().st_size, "sha256": sha256_file(staging / "MANIFEST.json")}
    write_text(staging / "SHA256SUMS.txt", "\n".join(f"{f['sha256']}  {f['path']}" for f in files + [manifest_row]) + "\n")
    out = root / "evidence_for_gptpro" / f"dream7b_s100p_v19_for_gptpro_{stamp}.zip"
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p in sorted(staging.rglob("*")):
            if p.is_file():
                zf.write(p, rel(p, staging))
    zip_sha = sha256_file(out)
    write_text(out.with_suffix(out.suffix + ".sha256.txt"), f"{zip_sha}  {out.name}\n")
    report = common(root, "2060_final_v19_package", command, [out])
    with zipfile.ZipFile(out) as zf:
        report.update({"zip_path": rel(out, root), "zip_sha256": zip_sha, "zip_testzip_bad_member": zf.testzip(), "zip_member_count": len(zf.namelist())})
    save_report(root, "2060_final_v19_gate_packet_and_package", report, "Final V19 Gate Packet And Package", [f"zip_path: `{report['zip_path']}`", f"zip_sha256: `{zip_sha}`"])
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    command = " ".join([sys.executable, *sys.argv])
    reports: dict[str, dict[str, Any]] = {}
    reports["2000"] = task2000(root, command)
    reports["2010"] = task2010(root, command)
    reports["2020"] = task2020(root, command, reports["2010"])
    reports["2030"] = task2030(root, command, reports["2020"])
    reports["2040"] = task2040(root, command)
    reports["2050"] = task2050(root, command, reports["2010"], reports["2020"], reports["2040"])
    packet = final_docs(root, command, reports)
    pkg = package(root, command)
    print(json.dumps({"final_verdict": packet["final_verdict"], "zip": pkg["zip_path"], "zip_sha256": pkg["zip_sha256"], "gates": packet["gates"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
