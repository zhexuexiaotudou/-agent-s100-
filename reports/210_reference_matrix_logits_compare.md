# Dream-7B Reference Matrix Logits Compare

- scope: `seq128 last-token logits numerical comparison only; generation quality not run`
- verdict: `blocked_against_gguf_q4_k_m_bf16_f16_q4_0_unavailable`
- case_count: `10`
- gguf_q4_k_m_vs_s100p_bpu_mean_cosine: `0.0`

## Backend Status

| Backend | Status | Reason |
| --- | --- | --- |
| `hf_pytorch_bf16` | `unavailable` | verified_dream7b_diffusion_forward_wrapper_not_available |
| `gguf_f16` | `unavailable` | not present in current v3 evidence set |
| `gguf_q4_0` | `unavailable` | not present in current v3 evidence set |
| `gguf_q4_k_m` | `available` |  |
| `s100p_bpu_raw_dequant` | `available` |  |

## Cases

| case | BF16 | F16 | Q4_0 | Q4_K_M | S100P raw nz | cosine Q4_K_M vs BPU | ref top1 | bpu top1 |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `zeros` | False | False | False | True | 0 | 0.0 | 151643 | 152063 |
| `ramp` | False | False | False | True | 0 | 0.0 | 151643 | 152063 |
| `repeated_frequent_token` | False | False | False | True | 0 | 0.0 | 220 | 152063 |
| `repeated_rare_token` | False | False | False | True | 0 | 0.0 | 151643 | 152063 |
| `alternating_two_tokens` | False | False | False | True | 0 | 0.0 | 15 | 152063 |
| `short_english_prompt_padded` | False | False | False | True | 0 | 0.0 | 151643 | 152063 |
| `short_chinese_prompt_padded` | False | False | False | True | 0 | 0.0 | 151643 | 152063 |
| `openclaw_style_prompt_padded` | False | False | False | True | 0 | 0.0 | 151643 | 152063 |
| `exactly_128_token_synthetic_prompt` | False | False | False | True | 0 | 0.0 | 151643 | 152063 |
| `prompt_with_mask_tail` | False | False | False | True | 0 | 0.0 | 151643 | 152063 |

## Missing Artifacts

- `verified Dream-7B HF/PyTorch BF16 diffusion forward wrapper and logits`
- `GGUF F16 logits for the same seq128 token-id cases`
- `GGUF Q4_0 logits for the same seq128 token-id cases`
