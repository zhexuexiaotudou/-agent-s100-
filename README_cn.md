# Digua S100P / OpenClaw AI-NAS 演示项目

本仓库是将 S100P 开发板打造为常驻 AI-NAS 网关的证据与演示仓库。OpenClaw 提供面向 NAS
的交互体验，Qwen 在 S100P 本地运行，边缘-云端路由器决定请求是否可以离开设备。

## 离线 UI 工作台

在 S100P 和 NAS 均不在线期间，`/ui` 的保留式改版已于 2026-07-16 在本地完成。改版保留原生
HTML/CSS/JS、现有路由和 API 调用，以及身份、ACL、受控复制和回收站软删除边界。页面现在
默认进入以任务为中心的首页；断开设备时不再显示虚构容量、身份或通知；桌面导航按任务分组，
移动端使用五项底栏和完整的“更多”面板，并覆盖响应式、暗色模式、减少动态效果与触控目标检查。

本地 UI 证据记录在
[`docs/offline_ui_delivery_20260716.md`](docs/offline_ui_delivery_20260716.md)。S100P/NAS 的真实功能验收
与部署明确延后，待两台设备恢复在线后执行。

非 Dream 7B 已实现功能的离线加固结果，以及设备恢复后的真实链路验收门，记录在
[`docs/non_dream7b_offline_hardening_20260716.md`](docs/non_dream7b_offline_hardening_20260716.md)。

## 当前状态

状态时间戳：2026-07-06 17:53 CST。

三项演示预期已在 S100P 测试机上达成：

| 演示 | 预期行为 | 当前结果 | 证据 |
| --- | --- | --- | --- |
| 1. S100P 作为常驻网关 | S100P 在用户登录/登出后保持 AI 网关在线，提供稳定的本地入口 | `openclaw-gateway.service` 和 `qwen25-local-openai-gateway.service` 均为 `active/enabled`；`loginctl` linger 为 `yes` | OpenClaw `/api/health` 在 `127.0.0.1:8765`；Qwen `/health` 在 `127.0.0.1:18080` |
| 2. OpenClaw 实现 AI-NAS | OpenClaw 能驱动 NAS 操作，而非仅聊天 | `ok_ai_nas_openclaw_nas_control_gate`，10/10 检查通过 | `/mnt/nas/openclaw/reports/qwen25_ai_nas/openclaw_nas_control_gate_20260629-210023-832862/openclaw_nas_control_gate.json` |
| 3. 边缘+云端路由 | 每个查询首先进入本地 Qwen；隐私/简单请求留在 S100P；公共复杂请求可使用受控云端端点 | `ok_ai_nas_edge_cloud_router`；3/3 分类来自 `qwen_structured_json`；2 个本地，1 个云端；无私密查询发送至云端 | `/mnt/nas/openclaw/reports/qwen25_ai_nas/edge_cloud_router_20260629-210034-495865/edge_cloud_router.json` |

最新 Qwen AI-NAS 验收包同样通过：

- 判定：`ok_qwen25_ai_nas_acceptance_packet`
- 路由：`ai_nas_allowlisted_tools`
- 生成报告：个人清单、证据报告、案例包、文件夹 RAG 和网关轮次报告
- 证据：`/mnt/nas/openclaw/reports/models/qwen25_ai_nas_acceptance_20260629-210016/qwen25_ai_nas_acceptance.json`

## Harness 默认服务状态

AI-NAS harness 已集成到 OpenClaw 默认服务路径，启用了受限的、用户确认的复制功能。

- 最终判定：`harness_default_service_integrated_limited_copy_enabled`
- 最终包：`01_final_evidence/digua_ai_nas_harness_default_service_gate_packet.json`
- 评审包：`evidence_for_gptpro/digua_ai_nas_harness_default_service_for_gptpro_20260704-143537.zip`
- 包 SHA256：`38bc412b3cf0bbf1a159bdc75413a680f9cc2f3c5ec14d9878a8fb962e0c2fbf`
- 实时状态端点：S100P 上 `http://127.0.0.1:8765/api/harness/status`

