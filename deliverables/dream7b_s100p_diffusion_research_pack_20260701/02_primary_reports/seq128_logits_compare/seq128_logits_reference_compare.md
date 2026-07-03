# Dream7B Seq128 Logits Reference Compare

- generated_at: `2026-07-01T01:55:09.152237+08:00`
- verdict: `blocked_dream7b_seq128_logits_reference_compare`
- reference: `gguf_q4km_dump_logits`
- case_count: `2`
- top1_agreement: `0.0`
- ref_top1_in_bpu_top5: `0.0`
- mean_cosine: `0.0`
- min_bpu_top1_probability: `6.576178451178451e-06`
- max_bpu_normalized_entropy: `1.0`

## Cases

| case | ref_top1 | bpu_top1 | top1_match | ref_top1_in_bpu_top5 | cosine | bpu_top1_prob | bpu_entropy |
| --- | ---: | ---: | --- | --- | ---: | ---: | ---: |
| `zeros` | 151643 | 152063 | False | False | 0.000000 | 0.000007 | 1.000000 |
| `ramp` | 151643 | 152063 | False | False | 0.000000 | 0.000007 | 1.000000 |

## Errors

- `top1_agreement_below_threshold`
- `ref_top1_in_bpu_top5_below_threshold`
- `mean_cosine_below_threshold`
- `bpu_top1_probability_below_threshold`
- `bpu_entropy_too_uniform`

## Boundary

- This compares seq128 BPU HBM against the local GGUF q4km dump-logits reference, not BF16.
- Passing this gate would support continuing to generation quality; failing it blocks product promotion but does not alone prove the HBM graph is mathematically wrong versus BF16.
