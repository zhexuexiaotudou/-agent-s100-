# HF Final Norm + LM Head Only Export v7

- verdict: `pass_hf_final_lmhead_only_logits_exported`
- completed: `42`
- failed: `0`
- norm_tensor: `model.norm.weight`
- lm_tensor: `lm_head.weight`

| case | variant | allzero | nonzero | top1 |
| --- | --- | ---: | ---: | ---: |
| `zeros` | `real_x` | `False` | 152064 | 82733 |
| `zeros` | `real_x_div_2` | `False` | 152064 | 82733 |
| `zeros` | `real_x_div_2p25` | `False` | 152064 | 82733 |
| `zeros` | `real_x_div_2p5` | `False` | 152064 | 82733 |
| `zeros` | `real_x_div_2p75` | `False` | 152064 | 82733 |
| `zeros` | `real_x_div_3` | `False` | 152064 | 82733 |
| `zeros` | `real_x_div_3p25` | `False` | 152064 | 82733 |
| `zeros` | `real_x_div_3p5` | `False` | 152064 | 82733 |
| `zeros` | `real_x_div_4` | `False` | 152064 | 82733 |
| `zeros` | `real_x_clip_8` | `False` | 152064 | 75337 |
| `zeros` | `real_x_clip_6` | `False` | 152064 | 75337 |
| `zeros` | `real_x_clip_5` | `False` | 152064 | 75337 |
| `zeros` | `real_x_clip_4` | `False` | 152064 | 75337 |
| `zeros` | `real_x_z_normalized` | `False` | 152064 | 82733 |
| `ramp` | `real_x` | `False` | 152064 | 61183 |
| `ramp` | `real_x_div_2` | `False` | 152064 | 61183 |
| `ramp` | `real_x_div_2p25` | `False` | 152064 | 61183 |
| `ramp` | `real_x_div_2p5` | `False` | 152064 | 61183 |
| `ramp` | `real_x_div_2p75` | `False` | 152064 | 61183 |
| `ramp` | `real_x_div_3` | `False` | 152064 | 61183 |
| `ramp` | `real_x_div_3p25` | `False` | 152064 | 61183 |
| `ramp` | `real_x_div_3p5` | `False` | 152064 | 61183 |
| `ramp` | `real_x_div_4` | `False` | 152064 | 61183 |
| `ramp` | `real_x_clip_8` | `False` | 152064 | 61183 |
| `ramp` | `real_x_clip_6` | `False` | 152064 | 61183 |
| `ramp` | `real_x_clip_5` | `False` | 152064 | 61183 |
| `ramp` | `real_x_clip_4` | `False` | 152064 | 61183 |
| `ramp` | `real_x_z_normalized` | `False` | 152064 | 61183 |
| `short_chinese_prompt_padded` | `real_x` | `False` | 152064 | 57992 |
| `short_chinese_prompt_padded` | `real_x_div_2` | `False` | 152064 | 57992 |
| `short_chinese_prompt_padded` | `real_x_div_2p25` | `False` | 152064 | 57992 |
| `short_chinese_prompt_padded` | `real_x_div_2p5` | `False` | 152064 | 57992 |
| `short_chinese_prompt_padded` | `real_x_div_2p75` | `False` | 152064 | 57992 |
| `short_chinese_prompt_padded` | `real_x_div_3` | `False` | 152064 | 57992 |
| `short_chinese_prompt_padded` | `real_x_div_3p25` | `False` | 152064 | 57992 |
| `short_chinese_prompt_padded` | `real_x_div_3p5` | `False` | 152064 | 57992 |
| `short_chinese_prompt_padded` | `real_x_div_4` | `False` | 152064 | 57992 |
| `short_chinese_prompt_padded` | `real_x_clip_8` | `False` | 152064 | 57992 |
| `short_chinese_prompt_padded` | `real_x_clip_6` | `False` | 152064 | 57992 |
| `short_chinese_prompt_padded` | `real_x_clip_5` | `False` | 152064 | 57992 |
| `short_chinese_prompt_padded` | `real_x_clip_4` | `False` | 152064 | 57992 |
| `short_chinese_prompt_padded` | `real_x_z_normalized` | `False` | 152064 | 57992 |
