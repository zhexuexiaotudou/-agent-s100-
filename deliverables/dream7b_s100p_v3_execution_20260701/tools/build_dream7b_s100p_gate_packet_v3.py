#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common_artifact_utils import read_json, utc_now_iso, write_json


def opt(root: Path, rel: str) -> dict[str, Any]:
    p = root / rel
    if not p.is_file():
        return {"_missing": True, "_path": rel}
    return read_json(p)


def status_from_v2(v2: dict[str, Any], key: str) -> str:
    return (v2.get("gate_status") or {}).get(key, "inconclusive")


def determine_packet(root: Path) -> dict[str, Any]:
    v2 = opt(root, "01_final_evidence/dream7b_s100p_gate_packet_v2.json")
    hygiene = opt(root, "reports/105_package_hygiene_v3.json")
    io = opt(root, "reports/110_segment_io_contract.json")
    sweep = opt(root, "reports/120_final_segment_input_sweep.json")
    boundary = opt(root, "reports/130_s100p_boundary_dump_subprocess.json")
    bf16 = opt(root, "reports/140_bf16_reference_status.json")
    bf16_boundary = opt(root, "reports/140_bf16_boundary_status.json")

    bf16_status = bf16.get("bf16_reference_status", "unavailable")
    deployment_reference_status = v2.get("deployment_reference_status", "fail") if not v2.get("_missing") else "fail"
    input_contract_unresolved = io.get("seg26_to_seg27_contract_match") != "pass"
    sweep_verdict = sweep.get("final_segment_input_sweep_verdict", "missing")
    boundary_status = boundary.get("s100p_boundary_dump_subprocess_verdict", "missing")

    gate_status = {
        "compile_feasible": status_from_v2(v2, "compile_feasible") if not v2.get("_missing") else "inconclusive",
        "s100p_runtime_valid": status_from_v2(v2, "s100p_runtime_valid") if not v2.get("_missing") else "inconclusive",
        "logits_numerically_valid": "inconclusive",
        "generation_quality_valid": "pending",
        "product_route_valid": "pending",
    }

    blocking = []
    if v2.get("_missing"):
        blocking.append("v2_gate_packet_missing")
    if hygiene.get("package_hygiene_valid") == "fail":
        blocking.append("package_hygiene_failed")
    if bf16_status != "available":
        blocking.append("bf16_reference_unavailable_or_unverified")
    if deployment_reference_status == "fail":
        blocking.append("deployment_reference_gguf_q4km_failed")
    if input_contract_unresolved:
        blocking.append("seg26_to_seg27_contract_unresolved")
    if sweep_verdict in ("blocked", "fail", "inconclusive", "missing"):
        blocking.append("final_segment_input_sweep_unresolved")
    if boundary_status in ("fail", "missing"):
        blocking.append("boundary_dump_subprocess_failed_or_missing")

    # This run has no accepted BF16-vs-BPU metrics. Keep A/B unreachable unless a future
    # report explicitly supplies verified BF16 comparison metrics.
    verdict = "deployment_blocked_against_deployment_reference_but_bf16_unresolved"
    verdict_class = "C"
    if bf16_status == "available":
        verdict = "inconclusive_due_to_missing_artifact_reference_or_input_alignment"
        verdict_class = "D"
    if v2.get("_missing") or io.get("_missing") or sweep.get("_missing") or bf16.get("_missing"):
        verdict = "inconclusive_due_to_missing_artifact_reference_or_input_alignment"
        verdict_class = "D"

    first_divergent = "unknown_without_bf16_boundaries"
    observed_late_boundary = None
    late = boundary.get("late_segment_constant_outputs") or []
    if late:
        observed_late_boundary = late[0]

    safe_claim = (
        "Dream7B seq128 B=1 segmented HBM with lm_head q16 last-token logits passed compile feasibility and S100P load/run/shape checks. "
        "However, the tested BPU logits path is blocked against the available GGUF Q4_K_M deployment reference, and BF16/PyTorch ground truth is unresolved. "
        "Current evidence localizes the anomaly to the real segmented chain output path around seg26_27 -> seg27_28 or final-segment input/runtime interpretation, because isolated seg27_28 responds to synthetic hidden inputs but outputs all-zero logits for real BPU seg26 hidden states."
    )

    return {
        "schema_version": "dream7b_s100p_gate_packet_v3",
        "created_at_utc": utc_now_iso(),
        "verdict": verdict,
        "verdict_class": verdict_class,
        "gate_status": gate_status,
        "deployment_reference_status": deployment_reference_status,
        "bf16_reference_status": bf16_status,
        "bf16_boundary_status": bf16_boundary.get("bf16_boundary_status", "unavailable"),
        "segment_io_contract_status": io.get("segment_io_contract_verdict", "missing"),
        "seg26_to_seg27_contract_match": io.get("seg26_to_seg27_contract_match", "missing"),
        "seg26_to_seg27_contract_blocking_fields": io.get("blocking_fields_missing", []),
        "final_segment_input_sweep_status": sweep_verdict,
        "final_segment_input_sweep_conclusion": {
            "real_hidden_constant_output": sweep.get("real_hidden_constant_output"),
            "synthetic_controls_nonconstant": sweep.get("synthetic_controls_nonconstant"),
            "smallest_recovery_variant": sweep.get("smallest_recovery_variant"),
            "likely_issue_class": sweep.get("likely_issue_class"),
            "synthetic_nonconstant_variants": sweep.get("synthetic_nonconstant_variants"),
        },
        "s100p_boundary_dump_subprocess_status": boundary_status,
        "boundary_cases_completed": boundary.get("cases_completed"),
        "boundary_cases_failed": boundary.get("cases_failed"),
        "first_divergent_segment": first_divergent,
        "observed_late_boundary_constant_output": observed_late_boundary,
        "blocking_issues": sorted(set(blocking)),
        "evidence_table": {
            "v2_gate_packet": "01_final_evidence/dream7b_s100p_gate_packet_v2.json",
            "105_package_hygiene_v3": "reports/105_package_hygiene_v3.json",
            "110_segment_io_contract": "reports/110_segment_io_contract.json",
            "120_final_segment_input_sweep": "reports/120_final_segment_input_sweep.json",
            "130_s100p_boundary_dump_subprocess": "reports/130_s100p_boundary_dump_subprocess.json",
            "140_bf16_reference_status": "reports/140_bf16_reference_status.json",
            "140_bf16_boundary_status": "reports/140_bf16_boundary_status.json",
        },
        "safe_claim_boundary": safe_claim,
        "next_minimal_experiment": (
            "Instrument or obtain HBRT input tensor descriptors for seg27_28, including dtype, layout, and input quantization; "
            "then build a verified Dream7B BF16/PyTorch wrapper for the same seg26 hidden input."
        ),
        "source_reports": {
            "v2": v2,
            "hygiene": hygiene,
            "io_contract": io,
            "input_sweep": sweep,
            "boundary_subprocess": boundary,
            "bf16": bf16,
            "bf16_boundary": bf16_boundary,
        },
    }


