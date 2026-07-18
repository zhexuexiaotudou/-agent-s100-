# OpenClaw MiniMax 云端外溢路径（2026-07-18）

## 目标

- `你是谁`、`Who are you?` 等助手身份问题在门户内直接返回本地身份说明，不调用 Qwen 路由器，也不产生云端请求。
- 1.5B Qwen 提供语义建议，确定性 Workspace Harness 策略拥有最终路由权。只有
  `privacy_level=0`、明确需要最新外部信息、没有本地工具/数据依赖且用户未禁止联网的公开任务，
  并满足“复杂度不低于 2”或“用户明确发出联网检索命令”之一，才允许进入云端路径。
- 云端生成统一通过 S100P 上的 OpenClaw `custom-gateway/MiniMax-M2.7` provider；门户不读取、不保存 MiniMax API token。

## 调用链与权限边界

```text
AI-NAS portal (sunrise, 127.0.0.1:8765)
  -> Qwen route/privacy decision (127.0.0.1:18080)
  -> OpenClaw cloud bridge (root, 127.0.0.1:18082, local bearer token)
  -> openclaw agent --agent web-research --model custom-gateway/MiniMax-M2.7
  -> Tavily web search/extract tools
  -> OpenClaw gateway (root, 127.0.0.1:18789)
  -> MiniMax provider
```

`openclaw_cloud_inference_bridge.py` 提供 OpenAI-compatible chat completion 适配，但内部固定调用隔离的
`web-research` agent。该 agent 的绝对工具 allowlist 只有 `web_search`、`web_fetch`、
`tavily_search` 和 `tavily_extract`，并额外 deny 文件、shell、消息、浏览器、NAS probe 和跨 agent
工具。桥只有在 OpenClaw 确认至少完成一次允许的联网工具调用且零工具失败时才返回成功；任何未
调用搜索、调用越权工具或搜索失败都会返回结构化 502，由门户按既有策略回落本地 7B。模型和
agent 都在服务参数中固定，客户端请求不能更换。服务拒绝非回环地址绑定，限制请求和 prompt
大小，审计只返回 prompt hash、长度、联网工具名/次数和公开来源 URL，不记录 prompt 原文。

桥凭据保存在 `/home/sunrise/.config/digua/cloud_bridge_token`，部署时生成，权限必须为 `0600`。该凭据只保护门户到本机桥的调用，不是 MiniMax token。MiniMax token 继续由 root OpenClaw 配置管理，禁止写入仓库、systemd unit、报告或日志。

## 部署

1. 将 `scripts/probes/openclaw_cloud_inference_bridge.py` 同步到 `/mnt/nas/openclaw/scripts/probes/`。
2. 以 root 运行 `scripts/production/configure_openclaw_web_research_agent.sh`。脚本会先备份
   `/root/.openclaw/openclaw.json`，再创建或收敛 `web-research` agent、固定 MiniMax 模型并写入
   四项工具 allowlist；不输出 Tavily 或 MiniMax 凭据。设置 `RESTART_OPENCLAW_GATEWAY=1` 时才
   重启 root OpenClaw gateway。
3. 将 `configs/systemd/digua-openclaw-cloud-bridge.service` 安装到 `/etc/systemd/system/`。
4. 在 S100P 本机生成桥凭据并设置 `sunrise:sunrise`、`0600`，不要输出凭据内容。
5. 将 `configs/systemd/user/openclaw-gateway.service.d/30-minimax-cloud-overflow.conf` 安装到门户 user service 的同名 drop-in 目录。其内容为：

   ```ini
   Environment=AI_NAS_CLOUD_CHAT_URL=http://127.0.0.1:18082/v1
   Environment=AI_NAS_CLOUD_CHAT_MODEL=custom-gateway/MiniMax-M2.7
   Environment=AI_NAS_CLOUD_CHAT_TOKEN_FILE=/home/sunrise/.config/digua/cloud_bridge_token
   Environment=AI_NAS_CLOUD_CHAT_TIMEOUT_SECONDS=210
   ```

6. 先启动并检查 root bridge，再重启 `sunrise` 的门户 user service。

