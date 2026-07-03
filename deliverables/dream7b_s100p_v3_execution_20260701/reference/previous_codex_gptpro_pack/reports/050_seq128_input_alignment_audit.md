# Seq128 Input Alignment Audit

- input_alignment_valid: `pass`
- tokenizer_decode_status: `inconclusive_tokenizer_api_not_used`
- case_count: `6`

| case | len | nonpad | masks | semantic | diagnostic | errors |
| --- | ---: | ---: | ---: | --- | --- | --- |
| `zeros` | 128 | 0 | 0 | False | True | `` |
| `ramp` | 128 | 128 | 0 | False | True | `` |
| `single_token_repeat` | 128 | 128 | 0 | False | True | `` |
| `alternating_tokens` | 128 | 128 | 0 | False | True | `` |
| `real_prompt_padded` | 128 | 10 | 0 | True | False | `` |
| `real_prompt_mask_tail` | 128 | 14 | 4 | True | False | `` |
