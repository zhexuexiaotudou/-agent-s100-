#!/usr/bin/env python3
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
packet = root / "01_final_evidence" / "dream7b_s100p_lladacpp_style_continue_gate_packet.json"
if not packet.exists():
    raise SystemExit("missing final packet")
data = json.loads(packet.read_text(encoding="utf-8"))
expected = "bpu_operator_alignment_failed_review_required"
if data.get("final_verdict") != expected:
    raise SystemExit(f"unexpected final_verdict {data.get('final_verdict')!r}")
truth = root / "dream_s100p_lladacpp" / "reference" / "full_truth_31.jsonl"
if len([line for line in truth.read_text(encoding="utf-8").splitlines() if line.strip()]) != 31:
    raise SystemExit("truth row count is not 31")
print("SELF_CHECK_PASS")
