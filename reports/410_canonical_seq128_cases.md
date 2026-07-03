# Task 410 Canonical seq128 Cases

- verdict: `pass_canonical_cases_verified`
- case_count: `10`
- All cases have 128 token IDs, positions, masks, and last_token_index 127.

| case | type | token_ids_sha256_prefix |
| --- | --- | --- |
| zeros | diagnostic | 1b912946d3fd5846 |
| ramp | diagnostic | f0d76dfdfbf5467a |
| repeated_frequent_token | diagnostic | 6285266a2fb67a34 |
| repeated_rare_token | diagnostic | 5ea5eb622675b234 |
| alternating_two_tokens | diagnostic | 37e76277f06f791e |
| short_english_prompt_padded | semantic | 887ea52fe6542082 |
| short_chinese_prompt_padded | semantic | ac26ad530204a4bc |
| openclaw_style_prompt_padded | semantic | 27eaf7ec33df2e2b |
| exactly_128_token_synthetic_prompt | diagnostic | 00b74a18a594b2de |
| prompt_with_mask_tail | semantic | a61399757647c412 |
