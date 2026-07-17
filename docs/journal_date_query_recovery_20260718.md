# AI 助手按日期读取日记修复记录（2026-07-18）

## 问题与根因

用户在 AI 助手中询问“2026年5月20日干什么了”时，页面返回本地 Qwen 的通用隐私拒答，没有读取用户已有的 `Documents/2026年日记.docx`。

实机日志显示该请求只调用了 `/api/copilot/chat` 和 token 路由，没有调用日记或文档检索接口。原因是助手意图识别只支持“日记总结”和“写日记”，没有覆盖“日期 + 干什么/做了什么”这种读取问法。旧逻辑还把“日记”中的单个“记”字当成写入触发词，存在把读取请求误判为写入的风险。

## 修复边界

- 完整日期支持 `YYYY年M月D日`、`YYYY-MM-DD`、`YYYY/MM/DD` 和 `YYYY.MM.DD`。
- “日期 + 干什么/做了什么/去了哪里”等个人活动问法，以及“查看某日日记”，路由到 `Documents` 范围内的本地 SQLite FTS-first 文档 RAG。
- ISO/斜杠日期同时规范化成中文日期，确保能命中 Word 日记正文。
- 只有明确的“写/记录/新增日记”才走日记写入；读取不会再因“日记”中的“记”字触发写入。
- 文档召回继续执行登录用户 ACL；私有原文不发送云端，Qwen 没有工具执行权。

## 本地验证

- Python 编译通过。
- 定向回归：`tests/test_copilot_local_qwen_chat.py`、`tests/test_document_fts_rag.py`、`tests/test_journal_routes.py`、`tests/test_offline_ui_contract.py` 共 36 项通过。
- 使用从 NAS 只读复制的真实 `2026年日记.docx` 验证：查询被识别为 `document_query`，规范化日期为 `2026年5月20日`，召回 1 条 Word 证据，`cloud_used=false`，`qwen_execution_authority=false`。

## 待完成的实机门禁

本文件随修复 PR 首次提交时，S100P 部署、真实登录页面回答、CI、合并与生产验证仍待完成；完成后需把最终 commit、部署时间、HTTP/UI 结果和回滚点补入本文件。
