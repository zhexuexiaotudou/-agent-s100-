# 参考文献与报告章节映射

| 编号 | 参考文献 | 支撑的报告内容 | 对应章节 |
|---|---|---|---|
| [1] | D-Robotics RDK Kit / RDK S100 文档 | RDK S100P 硬件平台、边缘 AI 设备、resident gateway 的硬件背景 | 系统组成、硬件平台、部署环境 |
| [2] | D-Robotics LLM Toolchain | S100 LLM SDK、Qwen2.5 HBM、板端本地推理工具链 | 软件设计、模型部署、本地推理链路 |
| [3] | OpenClaw Documentation | OpenClaw Gateway、控制入口、agent/NAS action surface | 软件架构、OpenClaw 控制层、交互入口 |
| [4] | Qwen2.5-1.5B-Instruct model card | 本地 Qwen2.5 模型选择、模型 ID、tokenizer 来源 | 模型选型、语义理解、token budget |
| [5] | Hugging Face Transformers Auto Classes | `AutoTokenizer` 加载机制、本地 tokenizer 接入方式 | token budget、tokenizer 实现 |
| [6] | Hugging Face Tokenizers | `tokenizer.json`、fast tokenizer、tokenizers backend | tokenizer 技术实现、token 统计 |
| [7] | SQLite FTS5 Extension | SQLite/FTS5 元数据索引、文档全文检索、本地数据库依赖 | NAS 数据索引、文档检索、系统实现 |
| [8] | Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks | 检索增强生成、文档问答、folder RAG 的方法来源 | 文档 RAG、文件问答、知识检索 |
| [9] | OWASP Top 10 for Large Language Model Applications | prompt injection、防止敏感信息泄露、工具调用权限边界、excessive agency 风险 | 安全设计、隐私保护、工具调用边界 |
| [10] | Local-first software | local-first / privacy-first 设计原则，本地数据控制优先 | 设计目标、隐私保护、边云协同 |
| [11] | QNAP TS-264C 产品页 | NAS 硬件环境、私有云/本地存储背景 | 系统组成、NAS 数据管理、实验环境 |
| 自研-A | Workspace Harness / policy-first router | 项目自研设计，不作为外部参考文献；由 `ai_nas_harness/`、`config/workspace_tool_policy.yaml`、`docs/STAGE3_POLICY_FIRST_ARCHITECTURE.md` 和 gate 证据支撑 | 安全架构、执行控制 |
| 自研-B | allowlist dispatcher / `ai_nas_allowlisted_tool.sh` | 项目自研执行边界，不作为外部参考文献；由 `config/workspace_tool_policy.yaml`、`gates/` 和 acceptance packet 支撑 | 工具调用安全、权限控制 |
| 自研-C | copy route / approval token / rollback | 项目自研受控写操作设计，不作为外部参考文献；由 `docs/STAGE4_4_COPY_ROUTE_CONTRACT.md`、`src/harness/copy_route_guard.py`、`ai_nas_harness/approval_token.py` 支撑 | 受控 NAS 操作、审计与回滚 |
| 自研-D | gate / evidence packet / audit trace | 项目自研证据链，不作为外部参考文献；由 `gates/`、`evidence_for_gptpro/`、`tmp/demo_three_features_final_recheck/` 和报告路径支撑 | 验收方法、审计证据 |
| 自研-E | Digua Journal / 周期总结 | 项目自研日志与总结模块，不作为外部参考文献；由 `src/digua_journal/`、`docs/DIGUA_JOURNAL_PRODUCTION_ARCHITECTURE.md`、`docs/DIGUA_JOURNAL_PRODUCTION_REPORT_SECTION.md` 支撑 | 日志总结、运行复盘 |

## 最终判断

1. 推荐最终参考文献数量：11 条，覆盖 S100P、OpenClaw、Qwen2.5、Hugging Face tokenizer、SQLite/FTS5、RAG、LLM 安全、local-first/privacy-first 和 NAS 环境。
2. 最关键参考文献：[1]、[2]、[3]、[4]、[7]、[8]、[9]。这些直接支撑硬件平台、模型路线、控制框架、索引/RAG 和安全边界。
3. 自研实现不需要外部文献背书，但需要在报告中引用项目证据：Workspace Harness、allowlist dispatcher、copy route approval token/rollback、gate evidence packet、Digua Journal。
4. 需要谨慎的表述：不要承诺完整替代商用 NAS；不要把受控 copy route 写成任意写操作；不要把 benchmark token reduction 写成真实费用节省；不要把 fixture ACL 写成真实 SMB/AD/LDAP 全兼容；不要把 controlled local cloud stub 写成真实云服务已验收。
