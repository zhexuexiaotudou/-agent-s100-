# Dequant Audit

- verdict: `upstream_graph_or_runtime_issue_raw_constant`
- raw_constant_cases: `['zeros', 'ramp', 'repeated_frequent_token', 'repeated_rare_token', 'alternating_two_tokens', 'short_english_prompt_padded', 'short_chinese_prompt_padded', 'openclaw_style_prompt_padded', 'exactly_128_token_synthetic_prompt', 'prompt_with_mask_tail']`

| case | scale | raw_constant | official_entropy | best_variant |
| --- | ---: | --- | ---: | --- |
| `zeros` | 0.00025415877462364733 | True | 1.0 | `{'variant': 'identity_float', 'cosine': 0.0}` |
| `ramp` | 0.00025415877462364733 | True | 1.0 | `{'variant': 'identity_float', 'cosine': 0.0}` |
| `repeated_frequent_token` | 0.00025415877462364733 | True | 1.0 | `{'variant': 'identity_float', 'cosine': 0.0}` |
| `repeated_rare_token` | 0.00025415877462364733 | True | 1.0 | `{'variant': 'identity_float', 'cosine': 0.0}` |
| `alternating_two_tokens` | 0.00025415877462364733 | True | 1.0 | `{'variant': 'identity_float', 'cosine': 0.0}` |
| `short_english_prompt_padded` | 0.00025415877462364733 | True | 1.0 | `{'variant': 'identity_float', 'cosine': 0.0}` |
| `short_chinese_prompt_padded` | 0.00025415877462364733 | True | 1.0 | `{'variant': 'identity_float', 'cosine': 0.0}` |
| `openclaw_style_prompt_padded` | 0.00025415877462364733 | True | 1.0 | `{'variant': 'identity_float', 'cosine': 0.0}` |
| `exactly_128_token_synthetic_prompt` | 0.00025415877462364733 | True | 1.0 | `{'variant': 'identity_float', 'cosine': 0.0}` |
| `prompt_with_mask_tail` | 0.00025415877462364733 | True | 1.0 | `{'variant': 'identity_float', 'cosine': 0.0}` |
