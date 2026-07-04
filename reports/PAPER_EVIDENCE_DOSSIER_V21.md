# Paper Evidence Dossier v21

## Claim
The current tested Dream7B seq128 segmented-HBM S100P full-BPU path remains falsified against HF/PyTorch BF16 logits truth; v21 additionally shows that early semantic BPU islands [1], [2], and [1,2] do not provide a deployable correctness-first route.

## Evidence Table
| Gate | Evidence | Result |
| --- | --- | --- |
| HF semantic truth | 8/8 original semantic rows on cuda | pass |
| BPU island [1] | strict 1/8 original semantic | not deployable |
| BPU island [2] | strict 5/8 original semantic | not deployable |
| BPU island [1,2] | strict 2/8 original semantic | not deployable |
| Ramp outlier | B_ramp_not_outlier_semantic_also_fails | ramp not sole explanation |
| Position path | nonlinear_or_token_dependent_unrecoverable_without_internal_tensor | not deployable |

Generation quality and product routes were intentionally not run.
