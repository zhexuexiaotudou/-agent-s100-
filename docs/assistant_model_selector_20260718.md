# AI 助手模型选择（2026-07-18）

## 目标

AI 助手输入框提供三个明确选项：

- `Qwen2.5 1.5B（本地）`
- `Qwen2.5 7B（本地）`
- `MiniMax 2.7（云端）`

默认选择 1.5B。本地选择只改变通用对话和本地路由所使用的 Qwen 模型，不扩大 Qwen 的 NAS 操作权限。

## 本地 BPU 切换边界

S100P 当前不能让 1.5B 和 7B 的 `oellm_multichat` runtime 同时常驻。2026-07-18 复核时，1.5B runtime 常驻后，独立 18081 端口启动 7B 会返回 `HBRT4_STATUS_BAD_DATA`。因此两个本地选项统一进入 18080 网关：网关根据请求中的 allowlist model id，在同一个锁内关闭旧 runtime、装载目标 HBM，再复用该 runtime 完成本次会话。

18081 的 7B shadow service 不再作为产品入口；部署该功能时应停止并禁用它，避免第二个进程抢占 BPU。

## 云端与隐私边界

手动选择 MiniMax 2.7 不会绕过本地判断：

1. 身份问题由确定性的本地身份回答直接处理。
2. NAS 文件、照片、文档、备份、快照和其他本地工具意图继续走本地 allowlist API。
3. 普通问题先由本地 1.5B 完成隐私分类；仅 `privacy_level=none` 且没有本地工具意图时，才通过 18082 OpenClaw bridge 调用 `custom-gateway/MiniMax-M2.7`。
4. 私有、NAS 范围或不确定内容自动回落到本地 1.5B，并返回 `model_selection_fallback=cloud_blocked_by_local_privacy_guard`。

MiniMax token 仍只由 root OpenClaw 配置持有。网页和门户服务只使用 loopback bridge 的本机凭据，仓库和响应中均不保存或返回 MiniMax token。

## API 契约

`POST /api/copilot/chat` 新增可选字段 `model_choice`：

- `qwen2.5-1.5b-local`
- `qwen2.5-7b-local`
- `minimax2.7-cloud`

省略该字段时保留既有自动路由行为。未知值返回 `400 assistant_model_not_allowed`。本地 Qwen 网关的 `/v1/models` 返回两个允许的本地模型；请求未知 model id 返回 `400 model_not_allowed`。

## 回滚

1. 恢复部署前的 `qwen25_openai_gateway.py`、`qwen25_official_route_policy.json`、门户后端和前端静态文件。
2. 重启 `qwen25-local-openai-gateway.service` 和门户 user service。
3. 如需恢复历史 shadow 入口，再启用 `qwen25-7b-shadow-openai-gateway.service`；它不能与 18080 常驻 runtime 同时接受推理请求。

生产验收证据在合并和 S100P 部署后补充到本文。
