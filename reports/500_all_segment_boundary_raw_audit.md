# Task 500 All-segment Boundary Raw Audit

- verdict: `pass_all_segment_raw_boundaries_packaged`
- missing raw/dequant arrays: `0`
- packaged files under boundary root: `261`

| case | first any int16 extreme | first both-sided extreme | first >1% saturation | first std jump >10x | first allzero raw |
| --- | ---: | ---: | ---: | ---: | ---: |
| `zeros` | 9 | 12 | 12 | 11 | 27 |
| `ramp` | 9 | 12 | 12 | 11 | 27 |
| `short_chinese_prompt_padded` | 9 | 12 | 12 | 11 | 27 |
