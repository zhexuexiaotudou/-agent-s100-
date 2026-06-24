# Dream7B BPU q8 Logits Quality Diagnosis

Date: 2026-06-22

## Problem Statement

BPU diffusion generation produces garbage text while GGUF/CPU produces
correct text for the same prompt. This diagnosis locates the root cause
of the BPU logits quality failure.

## Method

Same 16-token input run through both:
- GGUF/CPU: dump-logits binary exports raw float32 logits
- BPU: per-segment diagnostic saves raw int16 and dequantized float32 for
  each of 10 HBM segments (fine-adjacent plan)

## GGUF vs BPU Logits Comparison (position 15)

| Metric | GGUF/CPU | BPU |
|---|---|---|
| min | -6.14 | -4.05 |
| max | 16.99 | 1.24 |
| std | 1.60 | 0.46 |
| top-1 token | 151643 (EOS) | 4458 (garbage) |
| top-1 logit | 16.99 | 1.24 |
| top-1 probability | high | 0.0095% |
| entropy | low | 11.79/11.93 (98.8% uniform) |
| correlation | 0.36 | not proportional |

All 16 positions: BPU top-1 is always token 4458. Argmax match: 0/16.

## BPU Per-Segment Hidden State Statistics

| Segment | Scale | Raw min | Raw max | Deq std | Saturation |
|---|---|---|---|---|---|
| seg00_02 | 0.000132 | -25207 | 21521 | 0.26 | no |
| seg02_04 | 0.002935 | -417 | 1757 | 0.25 | no |
| seg04_07 | 0.009440 | -119 | 86 | 0.21 | no |
| seg07_10 | 0.000210 | -18982 | 9911 | 0.29 | no |
| seg10_14 | 0.000377 | -5227 | 4339 | 0.27 | no |
| seg14_17 | 0.000655 | -3197 | 932 | 0.18 | no |
| seg17_21 | 0.000721 | -12977 | 3379 | 0.34 | no |
| seg21_24 | 0.000308 | -32768 | 24636 | 0.88 | YES int16 floor |
| seg24_26 | 0.001025 | -32768 | 16182 | 1.81 | YES int16 floor |
| seg26_28 | 0.000306 | -13503 | 4065 | 0.47 | no but input damaged |

## Root Cause

1. Primary: int16 saturation in seg21_24 and seg24_26. Late-layer hidden
   states exceed int16 dynamic range, causing value clipping. This corrupts
   the hidden states fed into the final logits projection.

2. Secondary: q8 weight quantization of lm_head without calibration. The
   8-bit quantized lm_head projection compresses the logit dynamic range.

The compilation script wsl_compile_dream_full_forward.py uses w_bits=8
for all FakeQuantLinear layers including lm_head, with no calibration
data. Scales are computed from weight distributions only.

## Fix Path

Fix A: Recompile late segments (seg21_24, seg24_26, seg26_28) with
higher w_bits (e.g. 16) or calibration data.

Fix B: Recompile lm_head with w_bits=16, keeping other layers at 8.
Highest-impact single change.

Fix C: Add activation calibration using representative prompts.

## Verification

After fix, re-run diagnostic: argmax match >80%, top-1 probability >5%,
then run dream7b-bpu-diffusion-generate with 3 prompts. Output must be
readable Chinese.
