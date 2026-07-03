# S100P Dequant/Layout Audit

- verdict: `upstream_graph_or_runtime_issue_raw_constant`
- all_final_raw_logits_zero: `True`
- layout_dequant_rescue_found: `False`

## Audit Dimensions

| dimension | status | note |
| --- | --- | --- |
| `official_dequant` | `executed` | scale_x |
| `per_tensor_scale` | `available` | HBRT output quant metadata exposes scalar scale and zero_point |
| `per_channel_scale` | `unavailable` | current HBRT metadata for final logits exposes scalar scale only; no per-channel vector scale was available |
| `signed_unsigned_reinterpretation` | `executed` | ['identity_float', 'uint16_reinterpret'] |
| `endian_swap` | `executed` | byteswap_int16 |
| `stride_layout_variants` | `logically_non_rescuing_for_final_logits` | final raw logits are all zero for all tested cases; stride or permutation cannot recover nonzero values from an all-zero vector |
| `raw_int_stats` | `available` |  |

## Final Logits Cases

| case | raw nonzero | raw min | raw max | best variant | best cosine |
| --- | ---: | ---: | ---: | --- | ---: |
| `zeros` | 0 | 0.0 | 0.0 | `identity_float` | 0.0 |
| `ramp` | 0 | 0.0 | 0.0 | `identity_float` | 0.0 |
| `repeated_frequent_token` | 0 | 0.0 | 0.0 | `identity_float` | 0.0 |
| `repeated_rare_token` | 0 | 0.0 | 0.0 | `identity_float` | 0.0 |
| `alternating_two_tokens` | 0 | 0.0 | 0.0 | `identity_float` | 0.0 |
| `short_english_prompt_padded` | 0 | 0.0 | 0.0 | `identity_float` | 0.0 |
| `short_chinese_prompt_padded` | 0 | 0.0 | 0.0 | `identity_float` | 0.0 |
| `openclaw_style_prompt_padded` | 0 | 0.0 | 0.0 | `identity_float` | 0.0 |
| `exactly_128_token_synthetic_prompt` | 0 | 0.0 | 0.0 | `identity_float` | 0.0 |
| `prompt_with_mask_tail` | 0 | 0.0 | 0.0 | `identity_float` | 0.0 |

## Interpretation

All tested final raw logits are already constant all-zero. Official dequant, scalar scale, zero-point handling, uint16 reinterpretation, and endian swap cannot recover nonzero logits. Late hidden states are nonzero and often saturated, so the current failure is upstream of output dequant and at or before final segment execution/output emission.
