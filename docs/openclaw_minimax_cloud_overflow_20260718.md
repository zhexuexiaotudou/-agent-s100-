# OpenClaw MiniMax 云端外溢路径（2026-07-18）

## 目标

- `你是谁`、`Who are you?` 等助手身份问题在门户内直接返回本地身份说明，不调用 Qwen 路由器，也不产生云端请求。
- 1.5B Qwen 提供语义建议，确定性 Workspace Harness 策略拥有最终路由权。只有
  `privacy_level=0`、复杂度不低于 2、明确需要最新外部信息、没有本地工具/数据依赖且用户未
  禁止联网的公开任务才允许进入云端路径。
- 云端生成统一通过 S100P 上的 OpenClaw `custom-gateway/MiniMax-M2.7` provider；门户不读取、不保存 MiniMax API token。

## 调用链与权限边界

```text
AI-NAS portal (sunrise, 127.0.0.1:8765)
  -> Qwen route/privacy decision (127.0.0.1:18080)
  -> OpenClaw cloud bridge (root, 127.0.0.1:18082, local bearer token)
  -> openclaw infer model run --gateway --model custom-gateway/MiniMax-M2.7
  -> OpenClaw gateway (root, 127.0.0.1:18765)
  -> MiniMax provider
```

`openclaw_cloud_inference_bridge.py` 只提供 OpenAI-compatible chat completion 适配，不开放 agent、tool、shell 或 NAS 写操作。模型在服务参数中固定，客户端请求不能更换 provider。服务拒绝非回环地址绑定，限制请求和 prompt 大小，审计只返回 prompt hash 与长度，不记录 prompt 原文。

桥凭据保存在 `/home/sunrise/.config/digua/cloud_bridge_token`，部署时生成，权限必须为 `0600`。该凭据只保护门户到本机桥的调用，不是 MiniMax token。MiniMax token 继续由 root OpenClaw 配置管理，禁止写入仓库、systemd unit、报告或日志。

## 部署

1. 将 `scripts/probes/openclaw_cloud_inference_bridge.py` 同步到 `/mnt/nas/openclaw/scripts/probes/`。
2. 将 `configs/systemd/digua-openclaw-cloud-bridge.service` 安装到 `/etc/systemd/system/`。
3. 在 S100P 本机生成桥凭据并设置 `sunrise:sunrise`、`0600`，不要输出凭据内容。
4. 将 `configs/systemd/user/openclaw-gateway.service.d/30-minimax-cloud-overflow.conf` 安装到门户 user service 的同名 drop-in 目录。其内容为：

   ```ini
   Environment=AI_NAS_CLOUD_CHAT_URL=http://127.0.0.1:18082/v1
   Environment=AI_NAS_CLOUD_CHAT_MODEL=custom-gateway/MiniMax-M2.7
   Environment=AI_NAS_CLOUD_CHAT_TOKEN_FILE=/home/sunrise/.config/digua/cloud_bridge_token
   Environment=AI_NAS_CLOUD_CHAT_TIMEOUT_SECONDS=210
   ```

5. 先启动并检查 root bridge，再重启 `sunrise` 的门户 user service。

桥服务必须显式设置 `HOME=/root`，并将 OpenClaw 自带的 Node.js 22 目录放在 `PATH` 首位。systemd 的默认 PATH 可能命中系统 Node.js 20，届时 OpenClaw 会以版本不满足要求退出。OpenClaw CLI 还会维护 `/root/.openclaw/state` 的权限，因此沙箱仅对这个 state 目录开放写权限；provider 配置和桥脚本仍为只读。

门户的云端 HTTP 等待时间为 210 秒，比 bridge 的 180 秒推理上限更长，使 bridge 能返回明确的超时响应。门户 HTTP 客户端必须把底层 `TimeoutError` 转成结构化 `cloud_overflow_failed`，不能让浏览器连接被直接关闭。

## 验收

- `GET http://127.0.0.1:18082/health` 返回 `ok=true`，端口只监听 loopback。
- 未携带或携带错误桥凭据的 completion 请求返回 `401`。
- OpenClaw CLI 的固定 provider 探针返回 `provider=custom-gateway`、`model=MiniMax-M2.7`。
- 门户输入 `你是谁`：返回 `identity_answer_source=deterministic_local_identity`、`cloud_used=false`，OpenClaw bridge 无对应调用。
- 门户输入明确公开、复杂且需要最新外部信息的问题：返回
  `assistant_mode=cloud_overflow_chat`、`cloud_used=true`，回答来自 OpenClaw/MiniMax。
