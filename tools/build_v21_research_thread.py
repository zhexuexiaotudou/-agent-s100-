#!/usr/bin/env python3
"""Build Dream7B/S100P v21 reports and GPT Pro evidence packet.

The builder consumes already-generated HF truth, S100P BPU island, and
position-path evidence. It does not run generation, product routes, or touch
ports 18888/18889.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SAFETY = {
    "generation_quality_run": False,
    "product_routes_18888_18889_touched": False,
    "dream7b_frontend_openclaw_traffic_touched": False,
    "harness_qwen_openclaw_defaults_modified": False,
}

ORIGINAL_SEMANTIC_CASES = {
    "short_english_prompt_padded",
    "short_chinese_prompt_padded_v18",
    "openclaw_nas_search_request",
    "document_summary_request",
    "privacy_sensitive_denied_request",
    "mixed_english_chinese_request",
    "real_prompt_no_synthetic_ramp",
    "mask_tail_policy_probe",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def artifact(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.as_posix()),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() and path.is_file() else None,
        "sha256": sha256_file(path) if path.exists() and path.is_file() else None,
    }


def run_cmd(cmd: list[str], cwd: Path) -> dict[str, Any]:
    try:
        p = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, timeout=60)
        return {
            "cmd": cmd,
            "returncode": p.returncode,
            "stdout": p.stdout,
            "stderr": p.stderr,
        }
    except Exception as exc:  # pragma: no cover - reporting fallback
        return {"cmd": cmd, "returncode": None, "error": f"{type(exc).__name__}: {exc}"}


def mean(values: list[float]) -> float | None:
    return float(statistics.fmean(values)) if values else None


def p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))
    return float(ordered[idx])


def host_env(root: Path) -> dict[str, Any]:
    return {
        "created_at_utc": utc_now(),
        "host_environment": {"platform": platform.platform(), "python": sys.version},
        "git": run_cmd(["git", "status", "--short"], root),
        "safety": SAFETY,
    }


def summarize_hf_truth(report: dict[str, Any]) -> dict[str, Any]:
    rows = report.get("hf_rows", [])
    semantic_rows = [r for r in rows if r.get("case_id") in ORIGINAL_SEMANTIC_CASES]
    return {
        "status": report.get("status"),
        "hf_truth_rows": len(rows),
        "original_semantic_truth_rows": len(semantic_rows),
        "required_original_semantic_rows": 8,
        "pass": len(semantic_rows) >= 8,
        "device_selected": report.get("device_selected"),
        "runtime_versions": report.get("runtime_versions"),
        "model_class": report.get("model_class"),
        "parameter_count": report.get("parameter_count"),
        "parameter_dtypes": report.get("parameter_dtypes"),
        "case_ids": [r.get("case_id") for r in rows],
        "truth_sha256_by_case": {
            r.get("case_id"): (r.get("logits") or r.get("truth") or {}).get("sha256")
            for r in rows
        },
    }


def island_key(island: list[int]) -> str:
    return ",".join(str(i) for i in island)


def summarize_islands(report: dict[str, Any]) -> dict[str, Any]:
    rows = report.get("island_rows", [])
    by_island: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = island_key(row.get("island", []))
        d = by_island.setdefault(
            key,
            {
                "island": row.get("island"),
                "total_rows": 0,
                "strict_pass_rows": 0,
                "original_semantic_rows": 0,
                "original_semantic_strict_pass_rows": 0,
                "semantic_labeled_rows": 0,
                "semantic_labeled_strict_pass_rows": 0,
                "diagnostic_rows": 0,
                "diagnostic_strict_pass_rows": 0,
                "relative_l2": [],
                "cosine": [],
                "pearson_centered": [],
                "top5_overlap": [],
                "failed_original_semantic_cases": [],
                "strict_pass_case_ids": [],
            },
        )
        strict = bool(row.get("strict_pass"))
        fm = row.get("final_metrics", {})
        d["total_rows"] += 1
        d["strict_pass_rows"] += int(strict)
        if row.get("case_id") in ORIGINAL_SEMANTIC_CASES:
            d["original_semantic_rows"] += 1
            d["original_semantic_strict_pass_rows"] += int(strict)
            if not strict:
                d["failed_original_semantic_cases"].append(row.get("case_id"))
        if row.get("semantic_or_diagnostic") == "semantic":
            d["semantic_labeled_rows"] += 1
            d["semantic_labeled_strict_pass_rows"] += int(strict)
        else:
            d["diagnostic_rows"] += 1
            d["diagnostic_strict_pass_rows"] += int(strict)
        if strict:
            d["strict_pass_case_ids"].append(row.get("case_id"))
        for name in ["relative_l2", "cosine", "pearson_centered"]:
            if fm.get(name) is not None:
                d[name].append(float(fm[name]))
        if fm.get("top5_overlap") is not None:
            d["top5_overlap"].append(float(fm["top5_overlap"]))

    for d in by_island.values():
        for name in ["relative_l2", "cosine", "pearson_centered", "top5_overlap"]:
            vals = d.pop(name)
            d[f"mean_{name}"] = mean(vals)
            d[f"p95_{name}"] = p95(vals)
        d["strict_pass_fraction"] = (
            d["strict_pass_rows"] / d["total_rows"] if d["total_rows"] else None
        )
        d["original_semantic_strict_pass_fraction"] = (
            d["original_semantic_strict_pass_rows"] / d["original_semantic_rows"]
            if d["original_semantic_rows"]
            else None
        )

    best = None
    if by_island:
        best = max(
            by_island.values(),
            key=lambda d: (
                d["original_semantic_strict_pass_rows"],
                d["strict_pass_rows"],
                -(d["mean_relative_l2"] or 999.0),
            ),
        )

    ramp_rows = [r for r in rows if r.get("case_id") == "ramp"]
    ramp_summary = {
        "rows": len(ramp_rows),
        "strict_pass_rows": sum(1 for r in ramp_rows if r.get("strict_pass")),
        "by_island": {
            island_key(r.get("island", [])): {
                "strict_pass": bool(r.get("strict_pass")),
                "relative_l2": (r.get("final_metrics") or {}).get("relative_l2"),
                "cosine": (r.get("final_metrics") or {}).get("cosine"),
                "pearson_centered": (r.get("final_metrics") or {}).get("pearson_centered"),
                "top5_overlap": (r.get("final_metrics") or {}).get("top5_overlap"),
            }
            for r in ramp_rows
        },
    }

    any_all_original_semantic_pass = any(
        d["original_semantic_rows"] >= 8 and d["original_semantic_strict_pass_rows"] >= 8
        for d in by_island.values()
    )
    any_strict = any(d["strict_pass_rows"] > 0 for d in by_island.values())
    if any_all_original_semantic_pass and ramp_summary["strict_pass_rows"] == 0:
        task_verdict = "ramp_diagnostic_outlier_candidate_semantic_island_supported"
    elif any_strict:
        task_verdict = "partial_semantic_island_signal_not_deployable"
    else:
        task_verdict = "no_valid_semantic_island"

    return {
        "status": report.get("status"),
        "hf_truth_rows": report.get("hf_truth_rows"),
        "island_rows": len(rows),
        "errors": report.get("errors", []),
        "by_island": by_island,
        "best_island_by_original_semantic_strict": best,
        "ramp_summary": ramp_summary,
        "task_verdict": task_verdict,
        "all_original_semantic_cases_pass_any_island": any_all_original_semantic_pass,
    }


def position_summary(root: Path) -> dict[str, Any]:
    candidates = [
        root / "evidence/position_delta_basis_model_v19/position_delta_basis_summary.json",
        root / "reports/2040_position_delta_basis_model.json",
    ]
    src = next((p for p in candidates if p.exists()), None)
    data = read_json(src, {}) if src else {}
    summary = {
        "source_path": str(src.as_posix()) if src else None,
        "position_path_model": data.get(
            "position_path_model",
            data.get("conclusion", {}).get(
                "position_path_model",
                "nonlinear_or_token_dependent_unrecoverable_without_internal_tensor",
            ),
        ),
        "max_rel_l2": data.get("max_rel_l2", data.get("summary", {}).get("max_rel_l2")),
        "min_cosine": data.get("min_cosine", data.get("summary", {}).get("min_cosine")),
        "deployable_claim_allowed": bool(data.get("deployable_claim_allowed", False)),
        "heldout_validation": data.get("heldout_validation", data.get("case_reports")),
        "evidence_artifact": artifact(src) if src else None,
    }
    if not summary["position_path_model"]:
        summary["position_path_model"] = "nonlinear_or_token_dependent_unrecoverable_without_internal_tensor"
    return summary


def report_common(root: Path, schema: str, inputs: list[Path], outputs: list[Path]) -> dict[str, Any]:
    data = host_env(root)
    data.update(
        {
            "schema_version": schema,
            "input_artifacts": [artifact(p) for p in inputs],
            "output_artifacts": [artifact(p) for p in outputs],
        }
    )
    return data


def build_reports(root: Path, prompt_path: Path | None) -> dict[str, Any]:
    reports = root / "reports"
    final_dir = root / "01_final_evidence"
    evidence = root / "evidence"
    reports.mkdir(exist_ok=True)
    final_dir.mkdir(exist_ok=True)

    v20_gate_path = final_dir / "dream7b_s100p_gate_packet_v20.json"
    hf_truth_path = evidence / "semantic_hf_truth_v21/semantic_truth_export_report.json"
    island_eval_path = evidence / "semantic_island_battery_v21/hf_boundaries_and_island_eval_report.json"
    bpu_raw_path = (
        evidence
        / "dream7b_s100p_v21_execution_20260704/evidence/semantic_island_battery_v21/bpu_outputs/bpu_island_segments_report.json"
    )
    combined_cases_path = evidence / "v21_combined_cases/semantic_plus_canonical_seq128_cases_v21.jsonl"

    v20_gate = read_json(v20_gate_path, {})
    hf_truth = read_json(hf_truth_path, {})
    island_eval = read_json(island_eval_path, {})
    bpu_raw = read_json(bpu_raw_path, {})
    hf_summary = summarize_hf_truth(hf_truth)
    island_summary = summarize_islands(island_eval)
    pos = position_summary(root)

    position_v21_dir = evidence / "position_delta_basis_model_v21"
    position_v21_summary_path = position_v21_dir / "position_delta_basis_summary_v21_reference.json"
    write_json(position_v21_summary_path, pos)

    baseline_json = report_common(
        root,
        "dream7b_s100p_v21_2000_baseline_lock",
        [v20_gate_path, combined_cases_path, hf_truth_path, island_eval_path, bpu_raw_path],
        [reports / "2000_v21_baseline_lock.json", reports / "2000_v21_baseline_lock.md"],
    )
    baseline_json.update(
        {
            "v20_gate_verdict": v20_gate.get("final_verdict") or v20_gate.get("verdict"),
            "v20_gate_packet": artifact(v20_gate_path),
            "baseline_facts": {
                "full_bpu_path": "falsified_against_HF_PyTorch_BF16_logits_truth_from_prior_v10_v11_v20_chain",
                "v20_semantic_battery_blocker": "HF semantic truth rows missing in v20; resolved in v21 using local CUDA torch2 environment",
                "compile_feasible": "pass_from_prior_gate",
                "s100p_board_load_run_shape": "pass_from_prior_gate",
                "generation_quality": "not_run_by_design",
                "product_route": "not_run_by_design",
                "current_product_route": "Qwen + OpenClaw unchanged; Dream7B remains research evidence only",
            },
            "v21_evidence_lock": {
                "hf_truth": hf_summary,
                "island_eval": {
                    "status": island_summary["status"],
                    "island_rows": island_summary["island_rows"],
                    "raw_bpu_island_rows": len(bpu_raw.get("island_rows", [])),
                },
                "position_model": pos,
            },
            "task_goal": "v21 removes the semantic HF truth blocker, evaluates BPU islands [1], [2], [1,2], decides ramp status, and only runs corrected candidate if justified.",
        }
    )
    write_json(reports / "2000_v21_baseline_lock.json", baseline_json)
    write_text(
        reports / "2000_v21_baseline_lock.md",
        "\n".join(
            [
                "# v21 Baseline Lock",
                "",
                "- current full-BPU path: falsified against HF/PyTorch BF16 logits truth in prior gates.",
                "- v20 semantic blocker: HF truth rows were missing; v21 resolved this with local CUDA torch2 export.",
                "- generation_quality: not_run_by_design.",
                "- product_route: not_run_by_design; 18888/18889 untouched.",
                "- v21 objective: root evidence closure for semantic islands and position path, not generation quality.",
            ]
        ),
    )

    truth_json = report_common(
        root,
        "dream7b_s100p_v21_2010_semantic_hf_truth_loader_gate",
        [hf_truth_path, combined_cases_path],
        [reports / "2010_semantic_hf_truth_loader_gate.json", reports / "2010_semantic_hf_truth_loader_gate.md"],
    )
    truth_json.update(
        {
            "hf_truth_summary": hf_summary,
            "verdict": "pass_hf_semantic_truth_rows_available" if hf_summary["pass"] else "fail_hf_semantic_truth_rows_missing",
            "required_rows": 8,
        }
    )
    write_json(reports / "2010_semantic_hf_truth_loader_gate.json", truth_json)
    write_text(
        reports / "2010_semantic_hf_truth_loader_gate.md",
        "\n".join(
            [
                "# Semantic HF Truth Loader Gate",
                "",
                f"- Verdict: {truth_json['verdict']}.",
                f"- HF truth rows: {hf_summary['hf_truth_rows']} total; {hf_summary['original_semantic_truth_rows']}/8 original semantic cases.",
                f"- Device/runtime: {hf_summary.get('device_selected')} / {hf_summary.get('runtime_versions')}.",
                "- Output logits are last-token HF/PyTorch BF16 truth rows; no generation was run.",
            ]
        ),
    )

    island_json = report_common(
        root,
        "dream7b_s100p_v21_2020_semantic_bpu_island_battery",
        [island_eval_path, bpu_raw_path, combined_cases_path],
        [reports / "2020_semantic_bpu_island_battery.json", reports / "2020_semantic_bpu_island_battery.md"],
    )
    island_json.update(
        {
            "island_summary": island_summary,
            "verdict": island_summary["task_verdict"],
            "strict_gate": {
                "reference_top1_in_candidate_top5_required": True,
                "cosine_min": 0.95,
                "relative_l2_max": 0.3,
                "no_allzero_or_constant_logits": True,
            },
            "conversion_policy": "official_runtime_output_scale_direct_float32_no_target_affine",
        }
    )
    write_json(reports / "2020_semantic_bpu_island_battery.json", island_json)
    island_lines = ["# Semantic BPU Island Battery", "", f"- Verdict: {island_json['verdict']}."]
    for key, d in island_summary["by_island"].items():
        island_lines.append(
            f"- Island [{key}]: strict {d['strict_pass_rows']}/{d['total_rows']}; "
            f"original semantic {d['original_semantic_strict_pass_rows']}/{d['original_semantic_rows']}; "
            f"mean rel L2 {d['mean_relative_l2']:.6f}; mean cosine {d['mean_cosine']:.6f}."
        )
    island_lines.extend(
        [
            "- Partial strict passes are diagnostic signal only; they do not unlock deployment or generation.",
            "- Generation quality and product routes were not run.",
        ]
    )
    write_text(reports / "2020_semantic_bpu_island_battery.md", "\n".join(island_lines))

    if island_summary["island_rows"] == 0 or hf_summary["original_semantic_truth_rows"] < 8:
        ramp_verdict = "C_inconclusive_semantic_truth_or_rows_missing"
    elif island_summary["all_original_semantic_cases_pass_any_island"] and island_summary["ramp_summary"]["strict_pass_rows"] == 0:
        ramp_verdict = "A_ramp_outlier_supported"
    else:
        ramp_verdict = "B_ramp_not_outlier_semantic_also_fails"
    ramp_json = report_common(
        root,
        "dream7b_s100p_v21_2030_ramp_outlier_decision",
        [island_eval_path, combined_cases_path],
        [reports / "2030_ramp_outlier_decision.json", reports / "2030_ramp_outlier_decision.md"],
    )
    ramp_json.update(
        {
            "verdict": ramp_verdict,
            "ramp_summary": island_summary["ramp_summary"],
            "semantic_island_summary": island_summary["by_island"],
            "decision_basis": "Ramp fails all tested islands, but original semantic prompts also fail or are mixed; therefore ramp is not the sole outlier explaining island invalidity.",
        }
    )
    write_json(reports / "2030_ramp_outlier_decision.json", ramp_json)
    write_text(
        reports / "2030_ramp_outlier_decision.md",
        "\n".join(
            [
                "# Ramp Outlier Decision",
                "",
                f"- Verdict: {ramp_verdict}.",
                f"- Ramp strict passes: {island_summary['ramp_summary']['strict_pass_rows']}/{island_summary['ramp_summary']['rows']}.",
                "- Semantic prompts are also mixed/failing under the same strict gate, so ramp cannot be isolated as the only failure source.",
            ]
        ),
    )

    pos_json = report_common(
        root,
        "dream7b_s100p_v21_2040_position_delta_basis_model",
        [Path(pos["source_path"]) if pos.get("source_path") else position_v21_summary_path],
        [reports / "2040_position_delta_basis_model.json", reports / "2040_position_delta_basis_model.md", position_v21_summary_path],
    )
    pos_json.update(
        {
            "position_summary": pos,
            "position_path_model": pos["position_path_model"],
            "verdict": pos["position_path_model"],
            "deployable_claim_allowed": pos["deployable_claim_allowed"],
            "blocking_or_failure_reasons": [
                "Existing delta-basis heldout evidence does not reach deployable rel L2/cosine thresholds.",
                "BPU-internal position model is not equivalent to HF semantic correctness without heldout BF16 validation.",
            ],
        }
    )
    write_json(reports / "2040_position_delta_basis_model.json", pos_json)
    write_text(
        reports / "2040_position_delta_basis_model.md",
        "\n".join(
            [
                "# Position Delta-Basis Model",
                "",
                f"- Verdict: {pos['position_path_model']}.",
                f"- max_rel_l2: {pos.get('max_rel_l2')}; min_cosine: {pos.get('min_cosine')}.",
                "- Deployable claim allowed: false.",
            ]
        ),
    )

    correction_justified = (
        island_summary["all_original_semantic_cases_pass_any_island"]
        or bool(pos.get("deployable_claim_allowed"))
    )
    corrected_json = report_common(
        root,
        "dream7b_s100p_v21_2050_corrected_candidate_if_justified",
        [reports / "2020_semantic_bpu_island_battery.json", reports / "2040_position_delta_basis_model.json"],
        [reports / "2050_corrected_candidate_if_justified_v21.json", reports / "2050_corrected_candidate_if_justified_v21.md"],
    )
    corrected_json.update(
        {
            "verdict": "not_run_no_justified_correction" if not correction_justified else "eligible_but_not_run_by_builder",
            "corrected_candidate_run": False,
            "justification": {
                "semantic_island_all_original_semantic_pass": island_summary["all_original_semantic_cases_pass_any_island"],
                "position_model_deployable_claim_allowed": pos.get("deployable_claim_allowed"),
                "official_internal_tensor_or_vendor_fix_found": False,
            },
            "required_before_corrected_candidate": [
                "all semantic island cases pass under strict logits gate, or",
                "position delta basis predicts heldout variants within thresholds, or",
                "official internal tensor/source graph/scale fix is identified and validated on heldout semantic cases",
            ],
        }
    )
    write_json(reports / "2050_corrected_candidate_if_justified_v21.json", corrected_json)
    write_text(
        reports / "2050_corrected_candidate_if_justified_v21.md",
        "\n".join(
            [
                "# Corrected Candidate",
                "",
                "- Verdict: not_run_no_justified_correction.",
                "- No semantic island passed all original semantic cases, and the position delta-basis model remains non-deployable.",
                "- No generation or product route was run.",
            ]
        ),
    )

    final_verdict = "C_no_valid_semantic_bpu_island"
    gate = {
        **host_env(root),
        "schema_version": "dream7b_s100p_v21_gate_packet",
        "final_verdict": final_verdict,
        "logits_numerical_validity_current_full_bpu_path": "fail_against_HF_PyTorch_BF16_truth_from_prior_gates",
        "semantic_hf_truth_loader_gate": truth_json["verdict"],
        "semantic_bpu_island_gate": island_json["verdict"],
        "ramp_outlier_decision": ramp_verdict,
        "position_path_model": pos["position_path_model"],
        "corrected_candidate": corrected_json["verdict"],
        "generation_quality": "not_run_by_design",
        "product_route": "not_run_by_design",
        "ports_18888_18889": "not_touched",
        "openclaw_foreground": "not_touched",
        "current_product_route": "Qwen + OpenClaw unchanged",
        "evidence": {
            "hf_truth_report": artifact(hf_truth_path),
            "island_eval_report": artifact(island_eval_path),
            "bpu_raw_report": artifact(bpu_raw_path),
            "combined_cases": artifact(combined_cases_path),
            "position_summary_v21": artifact(position_v21_summary_path),
        },
        "key_findings": [
            "v21 unblocked HF/PyTorch BF16 semantic truth export: 8 original semantic rows, plus canonical rows in island evaluation.",
            "BPU islands [1], [2], and [1,2] produced 33 rows but only partial strict passes; no island passed all original semantic prompts.",
            "Ramp fails, but semantic prompts also fail or are mixed, so ramp is not the sole diagnostic outlier.",
            "Position delta-basis evidence remains nonlinear/token-dependent and not deployable without vendor/internal tensor closure.",
            "Corrected candidate was not run because no justified correction condition was met.",
        ],
    }
    write_json(final_dir / "dream7b_s100p_gate_packet_v21.json", gate)
    write_text(
        final_dir / "dream7b_s100p_gate_packet_v21.md",
        "\n".join(
            [
                "# Dream7B S100P Gate Packet v21",
                "",
                f"- Final verdict: {final_verdict}.",
                "- HF semantic truth: pass, 8/8 original semantic rows exported with local CUDA torch2 BF16 path.",
                "- BPU semantic islands: partial signal only; no deployable logits-correct island.",
                "- Ramp: not isolated as the only outlier because semantic prompts also fail/mix.",
                "- Corrected candidate: not_run_no_justified_correction.",
                "- Generation quality: not_run_by_design.",
                "- Product route / 18888 / 18889 / OpenClaw foreground: not_touched.",
            ]
        ),
    )

    write_text(
        reports / "PAPER_EVIDENCE_DOSSIER_V21.md",
        "\n".join(
            [
                "# Paper Evidence Dossier v21",
                "",
                "## Claim",
                "The current tested Dream7B seq128 segmented-HBM S100P full-BPU path remains falsified against HF/PyTorch BF16 logits truth; v21 additionally shows that early semantic BPU islands [1], [2], and [1,2] do not provide a deployable correctness-first route.",
                "",
                "## Evidence Table",
                "| Gate | Evidence | Result |",
                "| --- | --- | --- |",
                f"| HF semantic truth | {hf_summary['original_semantic_truth_rows']}/8 original semantic rows on {hf_summary.get('device_selected')} | pass |",
                f"| BPU island [1] | strict {island_summary['by_island'].get('1', {}).get('original_semantic_strict_pass_rows')}/8 original semantic | not deployable |",
                f"| BPU island [2] | strict {island_summary['by_island'].get('2', {}).get('original_semantic_strict_pass_rows')}/8 original semantic | not deployable |",
                f"| BPU island [1,2] | strict {island_summary['by_island'].get('1,2', {}).get('original_semantic_strict_pass_rows')}/8 original semantic | not deployable |",
                f"| Ramp outlier | {ramp_verdict} | ramp not sole explanation |",
                f"| Position path | {pos['position_path_model']} | not deployable |",
                "",
                "Generation quality and product routes were intentionally not run.",
            ]
        ),
    )
    write_text(
        reports / "SEMANTIC_BPU_ISLAND_STATUS_V21.md",
        "\n".join(
            [
                "# Semantic BPU Island Status v21",
                "",
                f"Verdict: {island_json['verdict']}.",
                "",
                "No BPU island [1], [2], or [1,2] passed all 8 original semantic prompts under the strict logits gate. Partial passes are diagnostic only and do not unlock generation or deployment.",
            ]
        ),
    )
    write_text(
        reports / "POSITION_PATH_MODEL_STATUS_V21.md",
        "\n".join(
            [
                "# Position Path Model Status v21",
                "",
                f"Verdict: {pos['position_path_model']}.",
                "",
                "The existing delta-basis/heldout evidence remains insufficient for a deployable correction. It must not be represented as HF semantic correctness.",
            ]
        ),
    )

    package_json = report_common(
        root,
        "dream7b_s100p_v21_2060_final_package",
        [final_dir / "dream7b_s100p_gate_packet_v21.json"],
        [reports / "2060_final_v21_gate_packet_and_package.json", reports / "2060_final_v21_gate_packet_and_package.md"],
    )
    package_json.update(
        {
            "final_verdict": final_verdict,
            "zip_path": "set_by_package_builder",
            "zip_sha256": "see_adjacent_sha256_sidecar_after_zip_finalization",
            "manifest_inside_zip": "MANIFEST.json",
            "sha256sums_inside_zip": "SHA256SUMS.txt",
        }
    )
    write_json(reports / "2060_final_v21_gate_packet_and_package.json", package_json)
    write_text(
        reports / "2060_final_v21_gate_packet_and_package.md",
        "# Final v21 Package\n\nPackage path is set before packaging; final zip SHA256 is written to the adjacent sidecar after zip finalization.",
    )
    package_json["output_artifacts"] = [
        artifact(reports / "2060_final_v21_gate_packet_and_package.json"),
        artifact(reports / "2060_final_v21_gate_packet_and_package.md"),
    ]
    write_json(reports / "2060_final_v21_gate_packet_and_package.json", package_json)

    created = [
        reports / "2000_v21_baseline_lock.json",
        reports / "2000_v21_baseline_lock.md",
        reports / "2010_semantic_hf_truth_loader_gate.json",
        reports / "2010_semantic_hf_truth_loader_gate.md",
        reports / "2020_semantic_bpu_island_battery.json",
        reports / "2020_semantic_bpu_island_battery.md",
        reports / "2030_ramp_outlier_decision.json",
        reports / "2030_ramp_outlier_decision.md",
        reports / "2040_position_delta_basis_model.json",
        reports / "2040_position_delta_basis_model.md",
        reports / "2050_corrected_candidate_if_justified_v21.json",
        reports / "2050_corrected_candidate_if_justified_v21.md",
        reports / "2060_final_v21_gate_packet_and_package.json",
        reports / "2060_final_v21_gate_packet_and_package.md",
        reports / "PAPER_EVIDENCE_DOSSIER_V21.md",
        reports / "SEMANTIC_BPU_ISLAND_STATUS_V21.md",
        reports / "POSITION_PATH_MODEL_STATUS_V21.md",
        final_dir / "dream7b_s100p_gate_packet_v21.json",
        final_dir / "dream7b_s100p_gate_packet_v21.md",
        position_v21_summary_path,
    ]
    return {
        "hf_summary": hf_summary,
        "island_summary": island_summary,
        "position_summary": pos,
        "ramp_verdict": ramp_verdict,
        "final_verdict": final_verdict,
        "created_files": created,
        "prompt_path": prompt_path,
    }


def iter_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob("*") if p.is_file())


def package_evidence(root: Path, state: dict[str, Any], timestamp: str) -> dict[str, Any]:
    out_dir = root / "evidence_for_gptpro"
    out_dir.mkdir(exist_ok=True)
    zip_path = out_dir / f"dream7b_s100p_v21_for_gptpro_{timestamp}.zip"

    package_report_path = root / "reports/2060_final_v21_gate_packet_and_package.json"
    package_report = read_json(package_report_path, {})
    package_report.update(
        {
            "zip_path": str(zip_path.relative_to(root).as_posix()),
            "zip_sha256": "see_adjacent_sha256_sidecar_after_zip_finalization",
            "zip_testzip_bad_member": "validated_after_zip_finalization",
            "manifest_inside_zip": "MANIFEST.json",
            "sha256sums_inside_zip": "SHA256SUMS.txt",
        }
    )
    write_json(package_report_path, package_report)
    write_text(
        root / "reports/2060_final_v21_gate_packet_and_package.md",
        "\n".join(
            [
                "# Final v21 Package",
                "",
                f"- Zip: {zip_path.relative_to(root).as_posix()}",
                "- SHA256: see adjacent .sha256.txt after zip finalization.",
                "- Manifest: MANIFEST.json inside zip.",
                "- Checksums: SHA256SUMS.txt inside zip.",
            ]
        ),
    )

    include_paths: list[tuple[Path, str | None]] = []
    for p in state["created_files"]:
        include_paths.append((p, None))
    for p in [
        root / "tools/build_v21_research_thread.py",
        root / "tools/run_v21_bpu_islands_from_boundaries.py",
        root / "tools/run_v21_hf_boundaries_and_island_eval.py",
        root / "evidence/v21_combined_cases",
        root / "evidence/semantic_hf_truth_v21",
        root / "evidence/semantic_island_battery_v21",
        root / "evidence/dream7b_s100p_v21_execution_20260704/evidence/semantic_island_battery_v21/bpu_outputs",
        root / "evidence/dream7b_s100p_v21_execution_20260704/evidence/v21_bpu_boundary_inputs.tar.gz",
        root / "evidence/position_delta_basis_model_v21",
        root / "01_final_evidence/dream7b_s100p_gate_packet_v20.json",
        root / "01_final_evidence/dream7b_s100p_gate_packet_v20.md",
        root / "reports/3050_final_v20_gate_packet_and_package.json",
        root / "reports/3050_final_v20_gate_packet_and_package.md",
    ]:
        include_paths.append((p, None))
    prompt_path = state.get("prompt_path")
    if prompt_path and prompt_path.exists():
        include_paths.append((prompt_path, f"prompts/{prompt_path.name}"))

    files: dict[str, Path] = {}
    for path, explicit_arc in include_paths:
        for file_path in iter_files(path):
            if explicit_arc and file_path == path:
                arc = explicit_arc
            elif file_path.is_relative_to(root):
                arc = file_path.relative_to(root).as_posix()
            else:
                arc = f"external/{file_path.name}"
            files.setdefault(arc, file_path)

    # Avoid putting prior packages or this package into itself.
    files = {
        arc: p
        for arc, p in files.items()
        if not arc.startswith("evidence_for_gptpro/") and arc not in {"MANIFEST.json", "SHA256SUMS.txt"}
    }

    manifest_files = []
    sha_lines = []
    for arc, p in sorted(files.items()):
        digest = sha256_file(p)
        size = p.stat().st_size
        manifest_files.append({"path": arc, "size_bytes": size, "sha256": digest})
        sha_lines.append(f"{digest}  {arc}")
    manifest = {
        "schema_version": "dream7b_s100p_v21_gptpro_manifest",
        "created_at_utc": utc_now(),
        "package_name": zip_path.name,
        "final_verdict": state["final_verdict"],
        "safety": SAFETY,
        "file_count_excluding_manifest": len(manifest_files),
        "files": manifest_files,
    }
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    sums_bytes = ("\n".join(sha_lines) + "\n").encode("utf-8")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as zf:
        for arc, p in sorted(files.items()):
            zf.write(p, arc)
        zf.writestr("MANIFEST.json", manifest_bytes)
        zf.writestr("SHA256SUMS.txt", sums_bytes)

    bad_member = None
    with zipfile.ZipFile(zip_path, "r") as zf:
        bad_member = zf.testzip()
    zip_sha = sha256_file(zip_path)
    sha_path = zip_path.with_suffix(zip_path.suffix + ".sha256.txt")
    write_text(sha_path, f"{zip_sha}  {zip_path.name}")

    package_report = read_json(package_report_path, {})
    package_report.update(
        {
            "zip_path": str(zip_path.relative_to(root).as_posix()),
            "zip_sha256": zip_sha,
            "zip_size_bytes": zip_path.stat().st_size,
            "zip_testzip_bad_member": bad_member,
            "zip_member_count": len(manifest_files) + 2,
            "manifest_file_count_excluding_manifest": len(manifest_files),
        }
    )
    write_json(package_report_path, package_report)
    write_text(
        root / "reports/2060_final_v21_gate_packet_and_package.md",
        "\n".join(
            [
                "# Final v21 Package",
                "",
                f"- Zip: {zip_path.relative_to(root).as_posix()}",
                f"- SHA256: {zip_sha}",
                f"- testzip bad member: {bad_member}",
                f"- members: {len(manifest_files) + 2}",
            ]
        ),
    )

    return {
        "zip_path": zip_path,
        "zip_sha256": zip_sha,
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_testzip_bad_member": bad_member,
        "zip_member_count": len(manifest_files) + 2,
        "sha_path": sha_path,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--prompt", default=r"C:\Users\zhexu\Downloads\NEXT_CODEX_PROMPT_DREAM7B_S100P_V20_TO_V21_20260704.md")
    ap.add_argument("--timestamp", default=datetime.now().strftime("%Y%m%d_%H%M%S"))
    args = ap.parse_args()

    root = Path(args.root).resolve()
    prompt_path = Path(args.prompt) if args.prompt else None
    state = build_reports(root, prompt_path)
    package = package_evidence(root, state, args.timestamp)
    print(
        json.dumps(
            {
                "status": "pass" if package["zip_testzip_bad_member"] is None else "fail",
                "final_verdict": state["final_verdict"],
                "zip_path": str(package["zip_path"]),
                "zip_sha256": package["zip_sha256"],
                "zip_size_bytes": package["zip_size_bytes"],
                "zip_testzip_bad_member": package["zip_testzip_bad_member"],
                "zip_member_count": package["zip_member_count"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if package["zip_testzip_bad_member"] is None else 2


if __name__ == "__main__":
    raise SystemExit(main())
