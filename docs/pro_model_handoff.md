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

## Prompt 5：AI-NAS 图像识别和 embedding 升级

完整上下文见
[`docs/ai_nas_visual_search_embedding_handoff.md`](ai_nas_visual_search_embedding_handoff.md)。

```text
你是一个资深本地 AI-NAS 产品架构师、视觉检索/向量数据库工程师。请为我的 Digua / AI-NAS 项目设计一套可落地的“自然语言搜图 + 图像识别 + 数据库 embedding”升级方案，目标是让用户输入“找穿白色上衣的照片”“白色 T 恤的人”“white shirt photo”这类查询时，系统能在 NAS 照片库中返回正确照片、缩略图、路径、证据和置信度。

项目背景：
- 项目形态是“低成本 NAS + S100P 本地 AI 层 + OpenClaw 控制层 + Web NAS OS 门户”。
- 当前已有 SQLite 索引、文件搜索、文档 embedding、OCR、照片基础 metadata、EXIF/GPS、pHash、local visual embedding fallback、照片语义搜索原型。
- 当前缺陷是图像 embedding 主要仍是整图/metadata/标签级别，无法可靠区分白色上衣、白车、白墙、白文件和白色背景。
- 必须优先本地/离线，不默认上传私人照片到云端。
- Web、API、AI 检索必须共享同一套 ACL/visible-paths 权限模型。
- 默认不做人脸识别、不做人脸聚类、不识别具体身份；只允许 generic person、衣服颜色、物体、场景等非身份属性。
- 每个结果必须返回 evidence：source path/source id、thumbnail/open URL、模型/运行时、命中的属性、置信度、生成的 embedding/检测 artifact 路径、隐私分类和降级原因。

请输出：
1. 为什么现有 local visual embedding / metadata 搜索不能解决“穿白色上衣”。
2. 离线索引 pipeline 和查询 pipeline。
3. 快速 MVP 与高质量生产方案的模型选择。
4. SQLite/向量索引 schema，包括 image embeddings、regions、attributes、captions/artifacts、ACL scope、model/runtime versioning 和 orphan cleanup。
5. “穿白色上衣”的专项实现：先检测 person/upper-body/clothing region，再判断 clothing color，排除 white car/wall/document/background。
6. API/UI 改造和 OpenClaw/Qwen 聊天路由。
7. 权限和隐私规则。
8. gate 设计：ai_nas_image_attribute_index_gate、ai_nas_semantic_image_search_gate、ai_nas_visual_acl_leakage_gate、ai_nas_visual_search_portal_gate。
9. MVP、可用版、生产强化版三阶段实施 checklist。
```

## Codex 采纳规则

GPT Pro 的输出不能直接替代实测。Codex 应按以下规则处理：

- 如果建议涉及命令、端口、版本、硬件能力，先验证再写成事实。
- 如果建议只是架构判断，可以写入 `docs/`，但标记为 baseline 假设。
- 如果建议涉及安全权限，默认采取更保守方案。
- 如果建议扩大 scope，必须新开 `experiment`，不要塞进第一版 baseline。
