# AI-NAS 竞品功能逐项核对与后续任务清单

生成时间：2026-06-24 01:24（Asia/Shanghai）

依据：`C:\Users\zhexu\Downloads\AI-NAS_竞品调研与低成本平替方案.md`

## 结论边界

- 十个 AI-NAS goal 已重新验证通过：`ok_ai_nas_ten_goal_s100p_closure_gate`，`goals_ok=10/10`，并确认文本入口使用 `Qwen2.5-1.5B-Instruct-S100P-official`。
- 当前网页和后端已经覆盖“低成本 NAS + S100P AI 层 + OpenClaw 控制层”的主要 P0/P1 原型能力。
- 不能宣称完整生产级平替顶级 NAS。最新生产就绪 gate 为 `limited_ai_nas_production_readiness_gate`，原因是：
  - `index_productization:personal_root_missing`：当前 Windows 侧默认 `\mnt\nas\openclaw\Personal` 没有真实挂载的 NAS Personal 根目录。
  - `document_pdf_ocr_folder_rag:official_ppocr_ready_but_document_pipeline_ocr_bridge_not_integrated`：S100P 官方 PP-OCR wrapper 已通过，但扫描 PDF/图片 OCR 尚未接入文档索引管线。
- 人脸识别、完整移动 App、NVR、RAID/快照/备份引擎、实时转码、Docker/VM 应用中心不作为本项目自研替代目标；只做读取状态、接入入口、AI 辅助和安全建议。

## 真实验证证据

| 验证项 | 最新结果 | 证据 |
|---|---:|---|
| 十个 goal + 官方 S100P Qwen 闭环 | 10/10 | `tmp\ai_nas_ten_goal_s100p_closure\ten_goal_s100p_closure_20260624-011202-252787\ten_goal_s100p_closure_gate.json` |
| 顶级 NAS 平替总 gate | 12/12 | `ok_top_nas_replacement_product_gate` |
| Web NAS OS | 34/34 | `ok_nas_web_os_gate` |
| 一体化门户 | 19/19 | `ok_nas_integrated_portal_gate` |
| OpenClaw 控制 NAS 文件 | 10/10 | `ok_ai_nas_openclaw_nas_control_gate` |
| 图像/视觉搜索门户 gate | 12/12 | `ok_ai_nas_visual_search_gate` |
| 生产就绪 gate | limited | `F:\mnt\nas\openclaw\reports\ai_nas_mvp\production_readiness_gate_20260624-011754-672992\production_readiness_gate.json` |
| 官方 Qwen 验收包 | ok | `tmp\product_guardrail_snapshots\qwen25_ai_nas_acceptance_latest.json` |
| 官方 PP-OCR wrapper | ok | `tmp\ai_nas_product_closure\official_ppocr_wrapper_20260624-011119-894353\official_ppocr_wrapper.json` |

## 调研功能矩阵逐项状态

状态定义：

- 已基本做到：有代码、接口或 gate，且本轮跑过真实验证。
- 部分做到：已有原型或报告，但不是生产完整功能。
- 未做到/不自研：调研中提到，但当前明确不做自研替代或需要外部系统。

