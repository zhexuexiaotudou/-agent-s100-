# Token Cost Reduction Analysis

| Metric | Value |
| --- | --- |
| final_verdict | tokenizer_token_budget_claim_supported |
| safe_wording_level | benchmark 中显著减少云端输入 token |
| average_reduction_ratio | 0.926837 |
| median_reduction_ratio | 1.0 |
| p90_reduction_ratio | 1.0 |
| cloud_call_avoidance_rate | 0.615385 |
| private_leak_count | 0 |
| quality_pass_rate | 1.0 |
| not_bill_savings | True |

结论边界：以上比例来自 synthetic NAS benchmark 的云端输入 token 对照，不等同于真实账单成本下降。真实账单结论需要价格模型和真实调用日志另行验证。