桥服务必须显式设置 `HOME=/root`，并将 OpenClaw 自带的 Node.js 22 目录放在 `PATH` 首位。systemd 的默认 PATH 可能命中系统 Node.js 20，届时 OpenClaw 会以版本不满足要求退出。OpenClaw CLI 会维护 `/root/.openclaw/state` 和隔离 agent 的 session 目录，因此沙箱只对这两个位置开放写权限；provider 配置、agent workspace 和桥脚本仍为只读。

门户的云端 HTTP 等待时间为 210 秒，比 bridge 的 180 秒推理上限更长，使 bridge 能返回明确的超时响应。门户 HTTP 客户端必须把底层 `TimeoutError` 转成结构化 `cloud_overflow_failed`，不能让浏览器连接被直接关闭。

## 验收

- `GET http://127.0.0.1:18082/health` 返回 `ok=true`，端口只监听 loopback。
- 未携带或携带错误桥凭据的 completion 请求返回 `401`。
- OpenClaw CLI 的 `web-research` agent 探针返回 `provider=custom-gateway`、`model=MiniMax-M2.7`，
  `toolSummary` 只包含允许的 search/extract 工具且 `failures=0`。
- 门户输入 `你是谁`：返回 `identity_answer_source=deterministic_local_identity`、`cloud_used=false`，OpenClaw bridge 无对应调用。
- 门户输入明确公开、复杂且需要最新外部信息的问题：返回
  `assistant_mode=cloud_overflow_chat`、`cloud_used=true`、`web_research.web_search_used=true`、
  `web_research.tool_calls>=1` 和公开来源 URL，回答来自 OpenClaw agent 联网检索与 MiniMax。
- 门户输入“联网搜索最新 AI 新闻”等短句：即使复杂度为 0，也必须记录
  `explicit_web_search=true` 并进入同一联网代理；普通简单对话仍保持本地。
- 含私有 NAS 内容或本地工具意图的请求仍留在本地，不允许通过 bridge。
- 公开复杂但不要求最新信息的请求使用本地 7B；同时需要本地数据和最新外部信息的请求标记为
  混合候选，但在安全拆分/脱敏/本地合并链路启用前保持本地。

## 回滚

1. 从门户 user service 移除三个 `AI_NAS_CLOUD_CHAT_*` 环境变量并重启门户；云端路径恢复为不发送请求的 `cloud_overflow_stub`。
2. `systemctl disable --now digua-openclaw-cloud-bridge.service`。
3. 保留 OpenClaw 既有 provider 配置，不改动 MiniMax token；必要时删除仅用于本机桥认证的 `cloud_bridge_token`。

回滚不会影响本地 Qwen、NAS 只读功能或 OpenClaw 根网关。

## 2026-07-18 生产验收

以下是当天早期单次 `infer` bridge 的历史基线；端口、transport 和调用方式以本文顶部调用链及
后文“OpenClaw 联网代理验收”为当前事实。

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

## 2026-07-18 OpenClaw 联网代理验收

