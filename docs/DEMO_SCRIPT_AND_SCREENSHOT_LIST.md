# Demo Script and Screenshot List

1. Show S100P service state: `systemctl is-active/is-enabled openclaw-gateway.service qwen25-local-openai-gateway.service`.
2. Show OpenClaw health: `curl http://127.0.0.1:8765/api/health`.
3. Show Qwen health and model identity: `curl http://127.0.0.1:18080/health` and `/v1/models`.
4. Show desktop portal screenshot: `evidence/final_demo/screenshots/openclaw_desktop_home.png`.
5. Show mobile viewport screenshot: `evidence/final_demo/screenshots/openclaw_mobile_home.png`.
6. Show claim matrix: `reports/PRODUCT_CLAIM_EVIDENCE_MATRIX.md`.
7. Show readonly demo cases: `reports/FINAL_READONLY_AI_NAS_DEMO_CASES.md`.
8. Show cloud redaction/token estimate: `reports/TOKEN_COST_AND_CLOUD_REDACTION_EVIDENCE.md`.
9. Show audit/rollback boundary: `reports/AUDIT_TRACE_ROLLBACK_EVIDENCE.md`.

Screenshot boundary: current screenshots verify portal access and responsive entry. Logged-in functional screenshots should be added once a non-secret test account is available.
