# Dream7B/S100P Gate Packet v9

Verdict class: `F_exact_final_segment_contract_falsified_on_same_input`

For the unmodified BPU seg26 hidden input (real_x) in all three prompt cases, S100P seg27_28 official-dequant logits are all-zero, while the exact HF layer27 + final norm + lm_head boundary produces nonzero/nonconstant logits for the same inputs. Across the 42-row sweep, top-1 agreement is 0/42, 15/42 rows are all-zero/constant against nonconstant HF references, and 36/42 rows have relative L2 > 0.9. This falsifies the final-segment contract on same input. Full deployment logits validity remains unproven without a full truth row.

## Gate Status
- `G0_safety_generation_quality_not_run`: `pass`
- `G0_safety_product_routes_18888_18889_untouched`: `pass`
- `G1_raw_endpoint_packaging`: `pass`
- `G2_exact_hf_layer27_final_boundary`: `pass`
- `G3_full_truth_reference_row`: `blocked`
- `G4_exact_final_same_input_comparison`: `fail_final_segment_contract`
- `G5_upstream_hidden_validity_vs_full_truth`: `blocked`
- `G6_evidence_packaging`: `evaluated_by_task_770_manifest_and_zip_checks`

## Scope
- Generation quality was not run.
- Product routes 18888/18889 were not enabled, modified, or tested.
- The decisive claim is limited to the same-input final-segment contract unless a full truth row is later added.