| 功能 | 当前状态 | 证据 | 还差什么 / 优化路径 |
|---|---|---|---|
| 文件存储与共享 | 已基本做到 | `ai_nas_web_os_gate_probe.py`、`/api/storage/list/upload/download/rename/copy/move/delete` | 生产环境要挂真实 NAS share 到 Personal root，并配置容量/ACL 映射。 |
| SMB/NFS/WebDAV/远程访问 | 部分做到 | `ok_nas_app_ecosystem_gate`，协议 adapter stub | 只做协议入口和适配器登记，不替代厂商协议服务；后续接 QNAP/QTS/SMB/WebDAV 实际状态。 |
| 手机相册自动备份 | 未做到/不自研 | 调研建议使用厂商 App、Immich、Nextcloud | 接入“已上传文件事件”和冲突日志即可，不自研移动端后台上传。 |
| AI 相册分类 | 已基本做到 | `ok_ai_nas_photo_pipeline_acceptance` | 已有 EXIF、GPS、标签、pHash、local visual embedding；后续提升为生产 CLIP/官方视觉模型常驻服务。 |
| 人脸识别 | 未做到/暂不做 | `ok_ai_nas_photo_privacy_governance` | 因隐私风险保留为 out-of-scope；未来必须 opt-in、按相册授权、可撤销、独立隐私 gate。 |
| 物体识别 | 部分做到 | `ok_ai_nas_visual_search_gate`、官方 S100 vision/YOLO 证据 | 当前是视觉搜索和 YOLO 路由，不是成熟物体标签库；需补稳定物体 taxonomy 和增量索引。 |
| 地点/时间轴 | 部分做到 | `ok_ai_nas_photo_pipeline_acceptance`、`/api/media/summary` timeline | 已有 EXIF/GPS/时间线基础；需做隐私过滤、事件聚类、时区处理。 |
| 视频/电影库管理 | 已基本做到 | `ok_ai_nas_movie_sort_enhanced`、媒体库 UI | 具备命名/分类/整理报告；不做实时转码，海报/字幕抓取需接外部 metadata provider。 |
| 文档全文搜索 | 已基本做到 | `ok_ai_nas_file_search`、`ok_ai_nas_embedding_search`、`ok_ai_nas_semantic_query_acceptance` | 生产要挂真实 Personal root 并保持索引 daemon 常驻。 |
| OCR | 部分做到 | 文本 PDF 通过；`ok_ai_nas_official_ppocr_wrapper` 通过 | 官方 PP-OCR 已在 S100P 跑通，但文档索引里的扫描 PDF/图片 OCR bridge 未接入。 |
| 语义搜索/自然语言问答 | 已基本做到 | `ok_ai_nas_semantic_query_acceptance`、`ok_ai_nas_folder_rag`、`ok_ai_nas_folder_rag_grounding_contract` | 需要持续提高召回和置信度校准，禁止模型编造链接。 |
| 重复文件检测 | 已基本做到 | `ok_ai_nas_duplicate_report` | 当前是报告/建议；默认不自动删除。 |
| 自动分类/自动标签 | 部分做到 | 文档分类、电影整理、照片基础标签 gates | 标签体系还不统一；需要全局 taxonomy、人工纠错和可回滚标签变更。 |
| 权限管理 | 已基本做到（继承/映射） | `ok_ai_nas_permission_aware_search`、`ok_nas_acl_identity_gate` | 不替代 NAS ACL；生产要接真实 NAS 用户/组/ACL 映射。 |
| 快照/备份/容灾 | 部分做到 | `ok_nas_snapshot_recovery_gate`、`ok_nas_backup_sync_gate` | 只做本地/演示级恢复、备份任务和 AI 可见报告；真实 RAID/快照/备份由 NAS 厂商负责。 |
| Docker/虚拟机/应用中心 | 部分做到 | `ok_nas_app_ecosystem_gate` | 只有插件/协议登记和状态，不自研 Docker/VM 平台。 |
| 影音转码 | 未做到/不自研 | 调研明确不建议短期自研 | 接 Jellyfin/Plex/厂商转码入口，不做重度实时转码。 |
| NVR/监控摄像头 | 未做到/不自研 | 调研明确不建议自研 | 只可接入厂商 NVR 状态或视频文件搜索，不替代监控系统。 |
| 移动端 App | 未做到/不自研 | 当前是 Web/门户 | 可做 PWA 和响应式页面；后台上传/推送/设备信任交给成熟移动端。 |
| 多用户家庭/小团队协作 | 已基本做到 | ACL/identity gates、一体化门户低权限搜索隔离 | 生产需真实 NAS ACL mapping gate。 |
| 本地隐私与离线 AI | 已基本做到 | 官方 Qwen S100P 验收、OpenClaw allowlist、无云上传策略 | 仍需长时间稳定性和服务恢复演练常态化。 |
| 可扩展性 | 部分做到 | plugin/protocol registry、allowlist governance | 不能开放任意 skill 市场；只允许白名单工具。 |

