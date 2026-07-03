# Triplet Logits Compare

- verdict: `inconclusive_triplet_compare_bf16_missing`
- case_count: `10`
- gguf_vs_bpu_mean_cosine: `0.0`

## Cases

| case | bf16 | gguf | bpu | gguf_vs_bpu_cosine | gguf_top1 | bpu_top1 |
| --- | --- | --- | --- | ---: | ---: | ---: |
| `zeros` | False | True | True | 0.0 | 151643 | 152063 |
| `ramp` | False | True | True | 0.0 | 151643 | 152063 |
| `repeated_frequent_token` | False | True | True | 0.0 | 220 | 152063 |
| `repeated_rare_token` | False | True | True | 0.0 | 151643 | 152063 |
| `alternating_two_tokens` | False | True | True | 0.0 | 15 | 152063 |
| `short_english_prompt_padded` | False | True | True | 0.0 | 151643 | 152063 |
| `short_chinese_prompt_padded` | False | True | True | 0.0 | 151643 | 152063 |
| `openclaw_style_prompt_padded` | False | True | True | 0.0 | 151643 | 152063 |
| `exactly_128_token_synthetic_prompt` | False | True | True | 0.0 | 151643 | 152063 |
| `prompt_with_mask_tail` | False | True | True | 0.0 | 151643 | 152063 |

## Errors

- `bf16_missing:alternating_two_tokens`
- `bf16_missing:exactly_128_token_synthetic_prompt`
- `bf16_missing:openclaw_style_prompt_padded`
- `bf16_missing:prompt_with_mask_tail`
- `bf16_missing:ramp`
- `bf16_missing:repeated_frequent_token`
- `bf16_missing:repeated_rare_token`
- `bf16_missing:short_chinese_prompt_padded`
- `bf16_missing:short_english_prompt_padded`
- `bf16_missing:zeros`