默认 harness 路径允许有边界的复制流程和 Auto Organizer 受控移动+重命名流程。两者均要求显式产品策略、键入审批或等效操作员确认、目标不可覆写保证以及回滚证据。非受控移动/重命名、删除、chmod、chown、覆写、递归操作、任意 shell 执行、Qwen 自主工具执行以及私有原始云出口均不在范围内。

## 产品交付验收

路线图 product-smoke 循环现已在 S100P 上可用。

- 产品状态 API：S100P 上 `http://127.0.0.1:8765/api/product/status`
- 产品证据 API：S100P 上 `http://127.0.0.1:8765/api/product/evidence/latest`
- Product smoke 判定：`ok_product_smoke_test`
- Product smoke 报告：`/mnt/nas/openclaw/reports/product_delivery/product_smoke_test_20260706-142946/product_smoke_test.json`
- 最终就绪判定：`ready_ai_nas_production_readiness_gate`
- 最终就绪报告：`/mnt/nas/openclaw/reports/product_delivery/production_readiness_gate_20260706-025926-730286/production_readiness_gate.json`
- 验收记录：`docs/product_delivery_acceptance_20260706.md`

实时 product smoke 验证了 `failure_count=0`、`warning_count=0`、
`production_ready=true`、`yolo_runtime_target=s100p_bpu_hbm`、
`yolo_detection_count=66`、`multimodal_embedding_count=5`、
`ai_space_asset_count=13`、`smart_category_count=29`、
`smart_name_count=43` 和 `subtitle_segment_count=1`。

## 演示产品交付验收

多模态 Auto Organizer 交付门在 S100P 实机上通过。

- Stage 9 判定：`ok_stage9_demo_product_delivery_gate`
- Stage 9 报告：`/mnt/nas/openclaw/reports/qwen25_ai_nas/stage9_demo_product_delivery_gate.json`
- Product smoke 报告：`/mnt/nas/openclaw/reports/qwen25_ai_nas/product_smoke_test_20260706-154654/product_smoke_test.json`
- GPT Pro 包：`/mnt/nas/openclaw/evidence_for_gptpro/digua_demo_product_delivery_20260706-154654.zip`
- 包 SHA256：`e79382b588b7a1a8ff0ab991ed8c334578928925282d9089f9452e1b59d5d708`

已验证的新增功能：

- Auto Organizer：受控移动+重命名、冲突安全后缀、删除/覆写阻止、回滚清单和回滚恢复。
- Assistant Trace：面向 assistant 入口点的全局 10 步追踪契约，无隐藏思维链存储。
- Demo 3 解释端点：Qwen 路由解释、token 预算解释、隐私分词器调试和 assistant trace API。
- 常驻链接：`openclaw-gateway.service` 和 `qwen25-local-openai-gateway.service` 均为 active；门户保持在 `127.0.0.1:8765` 的 loopback 作用域。

## 最终演示录制就绪

最终演示加固循环在 S100P 实机上通过，使用了用户级流程。

- 最终判定：`ok_stage9_final_recording_readiness_gate`
- 最终报告：`reports/stage9_final_recording_readiness_gate.json`
- 最终报告 Markdown：`reports/stage9_final_recording_readiness_gate.md`
- GPT Pro 证据包：`evidence_for_gptpro/digua_final_recording_readiness_20260706-175314.zip`
- 包 SHA256：`c59b2e8ebfbdc2621a09fa892da6008962fd70b8719602b3dcf8c068166a2982`
- 录制就绪说明：`docs/DEMO_PRODUCT_RECORDING_READINESS_20260706.md`

已验证的最终新增功能：

