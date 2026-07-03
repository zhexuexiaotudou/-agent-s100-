# Task 400 Evidence Hygiene and Raw Endpoints

- verdict: `pass_all_endpoint_raw_arrays_present_and_verified`
- verified endpoints: `42/42`
- raw endpoint manifest files: `168`
- All critical endpoint stats were recomputed from local `.npy` files.

| case | variant | input_abs_max | raw_allzero | raw_nonzero |
| --- | --- | --- | --- | --- |
| zeros | real_x | 16.29678726196289 | True | 0 |
| zeros | real_x_div_2 | 8.148393630981445 | True | 0 |
| zeros | real_x_div_2p75 | 5.926104545593262 | False | 152062 |
| zeros | real_x_div_3 | 5.432262420654297 | False | 152063 |
| zeros | real_x_clip_6 | 6.0 | False | 152064 |
| ramp | real_x | 16.29678726196289 | True | 0 |
| ramp | real_x_div_2 | 8.148393630981445 | True | 0 |
| ramp | real_x_div_2p75 | 5.926104545593262 | False | 152046 |
| ramp | real_x_div_3 | 5.432262420654297 | False | 152043 |
| ramp | real_x_clip_6 | 6.0 | False | 152045 |
| short_chinese_prompt_padded | real_x | 16.29678726196289 | True | 0 |
| short_chinese_prompt_padded | real_x_div_2 | 8.148393630981445 | True | 0 |
| short_chinese_prompt_padded | real_x_div_2p75 | 5.926104545593262 | False | 152046 |
| short_chinese_prompt_padded | real_x_div_3 | 5.432262420654297 | False | 152053 |
| short_chinese_prompt_padded | real_x_clip_6 | 6.0 | False | 152047 |