- [PR #79](https://github.com/zhexuexiaotudou/-agent-s100-/pull/79) 将 bridge 从单次
  `openclaw infer model run` 改为隔离的 `openclaw agent --agent web-research` 工具循环；
  [PR #82](https://github.com/zhexuexiaotudou/-agent-s100-/pull/82) 修复 `OpenAI` 中的 `open`
  被误判为本地打开目录命令的问题。两个 PR 的必需 CI 均通过，合并后的完整本地回归为
  `243 passed, 11 subtests passed`，当前生产运行文件与 `940d0d75d4efc45f7da8c694575034042f4f5414`
  中的对应文件一致。
- OpenClaw 直接实机验收 run ID 为 `29acf6f3-5ac1-4f6e-bc04-a0e84380f1bc`；系统 prompt
  暴露给 `web-research` 的工具严格只有四项 allowlist，实际调用 `tavily_search` 和
  `tavily_extract` 共 4 次、失败 0 次，provider/model 为
  `custom-gateway/MiniMax-M2.7`。
- 真实认证 `/api/copilot/chat` 请求返回 `assistant_mode=cloud_overflow_chat`、
  `cloud_used=true`、`transport=openclaw_agent`、`agent=web-research`、
  `web_search_used=true`；一次验收共调用 5 次批准的联网工具、失败 0 次，并返回 4 个公开来源
  URL。对照请求“你是谁”和“列出 NAS 文件”分别保持 `local_qwen_chat` 与
  `local_storage_list`，两者均为 `cloud_used=false`。
- 实机浏览器通过 SSH loopback tunnel 打开 `/ui` 后完成同一公开时效性问题；页面显示真实回答，
  服务摘要显示 `custom-gateway/MiniMax-M2.7`，展开“处理与隐私信息”可见
  `OpenClaw 联网检索` 和“云端调用：已调用”。
- `digua-openclaw-cloud-bridge.service`、sunrise 门户 user service 和 root OpenClaw gateway
  均为 `active`。bridge、门户后端和前端 JS 的线上 SHA-256 分别为
  `abb1a7e5abc4414a80b4d285a53036d3349b62dbe913b6940958fe3473a5e18d`、
  `e4c7264bd36d1c7de2b37e3e0cda0f9f26ca5257d8034b7e15e940dcb793d3fa` 和
  `0c65d2d29a3c189aeaee3608eaa42b384395ef94702027703668ce83bb4aaaa6`。
- 运行文件回滚点为 `/mnt/nas/openclaw/backups/openclaw-web-search/20260718-074832` 和
  `/mnt/nas/openclaw/backups/openclaw-web-search/20260718-075750`；OpenClaw 配置回滚副本为
  `/root/.openclaw/backups/ai-nas-web-research/openclaw.json.20260718-074839`。

## 2026-07-18 短句联网路由修复验收

- 失败现象已复现：约 5 token 的明确联网短句被复杂度门槛判为 `local_only`，没有调用
  OpenClaw bridge，最终由本地 1.5B 返回“无法直接联网”的拒答。根因不是 MiniMax token 或
  Tavily 故障，而是 `copilot_policy_route()` 要求所有云端请求的复杂度至少为 2。
- [PR #84](https://github.com/zhexuexiaotudou/-agent-s100-/pull/84) 增加
  `explicit_web_search` 决策信号：公开、无隐私、无本地工具依赖、需要最新信息且用户未禁止联网时，
  明确的联网短句可以绕过复杂度下限，但不能绕过隐私、NAS、本地数据或禁止联网边界。合并提交为
  `f5940909066187dd77d386360b2536819679018a`。
- 本地完整回归为 `245 passed, 11 subtests passed`；PR 的 `offline-regression`、
  `startup-link-check-contract`、`static-ui-contract` 和 `test` 四项 CI 全部通过。
- S100P 真实认证 `/api/copilot/chat` 输入 `联网搜索最新AI新闻` 后返回
  `selected_route=CLOUD_MINIMAX`、`assistant_mode=cloud_overflow_chat`、
  `explicit_web_search=true`、`agent=web-research` 和 `web_search_used=true`；OpenClaw 实际调用
  `tavily_search` 2 次、失败 0 次，并返回 Reuters、AP、Washington Post 等公开来源 URL。
- 两个安全对照均保持本地：`联网搜索我的 NAS 最新文件` 进入本地多模态检索且
  `cloud_used=false`；`联网搜索最新AI新闻，但不要联网` 进入本地 1.5B 且
  `cloud_used=false`。
- 实机浏览器输入同一短句后显示联网回答、来源链接、`云端返回`、
  `custom-gateway/MiniMax-M2.7`、`OpenClaw 联网检索` 和“云端调用：已调用”。
- 部署后 `openclaw-gateway.service` 和 `digua-openclaw-cloud-bridge.service` 均为 `active`。
  门户后端和前端 JS 的线上 SHA-256 分别为
  `e3b379d530e86693d402808bd84f3355bfe14a021de0e07b28eeb12a157d507b` 和
  `46065cd057147bff99369e947728cc1a1b43b9283d253d8475e0d8149534ca98`；运行文件回滚点为
  `/mnt/nas/openclaw/backups/short-web-search-routing/20260718-082339`。
