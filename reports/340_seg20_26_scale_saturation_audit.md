# Task 340 seg20..26 Scale Saturation Audit

- verdict: `late_hidden_scale_mismatch_identified`
- seg26 raw tensors show observed clamp at +/-19807 and dequant abs_max 16.296787 for the pulled cases.
- seg20..23 and BF16 boundaries are unavailable, so exact first BF16-divergent segment is blocked.

| case | raw_min | raw_max | neg_clamp_count | pos_clamp_count | dequant_abs_max |
| --- | --- | --- | --- | --- | --- |
| zeros | -19807 | 19807 | 222057 | 222153 | 16.29678726196289 |
| ramp | -19807 | 19807 | 220805 | 223178 | 16.29678726196289 |
| short_chinese_prompt_padded | -19807 | 19807 | 221148 | 222942 | 16.29678726196289 |
