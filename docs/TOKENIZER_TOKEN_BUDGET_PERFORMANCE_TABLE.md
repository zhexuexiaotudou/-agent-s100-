# Tokenizer / Token Budget Performance Table

| Metric | Value |
| --- | --- |
| real_qwen_tokenizer_used | True |
| tokenizer_identity_hash | 8695d2b54075568a870d2364c50a53a59be11e28305a1cf4cc5bdbb67a7223af |
| benchmark_case_count | 130 |
| average_reduction_ratio | 92.68% (0.926837) |
| median_reduction_ratio | 100% (1.0) |
| p90_reduction_ratio | 100% (1.0) |
| cloud_call_avoidance_rate | 61.54% (0.615385) |
| private_leak_count | 0 |
| quality_pass_rate | 100% (1.0) |
| safe_wording | benchmark 中显著减少云端输入 token |

该表只描述 benchmark 中的云端输入 token 对照，不代表真实账单成本下降或长期生产统计。

## By Task Type

| task_type | cases | avg_naive | avg_optimized | avg_reduction | cloud_avoidance |
| --- | --- | --- | --- | --- | --- |
| chinese_search | 10 | 719.3 | 0.0 | 1.0 | 1.0 |
| cloud_sensitive_mixed | 10 | 1212.0 | 316.1 | 0.739187 | 0.0 |
| document_qa | 30 | 1398.37 | 206.47 | 0.876154 | 0.333333 |
| file_organization_suggestion | 10 | 1276.5 | 0.0 | 1.0 | 1.0 |
| folder_summary | 10 | 1498.0 | 0.0 | 1.0 | 1.0 |
| mixed_zh_en_search | 10 | 756.0 | 0.0 | 1.0 | 1.0 |
| nas_search | 20 | 985.05 | 0.0 | 1.0 | 1.0 |
| public_research | 10 | 1854.2 | 312.1 | 0.831678 | 0.0 |
| report_generation | 20 | 1323.65 | 154.95 | 0.924773 | 0.5 |
