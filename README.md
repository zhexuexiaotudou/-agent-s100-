# Digua S100P / AI-NAS Workspace

This workspace records the S100P bring-up, OpenClaw/AI-NAS toolchain, and the
Dream7B deployment experiments.

Current project conclusion as of 2026-06-23: Dream7B is not the right model
path for this project. The reusable value is the deployment and validation
toolchain built while trying to make Dream7B work on S100P.

## Project Log

- 2026-05-17: 建立 S100P agent 化 bring-up 文档，沉淀刷机、联网、依赖和验收方法。
- 2026-06-09: 完成 Windows/S100P/NAS/OpenClaw 开机链路自检脚本与日志机制。
- 2026-06-13: 调研高端 AI-NAS 功能，形成低成本平替的文件、媒体、备份和助手目标。
- 2026-06-14: 建成 AI-NAS MVP 验收、BPU 优化分析和基础 Demo 录制材料。
- 2026-06-18: 完成 Dream7B S100P 证据包和 true-batch HBM 可行性分析。
- 2026-06-19: 完成 Dream7B B=4/B=16 运行分析，明确队列批处理仍是基线。
- 2026-06-20: 固化 Dream7B 部署基线和回滚状态，避免重复无效扫参。
- 2026-06-21: 刷新 S100P 运行状态、服务状态和 last-token 验证计划。
- 2026-06-22: 修复 OpenClaw/Dream 网关快路径，确认 Dream 通用对话质量边界。
- 2026-06-23: 转向官方 Qwen2.5 S100P 路由，完成 AI-NAS 产品闭环和交付包。
- 2026-06-24: 重做 OpenClaw 门户 UI、图像检索/设置，并接通 QNAP 官方 NAS 管理入口。

## Start Here

- `docs/project_retrospective_2026-06-23.md` - end-to-end project history,
  current conclusion, and what to keep.
- `docs/openclaw_official_nas_manager_discovery_2026-06-24.md` - current
  official NAS manager discovery result, S100P SSH-forward route, and
  new-user setup closure.
- `docs/dream7b_seq128_cloud_compile_closure_2026-06-23.md` - final cloud
  compile closure: seq128 HBM package produced and verified, but Dream compile
  work is paused and not promoted.
- `docs/reusable_toolchain_map_2026-06-23.md` - reusable assets by category:
  S100P bring-up, NAS link checks, systemd templates, probes, telemetry,
  quality gates, rollback, and report packets.
- `docs/competition_delivery_2026-06-23.md` - current competition delivery
  plan and final integrated demo flow.
- `docs/nodehub_submission_package_2026-06-23.md` - NodeHub submission file
  structure, quick start, evaluation points, and demo narrative.
- `docs/ai_nas_product_closure_goal_2026-06-23.md` - final AI-NAS Copilot
  product goal, current `ok_ai_nas_product_closure_gate`, satisfied evidence,
  and residual product boundaries.
- `docs/ai_nas_next_tasks_model_split_2026-06-23.md` - next-task handoff split
  between GPT-5.5-class architecture/reasoning tasks and DeepSeek-class
  mechanical execution tasks.
- `docs/ai_nas_commercial_parity_architecture.md`,
  `docs/ai_nas_permission_threat_model.md`,
  `docs/ai_nas_conversation_product_design.md`,
  `docs/ai_nas_multimodal_semantics_roadmap.md`,
  `docs/ai_nas_release_claim_audit.md`, and
  `docs/ai_nas_hard_failure_triage_runbook.md` - completed GPT-5.5-class
  planning, security, release-claim, and hard-failure triage constraints for
  the next DeepSeek-class execution pass.
- `docs/ai_nas_non_long_task_completion_2026-06-23.md` - current completion
  note for non-long DeepSeek-class tasks: Web OS UI, existing-module pages,
  small deterministic fixtures, docs sync, and truthful adapter stubs.
- `tmp/ai_nas_product_closure/product_closure_gate_*/product_closure_gate.md`
  - latest strict product-closure gate for the official Qwen2.5 plus S100
  vision route.
- `tmp/ai_nas_competition_delivery/competition_final_acceptance_*/competition_final_acceptance.md`
  - latest integrated acceptance packet for Qwen2.5 text plus official vision.
- `docs/dream7b_openclaw_two_track_deployment_2026-06-22.md` - latest
  Dream7B traffic boundary before the project pivot.
- `docs/dream7b_openclaw_fast_path_fix_2026-06-22.md` - latest Route A demo
  state and Route B blocked state.
- `scripts/probes/README.md` - probe script family index.

## Current Boundary

Do not treat the existing Dream7B artifacts as a promotion plan.

- Route A was only demo-ready for bounded OpenClaw / AI-NAS flows and
  deterministic fast-path status prompts.
- Route B / BPU work remains research-only. It is blocked by sequence length,
  board-side runtime validation, logits quality, Chinese generation quality,
  and promotion evidence. A `seq128, B=1` HBM package was compiled on
  2026-06-23, but it has not been loaded or quality-validated on S100P.
- True-batch runtime work produced useful telemetry and batching tools, but it
  did not make Dream7B a suitable product model for this project.

## Directory Map

| Path | Role | Keep / Move Policy |
| --- | --- | --- |
| `docs/` | Project decisions, runbooks, evidence summaries | Keep as the main knowledge base |
| `scripts/probes/` | AI-NAS and Dream7B probes, gates, report generators | Keep; reuse patterns for the next model/toolchain |
| `scripts/telemetry/` | Queue/true-batch telemetry normalization helpers | Keep |
| `configs/` | Service templates and model routing policy drafts | Keep; do not install blindly |
| `logs/` | Historical bring-up and link-check logs | Keep as evidence, but not a runtime dependency |
| `tmp/` | Large experiment artifacts, local mirrors, reports, WSL/runtime state | High-risk; inventory before deletion |
| `product/`, `downloads/` | Vendor images, packages, and downloaded binaries | High-risk; do not delete without confirmation |
| `hobot_dnn/`, `s100_debs/`, `s100_wheels/` | S100 vendor/runtime materials | Keep as reference dependencies |
| `output/` | Generated report artifacts | Keep if report history is needed |

## Working Rules

- Preserve the current OpenClaw/S100P evidence chain before deleting local
  artifacts.
- Use NAS-backed reports and generated JSON/Markdown packets as evidence. The
  GitHub repository is the shared release record; this Windows workspace may be
  used as a local working mirror.
- Keep new model work isolated from Dream7B-specific ports, aliases, and
  service names until a new model has its own promotion gates.
- For cleanup, classify first, then delete only the approved subset.
