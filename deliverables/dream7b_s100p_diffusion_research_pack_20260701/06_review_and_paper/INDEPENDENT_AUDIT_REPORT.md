# Independent Audit Report: Dream7B Diffusion On S100P

Date: 2026-07-01

## Audit Verdict

The evidence pack supports the bounded thesis. Dream7B seq128 B=1 lm_head q16 HBM is compile-feasible and S100P runtime-valid for the tested segmented chain, but the tested BPU logits path fails the numerical gate. The failure occurs at `logits_numerically_valid`, so generation quality and product routing should remain pending.

## Evidence Coverage

| Requirement | Evidence | Audit result |
| --- | --- | --- |
| Read package instructions | `README_FOR_GPT_PRO.md`, `GPT_PRO_REVIEW_PROMPT.md` | Complete |
| Audit final packet | `01_final_evidence/dream7b_s100p_diffusion_research_packet.json` | Complete |
| Audit runtime report | `02_primary_reports/seq128_runtime_gate/seq128_s100p_runtime_gate.json` | Complete |
| Audit logits report | `02_primary_reports/seq128_logits_compare/seq128_logits_reference_compare.json` | Complete |
| Cross-check prior context | `03_prior_evidence/docs/` selected docs | Complete |
| Inspect scripts for reproducibility | `04_scripts/` selected scripts | Complete |
| Check package integrity | `MANIFEST.csv`, `SHA256SUMS.txt` | Complete |

## Gate Findings

| Gate | Status | Evidence summary |
| --- | --- | --- |
| `compile_feasible` | Pass | The final packet reports matching SHA256 `c0e7d6c31af17871cf550ceec88c1bf1ec8de33f30f4d75a9f7b31aa1b73e1b1`; artifact metadata records `seq_len=128`, `batch_size=1`, `segment_count=28`, `hbm_count=28`, and `missing_or_bad=[]`. |
| `s100p_runtime_valid` | Pass | The runtime report records `ok_dream7b_seq128_s100p_runtime_gate`, representative segments `0,5,27` passed, the full chain executed 28 segments, and the final shape was `[1,152064]`. |
| `logits_numerically_valid` | Fail | The logits report records `top1_agreement=0.0`, `ref_top1_in_bpu_top5=0.0`, `mean_cosine=0.0`, `mean_bpu_top1_probability=6.576178451178451e-06`, and `max_bpu_normalized_entropy=1.0`. |
| `generation_quality_valid` | Pending | The gate was not run because the numerical gate failed. This is correct. |
| `product_route_valid` | Pending | The gate was not run because the numerical gate failed. This is correct. |

## Audit Questions

### 1. Does the package prove `compile_feasible` for seq128 B=1 lm_head q16?

Yes. The package proves compile feasibility for the named artifact. The final packet reports a matched SHA256 for the seq128 tar, and the artifact summary records `seq_len=128`, `batch_size=1`, `final_segment=27:28 lm_head_w_bits=16 final_logits_mode=last-token`, `segment_count=28`, and `hbm_count=28`.

### 2. Does the package prove S100P board load/run validity for the tested chain?

Yes. The runtime report proves board load/run validity for the tested chain. It records successful representative execution for segments `0`, `5`, and `27`, successful full-chain execution across 28 segments, final shape `[1,152064]`, and no resource-exhaustion error.

### 3. Does the package falsify numerical validity of the tested BPU logits path?

Yes. The package falsifies the tested BPU logits path under the defined gate. The BPU output disagrees with the GGUF reference on both synthetic cases, with zero top-1 agreement, zero reference-top-1-in-BPU-top-5 rate, zero mean cosine, and entropy equal to the uniform limit.

### 4. Is the use of GGUF Q4_K_M reference an acceptable deployment-blocking control, and what limitation should be stated?

Yes, it is an acceptable deployment-blocking control because the product route uses GGUF as the protected reference path. The limitation is material: this comparison does not replace a BF16 CPU or PyTorch reference comparison. It blocks deployment, but it does not alone prove that the HBM graph is mathematically wrong against an ideal BF16 implementation.

### 5. Are Gate 3 and Gate 4 correctly left pending rather than marked failed?

Yes. Gate 3 and Gate 4 depend on numerical plausibility. Since Gate 2 failed, the study correctly stops before generation-quality prompts and product-route tests. Marking them failed would overclaim evidence that was not collected.

### 6. Are there any claims in the final research note that are stronger than the evidence permits?

No critical overclaim was found. The note states that seq128 has compiled and run on S100P, and that accurate foreground deployment is blocked at the logits gate. The only phrase requiring care in a paper is "BPU last-token logits were effectively uniform/zero"; the report directly supports "uniform-like entropy and near-uniform top-1 probability," while "zero" should be tied to the observed cosine and probability metrics rather than asserted as a raw tensor fact.

### 7. What additional experiment would distinguish an HBM graph defect from a BF16/GGUF reference mismatch?

The next experiment should compare the final BPU segment with a BF16/PyTorch or compiler-side reference on the same hidden input. The procedure should capture the hidden tensor before `seg27_28`, run the final HBM segment and the reference `lm_head` on that identical tensor, inspect raw int16 logits before dequantization, verify output quantization scale handling, and then repeat the top-k, cosine, and entropy metrics.

## Script Reproducibility Check

The runtime gate script checks HBM path naming, model names, expected shapes, representative segments, full-chain execution, and resource-exhaustion errors. The logits comparison script runs GGUF `dump-logits`, executes the BPU chain, extracts last-token logits, and summarizes top-1 agreement, top-5 inclusion, cosine similarity, top-1 probability, and entropy. The final packet script imports the runtime and logits reports and applies the configured gate thresholds.

## Integrity Check

`MANIFEST.csv` and `SHA256SUMS.txt` are present. The package excludes the 8 GB HBM tar and includes only its SHA256, manifest, and summary. This is appropriate for GPT Pro review because the review task depends on provenance and report evidence rather than on direct inspection of the binary artifact.

## Audit Conclusion

The evidence supports a falsification-oriented paper. The strongest defensible conclusion is that runtime feasibility is necessary but insufficient for accurate Dream7B diffusion deployment on S100P. The tested path fails at numerical logits validation, and product promotion should remain blocked until a BF16-aligned final-segment comparison explains the mismatch.