- Auto Organizer 通过 AI Space 和智能分类索引对中性文件名进行分类，之后再回退到文件名启发式规则。
- `/api/assistant/chat` 从真实路由器、隐私、token 预算、工具执行和安全上下文中记录十个标准追踪步骤。
- OCR/RAG 产品端点可在 `/api/document-rag/query`、`/api/ocr/query` 和 `/api/ocr/status` 访问。
- Demo 2 重放了上传、本地索引、AI Space/多模态/人物安全、YOLO 搜索、OCR/RAG、Auto Organizer 审批/执行和回滚。
- Demo 3 重放了 assistant 对本地媒体搜索、私密文档摘要和公共复杂路由的请求。
- 最终安全标志保持 false：原始路径返回、删除、覆写、非受控移动/重命名、隐藏思维链存储和私密云端出口。

当前边界：真实 S100P YOLO 后端完成了本地处理并索引了资产，但最终演示图片集产生了零个 YOLO 检测框。这被记录为 smoke warning，而非合成通过。因此，人属性搜索在此最终包中对检测派生的属性为降级状态，而危险的身份识别和敏感属性推断保持阻断。

## 产品级加固

Stage 9 之后的最终加固阶段为录制流程添加了更严格的产品契约。

- 审计：`reports/final_product_hardening_audit/final_product_hardening_audit.md`
- 加固说明：`docs/PRODUCT_GRADE_HARDENING_20260706.md`
- Auto Organizer 现在在无 AI 索引证据时阻止产品回退：`blocker=ai_index_missing_for_asset`。
- Assistant Trace 现在将非合成的产品追踪与合成诊断追踪分开。
- OCR/RAG 现在有专用的文档和 OCR 路由模块以及 `ocr_rag` 产品状态卡片。

此加固阶段的 S100P 实时验收通过：

- 最终判定：`ok_stage9_final_recording_readiness_gate`
- 最终报告：`reports/stage9_final_recording_readiness_gate.json`
- GPT Pro 证据包：`evidence_for_gptpro/digua_final_recording_readiness_20260706-184743.zip`
- 包 SHA256：`17f578ccf3749da09a56994b39a06ff618cd42c8121c93d75f2d814ca0b89fc2`

当前边界：product smoke 具有 `failure_count=0` 和 `production_ready=true`，而 YOLO 和人物属性因相同的真实数据原因保持降级：S100P YOLO 后端以 `runtime_target=s100p_bpu_hbm` 完成，但当前演示图片产生了零检测框。

## Stage 10 发布产品交付

Stage 10 将当前演示系统转变为面向发布的 S100P 包，并添加了可复现的演示语料工作流。

- 最终 S100P 判定：`ok_stage10_release_product_delivery_gate`
- 验收说明：`docs/STAGE10_RELEASE_PRODUCT_DELIVERY_ACCEPTANCE_20260706.md`
- 最终报告：`reports/stage10_release_product_delivery_gate.json`
- Product smoke：`reports/product_smoke_test_20260706-210340/product_smoke_test.json`
- S100P 包 SHA256：`66caaca4df00914ea18111f9fc1fbcb1fdd861f75a33c6ed63a7685d1a72b51a`
- 证据包 SHA256：`3a4ace7dc4fd3e1abdb4f8a7a9c1d28118adf06d17c1f1f88e659fc8796c61fa`

- 发布包命令：`python3 scripts/build_release.py --version 0.1.0 --out dist/`
- 最终发布门：`python3 gates/stage10_release_product_delivery_gate.py --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas --personal-root /mnt/nas/openclaw/Personal --base-url http://127.0.0.1:8765 --timeout 240`
- Windows 访问说明：`docs/openclaw_windows_loopback_access_20260706.md` 解释了为何 Windows 上 `http://127.0.0.1:8765/ui` 需要通过 SSH 隧道连接 S100P loopback 网关。
- 演示语料：`demo_corpus/` 包含配方、清单、许可证声明、Wikimedia/Open Images 下载器、合成 OCR/RAG 文档生成、Personal 演示根目录构建器和验证脚本。
- 包完整性检查确认清单中声明的生成演示固件存在于发布 tar 包中。
- 发布安装器：`release/install/install_s100p.sh` 支持预检、NAS 挂载规划、模型路径验证、venv 设置、systemd 单元规划、首次运行向导、升级、回滚、卸载和支持包收集。

