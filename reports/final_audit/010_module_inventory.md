# 010 Module Inventory

| module | status | evidence | limitations |
| --- | --- | --- | --- |
| OpenClaw Gateway / operator portal | live_deployed | scripts/probes/ai_nas_operator_portal_server.py, src/openclaw/harness_default_middleware.py | Gateway remains LAN/S100P-loopback scoped; no public exposure claim. |
| Qwen local gateway | live_deployed | scripts/qwen25_openai_gateway.py | Qwen is an advisor/router; it has no autonomous tool execution authority. |
| Workspace Harness | live_deployed | 01_final_evidence/digua_ai_nas_harness_default_service_gate_packet.json | Only limited, confirmed single-file copy is enabled. |
| Policy Router | tested | tools/token_budget/cloud_route_decider.py, reports/17120_token_budget_product_final_summary.json | Benchmark evidence is not real billing evidence. |
| allowlist dispatcher | live_deployed | src/harness/copy_route_guard.py, 01_final_evidence/digua_ai_nas_harness_default_service_gate_packet.json | Mutating execution must stay behind dispatcher, hash, target-absent, and signed-token checks. |
| NAS Search | tested | tests/test_personal_inventory_sqlite_readonly.py, evidence/ui_v2/api/ui_v2_api_smoke.json | Some UI evidence marks SQLite inventory status degraded while read-only operation DB remains ok. |
| SQLite index | tested | tests/test_personal_inventory_sqlite_readonly.py, migrations/create_agent_runtime_tables.sql | Runtime SQLite DB files are intentionally excluded from the audit package. |
| Document FTS / RAG | tested | tests/test_document_fts_rag.py, reports/24040_fts_first_rag_eval_gate.json | FTS-first local RAG; embedding is optional and not default. |
| Report generation | tested | reports/AI_NAS_FINAL_DEMO_EVIDENCE.json, reports/24110_agent_runtime_final_evidence_package.md | Reports are evidence packages, not external certification. |
| Token Budget & Privacy Router | tested | reports/17120_token_budget_product_final_summary.json, SELF_CHECK.py | Can claim benchmark cloud-input token reduction, not real bill savings. |
| Copy Route default service | live_deployed | src/openclaw/routes/nas_copy_routes.py, tests/test_copy_route_guard.py | Delete, move, rename, chmod, overwrite, recursive operations are forbidden. |
| Digua Journal | live_deployed | 01_final_evidence/digua_ai_nas_digua_journal_production_gate_packet.json, 01_final_evidence/digua_journal_live_rollout_gate_packet.json | Repo integration is dirty/uncommitted; live rollout and repo merge status must be distinguished. |
| UI v2 | live_deployed | 01_final_evidence/digua_ai_nas_ui_v2_design_report_effect_gate_packet.json, evidence/ui_v2/playwright/ui_v2_playwright_validation.json | Fresh Playwright was not rerun in this audit because local Node/npm are missing. |
| Agent Runtime Context Pack | live_deployed | 01_final_evidence/digua_ai_nas_agent_runtime_deepening_packet.json, src/agent_runtime/service.py | HTTP POST auth remains enforced; unauthenticated context-pack smoke is blocked. |
| Memory Manager | live_deployed | src/agent_runtime/memory.py, reports/24020_agent_memory_manager_gate.json | Raw private content rows are expected to remain zero. |
| Multimodal NAS Index | live_deployed | src/agent_runtime/multimodal_index.py, reports/24030_multimodal_index_gate.json | Metadata-only index by default; thumbnail, OCR, embedding, video keyframe, and audio transcript are not default-enabled. |
| RAG Eval | tested | reports/24090_agent_runtime_eval_gate.json, benchmarks/rag_eval_cases.jsonl | Eval dataset is controlled benchmark evidence. |
| OpenTelemetry-like Trace | tested | reports/24050_trace_schema_gate.json, reports/agent_runtime_trace_samples.jsonl | Trace schema is local audit-like evidence, not a full OpenTelemetry backend. |
| Internal Tool Manifest | live_deployed | configs/internal_tool_manifest.json, reports/24060_internal_tool_manifest_gate.json | No public MCP exposure is allowed. |
| Continuous Eval Dataset | tested | reports/24070_continuous_eval_dataset_gate.json, benchmarks/agent_runtime_eval_cases.jsonl | Dataset is a gate suite, not longitudinal production telemetry. |
| Audit / Gate / Evidence Packet | tested | 01_final_evidence/, evidence_for_gptpro/ | Final audit package is a review artifact; repo remains dirty. |
| Dream7B research branch | deprecated_or_research_only | 01_final_evidence/dream7b_s100p_lladacpp_style_continue_gate_packet.json, dream_s100p_lladacpp/ | Not a product route; stops at BPU operator alignment review boundary. |
