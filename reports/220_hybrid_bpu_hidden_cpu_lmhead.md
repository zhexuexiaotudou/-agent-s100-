# Hybrid BPU Hidden + CPU lm_head Diagnostic

- CPU/HF reference status: `unavailable`
- current outcome: `decision_rule_not_executed_cpu_hf_lmhead_unavailable`

## Decision Rule

- If hybrid logits recover: `seg27_28/lm_head/output contract likely fault`
- If hybrid logits fail: `earlier hidden path or input alignment likely fault`

## S100P Dumped Cases

| case | seg26 available | seg26 abs_max | seg26 nonzero | seg27 nonzero |
| --- | --- | ---: | ---: | ---: |
| `zeros` | True | 16.29678726196289 | 458751 | 0 |
| `ramp` | True | 16.29678726196289 | 458752 | 0 |
| `short_chinese_prompt_padded` | True | 16.29678726196289 | 458752 | 0 |

## Current Non-Hybrid Localization

The hybrid llada.cpp-style CPU lm_head test is blocked, but the existing final-segment sweep shows real BPU seg26 hidden produces all-zero logits at x and x/2, while x/4 and narrower clipped/normalized variants produce nonconstant logits. This localizes the current fault to the seg26 hidden range/scale or final-segment input contract, without proving BF16 ground-truth failure.
