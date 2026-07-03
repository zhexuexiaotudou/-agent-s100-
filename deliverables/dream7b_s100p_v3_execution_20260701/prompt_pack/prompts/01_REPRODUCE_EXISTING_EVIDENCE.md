# 01 REPRODUCE EXISTING EVIDENCE

请先只做 evidence reproduction，不做修复。

## 任务

读取并总结：

```text
GPT_PRO_REVIEW_PROMPT.md
README_FOR_GPT_PRO.md
01_final_evidence/dream7b_s100p_diffusion_research_packet.json
02_primary_reports/seq128_runtime_gate/seq128_s100p_runtime_gate.json
02_primary_reports/seq128_logits_compare/seq128_logits_reference_compare.json
05_artifact_metadata/seq128_b1_lmheadq16_lasttoken_summary.json
MANIFEST.csv
SHA256SUMS.txt
```

然后执行：

1. 用脚本重新校验 review package 中所有 listed files 的 SHA256 和 size。
2. 检查 final packet 是否与 runtime/logits reports 一致。
3. 检查 scripts 中的 metrics 计算逻辑是否与 reports 一致。
4. 不要重新解释为“部署成功”；只按 gate 输出结论。

## 输出

```text
reports/000_reproduce_existing_evidence.json
reports/000_reproduce_existing_evidence.md
scripts/check_review_pack_integrity.py
```

## 报告必须包含

```text
compile_feasible: pass/fail/inconclusive
s100p_runtime_valid: pass/fail/inconclusive
logits_numerically_valid_against_gguf_q4km: pass/fail/inconclusive
generation_quality_valid: pending/blocked/not_run
product_route_valid: pending/blocked/not_run
```

还必须列出任何无法复核的 artifact，例如 excluded 8GB HBM tar。
