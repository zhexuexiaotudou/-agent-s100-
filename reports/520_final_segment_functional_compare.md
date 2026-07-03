# Task 520 Final Segment Functional Compare

- verdict: `pass_final_segment_mismatch_quantified_same_input`
- comparisons: `27`
- mismatches by top1/top5: `23`
- real_x BPU all-zero while HF lmhead nonzero cases: `3`

| case | variant | top1 agree | top5 overlap | cosine | BPU allzero | HF allzero | BPU top1 | HF top1 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `zeros` | `real_x` | `False` | 0 | 0 | `True` | `False` | 152063 | 82733 |
| `zeros` | `real_x_div_2` | `False` | 0 | 0 | `True` | `False` | 152063 | 82733 |
| `zeros` | `real_x_div_2p5` | `False` | 0 | 0 | `True` | `False` | 152063 | 82733 |
| `zeros` | `real_x_div_2p75` | `False` | 2 | 0.994481 | `False` | `False` | 74466 | 82733 |
| `zeros` | `real_x_div_3` | `False` | 2 | 0.993133 | `False` | `False` | 76842 | 82733 |
| `zeros` | `real_x_clip_8` | `False` | 0 | 0 | `True` | `False` | 152063 | 75337 |
| `zeros` | `real_x_clip_6` | `False` | 3 | 0.99457 | `False` | `False` | 76842 | 75337 |
| `zeros` | `real_x_clip_5` | `False` | 2 | 0.991307 | `False` | `False` | 76842 | 75337 |
| `zeros` | `real_x_z_normalized` | `False` | 0 | -0.363272 | `False` | `False` | 54462 | 82733 |
| `ramp` | `real_x` | `False` | 0 | 0 | `True` | `False` | 152063 | 61183 |
| `ramp` | `real_x_div_2` | `False` | 0 | 0 | `True` | `False` | 152063 | 61183 |
| `ramp` | `real_x_div_2p5` | `False` | 0 | 0 | `True` | `False` | 152063 | 61183 |
| `ramp` | `real_x_div_2p75` | `True` | 2 | 0.725317 | `False` | `False` | 61183 | 61183 |
| `ramp` | `real_x_div_3` | `True` | 2 | 0.657556 | `False` | `False` | 61183 | 61183 |
| `ramp` | `real_x_clip_8` | `False` | 0 | 0 | `True` | `False` | 152063 | 61183 |
| `ramp` | `real_x_clip_6` | `True` | 2 | 0.723169 | `False` | `False` | 61183 | 61183 |
| `ramp` | `real_x_clip_5` | `True` | 2 | 0.562974 | `False` | `False` | 61183 | 61183 |
| `ramp` | `real_x_z_normalized` | `False` | 0 | -0.476698 | `False` | `False` | 54462 | 61183 |
| `short_chinese_prompt_padded` | `real_x` | `False` | 0 | 0 | `True` | `False` | 152063 | 57992 |
| `short_chinese_prompt_padded` | `real_x_div_2` | `False` | 0 | 0 | `True` | `False` | 152063 | 57992 |
| `short_chinese_prompt_padded` | `real_x_div_2p5` | `False` | 0 | 0 | `True` | `False` | 152063 | 57992 |
| `short_chinese_prompt_padded` | `real_x_div_2p75` | `False` | 1 | 0.779518 | `False` | `False` | 72869 | 57992 |
| `short_chinese_prompt_padded` | `real_x_div_3` | `False` | 1 | 0.718091 | `False` | `False` | 72869 | 57992 |
| `short_chinese_prompt_padded` | `real_x_clip_8` | `False` | 0 | 0 | `True` | `False` | 152063 | 57992 |
| `short_chinese_prompt_padded` | `real_x_clip_6` | `False` | 1 | 0.857517 | `False` | `False` | 72869 | 57992 |
| `short_chinese_prompt_padded` | `real_x_clip_5` | `False` | 1 | 0.777363 | `False` | `False` | 72869 | 57992 |
| `short_chinese_prompt_padded` | `real_x_z_normalized` | `False` | 0 | -0.647821 | `False` | `False` | 66906 | 57992 |
