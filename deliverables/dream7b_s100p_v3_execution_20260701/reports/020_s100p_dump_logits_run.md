# S100P BPU Dump Logits

- verdict: `blocked_s100p_dump_logits_anomaly`
- case_count: `10`

| case | raw constant | entropy | top1 prob | top1 |
| --- | --- | ---: | ---: | ---: |
| `zeros` | True | 1.000000 | 0.00000658 | 152063 |
| `ramp` | True | 1.000000 | 0.00000658 | 152063 |
| `repeated_frequent_token` | True | 1.000000 | 0.00000658 | 152063 |
| `repeated_rare_token` | True | 1.000000 | 0.00000658 | 152063 |
| `alternating_two_tokens` | True | 1.000000 | 0.00000658 | 152063 |
| `short_english_prompt_padded` | True | 1.000000 | 0.00000658 | 152063 |
| `short_chinese_prompt_padded` | True | 1.000000 | 0.00000658 | 152063 |
| `openclaw_style_prompt_padded` | True | 1.000000 | 0.00000658 | 152063 |
| `exactly_128_token_synthetic_prompt` | True | 1.000000 | 0.00000658 | 152063 |
| `prompt_with_mask_tail` | True | 1.000000 | 0.00000658 | 152063 |

## Errors

- none
