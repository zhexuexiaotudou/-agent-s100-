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

## 实机复测发现的第二层问题

首次路由修复合并为 PR #51，合并 commit 为 `c043858e2da1e30454845c21fa76053400e88c23`。部署后实机请求已正确进入 `local_document_query`，但文档回答层仍将 Qwen 的“无法提供具体信息”当作有效回答。原因是拒答校验仅在金额类查询中生效。

第二层修复将指定日期的日记查询改为严格证据答复：

- 只保留摘要中含目标日期的证据，并优先保留文件名或路径含“日记/diary/journal”的文档。
- 从目标日期开始提取该日内容，遇到下一个完整日期标题即截断，避免混入其他日期或合同文档。
- 指定日期日记不再调用 Qwen 生成答案，直接返回可追溯的本地文档证据。
- 普通文档查询中的“无法提供/无法获取/人工智能语言模型”等泛化拒答，也会被 grounding 校验拒收并回退到本地证据。

## 本地验证

- Python 编译通过。
- 第二层定向回归：`tests/test_copilot_local_qwen_chat.py` 共 23 项通过，包含精确日期日记答复与非金额拒答回退。
- 定向回归：`tests/test_copilot_local_qwen_chat.py`、`tests/test_document_fts_rag.py`、`tests/test_journal_routes.py`、`tests/test_offline_ui_contract.py` 共 36 项通过。
- 第二层完整回归：`python -m unittest discover -s tests -v` 共 185 项通过。
- 使用从 NAS 只读复制的真实 `2026年日记.docx` 验证：查询被识别为 `document_query`，规范化日期为 `2026年5月20日`，召回 1 条 Word 证据，`cloud_used=false`，`qwen_execution_authority=false`。

## 合并、部署与实机门禁

- 第二层修复 commit：`09b0b9e3`；PR #54；合并 commit：`a3a063ee0fdb89ebeb74677c5788c458c099806e`。
- GitHub Actions：`startup-link-check-contract` 17 秒通过；`offline-regression` 1 分 19 秒通过。
- 2026-07-18 02:07 CST 部署到 `sunrise@192.168.127.10` 的用户级 `openclaw-gateway.service`，目标仍为回环 `127.0.0.1:8765`，未扩大网络暴露面。
- 部署文件 SHA-256：`be0204e1608a907f35984dfa877f1e380c4148795b4ca3f0ccb298e10e7cf63e`；服务重启后 `portal_ui=200`、`lan_ui=200`、`qwen_health=200`。
- 真实登录页面 `http://digua.local/ui#assistant` 提交“2026年5月20日我干什么了？”后，显示“本地文档返回”和“1 条证据 · 未上云”，答案包含法餐、香槟玫瑰和家庭浪漫支出 1314 元，证据只有 `2026年日记.docx`。
- 实机返回字段为 `assistant_mode=local_document_query`、`document_answer_source=deterministic_journal_evidence`、`qwen_document_answer_used=false`、`evidence_count=1`、`cloud_used=false`、`qwen_execution_authority=false`。
- 回滚点：`/mnt/nas/openclaw/deployment/backups/journal-date-query-grounding-20260718-020709/ai_nas_operator_portal_server.py`，其 SHA-256 为 `ef75d14c65630f4059fcf5f7d3d6aea4e4ceafd4c69762308c298094de64ba84`。
