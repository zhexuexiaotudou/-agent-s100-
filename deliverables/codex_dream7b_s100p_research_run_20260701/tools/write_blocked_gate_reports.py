#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from dream7b_research_common import now_iso, read_json, write_json, write_text


def main() -> int:
    parser = argparse.ArgumentParser(description="Write blocked/not-run Gate 3 and Gate 4 reports when Gate 2 is not pass.")
    parser.add_argument("--run-root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    root = Path(args.run_root)
    packet_path = root / "01_final_evidence" / "dream7b_s100p_gate_packet_v2.json"
    packet = read_json(packet_path) if packet_path.is_file() else {}
    gate2 = (packet.get("gate_status") or {}).get("logits_numerically_valid")
    reports = root / "reports"
    gen = {
        "created_at": now_iso(),
        "report_name": "080_generation_quality_gate",
        "gate_status": "blocked" if gate2 != "pass" else "not_run",
        "reason": f"Gate 2 logits_numerically_valid is {gate2}; generation quality gate is only allowed after Gate 2 pass.",
        "product_route_changed": False,
        "cases_run": [],
    }
    prod = {
        "created_at": now_iso(),
        "report_name": "090_product_route_isolation_gate",
        "gate_status": "blocked",
        "reason": "Product route validation is only allowed after Gate 2 and Gate 3 pass.",
        "foreground_18888_changed": False,
        "experimental_18889_enabled": False,
        "shadow_replay_run": False,
    }
    write_json(reports / "080_generation_quality_gate.json", gen)
    write_text(reports / "080_generation_quality_gate.md", f"# Generation Quality Gate\n\n- gate_status: `{gen['gate_status']}`\n- reason: {gen['reason']}\n- product_route_changed: `False`\n")
    write_json(reports / "090_product_route_isolation_gate.json", prod)
    write_text(reports / "090_product_route_isolation_gate.md", f"# Product Route Isolation Gate\n\n- gate_status: `{prod['gate_status']}`\n- reason: {prod['reason']}\n- foreground_18888_changed: `False`\n- experimental_18889_enabled: `False`\n")
    print(reports / "080_generation_quality_gate.json")
    print(reports / "090_product_route_isolation_gate.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