发布包输出：

- `dist/digua-ai-nas-s100p-0.1.0.tar.gz`
- `dist/digua-ai-nas-s100p-0.1.0.zip`
- `dist/digua-ai-nas-s100p-0.1.0.sha256`
- `dist/release_manifest.json`

用户快速开始：

```bash
sudo bash release/install/install_s100p.sh \
  --nas-protocol nfs \
  --nas-host 192.168.1.20 \
  --nas-share /OpenClawWorkspace \
  --mount-point /mnt/nas/openclaw \
  --personal-root /mnt/nas/openclaw/Personal \
  --install-root /opt/digua-ai-nas
```

Stage 10 安全边界：

- 模型权重不打包；
- 第三方图片默认不打包；
- 私有用户数据和运行时数据库文件排除在发布包外；
- 网关默认使用 loopback/LAN，而非公网；
- NAS 访问限定在已配置的 OpenClaw 工作区；
- 删除、覆写、非受控移动/重命名、Qwen 自主文件执行、隐藏思维链存储、云端视觉/OCR/ASR 以及私有原始云出口保持禁用。

当前 Stage 10 录制边界：YOLO 检测框录制必须显示真实 `detection_count > 0` 或记录显式阻断原因 `yolo_demo_images_not_detectable`。在实时 S100P product smoke 报告零 YOLO 检测框期间，不得声称检测框检测。

## AI 相册界面工作区

现有 v2 Web UI 现包含位于 `/ai-album` 的"AI 相册"工作区。它将 AI Space、媒体预览、智能分类、人属性搜索、智能命名和 Auto Organizer 计划生成为一个本地 AI-NAS 相册页面。

- 路由：S100P loopback 上 `http://127.0.0.1:8765/ai-album`。
- 交付说明：`docs/AI_ALBUM_UI_DELIVERY.md`
- Gate：`gates/stage11_ai_album_ui_gate.py`
- S100P 判定：`ok_stage11_ai_album_ui_gate`
- S100P 报告：`/mnt/nas/openclaw/reports/qwen25_ai_nas/stage11_ai_album_ui_gate.json`
- 范围：本地搜索、智能分类浏览、缩略图网格、双击图片查看器、选中资产详情、身份查询 UI 阻断和受控 Auto Organizer 计划工作流。
- 边界：无人脸身份识别、无敏感属性推断、无原始路径显示、无删除/覆写 UI、无公网暴露。

## AI Space 产品验收

AI Space / 智能分类 / 字幕提取交付门在 S100P 上通过。

- Stage 7 判定：`ok_stage7_ai_space_product_delivery_gate`
- Stage 7 报告：`/mnt/nas/openclaw/reports/qwen25_ai_nas/stage7_ai_space_product_delivery_gate.json`
- GPT Pro 包：`/mnt/nas/openclaw/evidence_for_gptpro/digua_ai_space_product_delivery_latest.zip`
- 验收说明：`docs/AI_SPACE_PRODUCT_ACCEPTANCE_20260706.md`

已验证模块：

- 实时本地 CLIP 图片嵌入：`model_family=clip`、`vector_dim=512`、`production_semantic_embedding_count=17`、`cloud_used=false`。
- 人属性搜索：`person_detection_count=31`、`attribute_count=31`，身份请求被阻断。
- AI Space：`asset_count=220`、`evidence_count=220`，无原始路径返回。
- 智能分类：`category_count=12`、`membership_count=986`，仅虚拟分类；无物理文件移动。
- 字幕提取：本地 `transformers_whisper` 后端，`segment_count=1`，SRT/VTT 已生成，`cloud_used=false`。

## 智能相册上传与中文命名验收

智能相册自动分类和中文命名交付门在 S100P 上通过。

