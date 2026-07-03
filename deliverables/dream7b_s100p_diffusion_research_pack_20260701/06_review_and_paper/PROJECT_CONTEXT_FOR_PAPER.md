# Project Context For Paper Draft

## Identity Sentence

This paper evaluates Dream7B diffusion deployment on S100P with a layered falsification protocol and shows that compile success and board runtime success do not establish accurate deployment.

## Bounded Thesis

Dream7B seq128 B=1 lm_head q16 HBM reaches `compile_feasible` and `s100p_runtime_valid`, but the tested BPU path fails `logits_numerically_valid` against the available GGUF Q4_K_M dump-logits reference.

## Claim Boundaries

- The paper may claim that the tested seq128 segmented HBM chain compiles and runs on S100P.
- The paper may claim that the tested logits path fails the deployed numerical gate.
- The paper must not claim that all diffusion models are impossible on S100P.
- The paper must not claim that seq128 generation quality failed.
- The paper must not claim that product routing failed.
- The paper must state that the reference is GGUF Q4_K_M, not a completed BF16 CPU reference.
- Seq16 evidence is a negative control and boundary condition, not proof about seq128.

## Evidence Anchor

- Final packet: `01_final_evidence/dream7b_s100p_diffusion_research_packet.json`
- Runtime gate: `02_primary_reports/seq128_runtime_gate/seq128_s100p_runtime_gate.json`
- Logits comparison: `02_primary_reports/seq128_logits_compare/seq128_logits_reference_compare.json`
- Artifact metadata: `05_artifact_metadata/seq128_b1_lmheadq16_lasttoken_summary.json`
- Two-track boundary: `03_prior_evidence/docs/dream7b_openclaw_two_track_deployment_2026-06-22.md`

## Contribution Claims

1. **Layered falsification.** The study separates compile feasibility, board runtime validity, numerical logits validity, generation quality, and product routing.
2. **Runtime feasibility.** The seq128 segmented HBM package loads and runs representative segments and the full 28-segment chain on S100P.
3. **Numerical failure.** The tested BPU logits path fails top-1 agreement, top-5 inclusion, cosine similarity, and entropy checks against the available GGUF reference.
4. **Deployment boundary.** The evidence blocks foreground product promotion while preserving the existing 18888 GGUF route and seq16 baseline.

