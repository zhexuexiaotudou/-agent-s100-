# Design Report Safe Claim Version

- Digua AI-NAS can be described as a privacy-first S100P + OpenClaw + Qwen + NAS prototype with live local gateway evidence, policy-first harness controls, token-budget benchmarks, and metadata-first Agent Runtime capabilities.
- Do not describe optional embedding, Dream7B research, or controlled copy as default full production capabilities.

| safe claim | evidence |
| --- | --- |
| S100P runs the resident OpenClaw/Qwen gateway path on local services. | README.md, reports/final_audit/030_service_health_and_ports.json |
| OpenClaw exposes a LAN/loopback web entry and `/ui` route. | reports/final_audit/030_service_health_and_ports.json |
| Mobile responsive core pages have prior screenshot evidence; this audit did not rerun fresh mobile Playwright. | evidence/ui_v2/screenshots/mobile/01_files_mobile.png, evidence/ui_v2/screenshots/mobile/02_reports_mobile.png |
| Qwen2.5 local gateway is live on S100P port 18080. | reports/final_audit/030_service_health_and_ports.json |
| Real Qwen tokenizer benchmark supports token-budget routing and accounting. | reports/17120_token_budget_product_final_summary.json |
| Private cases are blocked or redacted in benchmark gates with private leak count zero. | reports/17120_token_budget_product_final_summary.json |
| Context compression is implemented and tested in token budget flow. | tools/token_budget/context_compressor.py, tests/test_context_compressor.py |
| Local-first router evidence supports cloud as controlled overflow. | scripts/probes/ai_nas_edge_cloud_router_probe.py, README.md |
| Benchmark cloud input token average reduction is 92.68%. | reports/17120_token_budget_product_final_summary.json |
| Harness is integrated into default OpenClaw service with live status on 8765. | 01_final_evidence/digua_ai_nas_harness_default_service_gate_packet.json |
| Copy, routing, privacy, and dispatcher gates are policy-first. | src/harness/, tests/test_copy_route_guard.py |
| Live harness status reports Qwen execution authority false. | reports/final_audit/030_service_health_and_ports.json |
| Dispatcher exists and is required for copy execute. | reports/final_audit/030_service_health_and_ports.json |
| Route and inventory tests cover permission boundaries. | tests/test_copy_route_guard.py, tests/test_personal_inventory_readonly.py |
| Trace schema and samples exist for audit trail. | reports/24050_trace_schema_gate.json, reports/agent_runtime_trace_samples.jsonl |
| Gate reports and final packets exist. | reports/, 01_final_evidence/ |
| SQLite metadata/index flow exists; current UI packet noted inventory degraded. | tests/test_personal_inventory_readonly.py, evidence/ui_v2/api/ui_v2_api_smoke.json |
| Document retrieval is FTS-first and tested. | tests/test_document_fts_rag.py, reports/24040_fts_first_rag_eval_gate.json |
| Embedding is optional/feature-flagged, not default production semantic search. | reports/final_audit/030_service_health_and_ports.json |
| FTS-first document Q&A/eval is supported. | tests/test_document_fts_rag.py, reports/24090_agent_runtime_eval_gate.json |
| Evidence report generation is present. | reports/AI_NAS_FINAL_DEMO_EVIDENCE.json |
| Folder summary benchmark route exists. | benchmarks/token_budget_eval_cases.jsonl, reports/17120_token_budget_product_final_summary.json |
| File organization suggestion route is benchmark-supported. | reports/17120_token_budget_product_final_summary.json |
| Journal production and live rollout packets support period summaries. | 01_final_evidence/digua_ai_nas_digua_journal_production_gate_packet.json, 01_final_evidence/digua_journal_live_rollout_gate_packet.json |
| Only user-confirmed single-file copy with signed token/hash/target-absent/dispatcher is enabled. | 01_final_evidence/digua_ai_nas_harness_default_service_gate_packet.json, tests/test_copy_route_guard.py |
| Live harness status lists preview/dry-run/confirm/execute/rollback routes. | reports/final_audit/030_service_health_and_ports.json |
| Live status reports delete, move, rename, chmod, chown, overwrite, recursive actions forbidden. | reports/final_audit/030_service_health_and_ports.json |
| Prior desktop screenshot evidence exists and `/ui` responds on 8765/18766. | evidence/ui_v2/screenshots/desktop/, reports/final_audit/030_service_health_and_ports.json |
| Two mobile screenshot flows exist; not six fresh mobile flows this audit. | evidence/ui_v2/screenshots/mobile/ |
| Live harness status embeds Agent Runtime ok and routes. | 01_final_evidence/digua_ai_nas_agent_runtime_deepening_packet.json, reports/final_audit/030_service_health_and_ports.json |
| Metadata index for documents/images/video/audio/code/archive is live. | reports/24030_multimodal_index_gate.json, reports/final_audit/030_service_health_and_ports.json |
| RAG eval gate and dataset exist. | reports/24090_agent_runtime_eval_gate.json, benchmarks/rag_eval_cases.jsonl |
| Local OpenTelemetry-like trace schema exists. | reports/24050_trace_schema_gate.json |
| Dream7B has research truth-set evidence but remains blocked at BPU operator alignment. | 01_final_evidence/dream7b_s100p_lladacpp_style_continue_gate_packet.json |
| Local Qwen/router path is default; cloud private raw egress is false. | README.md, reports/final_audit/030_service_health_and_ports.json |
