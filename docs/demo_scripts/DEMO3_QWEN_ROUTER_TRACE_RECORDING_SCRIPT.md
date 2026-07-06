# Demo 3 Recording Script: Qwen Router, Privacy, Token Budget, Trace

## Goal

Show that assistant requests first enter the local Qwen routing path, then pass privacy tokenization, token budgeting, route decision, selected tool execution, safety gate, evidence summary, and final answer trace.

## Gate Command

```bash
cd /mnt/nas/openclaw
python3 gates/stage9_demo3_real_trace_flow_gate.py \
  --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas \
  --base-url http://127.0.0.1:8765 \
  --timeout 240
```

## User Queries To Show

1. `列出最近上传的照片`
2. `总结我的家庭发票和合同里涉及金额的内容`
3. `不要引用本地文件，只根据公开信息比较高端 AI NAS 的发展趋势`

## Expected Output

Query A:

```json
{
  "qwen_touched": true,
  "task_type": "media_search",
  "task_complexity": "simple",
  "route": "local_only or private_local_only",
  "cloud_used": false,
  "tool_execution": "local_media_search"
}
```

Query B:

```json
{
  "privacy_level": "high",
  "route": "private_local_only",
  "cloud_allowed": false,
  "cloud_used": false,
  "raw_private_cloud_egress": false
}
```

Query C:

```json
{
  "privacy_level": "none",
  "task_complexity": "complex",
  "route": "cloud_allowed_redacted",
  "redaction_applied": true,
  "cloud_payload_contains_private_context": false
}
```

Every trace must include these ten steps:

```text
received
qwen_router
privacy_tokenizer
task_classifier
route_decision
token_budget
tool_execution
safety_gate
evidence_summary
final_answer
```

## Subtitle

Every assistant answer has an auditable execution trace. The trace records routing, privacy, token budget, tool execution, and evidence, not hidden chain-of-thought.

## Do Not Say

- Do not say hidden model reasoning is displayed.
- Do not say raw private context is sent to cloud.
- Do not say all tasks never use cloud.
- Do not say Qwen directly executes file operations.
