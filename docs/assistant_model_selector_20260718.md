# AI 助手模型选择（2026-07-18）

## 目标

AI 助手输入框提供三个明确选项：

- `Qwen2.5 1.5B（本地）`
- `Qwen2.5 7B（本地）`
- `MiniMax 2.7（云端）`

默认选择 1.5B。本地选择只改变通用对话和本地路由所使用的 Qwen 模型，不扩大 Qwen 的 NAS 操作权限。

## 两个本地运行时

1.5B 使用 S100P BPU `oellm_multichat`，监听 `127.0.0.1:18080`。7B 使用板端已有的 `Qwen2.5-7B-Instruct-Q4_K_M.gguf` 和 `llama-cpp-python` CPU runtime，监听 `127.0.0.1:18081`。两个端口均不对局域网或公网开放。

不能把 7B 描述成当前 BPU 模型。2026-07-18 的真实补全复核表明，7B HBM 在干净重启后仍因 ION 无法分配约 7.4GB 而失败。6 月 24 日的 `ok_qwen25_7b_shadow_acceptance_packet` 只验收了健康页、模型清单和 NAS allowlist 工具流；其中 chat 响应是网关根据工具结果生成的固定摘要，没有执行 7B 文本生成。因此本次功能选择诚实可验收的本地 CPU 7B 路径。

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

省略该字段时保留既有自动路由行为。未知值返回 `400 assistant_model_not_allowed`。18080 和 18081 的 `/v1/models` 分别报告 1.5B BPU 与 7B CPU 模型。

## 回滚

1. 恢复部署前的门户后端和前端静态文件。
2. 禁用并停止 `qwen7b-cpu.service`，重启门户 user service。
3. 1.5B BPU、MiniMax bridge 与 NAS 本地工具不受该回滚影响。

生产验收证据在合并和 S100P 部署后补充到本文。
