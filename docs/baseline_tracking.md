# Baseline Tracking

本文把 baseline 拆成 Codex 可跟踪的任务。每个任务都应开 GitHub issue，或者至少在本文中更新状态。

状态定义：

| 状态 | 含义 |
| --- | --- |
| `todo` | 尚未开始 |
| `doing` | 正在实机验证 |
| `blocked` | 被硬件、网络、权限或依赖阻塞 |
| `verified` | 已通过验收并有证据 |
| `dropped` | 明确不进当前 baseline |

## Epic A：S100P PC Parity

| ID | 标题 | 状态 | DoD |
| --- | --- | --- | --- |
| A-001 | S100P 硬件/系统盘点 | verified | 记录 Ubuntu、kernel、架构、磁盘、网络、Node/npm、OpenClaw 状态 |
| A-002 | RDK Studio 部署 OpenClaw Gateway | verified | Gateway 可启动，Control UI 可访问，重启后恢复 |
| A-003 | NAS workspace 挂载到 S100P | todo | S100P 可读写 NAS，重启后自动挂载 |
| A-004 | WebChat/Telegram smoke test | todo | 消息能触发命令并返回状态 |
| A-005 | 工具执行 allowlist | todo | 只允许执行 `scripts/` 下白名单脚本 |
| A-006 | Docker / sandbox 验证 | todo | 非主会话不能写宿主机敏感路径 |
| A-007 | Browser automation smoke test | todo | 能打开测试网页、截图、保存到 NAS |
| A-008 | ROS2 status 工具 | todo | OpenClaw 能查询 ROS2 node/topic/service |
| A-009 | ROS bag 采集工具 | todo | 聊天命令能开始/停止采集，并写入 NAS |
| A-010 | 7x24 稳定性测试 | todo | 连续运行 7 天，记录重启、内存、磁盘、日志 |

## Epic B：AI NAS Homework

| ID | 标题 | 状态 | DoD |
| --- | --- | --- | --- |
| B-001 | NAS 资料库目录规范 | verified | Personal root、受控测试文件、搜索和下载链路已进入 gate；每次换真实部署仍需重新确认挂载和 ACL |
| B-002 | 文档索引和摘要 | verified | SQLite/FTS、embedding search、folder RAG、OCR bridge 和证据合同已有 bounded gate |
| B-003 | 图片 caption / 语义搜索 baseline | doing | EXIF/GPS、标签、pHash、local visual embedding 和粗粒度照片搜索已通过；细粒度服装/属性搜索仍是下一步 |
| B-004 | 机器人数据集 card | todo | 每次采集自动生成 dataset card |
| B-005 | 日志分析助手 | doing | ops/report 证据已有 gate；面向用户的日志助手仍需单独产品化 |
| B-006 | GitHub/Codex workflow | doing | 当前 repo 已作为进展沉淀入口；issue -> branch -> PR 全链路仍需固定脚本和验收 |
| B-007 | 周报/实验报告生成 | doing | folder summary 和 scheduled dry-run 已接入 AI-NAS 规则；周报模板仍需补齐 |
| B-008 | Home Assistant / 设备只读状态 | todo | 只查询状态，不做控制 |
| B-009 | 低风险自动化控制 | doing | non-destructive schedule dry-run 和 action approval/rollback 思路已形成；真实控制动作仍需白名单和确认 |
| B-010 | 安全审计清单 | verified | ACL/permission-aware search、allowlist governance、privacy boundary 已作为 AI-NAS gate 约束；部署前仍需现场复查 token、端口和共享权限 |

### 2026-06-24 AI-NAS 扩展项

| ID | 标题 | 状态 | DoD |
| --- | --- | --- | --- |
| B-011 | 真实 Personal root 集成 | verified | 受控真实测试文件、索引刷新、搜索、下载链路通过 gate |
| B-012 | 官方 S100P PP-OCR 文档桥接 | verified | 扫描图片/PDF OCR 写回 `ocr_results` 和文档索引，生产 readiness blocker 清零 |
| B-013 | 用户可见定时整理规则 | verified | Web 控制台可创建、启停、dry-run `index_refresh`、`duplicate_report`、`folder_summary` |
| B-014 | 媒体库增强 | verified | 电影标题/年份/季集、字幕/海报 sidecar、播放器链接可显示；不宣称实时转码替代 |
| B-015 | PWA / 移动 Web 入口 | verified | manifest、icon、service worker、移动页面结构、登录/上传/搜索/聊天/媒体链接 gate 通过 |
| B-016 | 细粒度视觉属性搜索 | todo | 新增 region-level person/clothing/object 属性索引，支持“找穿白色上衣的照片”并通过 ACL 泄漏 gate |

## 当前最近事实

- Windows 共享网络已使 S100P 通过 `192.168.137.10` 上网。
- S100P 已手动安装 Node.js `v20.19.2` arm64 tarball，并修正 `/usr/bin/node` 链接后 `node -v` 成功。
- RDK Studio 已通过 `root@192.168.137.10:22` 重新连接 S100P。
- RDK Studio 页面已显示 OpenClaw 部署成功。
- 实战记录见 `docs/04_openclaw_windows_ics_deploy.md`。
- AI-NAS 十个 goal 已在 Digua 工作区闭环，最新整理见 `docs/ai_nas_progress_2026-06-24.md`。
- 当前最重要的新增缺口不是普通文件搜索，而是细粒度图像语义和 embedding：例如“找穿白色上衣的照片”需要 region-level clothing attributes，而不能只用整图白色程度。

## Codex 每次更新 issue 时应补充

- 当前板端 IP。
- 当前执行用户。
- 是否使用 Windows ICS 共享网络。
- OpenClaw 页面状态截图。
- 关键命令输出。
- 失败日志路径。
- 是否需要 GPT Pro 复审。
