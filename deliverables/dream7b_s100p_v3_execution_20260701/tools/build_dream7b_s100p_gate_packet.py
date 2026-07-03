#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from dream7b_research_common import now_iso, read_json, write_json, write_text


def read_optional(path: Path) -> dict:
    return read_json(path) if path.is_file() else {"verdict": "missing", "path": str(path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build unified Dream7B S100P gate packet v2.")
    parser.add_argument("--run-root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    root = Path(args.run_root)
    reports = root / "reports"
    data = {
        "reproduce": read_optional(reports / "000_reproduce_existing_evidence.json"),
        "s100p_dump": read_optional(reports / "020_s100p_dump_logits_run.json"),
        "boundary": read_optional(reports / "030_segment_boundary_compare.json"),
        "final_segment": read_optional(reports / "040_final_segment_lmheadq16_audit.json"),
        "final_segment_metadata": read_optional(reports / "040a_final_segment_metadata.json"),
        "input_alignment": read_optional(reports / "050_seq128_input_alignment_audit.json"),
        "dequant": read_optional(reports / "060_dequant_audit.json"),
        "battery": read_optional(reports / "070_logits_probe_battery_triplet.json"),
        "generation": read_optional(reports / "080_generation_quality_gate.json"),
        "product_route": read_optional(reports / "090_product_route_isolation_gate.json"),
        "raw_evidence_inventory": read_optional(reports / "100_raw_evidence_inventory.json"),
    }
    repro_gates = data["reproduce"].get("gate_status", {})
    input_status = data["input_alignment"].get("input_alignment_valid", "inconclusive")
    bf16_missing = "bf16_missing" in " ".join(data["battery"].get("errors", [])) or data["battery"].get("verdict", "").startswith("inconclusive")
    gguf_fail = data["reproduce"].get("gate_status", {}).get("logits_numerically_valid_against_gguf_q4km") == "fail"
    raw_constant = bool(data["dequant"].get("raw_constant_cases"))
    s100p_logits_anomaly = str(data["s100p_dump"].get("verdict", "")).startswith("blocked_s100p_dump_logits_anomaly")
    real_seg26_final_constant = any(
        case.get("input_kind") == "real_bpu_seg26_output" and (case.get("raw_stats") or {}).get("constant")
        for case in data["final_segment"].get("cases", [])
    )
    gate2_status = "inconclusive"
    blocking = []
    if input_status != "pass":
        blocking.append("input_alignment_unresolved")
    if bf16_missing:
        blocking.append("bf16_reference_unavailable")
    if gguf_fail:
        blocking.append("deployment_reference_gguf_q4km_failed")
    if s100p_logits_anomaly:
        blocking.append("s100p_logits_uniform_or_constant")
    if raw_constant:
        blocking.append("raw_output_constant_cases")
    if real_seg26_final_constant:
        blocking.append("real_bpu_seg26_to_final_constant")
    if input_status == "pass" and not bf16_missing and gguf_fail:
        gate2_status = "fail"
    elif input_status == "pass" and bf16_missing:
        gate2_status = "inconclusive"
    verdict = (
        "deployment_blocked_against_deployment_reference_but_bf16_unresolved"
        if gguf_fail and bf16_missing
        else "inconclusive_due_to_missing_reference_or_alignment"
    )
    packet = {
        "created_at": now_iso(),
        "verdict": verdict,
        "verdict_class": "C" if verdict.startswith("deployment_blocked") else "D",
        "gate_status": {
            "compile_feasible": repro_gates.get("compile_feasible", "inconclusive"),
            "s100p_runtime_valid": repro_gates.get("s100p_runtime_valid", "inconclusive"),
            "logits_numerically_valid": gate2_status,
            "generation_quality_valid": "pending" if gate2_status != "pass" else data["generation"].get("gate_status", "missing"),
            "product_route_valid": "pending",
        },
        "deployment_reference_status": "fail" if gguf_fail else "inconclusive",
        "bf16_reference_status": "unavailable",
        "blocking_issues": blocking,
        "first_divergent_segment": data["boundary"].get("first_divergent_segment"),
        "evidence_table": {
            "000_reproduce_existing_evidence": str(reports / "000_reproduce_existing_evidence.json"),
            "020_s100p_dump_logits_run": str(reports / "020_s100p_dump_logits_run.json"),
            "030_segment_boundary_compare": str(reports / "030_segment_boundary_compare.json"),
            "040_final_segment_lmheadq16_audit": str(reports / "040_final_segment_lmheadq16_audit.json"),
            "040a_final_segment_metadata": str(reports / "040a_final_segment_metadata.json"),
            "050_seq128_input_alignment_audit": str(reports / "050_seq128_input_alignment_audit.json"),
            "060_dequant_audit": str(reports / "060_dequant_audit.json"),
            "070_logits_probe_battery_triplet": str(reports / "070_logits_probe_battery_triplet.json"),
            "100_raw_evidence_inventory": str(reports / "100_raw_evidence_inventory.json"),
        },
        "claim_boundary_text": "The tested seq128 HBM chain passed compile and S100P load/run gates. It remains blocked against the available GGUF Q4_K_M deployment reference, while BF16/PyTorch ground truth is unresolved. Gate 3 and Gate 4 remain pending/blocked, not failed.",
        "next_minimal_experiment": "Provide a verified BF16/PyTorch Dream7B forward wrapper and compare seg27_28 on the same hidden input to separate HBM graph defects from GGUF/dequant/postprocess mismatch.",
        "source_reports": data,
    }
    out_json = root / "01_final_evidence" / "dream7b_s100p_gate_packet_v2.json"
    out_md = root / "01_final_evidence" / "dream7b_s100p_gate_packet_v2.md"
    write_json(out_json, packet)
    lines = ["# Dream7B S100P Gate Packet V2", "", f"- verdict: `{packet['verdict']}`", f"- blocking_issues: `{', '.join(blocking)}`", "", "## Gates", ""]
    for k, v in packet["gate_status"].items():
        lines.append(f"- {k}: `{v}`")
    lines.extend(["", "## Claim Boundary", "", packet["claim_boundary_text"], "", "## Next Minimal Experiment", "", packet["next_minimal_experiment"], ""])
    write_text(out_md, "\n".join(lines))
    print(out_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