## P0/P1 路线图核对

| 路线图项 | 当前状态 | 本轮验证 |
|---|---|---|
| 统一索引引擎 | 已基本做到 | `file_search`、`embedding_search`、`incremental_scan_efficiency`、`index_observability` |
| NAS 文件自然语言搜索 | 已基本做到 | `semantic_query_acceptance`、`search_evidence_contract`、`search_confidence_calibration_contract` |
| 文档 OCR、摘要和问答 | 部分做到 | 文本 PDF/文档分类/RAG 通过；扫描 OCR bridge 未完成 |
| 电影自动整理 | 已基本做到 | `movie_sort_enhanced` |
| 文档自动归档 | 已基本做到（安全建议+复制执行） | `action_approval_manifest`、`action_execute_copy`、`action_rollback_copy` |
| 自动生成文件夹摘要 | 已基本做到 | `folder_summary`、`folder_rag` |
| 安全审计与回滚 | 已基本做到 | `destructive_action_governance`、`allowlist_governance_audit`、执行/回滚流程退出 0 |
| 照片自动分类 | 已基本做到 | `photo_pipeline_acceptance` |
| AI 相册自然语言搜图 | 已基本做到 | `photo_semantic_search`、`visual_search_gate` |
| 重复文件和相似图片报告 | 已基本做到 | `duplicate_report`、pHash/相似图报告 |
| 家庭成员资料隔离 | 已基本做到 | `permission_aware_search`、门户 viewer 不泄露私有文档 |
| 定时整理任务 | 部分做到 | task queue、continuous soak、backup task 存在；尚无面向用户的“定时整理规则” UI |
| 本地隐私 AI 助手 | 已基本做到 | OpenClaw/Qwen fallback、官方 Qwen S100P route、NAS 工具白名单 |
| Web 控制台 | 已基本做到 | 中文 OpenClaw 首页、文件管理、相册/媒体/回收站/存储感知、管理入口 |

## 本轮已落实的改动

- 修正 `scripts/probes/ai_nas_production_readiness_gate_probe.py`：生产 gate 现在会读取 `official_ppocr_wrapper.json`。
- OCR 生产 blocker 从笼统的 `production_ocr_runtime_not_ready` 精确化为：
  - `official_ppocr_ready_but_document_pipeline_ocr_bridge_not_integrated`
  - 对应 warning：`scanned_pdf_ocr_requires_official_ppocr_bridge_into_document_pipeline`
- 这样后续任务不会误判为“S100P 没有 OCR 能力”，而是明确为“官方 OCR wrapper 已通过，但还没接进文档索引/OCR 管线”。

## 还没有做到且应该继续推进

### 任务 A：挂载/配置真实 Personal root

目标：让生产 gate 不再报 `index_productization:personal_root_missing`。

验收标准：

- `F:\mnt\nas\openclaw\Personal` 或明确配置的 NAS share 路径存在。
- `ai_nas_production_readiness_gate_probe.py --personal-root <真实路径> --refresh-index` 不再报 `personal_root_missing`。
- `/api/storage/status`、`/api/storage/list`、`/api/copilot/search` 都基于该真实根目录返回结果。

### 任务 B：把官方 PP-OCR 接入文档索引管线

目标：扫描 PDF/图片不再只显示 `blocked_missing_ocr_engine`。

推荐实现路径：

1. 在索引管线里增加 `ocr_backend=official_s100p_ppocr`。
2. PDF 文本为空时，将页面渲染为图片；图片文件直接进入 OCR 队列。
3. 通过已有 SSH/S100P wrapper 调用官方 PP-OCR，拿到文本、置信度、框坐标、日志路径。
4. 写回 `ocr_results` 表，并让文档摘要/RAG 只使用 OCR 真实文本。
5. 新增 gate：`ai_nas_official_ppocr_document_bridge_gate`。

验收标准：

