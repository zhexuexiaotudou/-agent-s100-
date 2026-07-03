# Task 350 Final Segment Threshold Contract

- verdict: `threshold_localized_nonzero_recovery_not_correctness`
- Dense S100P sweep refined the old coarse `/4` result: first nonzero divisor is `/2.75` in zeros/ramp/short_chinese.
- The all-zero transition lies between `/2` abs_max 8.148 and `/2.75` abs_max about 5.926; clip first recovers at +/-6.

| case | first nonzero divisor | x/2 allzero | x/3 nonzero_count |
| --- | --- | --- | --- |
| ramp | real_x_div_2p75 | True | 152043 |
| short_chinese_prompt_padded | real_x_div_2p75 | True | 152053 |
| zeros | real_x_div_2p75 | True | 152063 |
