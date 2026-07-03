# Task 610 Final Output Dequant Audit

- verdict: `pass_official_final_output_scale_applied`
- rows: `42`
- errors: `0`

| variant | scale | raw allzero | raw max | deq max | relL2 vs HF head | pearson | max ties |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `real_x` | 0.000254158775 | `True` | 0 | 0 | 0.9999999999999996 | 0.0 | 152064 |
| `real_x_div_2p75` | 0.000254158775 | `False` | 3.28e+04 | 8.33 | 0.3382119924657188 | 0.9494248782352424 | 10 |
| `real_x_div_3` | 0.000254158775 | `False` | 3.28e+04 | 8.33 | 0.4067405564634382 | 0.9388709711835209 | 3 |
| `real_x_clip_6` | 0.000254158775 | `False` | 3.28e+04 | 8.33 | 0.3236379268651147 | 0.9528195235490057 | 11 |
| `real_x_z_normalized` | 0.000254158775 | `False` | 1.16e+04 | 2.94 | 1.0299614862010023 | 0.06851965642833163 | 1 |
