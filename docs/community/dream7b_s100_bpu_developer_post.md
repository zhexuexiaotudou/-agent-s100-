# 在 S100 BPU 上部署 Dream7B：首个扩散语言模型端侧部署 skill

## 核心故事

这次工作把 Dream7B 部署到了 S100P 的 BPU 路径上，并通过本地 OpenAI 兼容网关接入 OpenClaw。它不是把一个普通自回归模型直接塞进现成 chat runtime，而是把扩散语言模型的执行特点拆开处理：权重和图编译走兼容 skeleton，HBM 在 BPU 上分段执行，扩散采样循环留在 host 侧调度。

最终形成的是一个低成本 AI-NAS 智能层：便宜 NAS 继续负责存储、RAID、备份和共享，S100P 常驻负责本地模型、隐私查询和受控工具调用，OpenClaw 把自然语言变成固定 allowlisted tool。所有文件操作都有 Markdown/JSON 报告，不自动删除、不移动源文件、不覆盖。

## 为什么有价值

- **扩散语言模型上 BPU**：Dream7B 不是官方 OELLM registry 原生支持的模型，部署链路本身有复用价值。
- **端侧隐私**：合同、发票、家庭照片、聊天截图等 query 先进入本地 Dream7B/路由策略，不直接发云。
- **省 token**：简单文件检索、摘要、分类和 NAS 本地问答在端侧完成，复杂非隐私任务才交给云端。
- **AI-NAS 产品化**：S100P 不是替代 NAS OS，而是给现有 NAS 增加本地智能层。

## 当前实测证据

S100P 默认服务：

- `dream7b-bpu-batch-queue.service`: active / enabled
- `Dream7B-S100P-local`: OpenAI 兼容网关可用
- latest BPU telemetry: `avg_bpu=93.014`, `failed_jobs=0`
- latest soak: `avg_bpu=93.037`, `failed_jobs=0`

Dream7B benchmark report:

```text
/mnt/nas/openclaw/reports/ai_nas_mvp/dream7b_perf_identity_20260618-120209-292585/dream7b_perf_identity.json
```

关键结果：

- model confirmed: `Dream7B-S100P-local`
- failed prompt cases: `0`
- self-introduction: `Hello! I'm Dream Dream7 model. How can I assist you today`
- TTFT 当前按非流式 first response byte 统计，是首响应上界，不是原生 SSE token streaming。

端云路由 report:

```text
/mnt/nas/openclaw/reports/ai_nas_mvp/edge_cloud_router_20260618-120517-950987/edge_cloud_router.json
```

路由结果：

- 简单 NAS 任务：local
- 隐私 NAS/照片/发票任务：local
- 非隐私复杂市场/故事任务：cloud dry-run
- `privacy_query_sent_to_cloud=false`

## Demo 三段式

1. **S100 常驻 gateway**
   - 展示 Dream7B queue、Dream7B OpenAI gateway、OpenClaw gateway、AI-NAS index daemon。
   - 重点是 active/enabled、health endpoint、restart policy、recovery drill。

2. **S100 + OpenClaw AI-NAS**
   - 查找 2024 装修合同/发票/聊天截图。
   - 生成 case packet、folder RAG、重复文件报告。
   - 整理电影只复制，不删除、不移动、不覆盖。

3. **端 + 云**
   - 所有 query 先进入本地路由。
   - 简单任务和隐私任务留端侧。
   - 非隐私复杂任务才进入云端，并且第一版默认 dry-run。

## 复现入口

```bash
python3 scripts/probes/dream7b_perf_identity_probe.py --base-url http://127.0.0.1:18888
python3 scripts/probes/ai_nas_edge_cloud_router_probe.py
python3 scripts/probes/ai_nas_appliance_experience_acceptance_probe.py
```

Skill package:

```text
docs/community/dream7b-s100-bpu-deploy/SKILL.md
```

## 表述边界

- 不宣称持续 100% 平均 BPU。
- 不把非流式 TTFT 写成原生 token streaming。
- 不说 Dream7B 已被官方 SDK 原生支持。
- 不承诺自动删除、自动移动或覆盖 NAS 文件。
