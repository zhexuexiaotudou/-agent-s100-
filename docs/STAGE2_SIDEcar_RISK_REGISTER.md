# Stage 2 Sidecar Risk Register

| Risk | Evidence | Impact | Mitigation |
|---|---|---|---|
| Local Qwen unavailable in this Windows run | `reports/2060_qwen_runtime_identity_gate.json` | Blocks Stage 3 claim | Re-run on S100P and require live health/model identity |
| Sidecar is mock/sidecar-like, not real Zleap | `reports/2070_stage2_sidecar_mock_isolation.json` | Product integration unknown | Trial real Zleap only on isolated port |
| Read-only bridge is dry-run | `reports/2080_stage2_readonly_nas_search_bridge.json`, `reports/2090_stage2_document_rag_bridge.json` | Real dispatcher behavior still unproven for sidecar | Run controlled read-only dispatcher execution next |
| Write approval is schema-only | `reports/2050_approval_token_schema_gate.json` | No safe write workspace yet | Keep all write/destructive tools disabled |
| Cloud egress is gate-tested, not product-enabled | `reports/2030_cloud_redaction_hardening_gate.json` | Private leakage risk if expanded carelessly | Keep cloud public/redacted only and add live egress audit before expansion |
| Git metadata is unusable in this checkout | final packet environment.git_status | Commit-based diff evidence unavailable | Use artifact hashes and generated reports as the evidence source |
