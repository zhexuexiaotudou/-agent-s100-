# AI-NAS Final Demo Evidence

Generated: 2026-07-04T11:54:15+08:00

```json
{
  "generated_at": "2026-07-04T11:54:15+08:00",
  "final_verdict": "ready_with_minor_wording_fixes",
  "claim_counts": {
    "total": 23,
    "supported": 18,
    "partially_supported": 3,
    "should_reword": 2,
    "unsupported": 0
  },
  "required_outputs": {
    "claim_matrix_json": "reports/PRODUCT_CLAIM_EVIDENCE_MATRIX.json",
    "service_health_json": "reports/FINAL_SERVICE_HEALTH_AND_IDENTITY.json",
    "web_mobile_json": "reports/WEB_MOBILE_ACCESS_EVIDENCE.json",
    "demo_cases_json": "reports/FINAL_READONLY_AI_NAS_DEMO_CASES.json",
    "database_json": "reports/DATABASE_INDEXING_EVIDENCE.json",
    "token_json": "reports/TOKEN_COST_AND_CLOUD_REDACTION_EVIDENCE.json",
    "audit_json": "reports/AUDIT_TRACE_ROLLBACK_EVIDENCE.json"
  },
  "unsupported_or_reword_claims": [
    {
      "claim_text": "真实 NAS 写操作是否已开放。",
      "status": "should_reword",
      "safe_wording": "真实 NAS 写操作仍锁定；当前只支持只读 AI-NAS 和 sandbox/dry-run 写入治理验证。",
      "unsafe_wording": "真实 NAS 写操作已安全开放。"
    },
    {
      "claim_text": "Dream7B 是否属于前台产品能力。",
      "status": "should_reword",
      "safe_wording": "Dream7B 是历史 runtime/研究证据，不作为当前 AI-NAS 前台产品能力；当前产品路径是 Qwen + OpenClaw。",
      "unsafe_wording": "Dream7B 是当前 OpenClaw AI-NAS 前台模型能力。"
    },
    {
      "claim_text": "手机浏览器适配可用。",
      "status": "partially_supported",
      "safe_wording": "支持手机浏览器访问基础入口；已有 PWA/mobile 结构 gate，当前包含移动视口截图。",
      "unsafe_wording": "手机端所有复杂工作流都已完整验收。"
    },
    {
      "claim_text": "文件整理建议可用。",
      "status": "partially_supported",
      "safe_wording": "系统可生成文件整理/写操作 dry-run 方案、审批和回滚计划；真实移动/删除仍未开放。",
      "unsafe_wording": "系统已自动整理真实 NAS 文件。"
    },
    {
      "claim_text": "token 成本降低有数据支持。",
      "status": "partially_supported",
      "safe_wording": "有本地脱敏与字符启发式 token 估算，支持‘减少不必要云端 token 消耗’。",
      "unsafe_wording": "已证明大幅降低真实账单成本。"
    }
  ],
  "live_boundary": [
    "User-level qwen25-local-openai-gateway.service may be inactive; current active route is system-level qwen25-local-openai-gateway.service.",
    "S100P default route currently uses 192.168.137.1; do not claim PC network independence without a fresh route/NAT recheck."
  ]
}
```
