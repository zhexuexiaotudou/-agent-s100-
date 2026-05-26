# OpenClaw + S100P + TS-264C Baseline

本文定义两个 baseline 方向：

- Baseline A：S100P 是否能实现 PC 上 OpenClaw 的类似效果。
- Baseline B：高价位 AI NAS / OpenClaw NAS 常见能力，如何用 S100P + TS-264C 抄产品作业。

核心定位：

| 组件 | 推荐角色 | 不推荐第一版承担 |
| --- | --- | --- |
| S100P | OpenClaw 主 Gateway、机器人上位机、ROS2/传感器/边缘 AI 工具节点 | 完整替代 x86 PC、本地大模型主力、重浏览器自动化 |
| TS-264C NAS | workspace、memory、logs、数据集、备份、快照、轻量 sidecar 服务 | 高端 AI NAS 或本地大模型主力 |
| PC | 初期对照组、Codex 工作站、重浏览器和重依赖 worker | 最终 7x24 主机依赖 |

## Baseline A：S100P PC Parity

判定口径不是“S100P 是否等于 PC”，而是三层能力：

| 层级 | PC OpenClaw 常见能力 | S100P 目标 |
| --- | --- | --- |
| Gateway / Chat / 控制面 | Gateway、Web UI、消息入口、配置 | 必须完成 |
| 工具执行面 | shell、文件、Git、Python、定时任务、轻浏览器 | 分项验证 |
| 本地 AI 推理面 | LLM、VLM、embedding、本地私有化 | 第一版不承诺 |

### A 侧功能 baseline

| 编号 | 功能 | S100P 做什么 | NAS 做什么 | 验收标准 |
| --- | --- | --- | --- | --- |
| A1 | OpenClaw Gateway 常驻 | 运行 Gateway，支持重启恢复 | 保存配置备份 | 重启 S100P 后 2 分钟内恢复 |
| A2 | Control UI 可用 | 只在 LAN/Tailscale 内暴露 UI | 保存配置快照 | 浏览器可打开 UI 并完成认证 |
| A3 | WebChat 或 Telegram 首通 | 接收消息并回传执行结果 | 保存会话日志 | 手机或浏览器能触发简单命令 |
| A4 | NAS workspace 挂载 | 挂载 `/mnt/nas/openclaw` | 提供专用共享和快照 | 重启后可读写，权限稳定 |
| A5 | 基础工具执行 | shell、Python、Git、curl、jq | 存放输出文件 | 聊天触发脚本，产物写回 NAS |
| A6 | 工具 allowlist | 只允许白名单脚本 | 保存审计日志 | 非白名单命令被拒绝 |
| A7 | 浏览器 smoke test | 轻量 Playwright 或替代方案 | 存截图和报告 | 能打开测试网页并截图 |
| A8 | ROS2 status 工具 | 查询 ROS2 node/topic/service | 保存状态报告 | 聊天命令返回 ROS2 状态 |
| A9 | ROS bag / 数据采集 | 启停采集脚本 | 存 bag、图像、日志 | 每次任务生成数据目录和 metadata |
| A10 | 安全 baseline | Gateway 内网化、token 最小化 | NAS 最小共享 | 外网不可直接访问 Gateway |

### PC parity 分级

| 等级 | 目标 | S100P 目标状态 |
| --- | --- | --- |
| P0：能用 | Gateway、聊天入口、文件读写、简单脚本 | 必须完成 |
| P1：像 PC | Git、浏览器、文档处理、定时任务、NAS 资料操作 | 逐项验证 |
| P2：比 PC 更适合机器人 | ROS2、传感器、bag、SLAM、BPU 推理 | 差异化价值 |

第一版结论目标：S100P 不做 PC 全功能复制，而做“PC OpenClaw 的核心自动化能力 + PC 不擅长的机器人边缘能力”。

## Baseline B：AI NAS Homework

高价位 AI NAS 的产品叙事通常不是单纯存文件，而是本地资料库、语义检索、智能整理、工作流自动化和私有数据闭环。我们不先抄昂贵硬件和本地大模型，先抄功能层。

| 编号 | AI NAS 作业 | S100P + TS-264C 实现方式 | 验收标准 |
| --- | --- | --- | --- |
| B1 | 私有资料库问答 | NAS 存文档，OpenClaw 管索引和摘要 | 能回答 NAS 指定目录近期内容 |
| B2 | 语义照片搜索 | NAS 存照片，S100P/云 API 生成 caption | 文本能返回相关图片路径 |
| B3 | 视频/图像整理 | S100P 采集，ffmpeg 抽帧，NAS 归档 | 自动按日期和任务 ID 归档 |
| B4 | 机器人数据集管家 | S100P 采集 ROS bag、图像、雷达 | 自动生成 dataset card |
| B5 | 日志分析助手 | 读取 NAS 日志目录 | 输出失败摘要、关键错误和复现命令 |
| B6 | GitHub / Codex 开发助手 | issue -> branch -> PR -> review | 一条任务能形成 PR 证据链 |
| B7 | 周报/实验报告 | 汇总日志、数据集和 issue | 自动生成 Markdown 周报 |
| B8 | Home Assistant 只读状态 | 先只读设备状态 | 不执行控制动作 |
| B9 | 低风险自动控制 | 白名单 + 二次确认 | 控制动作有审计日志 |
| B10 | 多 agent / 多节点 | S100P robot agent，NAS storage agent，PC heavy worker | 每个节点权限和 workspace 分离 |

## 最小可行 baseline

目标：

1. S100P 作为 OpenClaw 主上位机。
2. TS-264C 作为持久化 workspace 和数据仓库。
3. PC 只作为开发工作站和可选 heavy worker。
4. 打通消息入口、Gateway 常驻、NAS 读写、基础脚本、ROS2 状态查询和数据归档。

非目标：

1. 不承诺完整替代 x86 PC。
2. 不在第一版跑本地大模型。
3. 不暴露 Gateway 到公网。
4. 不允许 agent 访问整个 NAS。
5. 不允许未白名单机器人控制动作。

## 推荐落地顺序

### 第 1 阶段：能跑

1. RDK Studio 成功部署 OpenClaw。
2. Gateway 常驻并可重启恢复。
3. Control UI 只在 LAN 或 Tailscale 内访问。
4. NAS 建专用共享 `/OpenClawWorkspace`。
5. S100P 挂载 NAS 到 `/mnt/nas/openclaw`。
6. WebChat 或 Telegram smoke test 通过。
7. 日志写入 NAS。

### 第 2 阶段：像 PC

1. 文件读写。
2. Git 操作。
3. Python 脚本。
4. 轻量浏览器自动化。
5. NAS 文档摘要。
6. GitHub/Codex PR review。

### 第 3 阶段：机器人差异化

1. ROS2 状态查询。
2. 传感器快照。
3. ROS bag 采集。
4. SLAM demo 或地图生成。
5. 数据自动归档到 NAS。
6. 自动生成实验报告。

### 第 4 阶段：AI NAS 产品功能

1. NAS 文档问答。
2. 图片/视频语义搜索。
3. 日志自动诊断。
4. 周报/实验报告。
5. 多 agent 分工。

## 参考入口

- D-Robotics RDK S100/S100P 文档：https://developer.d-robotics.cc/en/rdks100
- OpenClaw 文档：https://docs.openclaw.ai/
- QNAP TS-264C 产品页：https://www.qnap.com.cn/zh-cn/product/ts-264c
