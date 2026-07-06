# Assistant Trace Real Execution Hardening

## Change

`AssistantTraceRecorder` now supports `record_execution_trace()` in addition to the older coverage-oriented `record_standard_trace()`.

The product `/api/assistant/chat` path writes the standard ten steps from real call context:

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

The step payloads come from the current request's router decision, privacy tokenizer, token budget estimate, and selected tool execution.

## Acceptance

Run:

```bash
python3 gates/stage9_demo3_real_trace_flow_gate.py --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas --base-url http://127.0.0.1:8765 --timeout 240
```

Expected verdict:

```text
ok_stage9_demo3_real_trace_flow_gate
```

Final S100P recording readiness also passed this gate inside:

```text
reports/stage9_final_recording_readiness_gate.json
ok_stage9_final_recording_readiness_gate
```

## Boundaries

- Trace does not store hidden chain-of-thought.
- Trace does not store raw private paths.
- Trace does not store raw private cloud payloads.
- Public complex requests may use a local cloud stub if no real cloud endpoint is configured; the response must say `cloud_stub=true` and `real_cloud_call=false`.
