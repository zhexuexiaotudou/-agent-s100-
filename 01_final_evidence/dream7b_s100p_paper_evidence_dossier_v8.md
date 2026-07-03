# Dream7B/S100P v8 Paper Evidence Dossier

v8 corrects the v7 evidence-packaging overclaim and applies the official final-output dequant scale before comparing final-segment diagnostic logits. The v8 verdict is `E_final_segment_contract_fault_strongly_supported_full_reference_unresolved`.

The robust claim is bounded: S100P seq128 segmented HBM still lacks validated logits numerical correctness. All-segment boundary evidence shows earlier saturation beginning before the final segment, and official-dequant final outputs show the real `seg26` handoff still produces all-zero final logits while scaled/clipped diagnostics remain top-k weak or tie/saturation affected.

`seg27_28` is best treated as a final decoder-layer-through-lm-head segment unless exact compiler metadata proves otherwise. Therefore v7's HF final RMSNorm+lm_head-only route is retained as a diagnostic boundary candidate, not a final proof of exact function equivalence.

Generation quality and product route 18888/18889 were not run. Accurate deployment, BF16 falsification, and scale-fix claims remain forbidden unless a full BF16/FP32 or GGUF F16 truth row plus exact boundary comparison passes.
