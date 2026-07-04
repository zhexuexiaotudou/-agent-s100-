# Product Claim Evidence Matrix

| # | Claim | Status | Safe wording | Remaining gap |
| --- | --- | --- | --- | --- |
| 1 | 项目基于 RDK S100P 与 OpenClaw。 | supported | 本项目在 RDK S100P 上运行 OpenClaw Gateway/AI-NAS 门户，并以 NAS 专用 workspace 保存证据。 | PC 网络/NAT 依赖仍需作为运行边界说明。 |
| 2 | S100P 是本地 AI Gateway。 | supported | S100P 当前提供本地 OpenAI-compatible Qwen endpoint，作为 AI-NAS 的本地模型入口。 | Qwen health 中仍有历史 profile 字段，报告以 live endpoint 和 gate verdict 为准。 |
| 3 | OpenClaw 负责交互与任务编排。 | supported | OpenClaw 是用户交互和受控 NAS 工作流入口。 | 真实写操作仍需单独人工确认和 gate。 |
| 4 | Qwen2.5 本地模型网关已部署。 | supported | 本地 Qwen2.5 endpoint 可查询健康状态和模型身份。 | Qwen 仅提供理解/分类/回答，不持有工具执行权。 |
| 5 | Qwen 用于语义理解、摘要、建议或本地推理。 | supported | Qwen 在已验证路径中承担本地理解、分类、摘要和建议生成角色。 | 复杂质量评估和长文档体验仍需持续样本。 |
| 6 | Workspace Harness 控制工作区、上下文和工具边界。 | supported | Harness 作为 policy-first 控制层限制 workspace、工具暴露和参数记录。 | 真实写入仍未开放。 |
| 7 | 文件检索通过 allowlist dispatcher。 | supported | 文件检索通过 allowlisted dispatcher 路径执行并留下 trace。 | 索引覆盖面受当前 demo dataset 限制。 |
| 8 | 文档读取通过 allowlist dispatcher。 | supported | 文档 RAG/文件夹摘要在只读工具和 dispatcher 边界内执行。 | 按 ACL 可见路径限制解释，不承诺全 NAS 文档覆盖。 |
| 9 | 报告生成通过 allowlist dispatcher。 | supported | 证据包、case packet 和 folder RAG 报告通过受控工具生成。 | 报告内容仍需按 claim matrix 审核后入设计报告。 |
| 10 | ACL 权限检查有效。 | supported | 已验证 ACL 拒绝、viewer 只读和受控目标检查。 | 生产部署需同步真实 NAS/目录账号映射策略。 |
| 11 | 私有内容脱敏有效。 | supported | 已验证私有路径/敏感语境在上云前被本地脱敏，测试 private leak count 为 0。 | 新类型敏感字段需继续扩展脱敏规则和样本。 |
| 12 | runtime trace / audit 有记录。 | supported | 只读 shadow、工具调用、策略拒绝、脱敏和回滚均有 trace/audit 记录。 | 真实 NAS 写入上线前还需正式审计保留策略。 |
| 13 | 回滚设计存在。 | supported | 已完成 sandbox canary 回滚和真实 NAS 写操作 dry-run 规划。 | 真实 NAS 写入仍需 GPT Pro/人工复审后才能进入 preflight。 |
| 14 | 网页端访问可用。 | supported | OpenClaw 网页入口当前 HTTP 可访问，并已生成桌面视口截图。 | 功能页登录后全流程截图需使用有效测试账号补充。 |
| 15 | 手机浏览器适配可用。 | partially_supported | 支持手机浏览器访问基础入口；已有 PWA/mobile 结构 gate，当前包含移动视口截图。 | 需补登录后手机端完整功能流截图。 |
| 16 | 权限感知搜索可用。 | supported | 权限感知搜索在只读 shadow case 中通过，拒绝不可见私有路径。 | 生产用户/组映射仍需按真实账号体系复核。 |
| 17 | 语义检索 / 文档问答可用。 | supported | 当前可表述为 metadata/FTS/document chunk retrieval + Qwen-assisted semantic query understanding。 | 向量语义检索覆盖和质量仍需按真实数据集单独验收。 |
| 18 | 文件整理建议可用。 | partially_supported | 系统可生成文件整理/写操作 dry-run 方案、审批和回滚计划；真实移动/删除仍未开放。 | 真实 copy/move/delete 需另走人工确认和真实 NAS preflight。 |
| 19 | 云端只接收 public/redacted 内容。 | supported | 已验证私有 NAS 原文不进入云端路径；公共复杂任务可走受控 cloud stub/endpoint。 | 接入真实云 endpoint 前需复跑 egress gate。 |
| 20 | token 成本降低有数据支持。 | supported | 130 个 synthetic NAS benchmark 中使用真实 Qwen tokenizer 统计云端输入 token；平均云端输入 token 降幅为 92.68%（0.926837），cloud_call_avoidance_rate 为 61.54%（0.615385），private_leak_count = 0，quality_pass_rate = 100%。 | 真实账单成本仍需云 API 价格模型、生产 trace、缓存/重试统计和实际调用日志单独验证。 |
| 21 | 真实 NAS 写操作是否已开放。 | should_reword | 真实 NAS 写操作仍锁定；当前只支持只读 AI-NAS 和 sandbox/dry-run 写入治理验证。 | 需 GPT Pro/人工复审、真实 NAS preflight 和回滚演练。 |
| 22 | sandbox write canary 是否已完成。 | supported | sandbox write canary 已完成，且回滚恢复 before manifest；不能写成真实 NAS 写入。 | 真实 NAS 写入需独立 gate。 |
| 23 | Dream7B 是否属于前台产品能力。 | should_reword | Dream7B 是历史 runtime/研究证据，不作为当前 AI-NAS 前台产品能力；当前产品路径是 Qwen + OpenClaw。 | 如未来切换模型，需重新验收服务、质量、路由和回滚。 |

## Unsafe wording to avoid

- OpenClaw 已完整替代所有 PC/NAS 厂商能力。
- 所有 AI 推理都已在 S100P 上生产级闭环。
- OpenClaw 可直接执行任意 NAS 操作。
- Qwen 已自主完成所有 agent 工具执行。
- Qwen 可以绕过 policy 直接调用工具。
- Harness 已开放所有 NAS 工具。
- 模型可以任意搜索整个 NAS。
- 文档原文可不受限制地送云或外泄。
- 报告生成可以执行任意 shell 或写真实 NAS。
- ACL 绝对杜绝所有风险。
- 系统永久杜绝隐私泄露。
- 所有未来操作都天然可审计。
- 真实 NAS 写入已具备生产级自动回滚。
- 所有网页功能均已在未登录截图中验证。
- 手机端所有复杂工作流都已完整验收。
- 搜索会返回所有 NAS 文件。
- 已生产级向量语义检索全覆盖。
- 系统已自动整理真实 NAS 文件。
- 云端永远不会接触任何敏感内容。
- 真实账单成本已显著下降。
- 真实 NAS 写操作已安全开放。
- sandbox canary 等同于真实 NAS 写入。
- Dream7B 是当前 OpenClaw AI-NAS 前台模型能力。
