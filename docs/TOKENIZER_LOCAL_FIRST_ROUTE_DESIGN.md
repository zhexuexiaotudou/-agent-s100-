# Tokenizer Local-First Route Design

本设计把用户请求和 NAS 上下文依次经过本地 Qwen tokenizer、隐私脱敏、上下文压缩、路由判断和 trace 审计。

## Route

- `local_only`: 简单 NAS 搜索、文件夹摘要、文件整理 dry-run 等在本地完成，不生成 cloud payload。
- `cloud_allowed_redacted`: 公开或 mixed 场景只允许 redacted + compressed payload 上云，redaction_map 不进入 cloud payload。
- `cloud_blocked_private`: ACL denied、prompt injection、要求泄露原文等场景 fail closed。

## Token Budget

- `nas_search`: 512
- `document_qa`: 1200
- `folder_summary`: 1500
- `report_generation`: 2000
- `file_organization_suggestion`: 1200
- `public_research`: 3000

Tokenizer identity hash: `bf8d73106cf5f27f4f792da91dd6ce29e410e2335961d9b97f54bc853864ce2d`。