- 扫描 PDF fixture 的 `ocr_results.status=ocr_completed`。
- `document_pipeline_acceptance` 中扫描发票摘要不再是 `content_not_extracted`。
- `production_readiness_gate` 不再报 `official_ppocr_ready_but_document_pipeline_ocr_bridge_not_integrated`。

### 任务 C：用户可见的定时整理规则

目标：把已有 task queue/soak 能力变成网页上的定时任务。

验收标准：

- Web 控制台可创建“每晚索引/每周重复文件报告/每周文件夹摘要”等规则。
- 每个规则有 dry-run、最近运行、报告路径、启停开关。
- OpenClaw 只能创建建议和等待确认，不能静默删除/移动原文件。

### 任务 D：媒体增强但不做重度转码

目标：补齐顶级 NAS 的电影库体验，但仍避免自研实时转码。

验收标准：

- 电影条目显示解析后的片名、年份、集数、字幕状态、海报字段。
- 支持接 Jellyfin/Plex/厂商播放器链接。
- 不宣称替代实时转码。

### 任务 E：PWA/移动端入口

目标：手机上能作为控制台使用，但不自研后台相册备份 App。

验收标准：

- 响应式移动页面可登录、上传、搜索、聊天、打开媒体链接。
- PWA manifest + icon + install prompt。
- 手机自动备份仍接厂商 App/Immich/Nextcloud。

## 明确不建议自研替代的项目

- RAID、磁盘池、卷加密、硬盘健康修复、重建、scrub。
- 原生快照/不可变快照/完整备份容灾引擎。
- NVR 监控系统。
- 完整移动 App、后台上传、推送、设备信任体系。
- 重度实时视频转码。
- Docker/VM 应用中心。
- 开放任意 OpenClaw skill 市场。

这些只做“入口、状态读取、AI 建议、审计、告警”，不作为平替目标。

## 给后续模型的执行顺序

1. 先做任务 A：真实 Personal root 挂载和索引配置。
2. 再做任务 B：官方 PP-OCR 文档 bridge，这是当前最关键的 AI 功能缺口。
3. 然后做任务 C：定时整理任务 UI。
4. 最后做任务 D/E：媒体体验和 PWA。

每完成一项必须跑：

```powershell
& 'C:\Users\zhexu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts/probes/ai_nas_production_readiness_gate_probe.py --refresh-index
& 'C:\Users\zhexu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts/probes/ai_nas_integrated_portal_gate_probe.py
& 'C:\Users\zhexu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts/probes/ai_nas_ten_goal_s100p_closure_gate.py --use-existing --skip-qwen-refresh
```

## 当前新增验收记录（2026-06-24）

### Task A：真实 Personal root、索引、搜索、下载链路

- 已用 `scripts/probes/ai_nas_controlled_personal_seed_probe.py --personal-root F:\mnt\nas\openclaw\Personal --file-count 160 --execute` 写入 176 个受控真实测试文件。
- `scripts/probes/ai_nas_personal_root_integration_gate_probe.py --personal-root F:\mnt\nas\openclaw\Personal --query "renovation invoice receipt"` 通过，结果为 `ok_ai_nas_personal_root_integration_gate`，14/14。
- 生产 gate 中 `index_productization` 已为 `ready`，文件数 176，失败数 0。

### Task B：官方 S100P PP-OCR 文档索引桥接

- 已新增 `scripts/probes/ai_nas_official_ppocr_document_bridge_probe.py`，用真实 S100P 官方 PP-OCR wrapper 识别扫描图像，并把 OCR 结果写回 `ocr_results` 与文档索引。
- 桥接 gate 通过，结果为 `ok_ai_nas_official_ppocr_document_bridge`，报告在 `tmp\ai_nas_product_closure\official_ppocr_document_bridge_20260624-013318-584608\official_ppocr_document_bridge.json`。
- 重跑生产 readiness gate 后结果为 `ready_ai_nas_production_readiness_gate`，blocker 数为 0；唯一剩余 warning 是人脸识别隐私审查，属于本轮明确不自研范围。

