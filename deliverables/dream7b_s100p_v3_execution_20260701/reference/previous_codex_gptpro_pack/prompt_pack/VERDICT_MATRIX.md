# Verdict Matrix

## Case 1

BPU matches BF16, but mismatches GGUF Q4_K_M.

判定：

```text
HBM/S100P mathematical path likely valid.
Deployment reference mismatch unresolved.
Product promotion still blocked until GGUF mismatch is explained.
```

## Case 2

BPU mismatches BF16 and GGUF, while input alignment and dequant are verified.

判定：

```text
tested S100P HBM deployment falsified against BF16 reference.
Locate first divergent segment.
```

## Case 3

Boundary activations match until seg26, but final logits fail.

判定：

```text
Prioritize seg27_28 / lm_head q16 / last-token slicing / output dequant / vocab layout.
```

## Case 4

Segment 0 already mismatches.

判定：

```text
Prioritize token ids / position ids / attention mask / input layout.
Do not claim model failure before input alignment is fixed.
```

## Case 5

Raw BPU output is all-zero or constant.

判定：

```text
Likely graph/runtime/final segment output anomaly.
```

## Case 6

Raw BPU output has information, but dequant output becomes all-zero or entropy=1.

判定：

```text
Likely dequant/postprocess bug.
```

## Case 7

BF16/PyTorch reference cannot be established.

判定：

```text
Deployment blocked against GGUF Q4_K_M reference.
BF16 ground-truth failure unresolved.
```
