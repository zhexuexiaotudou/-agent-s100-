# Dream7B S100P Seq128 Logits Validity Route Status

Status date: 2026-07-04.

This document is the repo-level synchronization point for the Dream7B
seq128 segmented-HBM S100P logits-validity research route through v21. It is
not a product launch note and it is not a generation-quality report.

## Current Decision

The current tested Dream7B seq128 segmented-HBM full-BPU path on S100P is
falsified against HF/PyTorch BF16 logits truth. The current product route
remains Qwen + OpenClaw + AI-NAS gates. Dream7B stays in research/evidence
mode until a candidate passes logits validity first.

Current gate state:

| Gate | State |
| --- | --- |
| Compile feasible | pass from prior seq128 HBM gates |
| S100P board load/run/shape | pass from prior seq128 HBM gates |
| Current full-BPU logits numerical validity | fail against HF/PyTorch BF16 truth |
| Correctness-first BPU island or hybrid route | no deployable route found |
| Generation quality | not_run_by_design |
| Product route / 18888 / 18889 | not_run_by_design / not_touched |
| OpenClaw foreground traffic | not_touched |

Allowed claim:

> The current tested seq128 segmented-HBM + BPU runtime + lm_head q16 +
> last-token logits path is falsified by HF/PyTorch BF16 logits truth.

Forbidden claim:

> Dream7B can never run on S100P, or generation quality failed, or the product
> route failed.

Those claims are not supported by the evidence collected in this route.

## Route Timeline

| Stage | Main result | Evidence anchor |
| --- | --- | --- |
| v5-v6 | Compile and runtime shape evidence existed, but logits validity was only blocked against GGUF Q4_K_M and BF16/F16 truth rows were unresolved. | `01_final_evidence/dream7b_s100p_gate_packet_v5.md`, `01_final_evidence/dream7b_s100p_gate_packet_v6.md` |
| v7-v8 | Same-input final-segment fault became strongly supported. S100P `seg27_28` could return all-zero or mismatched logits while HF final norm + lm_head on the same hidden produced nonzero logits. | `01_final_evidence/dream7b_s100p_gate_packet_v7.md`, `01_final_evidence/dream7b_s100p_gate_packet_v8.md` |
| v9 | Exact same-input final segment contract was falsified: 0/42 top-1 agreement, 15/42 all-zero or constant candidate rows, and 36/42 rows with relative L2 > 0.9. Full deployment truth was still incomplete. | `01_final_evidence/dream7b_s100p_gate_packet_v9.md` |
| v10 | Full HF/PyTorch BF16 truth rows became available for canonical cases. Current full deployment was falsified, and evidence showed both upstream hidden mismatch and final-segment contract failure. | `01_final_evidence/dream7b_s100p_gate_packet_v10.md` |
| v11 | v10 was hardened with repeat BF16 truth, source hashes, boundary alignment, and suffix localization. First global divergent comparable segment was segment 0. | `01_final_evidence/dream7b_s100p_gate_packet_v11.md` |
| v13 | Full-BPU, BPU-prefix/HF-suffix, and BPU-island candidates all failed strict logits validity on canonical seq128 cases. | `01_final_evidence/dream7b_s100p_gate_packet_v13.md` |
| v14-v17 | `seg00_01` contract fault remained strongly supported, but exact closure required compiler/vendor source graph and quant metadata. No corrected candidate was justified. | `01_final_evidence/dream7b_s100p_gate_packet_v14.md` through `v17.md` |
| v18 | Position path appeared lookup-like/token-dependent; semantic island battery was blocked because semantic HF truth rows were not available. | `01_final_evidence/dream7b_s100p_gate_packet_v18.md` |
| v19 | Position delta-basis heldout modeling was unrecoverable without internal tensors; semantic HF truth remained blocked by S100P runtime speed after safetensors load. | `01_final_evidence/dream7b_s100p_gate_packet_v19.md` |
| Longrun | Environment repair, GGUF F16 search, operator-contract inventory, GatherND contract review, and candidate-route gates were consolidated. No corrected, logits-valid, generation, or product route was unlocked. | `01_final_evidence/dream7b_s100p_longrun_final_gate_packet.md` |
| v20 | Local export bundle was prepared because S100P HF reference runtime was too slow; semantic truth rows were still missing in the v20 gate. | `01_final_evidence/dream7b_s100p_gate_packet_v20.md` |
| v21 | Local CUDA torch2 BF16 path exported 8/8 original semantic truth rows. BPU islands `[1]`, `[2]`, and `[1,2]` produced partial signal only and no deployable logits-correct route. | `01_final_evidence/dream7b_s100p_gate_packet_v21.md` |

## Latest v21 Facts

v21 resolved the semantic HF truth blocker:

| Fact | Value |
| --- | --- |
| HF truth runtime | local CUDA torch2, BF16 path |
| Original semantic truth rows | 8/8 |
| Total truth rows in island evaluation | 11 |
| BPU island rows | 33 |
| Final v21 verdict | `C_no_valid_semantic_bpu_island` |

