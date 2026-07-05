# Digua AI-NAS 参考文献候选清单

访问日期统一为 2026-07-04。筛选原则：优先保留官方文档、官方模型卡、权威论文和安全标准资料；项目内部 evidence package、gate packet、报告草稿只作为项目证据，不进入外部参考文献。

| 序号 | 标题 | 作者或机构 | 年份 | 链接 | 资料类型 | 对应项目模块 | 是否建议进入最终参考文献 | 理由 |
|---|---|---:|---|---|---|---|---|---|
| C1 | D-Robotics RDK Kit / RDK S100 文档入口 | D-Robotics | n.d. | https://developer.d-robotics.cc/en/rdks100 | 官方文档 | RDK S100P、硬件平台、边缘网关 | 是 | 项目硬件平台的官方入口，可支撑 S100P 作为 resident gateway 和边缘 AI 节点的描述。 |
| C2 | LLM Toolchain | D-Robotics | n.d. | https://developer.d-robotics.cc/rdk_doc/rdk_s/Advanced_development/toolchain_development/LLM_Toolchain | 官方技术文档 | S100 LLM SDK、Qwen HBM、板端本地推理 | 是 | 仓库脚本和配置多次引用 D-Robotics LLM S100 SDK 与 Qwen2.5 HBM，需用官方工具链文档支撑。 |
| C3 | OpenClaw Documentation | OpenClaw | n.d. | https://docs.openclaw.ai/ | 官方文档 | OpenClaw Gateway、NAS action surface、agent/control layer | 是 | 项目把 OpenClaw 作为 AI-NAS 控制入口，官方文档是最直接外部依据。 |
| C4 | openclaw-ai/openclaw | OpenClaw | n.d. | https://github.com/openclaw-ai/openclaw | GitHub 仓库 | OpenClaw 框架实现与开源生态 | 否，备选 | 与 C3 支撑范围重叠；如报告需要强调开源仓库或版本溯源，可替换或补充 C3。 |
| C5 | Qwen2.5-1.5B-Instruct | Qwen Team | 2024 | https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct | 模型卡 | 本地 Qwen2.5 模型、OpenAI-compatible gateway、tokenizer 来源 | 是 | 项目当前模型 ID 与 1.5B Instruct 路线直接相关，比泛泛 Qwen 介绍更贴近实现。 |
| C6 | Qwen2.5 Technical Report | Qwen Team | 2025 | https://arxiv.org/abs/2412.15115 | 论文 / 技术报告 | Qwen2.5 模型族能力背景 | 否，备选 | 可支撑 Qwen2.5 模型族，但当前报告主要需要精确模型卡和板端工具链；为控制最终数量暂不进入。 |
| C7 | Auto Classes / AutoTokenizer | Hugging Face | n.d. | https://huggingface.co/docs/transformers/model_doc/auto | 官方文档 | Transformers AutoTokenizer、本地 tokenizer 加载 | 是 | 项目 token budget 使用 Qwen tokenizer 计数，需要引用 AutoTokenizer 机制。 |
| C8 | Tokenizers | Hugging Face | n.d. | https://huggingface.co/docs/tokenizers/index | 官方文档 | tokenizer.json、fast tokenizer、tokenizers backend | 是 | 项目报告中出现 `tokenizers_json` backend 和 tokenizer identity hash，需引用 HF Tokenizers 文档。 |
| C9 | SQLite FTS5 Extension | SQLite Consortium | n.d. | https://www.sqlite.org/fts5.html | 官方技术文档 | SQLite、FTS5、NAS 元数据/全文索引 | 是 | 项目 SQLite/FTS 文档检索和本地索引的核心外部依据。 |
| C10 | SQLite Documentation | SQLite Consortium | n.d. | https://www.sqlite.org/docs.html | 官方文档 | SQLite 数据库基础 | 否，备选 | 若报告只引用 FTS5，C9 已足够；如增加 SQLite 通用设计说明可补充。 |
| C11 | Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks | Patrick Lewis et al. | 2020 | https://arxiv.org/abs/2005.11401 | 论文 | RAG、文档问答、folder RAG grounding | 是 | RAG 经典论文，可支撑“检索增强生成/文档问答”的方法来源。 |
| C12 | OWASP Top 10 for Large Language Model Applications | OWASP Foundation | 2025 | https://owasp.org/www-project-top-10-for-large-language-model-applications/ | 安全标准 / 项目文档 | prompt injection、sensitive information disclosure、excessive agency、工具调用边界 | 是 | 与项目的 prompt injection 防护、Qwen 无执行权、allowlist dispatcher 和隐私边界直接相关。 |
| C13 | Prompt Injection Prevention Cheat Sheet | OWASP Foundation | n.d. | https://cheatsheetseries.owasp.org/cheatsheets/Prompt_Injection_Prevention_Cheat_Sheet.html | 安全技术文档 | prompt injection 防护细节 | 否，备选 | 比 C12 更细，但最终参考文献为避免安全资料重复，暂保留为备选。 |
| C14 | Local-first software: You own your data, in spite of the cloud | Martin Kleppmann, Adam Wiggins, Peter van Hardenberg, Mark McGranaghan | 2019 | https://www.inkandswitch.com/essay/local-first/ | 论文 | local-first、privacy-first、本地数据控制 | 是 | 项目叙事是 privacy-first AI-NAS，local-first 论文可支撑“数据优先留在本地”的设计原则；正式 DOI 为 10.1145/3359591.3359737。 |
| C15 | TS-264C | QNAP Systems, Inc. | n.d. | https://www.qnap.com.cn/zh-cn/product/ts-264c | 官方产品文档 | NAS 硬件、私有云/本地存储环境 | 是 | 仓库 baseline 明确使用 TS-264C，产品页可支撑 NAS 环境描述。 |
| C16 | NIST Privacy Framework | National Institute of Standards and Technology | 2020 | https://www.nist.gov/privacy-framework | 标准 / 框架 | 隐私风险治理 | 否，备选 | 可信度高，但当前项目更强调 local-first 架构与 LLM 应用安全，最终先不加入以控制数量。 |

## 最终筛选结论

- 推荐最终参考文献数量：11 条。
- 最关键参考文献：C1、C2、C3、C5、C9、C11、C12。
- 项目自研实现不作为外部参考文献：Workspace Harness、allowlist dispatcher、gate/evidence packet、copy route approval token/rollback、Digua Journal、项目内 privacy redaction 和 token trace 实现。
- 需要谨慎的表述：不要把 token benchmark 写成真实账单成本下降；不要把 fixture ACL 写成真实 NAS/SMB/AD 完整权限兼容；不要把受控 copy route 写成任意 NAS 写操作；不要把 controlled local cloud stub 写成真实云服务验收；不要把 OpenClaw/Qwen 的项目集成写成官方产品能力。
