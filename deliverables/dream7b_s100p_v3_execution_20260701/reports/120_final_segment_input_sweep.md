# Final Segment Input Sweep V3

- verdict: `pass`
- real_hidden_constant_output: `True`
- synthetic_controls_nonconstant: `True`
- smallest_recovery_variant: `real_x_div_4`
- likely_issue_class: `input_range_or_scale`

| variant | status | constant | allzero | nonzero | std | norm_entropy | top1 |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `real_x` | `pass` | True | True | 0 | 0.0 | 1.0 | 0 |
| `real_x_div_2` | `pass` | True | True | 0 | 0.0 | 1.0 | 0 |
| `real_x_div_4` | `pass` | False | False | 152059 | 0.8246555921828305 | 0.9787018150843415 | 76842 |
| `real_x_div_8` | `pass` | False | False | 152058 | 0.4637689703929305 | 0.990245932536855 | 85512 |
| `real_x_div_16` | `pass` | False | False | 152038 | 0.38345359806250856 | 0.9917419800810753 | 54462 |
| `real_x_div_32` | `pass` | False | False | 152053 | 0.3925311739573611 | 0.9906807827447952 | 51735 |
| `real_x_div_64` | `pass` | False | False | 152060 | 1.248871348203516 | 0.9099139122932334 | 32216 |
| `real_x_clip_16` | `pass` | True | True | 0 | 0.0 | 1.0 | 0 |
| `real_x_clip_8` | `pass` | True | True | 0 | 0.0 | 1.0 | 0 |
| `real_x_clip_4` | `pass` | False | False | 152064 | 0.8244867287435699 | 0.9793583365636399 | 85512 |
| `real_x_clip_2` | `pass` | False | False | 152056 | 0.46447696766555446 | 0.9904208744711783 | 85512 |
| `real_x_clip_1` | `pass` | False | False | 152044 | 0.38368675009826936 | 0.9918013900636511 | 54462 |
| `real_x_z_normalized` | `pass` | False | False | 152042 | 0.38327288099064066 | 0.9917408151709185 | 54462 |
| `synthetic_match_mean_std_normal` | `pass` | True | True | 0 | 0.0 | 1.0 | 0 |
| `synthetic_match_min_max_uniform` | `pass` | True | True | 0 | 0.0 | 1.0 | 0 |
| `synthetic_zeros` | `pass` | False | False | 152062 | 1.2518448336849501 | 0.9116778203334492 | 32216 |
| `synthetic_ones` | `pass` | False | False | 152061 | 0.42579590471044604 | 0.9888061781182369 | 51735 |
| `synthetic_ramp` | `pass` | False | False | 152052 | 0.42846334553574744 | 0.9883351230120643 | 51735 |
| `synthetic_last_token_impulse` | `pass` | False | False | 152060 | 0.43524578378288403 | 0.9877547051609764 | 66906 |
| `real_raw_int16_as_input` | `fail` | None | None | None | None | None | None |
