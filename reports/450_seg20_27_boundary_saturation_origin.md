# Task 450 seg20..27 Boundary Saturation Origin

- verdict: `partial_late_saturation_bounded_to_segment_range`
- S100P offline dump completed for seg20..27 on zeros/ramp/short_chinese.
- First observed full int16 positive max appears at seg20 for all three cases; BF16 divergence remains blocked.

| case | seg | raw_min | raw_max | raw_nonzero | deq_abs_max | constant |
| --- | --- | --- | --- | --- | --- | --- |
| zeros | 20 | -18460.0 | 32767.0 | 458677 | 23.074800491333008 | False |
| zeros | 21 | -8944.0 | 8944.0 | 458701 | 6.280498027801514 | False |
| zeros | 22 | -32768.0 | 32767.0 | 458741 | 43.65851593017578 | False |
| zeros | 23 | -4458.0 | 4458.0 | 458734 | 13.896108627319336 | False |
| zeros | 24 | -32768.0 | 32767.0 | 458751 | 16.745126724243164 | False |
| zeros | 25 | -32768.0 | 32767.0 | 458751 | 258.418701171875 | False |
| zeros | 26 | -19807.0 | 19807.0 | 458751 | 16.29678726196289 | False |
| zeros | 27 | 0.0 | 0.0 | 0 | 0.0 | True |
| ramp | 20 | -22363.0 | 32767.0 | 458682 | 23.074800491333008 | False |
| ramp | 21 | -8944.0 | 8944.0 | 458683 | 6.280498027801514 | False |
| ramp | 22 | -32768.0 | 32767.0 | 458746 | 43.65851593017578 | False |
| ramp | 23 | -4458.0 | 4458.0 | 458734 | 13.896108627319336 | False |
| ramp | 24 | -32768.0 | 32767.0 | 458750 | 16.745126724243164 | False |
| ramp | 25 | -32768.0 | 32767.0 | 458749 | 258.418701171875 | False |
| ramp | 26 | -19807.0 | 19807.0 | 458752 | 16.29678726196289 | False |
| ramp | 27 | 0.0 | 0.0 | 0 | 0.0 | True |
| short_chinese_prompt_padded | 20 | -19824.0 | 32767.0 | 458664 | 23.074800491333008 | False |
| short_chinese_prompt_padded | 21 | -8944.0 | 8944.0 | 458698 | 6.280498027801514 | False |
| short_chinese_prompt_padded | 22 | -32768.0 | 32767.0 | 458746 | 43.65851593017578 | False |
| short_chinese_prompt_padded | 23 | -4458.0 | 4458.0 | 458732 | 13.896108627319336 | False |
| short_chinese_prompt_padded | 24 | -32768.0 | 32767.0 | 458752 | 16.745126724243164 | False |
| short_chinese_prompt_padded | 25 | -32768.0 | 32767.0 | 458747 | 258.418701171875 | False |
| short_chinese_prompt_padded | 26 | -19807.0 | 19807.0 | 458752 | 16.29678726196289 | False |
| short_chinese_prompt_padded | 27 | 0.0 | 0.0 | 0 | 0.0 | True |