- Stage 7 判定：`ok_stage7_smart_album_classification_delivery_gate`
- Stage 7 报告：`/mnt/nas/openclaw/reports/qwen25_ai_nas/stage7_smart_album_classification_delivery_gate.json`
- Product smoke 报告：`/mnt/nas/openclaw/reports/product_delivery/product_smoke_test_20260706-142946/product_smoke_test.json`
- GPT Pro 包：`/mnt/nas/openclaw/evidence_for_gptpro/digua_smart_album_classification_delivery_latest.zip`
- 交付说明：`docs/SMART_ALBUM_CLASSIFICATION_DELIVERY.md`

已验证流程：

- `POST /api/media/upload` 将上传的图片保存在 Personal NAS 下，并记录媒体上传、多模态重建、YOLO 索引、人属性、智能分类、智能命名和 AI Space 任务。
- 上传的 `white_shirt_person_004.jpg` 返回资产 `mm_fb98a8eb7d323bbbdea2f181`，命中"人物照片"和"白色上衣"，并生成 `人物照片_白色上衣_照片_20260706_429.jpg`。
- 中文命名门验证了格式 `主分类_核心特征_场景或属性_日期_序号`，无非法文件名字符，无电话/身份证式敏感数字，以及"人物照片"、"猫咪"、"票据发票"和"笔记本电脑"的示例命名。
- 固件恢复后的最终实时 smoke 验证了 `yolo_detection_count=66`、`person_detection_count=31`、`ai_space_asset_count=13`、`smart_category_count=29` 和 `smart_name_count=43`。

## 演示叙述

项目故事应按从"在板子上跑模型"到"交付私有 AI-NAS 设备"的递进方式讲述。

1. S100P 不是一次性加速器演示。它是通过 systemd 用户服务保持在线、成为 NAS 本地 AI 控制面的常驻网关。
2. OpenClaw 是 NAS 产品界面。它将用户意图转化为真实的 NAS 工作流：列出文件、搜索文件夹、生成证据包、复制/重命名文件、阻止未授权写入，并要求对破坏性操作进行确认。
3. Qwen 是本地决策层。所有用户查询首先进入本地 Qwen。路由器询问 Qwen 该请求是否足够简单可本地处理，以及是否涉及隐私。只有公共的、复杂的工作才被允许发送到受控云端端点。
4. 价值主张是省 token + 隐私保护：端点将私有 NAS 上下文保留在设备上，仅将云端作为溢出通道而非默认路径。

建议的一句话推介：

> S100P + OpenClaw 将普通 NAS 转变为隐私优先的 AI-NAS：本地 Qwen 在设备上处理私密文件智能，云端仅用于通过本地路由器的公共复杂任务。

## 亮点

- **常驻网关**：`qwen25-local-openai-gateway.service` 在 `127.0.0.1:18080` 提供本地 OpenAI 兼容的 Qwen 端点；`openclaw-gateway.service` 在 `127.0.0.1:8765` 提供 AI-NAS Web OS / 操作员门户。
- **真实 NAS 操作**：OpenClaw gate 验证登录、目录列表、重命名、复制、删除确认、查看器只读行为、ACL 保护复制目标以及直接存储变更的 ACL 执行。
- **本地优先路由器**：边缘-云端探针要求 Qwen 生成结构化 JSON。策略仅作为隐私/失败的降级后备。
- **隐私底线**：发票、家庭照片、聊天截图、NAS 文件夹、财务和其他私密请求即使云端路径存在也强制本地处理。
- **证据优先交付**：每个演示声明都由 `/mnt/nas/openclaw/reports/...` 上的 JSON/Markdown 报告支撑，而非仅靠截图。
- **受控 Auto Organizer**：物理组织现在只允许通过 Auto Organizer 计划/演练/审批/执行/回滚流程进行。它不启用任意 NAS 移动/重命名、删除、覆写或 Qwen 自主文件操作。
- **模型路线清晰**：Dream7B 产物保留为工具链历史；当前产品路线是 Qwen + OpenClaw + AI-NAS gates。当前 Dream7B seq128 S100P logits 有效性研究状态总结在 `docs/DREAM7B_S100P_SEQ128_LOGITS_VALIDITY_ROUTE_STATUS_20260704.md`。
- **Dream7B 研究路线重置**：llada.cpp 风格的正确性优先路线现位于 `dream_s100p_lladacpp/` 下；31 行 HF/PyTorch 真值集、验证门和真值重放块驱动门已通过。该路线在 `bpu_operator_alignment_failed_review_required` 处暂停，直到存在真正的逐算子 BPU 输出、布局记录和量化缩放证据。