def write_md(path: Path, packet: dict[str, Any]) -> None:
    lines = [
        "# Dream7B S100P Gate Packet V3",
        "",
        f"- verdict: `{packet['verdict']}`",
        f"- verdict_class: `{packet['verdict_class']}`",
        f"- bf16_reference_status: `{packet['bf16_reference_status']}`",
        f"- deployment_reference_status: `{packet['deployment_reference_status']}`",
        "",
        "## Gate Status",
        "",
        "| Gate | Status |",
        "| --- | --- |",
    ]
    for key, value in packet["gate_status"].items():
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(["", "## V3 Localization", ""])
    lines.append(f"- segment_io_contract_status: `{packet['segment_io_contract_status']}`")
    lines.append(f"- seg26_to_seg27_contract_match: `{packet['seg26_to_seg27_contract_match']}`")
    lines.append(f"- final_segment_input_sweep_status: `{packet['final_segment_input_sweep_status']}`")
    lines.append(f"- final_segment_input_sweep_conclusion: `{packet['final_segment_input_sweep_conclusion']}`")
    lines.append(f"- s100p_boundary_dump_subprocess_status: `{packet['s100p_boundary_dump_subprocess_status']}`")
    lines.extend(["", "## Blocking Issues", ""])
    for issue in packet["blocking_issues"]:
        lines.append(f"- `{issue}`")
    lines.extend(["", "## Safe Claim Boundary", "", packet["safe_claim_boundary"], "", "## Next Minimal Experiment", "", packet["next_minimal_experiment"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_report(path: Path, packet: dict[str, Any]) -> None:
    text = f"""# Dream7B diffusion 在 S100P 上的 v3 分层证实/证伪定位报告

## 摘要

本轮 v3 只定位 `seg26_27 -> seg27_28` final segment input contract / layout / dtype / scale / runtime interpretation，不运行 generation quality，不启用或修改产品路由，不触碰 `18888`。最终判定保持 `{packet['verdict']}`。证据来自 `01_final_evidence/dream7b_s100p_gate_packet_v3.json` 字段 `verdict`、`gate_status`、`blocking_issues`。

## Gate 结果

`compile_feasible={packet['gate_status']['compile_feasible']}`，`s100p_runtime_valid={packet['gate_status']['s100p_runtime_valid']}`，`logits_numerically_valid={packet['gate_status']['logits_numerically_valid']}`，`generation_quality_valid={packet['gate_status']['generation_quality_valid']}`，`product_route_valid={packet['gate_status']['product_route_valid']}`。这些字段见 `01_final_evidence/dream7b_s100p_gate_packet_v3.json` 的 `gate_status`。

## v3 定位结果

Segment IO contract audit 状态为 `{packet['segment_io_contract_status']}`，`seg26_to_seg27_contract_match={packet['seg26_to_seg27_contract_match']}`。如果该项仍为 inconclusive，原因是 HBRT runtime 暴露的输入 descriptor、dtype 或 input quant params 不完整；详见 `reports/110_segment_io_contract.json` 字段 `blocking_fields_missing` 与 `seg26_to_seg27_comparison`。

Final segment input sweep 状态为 `{packet['final_segment_input_sweep_status']}`，结论字段为 `{packet['final_segment_input_sweep_conclusion']}`。该结果用于判断真实 seg26 hidden 经过缩放、裁剪、z-normalize 或 dtype 变体后，是否能让 `seg27_28` 从恒定输出恢复为 nonconstant logits；详见 `reports/120_final_segment_input_sweep.json` 字段 `variants`、`smallest_recovery_variant` 和 `likely_issue_class`。

Fresh-subprocess boundary dump 状态为 `{packet['s100p_boundary_dump_subprocess_status']}`，完成 case 数为 `{packet['boundary_cases_completed']}`，失败 case 数为 `{packet['boundary_cases_failed']}`。该结果用于区分上一轮 HBRT memory error 是否只是进程生命周期问题；详见 `reports/130_s100p_boundary_dump_subprocess.json` 字段 `cases`、`memory_errors`、`late_segment_constant_outputs`。

BF16/PyTorch reference 状态为 `{packet['bf16_reference_status']}`。本轮没有 verified Dream7B diffusion BF16 wrapper，因此不允许写 BF16 ground-truth failure；详见 `reports/140_bf16_reference_status.json` 字段 `bf16_reference_status`、`reason`、`no_bf16_ground_truth_claims_allowed`。

## 结论边界

{packet['safe_claim_boundary']}

## 下一步最小实验

{packet['next_minimal_experiment']}
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Dream7B/S100P v3 gate packet.")
    parser.add_argument("--run-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--output-json", default="01_final_evidence/dream7b_s100p_gate_packet_v3.json")
    parser.add_argument("--output-md", default="01_final_evidence/dream7b_s100p_gate_packet_v3.md")
    parser.add_argument("--technical-report", default="01_final_evidence/dream7b_s100p_final_technical_report_v3.md")
    args = parser.parse_args()
    root = Path(args.run_root)
    packet = determine_packet(root)
    write_json(root / args.output_json, packet)
    write_md(root / args.output_md, packet)
    write_report(root / args.technical_report, packet)
    print(root / args.output_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
