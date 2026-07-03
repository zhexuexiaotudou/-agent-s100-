# Dream7B/S100P Paper Evidence Dossier v10

## Research Question
Can Dream7B seq128 segmented HBM on S100P produce numerically valid logits for the tested artifact/runtime path?

## Method
Layered falsification: canonical token cases, manifest-level HBM mapping, exact same-input final-boundary comparison, optional full-truth comparison, and isolated calibration remediation.

## Evidence Table

| Gate | Status | Evidence |
|---|---|---|
| G0_safety | pass | reports/tasks 800-840 |
| G1_v9_reproducibility | pass | reports/tasks 800-840 |
| G2_canonical_cases | pass | reports/tasks 800-840 |
| G3_full_truth_row | pass | reports/tasks 800-840 |
| G4_hbm_mapping_evidence | pass_with_operator_graph_uncertainty | reports/tasks 800-840 |
| G5_same_input_final_segment_contract | fail | reports/tasks 800-840 |
| G6_upstream_hidden_validity | evaluated | reports/tasks 800-840 |
| G7_remediation_experiment | attempted_no_repair_supported | reports/tasks 800-840 |

## Conclusion
`B_full_deployment_falsified_against_bf16_or_f16_reference`: Full BF16 HF truth rows are available and the current S100P segmented-HBM deployment output fails against them for the three canonical real_x rows. The BPU seg26 hidden routed through the exact HF final boundary also fails against full truth, while the same-input seg27_28 final-segment contract failure persists. Therefore v10 falsifies the current deployment logits path and shows both upstream hidden mismatch and final-segment contract failure; it must not be over-localized to only one stage.

## Limitations
- Generation quality was not run.
- Product routes 18888/18889 were not enabled, modified, or tested.
- Operator graph metadata for seg27_28 was unavailable; mapping evidence is manifest-level plus runtime shape/scale evidence.
