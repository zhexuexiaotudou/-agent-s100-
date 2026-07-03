# Dream7B S100P Diffusion Research Evidence Pack

Package date: 2026-07-01

This pack is intended for an independent GPT Pro review before drafting a paper. It contains the evidence needed to evaluate whether the Dream7B diffusion model was accurately deployed on S100P under a gate-based definition of accuracy.

## Core Question

Can Dream7B diffusion be accurately deployed on S100P?

The answer must be layered, not binary:

- `compile_feasible`
- `s100p_runtime_valid`
- `logits_numerically_valid`
- `generation_quality_valid`
- `product_route_valid`

The current evidence supports this bounded conclusion:

> The seq128 B=1 lm_head q16 HBM package is compile-feasible and S100P runtime-valid, but it is falsified at `logits_numerically_valid` under the available GGUF reference comparison. Therefore it should not be promoted to generation or product routing.

Do not overstate this as "diffusion models can never run on S100P." The runtime gate passed. The falsification layer is numerical correctness of logits for the tested artifact and path.

## Directory Map

- `01_final_evidence/`
  - Final research note and final machine-readable evidence packet.
- `02_primary_reports/seq128_runtime_gate/`
  - S100P board load/run report for representative segments and the full 28-segment chain.
- `02_primary_reports/seq128_logits_compare/`
  - GGUF reference vs BPU logits report. This is the decisive failed gate.
- `02_primary_reports/research_packets_intermediate/`
  - Earlier packets showing the transition from Gate 0 pending to Gate 1 pass.
- `03_prior_evidence/docs/`
  - Prior reports needed to understand compile feasibility, seq16 negative controls, OpenClaw two-track boundary, and prior true-batch/product evidence.
- `03_prior_evidence/negative_controls/`
  - Prior negative-control packets and route boundary evidence.
- `04_scripts/`
  - Scripts used or referenced to generate and reproduce the reports.
- `05_artifact_metadata/`
  - seq128 cloud artifact summary, manifest, and tar SHA256. The 8 GB HBM tar itself is intentionally excluded.
- `06_review_and_paper/`
  - Completed independent audit report, project context, Chinese paper draft, and style/structure audit.
- `MANIFEST.csv`
  - File list with sizes and SHA256 hashes.
- `SHA256SUMS.txt`
  - Hashes for all files in the package.

## Evidence To Verify First

1. Read `01_final_evidence/dream7b_s100p_diffusion_research_packet.json`.
2. Confirm:
   - `verdict = falsified_or_blocked_dream7b_seq128_logits_numerical_gate`
   - `falsification_layer = logits_numerically_valid`
   - `compile_feasible.status = pass`
   - `s100p_runtime_valid.status = pass`
   - `logits_numerically_valid.status = fail`
3. Read `02_primary_reports/seq128_runtime_gate/seq128_s100p_runtime_gate.json`.
   - Confirm representative segments and full chain passed.
   - Confirm final output shape `[1, 152064]`.
4. Read `02_primary_reports/seq128_logits_compare/seq128_logits_reference_compare.json`.
   - Confirm `top1_agreement = 0.0`.
   - Confirm `ref_top1_in_bpu_top5 = 0.0`.
   - Confirm `mean_cosine = 0.0`.
   - Confirm `max_bpu_normalized_entropy = 1.0`.
   - Confirm the report used `reference = gguf_q4km_dump_logits`.

## Important Caveats

- The numerical reference used here is the available GGUF Q4_K_M dump-logits path, not a BF16 CPU reference. This is still sufficient to block deployment under the defined gate, but it should be described carefully in a paper.
- Gate 3 and Gate 4 were not run because Gate 2 failed. They are not independent failures.
- The 8 GB tar was excluded from this review package. Its SHA256, manifest, summary, size, and deployment path evidence are included.
- Production route boundaries were preserved: no 18888 overwrite, no foreground BPU route enablement, no seq16 baseline deletion, and no seq256 compile.

## Recommended Paper Framing

Use a falsification-oriented systems paper structure:

1. Problem and deployment context.
2. Layered gate methodology.
3. Artifact provenance and compile evidence.
4. S100P runtime validation.
5. Numerical logits validation and failure analysis.
6. Negative controls and two-track product boundary.
7. Discussion of what is proven, what is disproven, and what remains untested.
8. Conclusion: runtime feasibility is not sufficient for accurate deployment.