Strict logits gate summary for the original 8 semantic prompts:

| Island | Strict pass | Mean relative L2, all 11 rows | Mean cosine, all 11 rows | Status |
| --- | ---: | ---: | ---: | --- |
| `[1]` | 1/8 | 0.549493 | 0.940585 | not deployable |
| `[2]` | 5/8 | 0.518282 | 0.984170 | partial diagnostic signal only |
| `[1,2]` | 2/8 | 0.589896 | 0.969648 | not deployable |

Ramp decision:

`ramp` failed all three tested islands, but semantic prompts also failed or
were mixed. Therefore the current evidence does not support treating ramp as
the sole diagnostic outlier.

Position-path decision:

The position delta-basis model remains
`nonlinear_or_token_dependent_unrecoverable_without_internal_tensor`. Existing
heldout evidence records max relative L2 about `3.552954` and min cosine about
`0.019841`; this is not a deployable correction model.

Corrected-candidate decision:

`not_run_no_justified_correction`. No semantic island passed all original
semantic cases, no deployable position model was recovered, and no official
scale/source-graph/internal-tensor fix was found.

## Repo Evidence Map

Small, repo-trackable evidence anchors:

| Path | Role |
| --- | --- |
| `01_final_evidence/dream7b_s100p_gate_packet_v18.md` through `v21.md` | Final gate packets for the latest research rounds |
| `01_final_evidence/dream7b_s100p_longrun_final_gate_packet.md` | Longrun consolidation gate packet |
| `reports/1900_v18_baseline_lock.*` through `reports/1950_final_v18_gate_packet_and_package.*` | v18 baseline, position-path, semantic island, ramp, corrected candidate, and final package reports |
| `reports/2000_v19_baseline_lock.*` through `reports/2060_final_v19_gate_packet_and_package.*` | v19 semantic truth blocker and position delta-basis reports |
| `reports/2100_hf_semantic_truth_loader.*` through `reports/2800_longrun_final_package.*` | longrun root-cause and candidate-route consolidation |
| `reports/3000_v20_baseline_lock.*` through `reports/3050_final_v20_gate_packet_and_package.*` | v20 S100P reference runtime localization and x86/GPU export bundle |
| `reports/2000_v21_baseline_lock.*`, `reports/2010_semantic_hf_truth_loader_gate.*`, `reports/2020_semantic_bpu_island_battery.*`, `reports/2030_ramp_outlier_decision.*`, `reports/2040_position_delta_basis_model.*`, `reports/2050_corrected_candidate_if_justified_v21.*`, `reports/2060_final_v21_gate_packet_and_package.*` | v21 final reports |
| `reports/PAPER_EVIDENCE_DOSSIER_V21.md` | Paper-facing v21 evidence table |
| `reports/SEMANTIC_BPU_ISLAND_STATUS_V21.md` | Short semantic island status |
| `reports/POSITION_PATH_MODEL_STATUS_V21.md` | Short position-path status |
| `tools/build_v18_research_thread.py` through `tools/build_v21_research_thread.py` | Report/package builders |
| `tools/run_v18_position_path_recovery.py`, `tools/run_v18_semantic_island_battery.py`, `tools/run_v19_semantic_hf_truth_loader.py`, `tools/run_v20_single_case_forward_localization.py`, `tools/run_v21_bpu_islands_from_boundaries.py`, `tools/run_v21_hf_boundaries_and_island_eval.py` | Reproduction and evaluation helpers |

Large evidence remains local/NAS only and is intentionally not committed:

| Artifact | Local path or package |
| --- | --- |
| v21 GPT Pro review bundle | `evidence_for_gptpro/dream7b_s100p_v21_for_gptpro_20260704_122503.zip` |
| v21 GPT Pro bundle SHA256 | `cb5d401bf52e13589fbbbf01b5db91304a98d0a5b317e7081c0198da9cbe7b0e` |
| HF truth tensor dumps | `evidence/semantic_hf_truth_v21/` |
| HF boundary and suffix logits tensors | `evidence/semantic_island_battery_v21/` |
| Pulled S100P BPU island outputs | `evidence/dream7b_s100p_v21_execution_20260704/` |
| Full BPU output tar | `evidence/dream7b_s100p_v21_execution_20260704_bpu_outputs.tar.gz` |

## Boundary Rules For Future Work

Do not run generation quality until a logits-valid route exists. Do not enable
or modify 18888/18889 for this Dream7B research route. Do not attach Dream7B to
OpenClaw foreground traffic. Do not describe partial island passes as
deployment success.

Next useful work must be logits-only and correctness-first:

1. Obtain vendor/compiler source graph and quant metadata for `seg00_01`,
   especially position/GatherND handling and boundary layout.
2. Re-export or recalibrate `seg00_01` with official tensor-contract metadata,
   then rerun HF-prefix/BPU-island/HF-suffix logits gates.
3. If a new corrected artifact is produced, validate it only on canonical and
   semantic logits gates before any generation or product-route work.
4. Keep the product path documented as Qwen + OpenClaw unless a Dream7B
   candidate passes the complete logits gate first.
