# Dream7B S100P v3 Evidence Pack

This package is for GPT Pro review of the v3 Dream7B/S100P localization run.

Primary files:

- `01_final_evidence/dream7b_s100p_gate_packet_v3.json`
- `01_final_evidence/dream7b_s100p_final_technical_report_v3.md`
- `reports/110_segment_io_contract.json`
- `reports/120_final_segment_input_sweep.json`
- `reports/130_s100p_boundary_dump_subprocess.json`
- `reports/140_bf16_reference_status.json`
- `RAW_EVIDENCE_SUBSET_MANIFEST.json`

Scope: this run only investigates `seg26_27 -> seg27_28` final segment input contract/layout/dtype/scale/runtime interpretation. It does not run generation quality, does not enable product route, and does not touch `18888`.
