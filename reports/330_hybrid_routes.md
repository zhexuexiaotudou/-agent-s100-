# Task 330 Hybrid Routes

- Route A/B are blocked by missing verified HF lm_head and HF seg26 boundary.
- Route C was executed as dense final-segment diagnostic sweep on S100P for zeros/ramp/short_chinese.
- Corrected scale restores nonzero logits but is not correctness without BF16/GGUF F16 comparison.

| case | first nonzero divisor | first nonzero clip |
| --- | --- | --- |
| ramp | real_x_div_2p75 | real_x_clip_6 |
| short_chinese_prompt_padded | real_x_div_2p75 | real_x_clip_6 |
| zeros | real_x_div_2p75 | real_x_clip_6 |