- 含私有 NAS 内容或本地工具意图的请求仍留在本地，不允许通过 bridge。
- 公开复杂但不要求最新信息的请求使用本地 7B；同时需要本地数据和最新外部信息的请求标记为
  混合候选，但在安全拆分/脱敏/本地合并链路启用前保持本地。

## 回滚

1. 从门户 user service 移除三个 `AI_NAS_CLOUD_CHAT_*` 环境变量并重启门户；云端路径恢复为不发送请求的 `cloud_overflow_stub`。
2. `systemctl disable --now digua-openclaw-cloud-bridge.service`。
3. 保留 OpenClaw 既有 provider 配置，不改动 MiniMax token；必要时删除仅用于本机桥认证的 `cloud_bridge_token`。

回滚不会影响本地 Qwen、NAS 只读功能或 OpenClaw 根网关。

## 2026-07-18 生产验收

- 主功能经 [PR #60](https://github.com/zhexuexiaotudou/-agent-s100-/pull/60) 合并，systemd 运行环境修正经 [PR #61](https://github.com/zhexuexiaotudou/-agent-s100-/pull/61) 合并，门户长推理超时修正经 [PR #62](https://github.com/zhexuexiaotudou/-agent-s100-/pull/62) 合并。三个 PR 的 `offline-regression` 和 `startup-link-check-contract` 均通过。
- S100P 当前部署修订为 `1e9ed16f7d8a302f6174c1b11f786f4e68e4af37`。`openclaw-gateway.service`、门户 user service 和 `digua-openclaw-cloud-bridge.service` 均为 `active`；8765、18080、18082 和 18765 都只监听 loopback。
- 桥的真实 HTTP 探针返回 `provider=custom-gateway`、`model=MiniMax-M2.7`、`transport=openclaw_gateway` 以及 `BRIDGE_MINIMAX_OK`。
- 临时验收用户通过真实 `/api/copilot/chat` 调用两个案例：`你是谁` 返回 `deterministic_local_identity`、`cloud_used=false`、`cloud_payload_sent=false`；公开复杂分析返回 `router_route=cloud`、`privacy_level=none`、`cloud_overflow_chat`、`MiniMax-M2.7`。两个 HTTP 响应都为 200，临时用户随后删除。
- 部署备份保留在 `/mnt/nas/openclaw/deploy_backups/e244d95c-20260718034337`、`/mnt/nas/openclaw/deploy_backups/d85f3d99-20260718034913` 和 `/mnt/nas/openclaw/deploy_backups/1e9ed16f-20260718035733`。

## 2026-07-18 自动路由 v2 验收

- [PR #67](https://github.com/zhexuexiaotudou/-agent-s100-/pull/67) 取消用户模型选择权并建立
  1.5B / 7B / MiniMax 自动编排；[PR #68](https://github.com/zhexuexiaotudou/-agent-s100-/pull/68)
  收紧 MiniMax 的时效性门槛并增加统一决策字段。当前生产合并提交为
  `aca4941eae22a9587278bca3c45fce668dddd9af`。
- 门户运行文件哈希为：后端
  `cf1ef9e6374b1ff4dfd1f858ae069d5e9613b2346c4f7caaf128d71b6232bde2`，前端 JS
  `10c3f0ed1f512c1b538aef1e8ae7114f0a3f21c2986752cb77d198c5977034a3`。回滚备份位于
  `/mnt/nas/openclaw/deploy_backups/aca4941e-20260718055305`。
- 实机认证 API 验证：默认简单请求走 1.5B（约 234 ms）；公开复杂但无时效性请求走本地 7B
  （约 40.4 s）；本地数据 + 最新公开信息被标记为混合候选并留在本地 7B（约 40.5 s）；
  NAS Workspace 只调用 1.5B 语义路由且忽略旧 `model_choice`；身份问题零模型调用。
- MiniMax 门户重试返回 `CLOUD_MINIMAX`、`cloud_egress_allowed=true`、`cloud_used=true`，实际
  1.5B 路由约 4.9 ms，MiniMax 非流式完整响应约 118.3 s。独立 bridge 探针约 11.0 s 返回
  `MINIMAX_BRIDGE_OK`。
- 同一轮较长研究请求曾在实际发起 MiniMax 后失败，随后按策略回落本地 7B，总耗时约 167.4 s；
  因此当前结论是“链路可用且有安全回落”，不是“云端长请求无波动”。
- 实机浏览器确认页面不含模型选择器；详情显示 `workspace_harness_auto_v2`、请求 ID、路由枚举、
  隐私/复杂度/时效性/网络/混合/写风险字段，以及每一次实际模型调用的模型、位置、状态与耗时。
