# Final Segment Input-Contract Sweep

- verdict: `pass`
- smallest_recovery_variant: `real_x_div_4`
- likely_issue_class: `input_range_or_scale`
- HF seg26 hidden input: `unavailable`

## Required Variants

| variant | status | input abs_max | output allzero | output nonzero | output std | top1 |
| --- | --- | ---: | --- | ---: | ---: | ---: |
| `real_x` | `pass` | 16.29678726196289 | True | 0 | 0.0 | 0 |
| `real_x_div_2` | `pass` | 8.148393630981445 | True | 0 | 0.0 | 0 |
| `real_x_div_4` | `pass` | 4.074196815490723 | False | 152059 | 0.8246555921828305 | 76842 |
| `real_x_div_8` | `pass` | 2.0370984077453613 | False | 152058 | 0.4637689703929305 | 85512 |
| `real_x_div_16` | `pass` | 1.0185492038726807 | False | 152038 | 0.38345359806250856 | 54462 |
| `real_x_div_32` | `pass` | 0.5092746019363403 | False | 152053 | 0.3925311739573611 | 51735 |
| `real_x_clip_16` | `pass` | 16.0 | True | 0 | 0.0 | 0 |
| `real_x_clip_8` | `pass` | 8.0 | True | 0 | 0.0 | 0 |
| `real_x_clip_4` | `pass` | 4.0 | False | 152064 | 0.8244867287435699 | 85512 |
| `real_x_clip_2` | `pass` | 2.0 | False | 152056 | 0.46447696766555446 | 85512 |
| `real_x_clip_1` | `pass` | 1.0 | False | 152044 | 0.38368675009826936 | 54462 |
| `real_x_z_normalized` | `pass` | 1.0110434293746948 | False | 152042 | 0.38327288099064066 | 54462 |
| `synthetic_match_mean_std_normal` | `pass` | 74.40174865722656 | True | 0 | 0.0 | 0 |
| `synthetic_match_min_max_uniform` | `pass` | 16.296770095825195 | True | 0 | 0.0 | 0 |
| `synthetic_zeros` | `pass` | 0.0 | False | 152062 | 1.2518448336849501 | 32216 |
| `synthetic_ones` | `pass` | 1.0 | False | 152061 | 0.42579590471044604 | 51735 |
| `synthetic_ramp` | `pass` | 0.9921259880065918 | False | 152052 | 0.42846334553574744 | 51735 |
| `synthetic_last_token_impulse` | `pass` | 1.0 | False | 152060 | 0.43524578378288403 | 66906 |
| `real_raw_int16_as_input` | `fail` | 19807.0 | None | None | None | None |

## Interpretation

Real BPU seg26 hidden at original scale and /2 drives seg27_28 to all-zero logits. The first recovery is /4, and clip_4 / clip_2 / clip_1 / z-normalized variants are nonconstant. This is a diagnostic recovery only; it does not validate corrected logits against BF16 or GGUF. It points to input range/scale or final-segment input contract rather than generation quality.