## 仓库布局

| 路径 | 角色 |
| --- | --- |
| `scripts/qwen25_openai_gateway.py` | 本地 Qwen OpenAI 兼容网关和结构化边缘-云端分类入口 |
| `scripts/probes/ai_nas_edge_cloud_router_probe.py` | 端到端本地优先边缘-云端路由门 |
| `scripts/probes/qwen25_ai_nas_acceptance_packet.py` | Qwen AI-NAS 验收包生成器 |
| `scripts/probes/ai_nas_openclaw_nas_control_gate_probe.py` | OpenClaw NAS 控制、ACL 和破坏性操作门 |
| `scripts/probes/ai_nas_operator_portal_server.py` | AI-NAS Web OS / 操作员门户服务器 |
| `scripts/product_smoke_test.py` | 针对 `/api/product/status`、evidence、YOLO、多模态和 harness 边界的产品级实时 HTTP smoke gate |
| `gates/stage7_ai_space_product_delivery_gate.py` | 针对实时 CLIP、人属性、AI Space、智能分类和字幕提取的聚合产品门 |
| `src/person_attribute/` | 仅限本地的非身份识别人物属性搜索 |
| `src/ai_space/` | AI Space 目录和维度 |
| `src/smart_classification/` | 虚拟智能分类集合 |
| `src/subtitle_extraction/` | 本地 ASR 转录、SRT/VTT 和搜索支持 |
| `src/auto_organizer/` | 受控移动+重命名规划器、执行器、冲突策略和回滚 |
| `src/assistant_trace/` | 全局 assistant 执行追踪模式、记录器和路由 |
| `src/product_jobs/` | 产品后台任务队列 API |
| `src/harness/` | Harness 策略、复制路由守卫和 token 预算集成 |
| `src/openclaw/` | OpenClaw 默认服务中间件和 API 路由适配器 |
| `gates/stage*_gates.py` | 按阶段门控的 AI-NAS harness 验证脚本 |
| `reports/` | Gate 输出、追踪 JSONL 和回归证据 |
| `evidence_for_gptpro/` | 带 SHA256 附件的打包评审包 |
| `configs/systemd/qwen25-local-openai-gateway.service` | S100P 常驻 Qwen 网关单元 |
| `configs/systemd/openclaw-gateway.service` | S100P 常驻 OpenClaw AI-NAS 门户网关单元 |
| `dream_s100p_lladacpp/` | 隔离的 Dream7B llada.cpp 风格研究路线；非产品路线 |
| `docs/` | 项目决策、运维手册、验收说明和演示脚本 |
| `tmp/demo_three_features_final_recheck/` | 最新复查报告的本地副本 |

## 验证命令

从 Windows 主机的 `F:\Project\Digua` 执行。

```powershell
ssh -i C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519 sunrise@192.168.127.10 `
  'systemctl --user is-active openclaw-gateway.service; systemctl is-active qwen25-local-openai-gateway.service || systemctl --user is-active qwen25-local-openai-gateway.service; ss -ltnp "sport = :18080"; curl -fsS http://127.0.0.1:8765/api/health; curl -fsS http://127.0.0.1:18080/health'
