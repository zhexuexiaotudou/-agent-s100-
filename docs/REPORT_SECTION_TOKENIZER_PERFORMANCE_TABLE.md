# Report Section: Tokenizer Performance Table

| Metric | Final value | Evidence | Safe interpretation |
| --- | --- | --- | --- |
| real_qwen_tokenizer_used | true | reports/17010_qwen_tokenizer_identity_gate.json | 使用真实 Qwen tokenizer 文件进行统计。 |
| fallback_used | false | reports/17010_qwen_tokenizer_identity_gate.json | 本轮没有退回近似 tokenizer。 |
| tokenizer backend | tokenizers_json | reports/17010_qwen_tokenizer_identity_gate.json | tokenizer 通过本地 JSON backend 加载。 |
| tokenizer identity hash | 8695d2b54075568a870d2364c50a53a59be11e28305a1cf4cc5bdbb67a7223af | reports/17010_qwen_tokenizer_identity_gate.json | 后续复测应保持 tokenizer 身份可追溯。 |
| benchmark_case_count | 130 | reports/17070_token_budget_benchmark_results.json | 130 个 synthetic NAS benchmark cases。 |
| average_reduction_ratio | 92.68% (0.926837) | reports/17070_token_budget_benchmark_results.json | benchmark 中平均云端输入 token 明显减少。 |
| median_reduction_ratio | 100% (1.0) | reports/17070_token_budget_benchmark_results.json | 中位 case 在路由后无需 cloud input 或完全避免 cloud input。 |
| p90_reduction_ratio | 100% (1.0) | reports/17070_token_budget_benchmark_results.json | 高分位 case 仍保持较强云端输入缩减。 |
| cloud_call_avoidance_rate | 61.54% (0.615385) | reports/17070_token_budget_benchmark_results.json | 部分任务通过 local-only 或 blocked-private 避免云调用。 |
| private_leak_count | 0 | reports/17020_privacy_redactor_product_gate.json | benchmark 和 gate 中未发现私有原文进入 cloud payload。 |
| quality_pass_rate | 100% (1.0) | reports/17070_token_budget_benchmark_results.json | benchmark 质量检查全部通过。 |
| product_route_integration | true | reports/17090_token_budget_product_integration_gate.json | Harness/Gateway/Portal 已接入 token budget route。 |

## Wording Boundary

上述表格只描述 benchmark 中的 cloud input token 对照和产品 route gate，不等同于真实账单成本、真实云 API 价格节省或长期生产统计。报告中可写“显著减少 benchmark 云端输入 token”，不可写“已证明真实账单显著下降”。
