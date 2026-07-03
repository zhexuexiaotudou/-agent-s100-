# Final Segment Isolated Audit

- verdict: `blocked_final_segment_constant_or_uniform`
- top1_changes_with_input: `True`

| input | raw_constant | entropy | top1 |
| --- | --- | ---: | ---: |
| `zeros` | False | 0.911678 | 32216 |
| `ones` | False | 0.988806 | 51735 |
| `ramp` | False | 0.988335 | 51735 |
| `last_token_impulse` | False | 0.987755 | 66906 |
| `real_bpu_seg26_output` | True | 1.000000 | 152063 |
