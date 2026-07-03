# Codex completion checklist

Before final response, verify:

- [ ] `reports/105_package_hygiene_v3.json` exists and is parseable.
- [ ] `reports/110_segment_io_contract.json` exists and includes segment 26 and 27 contract comparison.
- [ ] `reports/120_final_segment_input_sweep.json` exists and includes real, scaled, clipped, normalized, and synthetic variants.
- [ ] `reports/130_s100p_boundary_dump_subprocess.json` exists or failure is explained.
- [ ] `reports/140_bf16_reference_status.json` exists and does not fabricate BF16 if unavailable.
- [ ] `01_final_evidence/dream7b_s100p_gate_packet_v3.json` exists.
- [ ] `01_final_evidence/dream7b_s100p_gate_packet_v3.md` exists.
- [ ] `01_final_evidence/dream7b_s100p_final_technical_report_v3.md` exists.
- [ ] Gate 3/4 remain pending/blocked unless actually run after Gate 2 pass.
- [ ] 18888 was not modified.
- [ ] Final GPT Pro zip uses POSIX `/` paths.
- [ ] Raw evidence subset manifest includes SHA256 and shape/dtype for included arrays.
