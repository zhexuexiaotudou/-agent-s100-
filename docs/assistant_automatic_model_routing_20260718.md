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
| 公开、无隐私、无本地工具意图的复杂任务 | `web_cloud_research` | `custom-gateway/MiniMax-M2.7` | OpenClaw loopback bridge `127.0.0.1:18082` |
| 上述云端任务遇到桥未配置或调用失败 | `web_cloud_research` | Qwen2.5 7B fallback | S100P CPU，`127.0.0.1:18081` |

“复杂”升级采用确定性下限：策略根据输入长度和明确的复杂任务信号判定是否进入 7B/云端分支。
1.5B 的语义判断会写入详情并参与 Workspace 建议，但不能单独触发高成本模型；这样短而简单的默认
请求不会因为 1.5B 一次误报而被提升到 7B，同时明确复杂的本地任务也不会被降级。

## Workspace 映射

| 意图 | Workspace |
| --- | --- |
| 照片、视频、媒体检索与相册 | `media_photo` |
| 文档问答与日记 | `document_rag` |
| 存储查询、目录与状态 | `nas_search` |
| 复制、重命名、新建目录、快照与备份 | `nas_action` |
| 运行状态与恢复 | `ops_recovery` |
| 应用、审计与报告 | `admin_audit` |
| 可上云的公开复杂研究 | `web_cloud_research` |
| 其他通用对话 | `main_router` |

## 回答详情契约

`POST /api/copilot/chat` 的响应包含：

- `selected_workspace`：最终 Workspace。
- `user_model_selection_allowed=false`：用户没有模型选择权。
- `model_routing.policy_id=workspace_harness_auto_v1`：当前编排策略。
- `model_routing.planned_answer_model`：策略原计划的回答模型。
- `model_routing.effective_answer_model`：最终实际回答模型；确定性回答或纯工具任务可为空。
- `model_routing.selection_reason`：为什么进入该模型分支。
- `model_routing.calls[]`：按实际顺序记录每一次模型请求的阶段、请求模型、provider、位置、
  目的、状态和耗时。结构化路由重试、MiniMax 失败以及 7B fallback 都必须单独出现。

网页的“查看详情”直接展示上述事实。模型正文只做 HTML 转义，不再替换成预设云端文案，也不再
执行会改变模型语义的产品文案清洗。

## 安全与诚实边界

- 1.5B 是 S100P BPU 路径；7B 是 S100P CPU 路径，不能描述成已工作的 7B BPU。
- MiniMax token 仍只由 root OpenClaw 配置持有。门户只读取 loopback bridge 凭据文件。
- MiniMax 不接收私密、NAS、本地文件或本地工具任务。
- 模型始终没有任意 shell、路径或 NAS 工具执行权。
- 当前 MiniMax bridge 是准确性优先的一次性 OpenClaw infer 调用，不等同于 OpenClaw 原生会话的
  流式事件和连续会话状态。

## 验收与回滚

合并前必须覆盖：默认 1.5B、私密复杂 7B、公开复杂 MiniMax、云端失败回落 7B、身份零模型调用、
工具 Workspace 不受旧 `model_choice` 影响、详情调用顺序，以及页面不存在模型下拉框。

部署时先备份门户后端、前端 JS 和 HTML。回滚只需恢复这三个文件并重启
`openclaw-gateway.service`；18080、18081、18082 服务和 NAS 数据不需要修改。
