# AI 助手自动模型编排（2026-07-18）

## 产品决定

AI 助手暂不向用户开放模型选择。网页只提交自然语言 `message`，模型由
Workspace Harness 自动安排。旧客户端即使继续提交 `model_choice`，后端也只把它记录为
`requested_model_ignored`，不能改变 Workspace、回答模型、云端边界或工具权限。

本次变更只调整回答模型的编排权，不把 NAS 工具执行权交给模型。Workspace 选择、隐私下限、
allowlist 工具映射和真实执行仍由确定性策略与现有受控 API 决定。

## 决策顺序

1. 身份问题直接使用确定性的本地身份契约，不调用语言模型。
2. 其他请求先调用本地 Qwen2.5 1.5B，输出意图、隐私、复杂度和 Workspace 建议。
3. 确定性策略拥有最终路由权：NAS、私密和简单请求都强制留在本地；Qwen 的建议不能单独触发
   上云或 7B 升级。
4. 有工具意图时，进入对应 Workspace 和 allowlist dispatcher。除文档 RAG 的有据回答外，
   不再调用通用回答模型。
5. 无工具意图时，按下表选择回答模型。

| 条件 | Workspace | 回答模型 | 位置 |
| --- | --- | --- | --- |
| 普通、简单、本地对话 | `main_router` | Qwen2.5 1.5B | S100P BPU，`127.0.0.1:18080` |
| 私密、受限或其他必须留在本地的复杂任务 | `main_router` | Qwen2.5 7B | S100P CPU，`127.0.0.1:18081` |
| 公开、无隐私、无本地工具意图，且明确需要最新外部信息的复杂任务 | `web_cloud_research` | `custom-gateway/MiniMax-M2.7` | OpenClaw loopback bridge `127.0.0.1:18082` |
| 上述云端任务遇到桥未配置或调用失败 | `web_cloud_research` | Qwen2.5 7B fallback | S100P CPU，`127.0.0.1:18081` |

“复杂”升级采用确定性下限：策略根据输入长度和明确的复杂任务信号判定是否进入 7B/云端分支。
1.5B 的语义判断会写入详情并参与 Workspace 建议，但不能单独触发高成本模型；这样短而简单的默认
请求不会因为 1.5B 一次误报而被提升到 7B，同时明确复杂的本地任务也不会被降级。

MiniMax 不是“复杂任务的默认大模型”。只有策略同时确认 `privacy_level=0`、复杂度不低于 2、
需要公开网络并具有明确时效性（例如当前、最新、近期、价格、固件、漏洞或新闻）时才允许外发。
公开但不要求最新信息的复杂推理仍交给本地 7B；用户明确要求离线时也保持本地。

同时需要本地资料和最新外部信息的输入会标记为 `hybrid_candidate`。当前版本没有声称已经具备
字段级安全拆分、最小化外发、脱敏审计和本地 7B 合并能力，因此这类输入不会把原始任务发往
云端，而是保持本地并记录 `hybrid_status=unsupported_safe_splitter_not_enabled`。

## Workspace 映射

| 意图 | Workspace |
| --- | --- |
| 照片、视频、媒体检索与相册 | `media_photo` |
| 文档问答与日记 | `document_rag` |
| 存储查询、目录与状态 | `nas_search` |
| 复制、重命名、新建目录、快照与备份 | `nas_action` |
| 运行状态与恢复 | `ops_recovery` |
| 应用、审计与报告 | `admin_audit` |
| 可上云且明确需要最新外部信息的公开复杂研究 | `web_cloud_research` |
| 其他通用对话 | `main_router` |

## 回答详情契约

`POST /api/copilot/chat` 的响应包含：

- `selected_workspace`：最终 Workspace。
- `user_model_selection_allowed=false`：用户没有模型选择权。
- `model_routing.policy_id=workspace_harness_auto_v2`：当前编排策略。
- `model_routing.planned_answer_model`：策略原计划的回答模型。
- `model_routing.effective_answer_model`：最终实际回答模型；确定性回答或纯工具任务可为空。
- `model_routing.selection_reason`：为什么进入该模型分支。
- `routing_decision` / `model_routing.decision`：统一的可审计决策，包含请求 ID、策略路由枚举、
  隐私等级（0/2/3）、复杂度（0-3）、时效性、公开网络需求、本地数据需求、写操作风险、确认
  要求、选中工具、云端外发许可和混合候选状态。
- `model_routing.calls[]`：按实际顺序记录每一次模型请求的阶段、请求模型、provider、位置、
  目的、状态和耗时。结构化路由重试、MiniMax 失败以及 7B fallback 都必须单独出现。

网页的“查看详情”直接展示上述事实。模型正文只做 HTML 转义，不再替换成预设云端文案，也不再
执行会改变模型语义的产品文案清洗。

## 安全与诚实边界

- 1.5B 是 S100P BPU 路径；7B 是 S100P CPU 路径，不能描述成已工作的 7B BPU。
- MiniMax token 仍只由 root OpenClaw 配置持有。门户只读取 loopback bridge 凭据文件。
- MiniMax 不接收私密、NAS、本地文件或本地工具任务。
- 含密码、API key、token、证件、银行卡、医疗、人脸、序列号、内网 IP、发票或合同等信号的
  请求一律不得上云；“我的/我们的”个人语境至少按中等隐私处理。
- 模型始终没有任意 shell、路径或 NAS 工具执行权。
- 当前复杂多文档 Workspace 仍使用既有本地文档 RAG 回答链；本次没有把它改成 7B 多文档
  合并器。7B 当前覆盖本地复杂通用推理以及 MiniMax 失败回落，避免把规划能力写成已实现事实。
