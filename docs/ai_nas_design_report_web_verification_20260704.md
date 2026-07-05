# AI-NAS 设计报告网页端实机验证记录（2026-07-04）

## 范围

- 报告来源：`C:\Users\zhexu\Desktop\地瓜AI-NAS设计报告.docx`
- 实机入口：`http://127.0.0.1:8767/ui`
- S100P 服务：`127.0.0.1:18766`，通过本机 SSH tunnel 暴露到 `127.0.0.1:8767`
- NAS 根目录：`/mnt/nas/openclaw/Personal`
- 临时验证 report root：`/mnt/nas/openclaw/tmp/ui_v2_real_report`
- 验证账号：临时 v2 服务 `admin/admin123`

## 受控样本

- `Collections/CodexWebVerify_20260704/level1/level2/level3/deep_file.txt`
- `Collections/CodexWebVerify_20260704/docs/ai_nas_design_verify.md`
- `Collections/CodexWebVerify_20260704/docs/copy_source.txt`
- `Documents/CodexWebVerify_20260704/ai_nas_design_report_sample.md`
- `Collections/CodexPreflight/source/web_ui_copy_source_20260704.txt`
- `Collections/CodexPreflight/target/` 用于 allowlist copy route 验证

## 功能矩阵

| 报告功能 | 网页入口 | 实机动作 | 结果 |
|---|---|---|---|
| 网页端/移动端访问 | 首页、底部移动导航 | Chrome 桌面 1440x1080 和移动 390x844 截图 | 通过 |
| 真实 NAS 文件路径浏览 | 文件 | 从 `Collections` 下钻到 `level1/level2/level3`，再上级切换 | 通过 |
| 文件下载/复制路径 | 文件详情 | 选择真实文件，显示相对路径、下载和复制路径入口 | 通过 |
| 受控单文件 copy route | 文件详情 | preview、dry-run、confirm、execute、rollback | 通过 |
| 高风险操作禁用 | 文件/设置 | 删除、移动、重命名、改权限、覆盖、递归操作显示禁用边界 | 通过 |
| AI 助手自然语言入口 | AI 助手 | 调用 `/api/copilot/chat` 和 `/api/token-budget/route` | 通过 |
| token 预算/隐私路由 | AI 助手、设置 | 私有路径上下文触发 `cloud_blocked_private`，泄露数为 0 | 通过 |
| 文档 RAG/证据 | 文档 | `/api/documents/list` + `/api/documents/query` 召回样本文档证据 | 通过 |
| 地瓜日记手动记录 | 笔记 | `/api/journal/manual-entry` 写入本地记录 | 通过 |
| 日/周/月/年周期总结 | 笔记 | `/api/journal/generate-summary` 生成 daily summary | 通过 |
| Markdown 导出 | 笔记 | `/api/journal/export` 生成本地 Markdown | 通过 |
| 审计 trace | 审计 | `/api/audit/summary` 返回 JSON，不再断连接 | 通过，见差异 |
| 相册/媒体 | 相册 | `/api/media/summary`、`/api/media/create-album` | 通过 |
| 备份同步 | 备份同步 | `/api/backup/create-task`、`/api/backup/run` | 通过 |
| 设置/身份/ACL/策略 | 设置 | storage、identity users、harness、token summary | 通过 |

## 浏览器截图

截图目录：`C:\Users\zhexu\AppData\Local\Temp\digua-ai-nas-web-verify-20260704-rerun`

- `01_files_deep_explorer.png`
- `02_copy_route_execute.png`
- `03_copy_route_rollback.png`
- `04_documents_query.png`
- `05_assistant_token_route.png`
- `06_journal_flow.png`
- `07_audit_page.png`
- `08_media_page.png`
- `09_backup_page.png`
- `10_settings_page.png`
- `11_mobile_files.png`

## 验证命令结果

- JS lint/syntax：`node --check web/static/digua_ai_nas_v2.js` 通过
- Python compile/type sanity：`python -m py_compile scripts/probes/ai_nas_operator_portal_server.py` 通过
- Tests：`py -3 -m pytest tests`，66 passed
- Product self-check：`py -3 SELF_CHECK.py`，`ok: true`
- Browser click verification：10 个桌面入口 + 1 个移动响应式检查全部通过，console errors 为空

## 与设计报告或预期不一致