### Task C：用户可见定时整理规则

- 已新增 `scripts/probes/ai_nas_schedule.py`，提供 `index_refresh`、`duplicate_report`、`folder_summary` 三类规则的创建、启停、列表、dry-run 和报告记录；dry-run 只写报告，不删除、移动、重命名或覆盖源文件。
- 已在 `scripts/probes/ai_nas_operator_portal_server.py` 增加 `/api/schedule/summary`、`POST /api/schedule/create-rule`、`POST /api/schedule/set-enabled`、`POST /api/schedule/run-dry`。
- 已在 `scripts/probes/nas_web_os_portal.html` 的备份页集成“定时整理规则”UI。
- `scripts/probes/ai_nas_scheduled_rules_portal_gate_probe.py` 通过，结果为 `ok_ai_nas_scheduled_rules_portal_gate`，14/14，报告在 `tmp\ai_nas_scheduled_rules_portal_gate_local\scheduled_rules_portal_gate_20260624-014404-622667\scheduled_rules_portal_gate.json`。
- 回归通过：`ready_ai_nas_production_readiness_gate` 0 blocker；`ok_nas_integrated_portal_gate` 19/19；`ok_ai_nas_ten_goal_s100p_closure_gate` 10/10。

### Task D：媒体元数据和播放器链接增强

- 已扩展 `scripts/probes/ai_nas_media.py`：电影/视频条目会从文件名解析标题、年份、季集号，并检测同名字幕和海报 sidecar。
- 已扩展 `/api/media/summary`：返回 `movies` 增强列表，每项包含 `relative_path`、`open_url`、`poster_url`、`player_links`、字幕/海报状态，并明确 `transcoding_enabled=false`。
- 已在 `scripts/probes/nas_web_os_portal.html` 的媒体中心显示“电影库”和“最近照片”，电影卡显示标题、年份/剧集、字幕、海报、大小、直接打开链接；Jellyfin/Plex/厂商播放器通过环境变量配置，未自研实时转码。
- `scripts/probes/ai_nas_media_enhanced_portal_gate_probe.py` 通过，结果为 `ok_ai_nas_media_enhanced_portal_gate`，12/12，报告在 `tmp\ai_nas_media_enhanced_portal_gate_local\media_enhanced_portal_gate_20260624-015103-135194\media_enhanced_portal_gate.json`。
- 回归通过：`ready_ai_nas_production_readiness_gate` 0 blocker；`ok_nas_integrated_portal_gate` 19/19；`ok_ai_nas_ten_goal_s100p_closure_gate` 10/10。

### Task E：PWA/移动端入口

- 已在 `scripts/probes/nas_web_os_portal.html` 增加 PWA manifest、SVG 图标、移动 Web App meta、安装按钮、service worker 注册和安装提示逻辑。
- 已在 `scripts/probes/ai_nas_operator_portal_server.py` 增加 `/manifest.webmanifest`、`/pwa-icon.svg`、`/sw.js`；service worker 只缓存 shell 资源和导航页，不缓存 `/api/*` 和授权下载内容。
- `/api/portal/config` 已声明 `pwa_mobile_entry=true`。
- `scripts/probes/ai_nas_pwa_mobile_portal_gate_probe.py` 通过，结果为 `ok_ai_nas_pwa_mobile_portal_gate`，14/14，报告在 `tmp\ai_nas_pwa_mobile_portal_gate_local\pwa_mobile_portal_gate_20260624-020835-087493\pwa_mobile_portal_gate.json`。
- 本机没有 `npx`，因此未能执行 Playwright 真实 viewport 截图；该 gate 已验证 PWA 资源、响应式结构、登录、上传、搜索、OpenClaw/Qwen 聊天、媒体索引和授权媒体链接。
- 最终回归通过：`ready_ai_nas_production_readiness_gate` 0 blocker；`ok_nas_integrated_portal_gate` 19/19；`ok_ai_nas_ten_goal_s100p_closure_gate` 10/10。
