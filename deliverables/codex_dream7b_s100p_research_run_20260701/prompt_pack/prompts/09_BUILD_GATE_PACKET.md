# 09 BUILD GATE PACKET

请实现一个统一 gate packet generator，把所有实验结果聚合为最终部署判定。

新建：

```text
tools/build_dream7b_s100p_gate_packet.py
```

## 输入

```text
reports/000_reproduce_existing_evidence.json
reports/010_triplet_reference_design.md
reports/020_s100p_dump_logits_run.json
reports/030_segment_boundary_compare.json
reports/040_final_segment_lmheadq16_audit.json
reports/050_seq128_input_alignment_audit.json
reports/060_dequant_audit.json
reports/070_logits_probe_battery_triplet.json
```

## 输出

```text
01_final_evidence/dream7b_s100p_gate_packet_v2.json
01_final_evidence/dream7b_s100p_gate_packet_v2.md
```

## Gate definitions

### Gate 0 compile_feasible

Pass only if:

```text
artifact manifest complete
expected HBM/HBO count present
hashes verified or excluded artifacts explicitly documented
```

### Gate 1 s100p_runtime_valid

Pass only if:

```text
representative segments and full chain run on S100P
expected final shape
no resource exhaustion
```

### Gate 2 logits_numerically_valid

Pass only if:

```text
BPU logits match BF16 reference above thresholds
and do not fail deployment reference without explanation
```

Fail if:

```text
BPU mismatches BF16 reference after input alignment and dequant are verified
```

Inconclusive if:

```text
BF16 reference unavailable
or input alignment unresolved
```

Blocked if:

```text
artifacts missing
```

### Gate 3 generation_quality_valid

Pending unless Gate 2 passes.

### Gate 4 product_route_valid

Pending unless Gate 3 passes.

Product route must remain isolated on 18889 until all gates pass.

## Thresholds

```text
top1 agreement >= 0.80 over semantic cases
ref top1 in candidate top5 >= 0.95
mean cosine >= 0.95
normalized entropy not near 1 for nontrivial semantic cases
no all-zero or constant logits unless expected by test design
```

## Final packet 必须包含

```text
verdict
evidence table
blocking issue
first divergent segment if known
next minimal experiment if inconclusive
claim boundary text suitable for a paper
```
