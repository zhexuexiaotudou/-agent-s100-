# GPT Pro 交接模板

本仓库默认由 Codex 执行和记录。GPT Pro 用于阶段性架构判断、方案对比和高层复审。

使用方式：

1. Codex 先执行实机操作并收集证据。
2. Codex 把问题压缩成一个 Pro prompt。
3. 用户把 prompt 喂给 GPT Pro。
4. GPT Pro 输出建议。
5. Codex 只采纳可验证、可落地的部分，并写入 repo。

## Prompt 1：阶段性架构复审

```text
我在做一个 S100P + TS-264C NAS + OpenClaw baseline。

当前定位：
- S100P：OpenClaw 主 Gateway、机器人上位机、ROS2/传感器/边缘 AI 工具节点。
- TS-264C NAS：workspace、memory、logs、数据集、备份、快照。
- PC：Codex 工作站和可选 heavy worker，不作为最终 7x24 主机依赖。

当前已验证事实：
<粘贴 Codex 给出的硬件、网络、OpenClaw、NAS、ROS2 证据>

当前阻塞：
<粘贴错误、日志、截图文字>

请从专业角度复审：
1. 当前 baseline 是否合理。
2. 哪些任务应该提前，哪些应推迟。
3. 哪些功能不应该让 S100P 承担。
4. NAS 权限和安全边界是否足够。
5. 下一批 GitHub issue 应该怎么拆。

请输出：
- 结论。
- 高风险点。
- 下一步优先级。
- 可直接放入 GitHub issue 的任务清单。
```

## Prompt 2：PC parity 复审

```text
我想验证 S100P 能否实现 PC 上 OpenClaw 的类似效果。

当前 PC OpenClaw 对照能力：
<列出 PC 上能做的功能>

当前 S100P 实测能力：
<列出 Codex 已验证功能和失败功能>

限制：
- 不承诺完整替代 x86 PC。
- 第一版不跑本地大模型。
- 不暴露 Gateway 到公网。
- NAS 只开放专用 workspace。

请帮我把能力分成：
P0：必须完成。
P1：逐项验证。
P2：S100P 机器人差异化价值。
Out of scope：不该第一版做。

每项请给出验收标准。
```

## Prompt 3：AI NAS 作业复刻

```text
我有 S100P + QNAP TS-264C，想复刻高价位 AI NAS / OpenClaw NAS 的产品功能层，不追求同等硬件。

目标：
- NAS 做私有数据中心。
- S100P 做 OpenClaw Gateway 和机器人边缘节点。
- Codex 跟踪 issue、PR、文档和验证。

请帮我从 AI NAS 产品角度拆解：
1. 哪些功能最值得抄。
2. 每个功能用 S100P + NAS 如何实现。
3. 验收标准是什么。
4. 哪些功能需要云 LLM/API，哪些可以本地完成。
5. 哪些功能存在安全风险。

请输出一个可放入 `docs/baseline_tracking.md` 的任务表。
```

## Prompt 4：安全模型复审

```text
请复审我的 OpenClaw + S100P + NAS 安全模型。

当前设计：
- Gateway 只在 LAN/Tailscale 内可访问。
- NAS 只给 OpenClaw 一个专用 workspace。
- 工具执行使用 allowlist。
- 机器人控制动作需要白名单和二次确认。
- token 不写入 Git。

当前实际配置：
<粘贴 Codex 收集到的端口、服务、共享路径、用户权限>

请找出：
1. 最大的数据泄露风险。
2. 最大的误操作风险。
3. 最小权限应如何落地。
4. 哪些检查应该写成脚本。
5. 哪些事项必须进入 GitHub issue 的验收标准。
```

## Codex 采纳规则

GPT Pro 的输出不能直接替代实测。Codex 应按以下规则处理：

- 如果建议涉及命令、端口、版本、硬件能力，先验证再写成事实。
- 如果建议只是架构判断，可以写入 `docs/`，但标记为 baseline 假设。
- 如果建议涉及安全权限，默认采取更保守方案。
- 如果建议扩大 scope，必须新开 `experiment`，不要塞进第一版 baseline。
