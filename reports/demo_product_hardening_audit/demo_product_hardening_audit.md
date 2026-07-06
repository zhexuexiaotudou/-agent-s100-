# Demo Product Hardening Audit

- generated_at: `2026-07-06T16:20:00+08:00`
- scope: current repo review before hardening
- method: code/API/gate inspection; no business code changed before this audit

| Demo | 当前 repo 状态 | 是否可直接录屏 | 主要证据 | 仍需强化 |
|---|---|---:|---|---|
| Demo 1: NAS-S100P-PC 链路确认 | READY_REAL | Yes | `README.md`, `gates/stage8_demo1_link_readiness_gate.py`, `scripts/product_smoke_test.py` | Gate 输出需要显式给出 `openclaw_active`, `qwen_active`, `nas_mount_readable`, `personal_root_readable`, `dashboard_reachable`, `raw_path_returned` |
| Demo 2: OpenClaw AI-NAS 五个核心功能 | READY_BUT_SHALLOW | No | portal server 已暴露 upload / AI Space / multimodal / YOLO / person attribute / smart classification / smart naming / document query / auto organizer | Auto Organizer 仍主要靠文件名启发；Demo2 gate 只查 status/count；OCR/RAG 需要产品级 endpoint 和 no-grounded contract |
| Demo 3: Qwen 端云路由 + trace | READY_BUT_SHALLOW | No | `/api/router/explain`, `/api/token-budget/explain`, `/api/privacy-tokenizer/debug`, `/api/assistant/chat`, assistant trace APIs | `/api/assistant/chat` 仍使用标准 trace 模板；Demo3 gate 只跑一条私有 query；需要三条真实 query 的 router/privacy/token/tool trace |

## Module Status

- `resident_link`: READY_REAL. 现有 gate 已覆盖 health/product/harness/Qwen/personal root/loopback，但录屏字段还不够直接。
- `ai_space`: READY_REAL. `src/ai_space/service.py` 已聚合 multimodal、YOLO、person attribute、smart classification、smart naming。
- `media_upload_auto_classify`: READY_REAL. `PortalState.media_upload_photo()` 已串起 upload -> multimodal -> YOLO -> person attribute -> smart classification -> smart naming -> AI Space。
- `multimodal_person_yolo_search`: READY_REAL. 路由已经存在，但需要真实 query gate 覆盖普通搜索和“这个人是谁”阻断。
- `ocr_document_rag`: READY_BUT_SHALLOW. 目前 `/api/documents/query` 可做 SQLite FTS-first RAG，但缺少 `/api/document-rag/query`, `/api/ocr/query`, `/api/ocr/status` 产品别名和无证据不强答契约。
- `auto_organizer`: READY_BUT_SHALLOW. 已有受控移动、重命名、审批、sha256、rollback，但 `naming_policy.py` 仍优先使用文件名。
- `assistant_trace`: READY_BUT_SHALLOW. Trace schema 有了，但 `record_standard_trace()` 会生成模板 payload。
- `stage9_aggregate_gate`: READY_BUT_SHALLOW. 当前 Stage9 聚合 Stage8 和 smoke，缺真实用户流 gate。

## Hardening Required

1. Auto Organizer 优先使用 AI Space、Smart Naming、Smart Classification、YOLO、person attribute，再 fallback 文件名。
2. fallback 必须标注 `classification_basis.source=fallback_filename_heuristic`。
3. `/api/assistant/chat` 返回真实任务分类、route、tool execution、answer 和 `trace_id`。
4. Trace payload 来自真实 router/privacy/token/tool 调用上下文，不保存隐藏 CoT，不保存 raw path/private content。
5. 补齐 OCR/RAG product endpoints，允许无证据时返回 `no_grounded_answer=true`。
6. 新增 Stage9 hardening gates：Demo2 real user flow、Demo3 real trace flow、Auto Organizer AI-driven、final recording readiness。
7. 新增三段录屏脚本和最终 readiness 文档。
