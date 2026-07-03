# 03 S100P BPU DUMP LOGITS

请修改或扩展现有 S100P runtime/logits scripts，使 BPU HBM chain 的每个 case 都能输出可比 artifact。

## 任务

基于：

```text
04_scripts/dream7b_seq128_logits_reference_compare.py
04_scripts/dream7b_seq128_s100p_runtime_gate.py
```

新建：

```text
tools/run_s100p_hbm_chain_dump_logits.py
```

对每个 input case：

1. 运行完整 28-segment chain。
2. 保存 final raw output tensor。
3. 保存 output quant scale、zero point 或 runtime metadata 中所有影响 dequant 的字段。
4. 保存 dequantized final logits `.npy`。
5. 保存 final tensor shape。
6. 保存 top-k、min/max/mean/std、nonzero_count、NaN/Inf count。

## 输出结构

```text
evidence/s100p_logits/{run_id}/{case_id}/
  raw_output.npy
  dequant_logits.npy
  tensor_metadata.json
  runtime_log.txt
```

## 报告输出

```text
reports/020_s100p_dump_logits_run.json
reports/020_s100p_dump_logits_run.md
```

## 硬性要求

- 不要只保存 top-k；必须保存完整 `[1,152064]` logits。
- 如果 runtime 只能返回 int tensor，必须保存 raw int tensor 和 dequant scale。
- 如果 dequant scale 缺失，报告必须 fail，不得猜测。
- 如果 final logits 全零、常数、NaN、Inf 或 entropy 接近 1，必须明确标注为 blocking anomaly。