- 当前 MiniMax bridge 为每个符合条件的公开时效性任务创建独立 OpenClaw `web-research` agent
  turn。该 agent 只能看到 `web_search`、`web_fetch`、`tavily_search` 和 `tavily_extract`，必须
  实际完成至少一次联网工具调用才能返回成功；它不具备 shell、文件、NAS、消息或浏览器工具。
  这仍是非流式的一次性门户响应，不等同于 OpenClaw 原生对话框的连续会话事件流。

## 验收与回滚

合并前必须覆盖：默认 1.5B、私密复杂 7B、公开但无时效性复杂任务仍走 7B、公开且需要最新
外部信息的复杂任务才走 MiniMax、禁止联网、敏感信息和混合候选不外发、云端失败回落 7B、
身份零模型调用、工具 Workspace 不受旧 `model_choice` 影响、详情调用顺序，以及页面不存在
模型下拉框。

部署时先备份门户后端、前端 JS 和 HTML。回滚只需恢复这三个文件并重启
`openclaw-gateway.service`；18080、18081、18082 服务和 NAS 数据不需要修改。

## 生产验收

- 实现经 [PR #67](https://github.com/zhexuexiaotudou/-agent-s100-/pull/67) 和
  [PR #68](https://github.com/zhexuexiaotudou/-agent-s100-/pull/68) 合并；自动编排基线提交为
  `aca4941eae22a9587278bca3c45fce668dddd9af`。PR #68 的 `static-ui-contract`、
  `startup-link-check-contract` 和 `offline-regression` 全部通过，本地完整回归为
  `227 passed, 3 subtests passed`。
- 自动编排基线部署时，S100P 门户重启与 `/api/health` 通过。部署后端/前端哈希分别为
  `cf1ef9e6374b1ff4dfd1f858ae069d5e9613b2346c4f7caaf128d71b6232bde2` 和
  `10c3f0ed1f512c1b538aef1e8ae7114f0a3f21c2986752cb77d198c5977034a3`；回滚点为
  `/mnt/nas/openclaw/deploy_backups/aca4941e-20260718055305`。
- 实机 API 已覆盖默认 1.5B、无时效性公开复杂任务 7B、混合候选留本地 7B、MiniMax 成功、
  MiniMax 失败回落 7B、NAS 工具忽略旧模型选择和身份零模型调用。临时用户已全部删除。
- MiniMax 成功案例的完整非流式门户响应约 118.3 s；同轮另一个较长请求出现一次上游失败并
  安全回落 7B。准确性与安全回落已验证，但当前 bridge 不等同于低延迟、流式且无波动的原生
  OpenClaw 会话。
- 实机浏览器确认用户无模型选择入口，且详情展示统一决策字段和每一次真实模型调用。

### 身份回答显示快路径

[PR #70](https://github.com/zhexuexiaotudou/-agent-s100-/pull/70) 将助手正文与辅助 Token Budget
详情解耦。`/api/copilot/chat` 返回后立即显示答案；`/api/token-budget/route` 并行执行并在完成后
补充详情，失败时也不能覆盖或延迟已经返回的回答。前端使用请求序号阻止较早请求的详情覆盖后续
对话。

生产拆分计时中，`Who are you?` 的确定性身份接口约 60.5 ms、零模型调用，Token Budget 路由约
82.2 ms。部署合并提交 `1a5ddad0291cd8ef3ddff9029d72b9eaf9d7c1db` 后，实机浏览器输入
“你是谁”到答案可见约 290 ms。线上 JS SHA-256 为
`344ba012e7b19be93ff1b2759fc33159aa890e3520351a9112cafad3c46a2bbf`，回滚点为
`/mnt/nas/openclaw/deploy_backups/1a5ddad0-20260718061857`。

### 日期文档检索回归修复

[PR #73](https://github.com/zhexuexiaotudou/-agent-s100-/pull/73) 补齐不带年份的日期和“干了什么”等
个人历史问法，防止它们落入通用 1.5B 对话。此类请求由确定性策略固定进入 `document_rag`；
有证据时直接返回本地可追溯内容，无证据时明确说明未命中，不调用云端，也不允许 Qwen 执行工具。

当前生产合并提交为 `3a54c9042c12c5f20029d3ef662173d3d1efcb4e`，线上后端 SHA-256 为
`c57dc96441b0c4911733279bcb8b0a9170ecc5ab8a16503ce5fea503a482b581`。完整验收与回滚点见
[`journal_date_query_recovery_20260718.md`](journal_date_query_recovery_20260718.md)。

### 相册部署覆盖后的组合恢复

相册预览分支曾基于 7 月 9 日回滚分支直接部署完整门户文件，导致上述自动模型编排、身份快路径
和日期文档检索在运行环境中一起退回旧实现。[PR #77](https://github.com/zhexuexiaotudou/-agent-s100-/pull/77)
把相册缩略图修复移植到当前 `main`，并以同一套回归同时验证助手和相册，避免按功能整文件覆盖。

当前生产合并提交为 `5a56931644ac987ce33227510541b9b2d99d8de3`；线上后端 SHA-256 为
`23963ba3475bd29d16b45a0083035da0a9a8c3eda1d7088167acd1d6b2adfa4a`。本地完整回归为
`238 passed, 11 subtests passed`，PR 的 4 项 CI 全绿。实机 UTF-8 请求结果：身份回答约 64 ms、
零模型调用；“5月20日我干了什么”进入本地文档 RAG 并返回 1 条日记证据；公开时效性复杂请求
由 `custom-gateway/MiniMax-M2.7` 返回 `cloud_overflow_chat`；相册缩略图 HTTP 200。浏览器 `/ui`
登录后输入“你是谁”也显示正确本地身份和模型详情。回滚点为
`/mnt/nas/openclaw/deployment/backups/restore-assistant-5a569316-20260718-071038`。
