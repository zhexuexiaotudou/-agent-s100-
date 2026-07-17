# OpenClaw MiniMax 云端外溢路径（2026-07-18）

## 目标

- `你是谁`、`Who are you?` 等助手身份问题在门户内直接返回本地身份说明，不调用 Qwen 路由器，也不产生云端请求。
- 只有 Qwen 路由器判定为 `privacy_level=none` 的公开复杂任务才允许进入云端路径。
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
   ```

5. 先启动并检查 root bridge，再重启 `sunrise` 的门户 user service。

桥服务必须显式设置 `HOME=/root`，并将 OpenClaw 自带的 Node.js 22 目录放在 `PATH` 首位。systemd 的默认 PATH 可能命中系统 Node.js 20，届时 OpenClaw 会以版本不满足要求退出。OpenClaw CLI 还会维护 `/root/.openclaw/state` 的权限，因此沙箱仅对这个 state 目录开放写权限；provider 配置和桥脚本仍为只读。

## 验收

- `GET http://127.0.0.1:18082/health` 返回 `ok=true`，端口只监听 loopback。
- 未携带或携带错误桥凭据的 completion 请求返回 `401`。
- OpenClaw CLI 的固定 provider 探针返回 `provider=custom-gateway`、`model=MiniMax-M2.7`。
- 门户输入 `你是谁`：返回 `identity_answer_source=deterministic_local_identity`、`cloud_used=false`，OpenClaw bridge 无对应调用。
- 门户输入明确公开且复杂的问题：返回 `assistant_mode=cloud_overflow_chat`、`cloud_used=true`，回答来自 OpenClaw/MiniMax。
- 含私有 NAS 内容或本地工具意图的请求仍留在本地，不允许通过 bridge。

## 回滚

1. 从门户 user service 移除三个 `AI_NAS_CLOUD_CHAT_*` 环境变量并重启门户；云端路径恢复为不发送请求的 `cloud_overflow_stub`。
2. `systemctl disable --now digua-openclaw-cloud-bridge.service`。
3. 保留 OpenClaw 既有 provider 配置，不改动 MiniMax token；必要时删除仅用于本机桥认证的 `cloud_bridge_token`。

回滚不会影响本地 Qwen、NAS 只读功能或 OpenClaw 根网关。