```

Qwen 可以由 system scope 或 user scope 承载，但回环端口 `18080` 必须只有一个实例占用。若两个 scope 同时启动，应先消除重复占用再把 unit 状态作为生产证据；仅有 HTTP 200 不能证明服务管理状态已经收敛。

```powershell
py -3 scripts\probes\qwen25_ai_nas_acceptance_packet.py --out-root tmp\demo_three_features_final_recheck
```

```powershell
ssh -i C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519 sunrise@192.168.127.10 `
  'cd /mnt/nas/openclaw/scripts/probes && python3 ai_nas_openclaw_nas_control_gate_probe.py --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas'
```

```powershell
ssh -i C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519 sunrise@192.168.127.10 `
  'cd /mnt/nas/openclaw/scripts/probes && python3 ai_nas_edge_cloud_router_probe.py --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas --use-qwen-classifier --require-qwen-touch --qwen-base-url http://127.0.0.1:18080 --execute-cloud --use-local-cloud-stub --require-cloud-call --timeout 180'
```

```powershell
ssh -i C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519 sunrise@192.168.127.10 `
  'cd /mnt/nas/openclaw && python3 scripts/product_smoke_test.py --base-url http://127.0.0.1:8765 --report-root /mnt/nas/openclaw/reports/product_delivery'
```

```powershell
ssh -i C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519 sunrise@192.168.127.10 `
  'cd /mnt/nas/openclaw && DIGUA_CLIP_BACKEND=clip DIGUA_CLIP_MODEL_DIR=/mnt/nas/openclaw/models/ai_nas_clip_vit_base_patch32 DIGUA_CLIP_DEVICE=cpu DIGUA_CLIP_REQUIRE_PRODUCTION=1 DIGUA_ASR_BACKEND=transformers_whisper DIGUA_ASR_MODEL_DIR=/mnt/nas/openclaw/models/whisper_tiny DIGUA_ASR_REQUIRE_REAL=1 python3 gates/stage7_ai_space_product_delivery_gate.py --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas --personal-root /mnt/nas/openclaw/Personal --no-rebuild'
```

```powershell
ssh -i C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519 sunrise@192.168.127.10 `
  'cd /mnt/nas/openclaw && DIGUA_CLIP_BACKEND=clip DIGUA_CLIP_MODEL_DIR=/mnt/nas/openclaw/models/ai_nas_clip_vit_base_patch32 DIGUA_CLIP_DEVICE=cpu DIGUA_CLIP_REQUIRE_PRODUCTION=1 DIGUA_ASR_BACKEND=transformers_whisper DIGUA_ASR_MODEL_DIR=/mnt/nas/openclaw/models/whisper_tiny DIGUA_ASR_REQUIRE_REAL=1 python3 gates/stage9_demo_product_delivery_gate.py --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas --personal-root /mnt/nas/openclaw/Personal --base-url http://127.0.0.1:8765 --qwen-url http://127.0.0.1:18080/health --timeout 45'
```

## 边界

- 路由器演示使用受控的本地云端桩，除非 `--cloud-base-url` 显式指向真实云服务。
- Qwen `/health` 仍包含历史模型/配置文件元数据字段，可能看起来不一致。验收时请使用上述 gate 判定和生成的报告路径作为真值来源。
- 不得声称人脸识别、家庭成员身份识别、年龄/性别/种族/情绪/健康推断、云端视觉或云端 ASR。
- 智能分类默认创建虚拟分类。物理组织必须通过复制计划 / Harness 审批和回滚进行。
- 字幕门使用合成演示音频固件验证本地 ASR 机制；生产演示应使用真实的用户提供的媒体。
- Dream7B 不再是推荐的产品路线。它仍作为运行时、批处理、遥测和验证历史有价值。最新的 seq128 分段 HBM 研究路线对于当前全 BPU 路径而言 logits 无效，在有 logits 有效候选方案之前必须排除在生成/产品路由之外。
- 本地检出现在是有效的 git 仓库，远程为 `https://github.com/zhexuexiaotudou/-agent-s100-.git`。大型无关的 Dream7B、分词器和日志产物不属于 harness 上传范围，除非显式暂存。