- 本次验证使用 S100P 上的临时 v2 服务 `127.0.0.1:18766`，未重启默认生产端口 `8765`，避免影响现有服务。
- `/api/storage/status` 和 `/api/audit/summary` 指向的既有 `personal_inventory.sqlite3` 在临时服务上下文中会触发只读 SQLite journal warning；现在网页/API 已降级为可读 warning，不再断连接。后续应为演示服务配置可写操作日志 DB 或只读连接模式。
- 文档问答当前是本地确定性检索和证据片段返回，不是完整向量 embedding RAG；它满足网页端可验证的文档问答入口和证据链，但语义召回质量仍需后续接入正式索引。

## 后续优化

- 将 v2 UI 合入默认 `8765` 服务前，先备份当前服务并做一次主端口灰度验证。
- 给 operation log 单独配置可写 SQLite，避免复用只读 inventory DB。
- 文档问答后续接入正式 SQLite FTS/embedding 索引，保留当前 `/api/documents/query` 作为 fallback。
- 备份和媒体创建入口可增加结果详情面板，显示刚创建的 task/album id。

## 受控工作流入口补齐验证（2026-07-05）

### 变更范围

- 移除前端兜底提示 `该入口已保留为受控工作流`；所有可见 `data-action` 均有明确 handler。
- 首页：最近任务、清除已完成、Token / 路由详情接入 workflow 面板和真实 `/api/token-budget/*` 读取。
- 顶栏：通知、帮助、管理员菜单接入 workflow 面板。
- AI 助手：使用指南、附件、继续追问、提炼要点、生成思维导图、导出 Markdown、证据来源、最近文件、Trace、相关智能体均接入具体交互。
- 文件：新建文件夹、无覆盖上传、复制路径、本地只读分享说明、快照创建接入真实 NAS 路径和 API。
- 审计：筛选、重置、页大小入口接入本地状态；空真实日志时仍显示可操作审计表格。

### 新增受控写入 API

- `POST /api/storage/create-folder`
  - 只接受 Personal root 内相对路径。
  - 要求当前用户对目标路径有 `write` 权限。
  - 父目录必须存在，目标已存在则拒绝。
- `POST /api/storage/upload-file`
  - 只接受文件名，不接受带路径分隔符的 filename。
  - 只允许无覆盖创建；`overwrite=true` 会被拒绝。
  - 单文件大小上限 5 MiB。
  - 写入后记录 storage operation。

### 实机样本

- API 直接验证样本：
  - 新建目录：`Collections/CodexWorkflowVerify_20260705-003207`
  - 上传文件：`Collections/CodexWorkflowVerify_20260705-003207/uploaded_from_web_api.txt`
- 浏览器 UI 验证样本：
  - 新建目录：`Collections/CodexWorkflowUI_20260705032609`
  - 上传文件：`Collections/CodexWorkflowUI_20260705032609/ui_upload_20260705032609.txt`

### 浏览器验证

- 入口：`http://127.0.0.1:8767/ui`
- Browser 插件路径：已尝试；在 `goto`/页面检查阶段 30 秒超时并重置内核，改用 bundled Playwright fallback。
- Playwright 截图目录：`C:\Users\zhexu\AppData\Local\Temp\digua-ai-nas-web-workflow-20260705`
- 结果文件：`C:\Users\zhexu\AppData\Local\Temp\digua-ai-nas-web-workflow-20260705\workflow_verify_result.json`
- 覆盖交互组：
  - `topbar_notifications`：通过
  - `topbar_help`：通过
  - `topbar_user_menu`：通过
  - `dashboard_tasks_and_token`：通过
  - `assistant_workflows`：通过
  - `files_login_create_upload_share_snapshot`：通过
  - `audit_filter_workflows`：通过
  - `mobile_responsive_files`：通过
- 控制台：error/warn 为空。
- 页面最终检查：未出现 `保留为受控工作流`，未出现 `未识别入口`。

### 最终检查命令

- `node --check web/static/digua_ai_nas_v2.js`：通过
- `python -m py_compile scripts/probes/ai_nas_operator_portal_server.py`：通过
- `py -3 -m pytest tests`：66 passed
- `py -3 SELF_CHECK.py`：`ok: true`
- build：目标 v2 UI 是静态 HTML/CSS/JS，由 Python server 直接服务；仓库根没有对应 npm build script，因此本项不适用。

### 仍保留的安全边界

- 删除、移动、重命名、改权限、覆盖、递归操作仍不直接执行。
- 单文件复制仍必须走 allowlisted copy route：preview、dry-run、confirm、execute、rollback。
- 分享入口只生成本地认证/只读预览信息，不创建公网链接。
