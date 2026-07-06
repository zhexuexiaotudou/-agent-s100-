# Assistant Trace Delivery - 2026-07-06

## Scope

Assistant Trace records product-level execution steps for assistant entrypoints
without storing hidden chain-of-thought. It is a user-visible audit surface for
the local router, privacy tokenizer, token budget, safety gate, tool execution
boundary, evidence summary, and final answer state.

## APIs

- `GET /api/assistant/trace/status`
- `GET /api/assistant/trace/{trace_id}`
- `GET /api/assistant/trace/stream/{trace_id}`
- `GET /api/assistant/traces`
- `POST /api/assistant/chat`
- `POST /api/assistant/trace/record-entrypoint`
- `POST /api/router/explain`
- `POST /api/token-budget/explain`
- `POST /api/privacy-tokenizer/debug`

## Standard Steps

1. `received`
2. `qwen_router`
3. `privacy_tokenizer`
4. `task_classifier`
5. `route_decision`
6. `token_budget`
7. `tool_execution`
8. `safety_gate`
9. `evidence_summary`
10. `final_answer`

## Final S100P Evidence

- Trace coverage gate: `/mnt/nas/openclaw/reports/qwen25_ai_nas/stage8_assistant_trace_global_coverage_gate.json`
- Demo 3 router trace gate: `/mnt/nas/openclaw/reports/qwen25_ai_nas/stage8_demo3_qwen_router_trace_gate.json`
- Stage 9 aggregate: `/mnt/nas/openclaw/reports/qwen25_ai_nas/stage9_demo_product_delivery_gate.json`
- Product smoke: `/mnt/nas/openclaw/reports/qwen25_ai_nas/product_smoke_test_20260706-154654/product_smoke_test.json`

The final Demo 3 gate verified Qwen router touch, local private routing,
token-budget private cloud avoidance, privacy-tokenizer span detection,
assistant trace IDs, removal of raw Qwen content preview, relative private path
redaction, and no absolute raw path in returned payloads.

## Boundary

Trace records store hashes and redacted previews. Hidden chain-of-thought is not
saved or displayed. Trace does not grant Qwen tool execution authority and does
not permit private raw cloud egress.
