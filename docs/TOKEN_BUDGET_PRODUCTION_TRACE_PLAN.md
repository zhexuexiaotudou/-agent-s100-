# Token Budget Production Trace Plan

## Goal

用 7-day local-only token trace 验证真实任务分布下的 token budget 趋势，同时保持隐私边界。该计划只收集统计字段，不记录 private raw content，不打开真实 NAS 写操作，不修改 8765 / 18080 / 18888 / 18889，也不把 Qwen 升级为工具执行主体。

## Trace Window

| Item | Plan |
| --- | --- |
| Duration | 7 days |
| Mode | local-only observation first, no new cloud provider required |
| Scope | OpenClaw / Gateway / Harness token budget decisions |
| Write actions | disabled unless a separate real NAS write gate is approved |
| Private raw content logging | prohibited |

## Fields To Record

| Field | Purpose |
| --- | --- |
| run_id | Correlate one request across budget, route and quality samples. |
| timestamp | Build hourly and daily task distribution. |
| user_role_hash | Compare role-level behavior without storing identity. |
| task_type | Group by NAS search, document QA, report generation, folder summary, file organization, public research and other routes. |
| naive_cloud_tokens | Estimate input tokens if the raw task had gone to cloud. |
| optimized_cloud_tokens | Estimate input tokens after local routing, redaction and compression. |
| route_decision | local-only, cloud_allowed_redacted or cloud_blocked_private. |
| redaction_applied | Confirm whether privacy redaction was needed. |
| compression_applied | Confirm whether context compression was used. |
| cloud_payload_hash | Hash only, for duplicate analysis without raw payload. |
| private_raw_logged | Must remain false. |
| quality_sample_bucket | Select a small review sample without exposing raw content. |

## Privacy Controls

1. Do not log NAS file contents, private file names, full paths, contact details, secrets, certificates, payment information or private chat text.
2. Keep redaction maps local and out of cloud payloads.
3. Store only hashes or category labels for payload correlation.
4. Fail closed when redaction confidence is low or ACL visibility is unclear.
5. Review trace schema before enabling any real cloud endpoint.

## Daily Checks

| Day | Check |
| --- | --- |
| Day 1 | Validate schema, field completeness and private_raw_logged = false. |
| Day 2 | Compare route distribution against benchmark routes. |
| Day 3 | Inspect per-task token budget stats and outlier tasks. |
| Day 4 | Review cloud route decisions for false positives and false negatives. |
| Day 5 | Run quality sample review for local-only and redacted-cloud candidates. |
| Day 6 | Check privacy samples and prompt-injection blocked-private cases. |
| Day 7 | Summarize cost trend readiness and provider-pricing prerequisites. |

## Cost Model Follow-up

After a cloud provider and pricing model are selected, compute an optional price model with input token price, output token price, cache policy, retry rate and observed route distribution. Until that step is complete, the report should keep the wording at “benchmark cloud input token reduction” and “production trace cost trend pending.”
