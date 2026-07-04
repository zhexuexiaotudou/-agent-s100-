# Token Budget Benchmark Results

| Metric | Value |
| --- | --- |
| total_cases | 130 |
| real_qwen_tokenizer_used | True |
| average_naive_cloud_tokens | 1240.65 |
| average_optimized_cloud_tokens | 119.81 |
| average_reduction_ratio | 0.926837 |
| median_reduction_ratio | 1.0 |
| p90_reduction_ratio | 1.0 |
| cloud_call_avoidance_rate | 0.615385 |
| private_leak_count | 0 |
| quality_pass_rate | 1.0 |

## By Task Type

| task_type | cases | avg_naive_tokens | avg_optimized_tokens | avg_reduction_ratio | cloud_avoidance_rate | private_leak_count |
| --- | --- | --- | --- | --- | --- | --- |
| chinese_search | 10 | 719.3 | 0.0 | 1.0 | 1.0 | 0 |
| cloud_sensitive_mixed | 10 | 1212.0 | 316.1 | 0.739187 | 0.0 | 0 |
| document_qa | 30 | 1398.37 | 206.47 | 0.876154 | 0.333333 | 0 |
| file_organization_suggestion | 10 | 1276.5 | 0.0 | 1.0 | 1.0 | 0 |
| folder_summary | 10 | 1498.0 | 0.0 | 1.0 | 1.0 | 0 |
| mixed_zh_en_search | 10 | 756.0 | 0.0 | 1.0 | 1.0 | 0 |
| nas_search | 20 | 985.05 | 0.0 | 1.0 | 1.0 | 0 |
| public_research | 10 | 1854.2 | 312.1 | 0.831678 | 0.0 | 0 |
| report_generation | 20 | 1323.65 | 154.95 | 0.924773 | 0.5 | 0 |
