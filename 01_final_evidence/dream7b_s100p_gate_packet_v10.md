# Dream7B/S100P Gate Packet v10

Verdict class: `B_full_deployment_falsified_against_bf16_or_f16_reference`

Full BF16 HF truth rows are available and the current S100P segmented-HBM deployment output fails against them for the three canonical real_x rows. The BPU seg26 hidden routed through the exact HF final boundary also fails against full truth, while the same-input seg27_28 final-segment contract failure persists. Therefore v10 falsifies the current deployment logits path and shows both upstream hidden mismatch and final-segment contract failure; it must not be over-localized to only one stage.

## Gate Status
- `G0_safety`: `pass`
- `G1_v9_reproducibility`: `pass`
- `G2_canonical_cases`: `pass`
- `G3_full_truth_row`: `pass`
- `G4_hbm_mapping_evidence`: `pass_with_operator_graph_uncertainty`
- `G5_same_input_final_segment_contract`: `fail`
- `G6_upstream_hidden_validity`: `evaluated`
- `G7_remediation_experiment`: `attempted_no_repair_supported`
