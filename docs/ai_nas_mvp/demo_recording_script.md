# Demo Recording Script

目标：录一段连续演示，展示 OpenClaw 对话、Dream 7B 本地模型、NAS 原始目录、整理结果、任务日志和 Markdown/JSON 报告。

## Preflight

Windows 侧：

```powershell
ssh -i C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519 sunrise@192.168.127.10 "sudo -n dream7b-default-status"
ssh -i C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519 sunrise@192.168.127.10 "sudo -n sh -c 'XDG_RUNTIME_DIR=/run/user/0 systemctl --user is-active openclaw-gateway.service; XDG_RUNTIME_DIR=/run/user/0 systemctl --user is-active dream7b-local-openai-gateway.service'"
ssh -i C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519 sunrise@192.168.127.10 "sudo -n sh -c 'curl -s http://127.0.0.1:18789/health; echo; curl -s http://127.0.0.1:18888/health; echo'"
```

预期模型证据：

- `active/enabled: active / enabled`
- `segment_major_24x256_default: True`
- `latest telemetry avg_bpu: 93.014 failed_jobs=0`
- `OpenClaw model: dream7b-local/Dream7B-S100P-local base_url=http://127.0.0.1:18888/v1`
- `openclaw-gateway.service`: active
- `dream7b-local-openai-gateway.service`: active

Allowlist 证据：

```bash
cd /root/.openclaw/workspace
scripts/run_allowlisted_tool.sh list | grep ai_nas
```

## Recording Flow

1. 展示定位标题：低成本 AI-NAS Copilot：用便宜 NAS + S100P + OpenClaw 平替高端 AI NAS 智能层。
2. 展示 `/mnt/nas/openclaw/Personal` 原始目录。
3. 展示 `Movies`、`Documents`、`Photos`、`Inbox`。
4. 展示 Dream 7B 本地模型证据：
   - `Dream7B-S100P-local`
   - `base_url=http://127.0.0.1:18888/v1`
   - 默认 Dream 服务 active/enabled
   - `segment_major_24x256_default: True`
5. 在 OpenClaw 输入：`扫描 Personal 并生成索引报告。`
6. 展示 `personal_inventory.md/json`，重点看 Movies、Documents、Photos、Inbox 四类。
7. 在 OpenClaw 输入：`找一下 2019 年的犯罪电影。`
8. 展示 `file_search.md/json`，重点看路径、理由、confidence。
9. 在 OpenClaw 输入：`总结 Documents 文件夹，这些合同里有哪些付款时间？`
10. 展示 `folder_summary.md/json`，重点看 summary、answer、parse_failures。
11. 在 OpenClaw 输入：`生成重复文件报告，不要删除文件。`
12. 展示 `duplicate_report.md/json`，重点看 duplicate group 和 `requires_human_confirmation=true`。
13. 在 OpenClaw 输入：`整理电影，但不要移动或删除原文件，只复制并写 manifest。`
14. 展示 `Personal/Sorted/Movies`、`movie_sort_enhanced.md/json`、`movie_sort_manifest.json`。
15. 展示安全策略：
   - no delete
   - no move
   - no overwrite
   - all operations write Markdown/JSON reports
   - all operations go through allowlisted tool IDs

## Machine Evidence For Recording

最新可直接展示的 live 证据：

- `/mnt/nas/openclaw/reports/ai_nas_mvp/openclaw_live_demo_20260614-135822/openclaw_live_demo.md`
- `/mnt/nas/openclaw/reports/ai_nas_mvp/openclaw_live_demo_20260614-135822/openclaw_live_demo.json`

最新 live 批次报告：

- `/mnt/nas/openclaw/reports/ai_nas_mvp/personal_inventory_20260614-215823/personal_inventory.md`
- `/mnt/nas/openclaw/reports/ai_nas_mvp/file_search_20260614-215825/file_search.md`
- `/mnt/nas/openclaw/reports/ai_nas_mvp/folder_summary_20260614-215827/folder_summary.md`
- `/mnt/nas/openclaw/reports/ai_nas_mvp/duplicate_report_20260614-215829/duplicate_report.md`
- `/mnt/nas/openclaw/reports/ai_nas_mvp/movie_sort_enhanced_20260614-215831/movie_sort_enhanced.md`
- `/mnt/nas/openclaw/reports/ai_nas_mvp/movie_sort_enhanced_20260614-215831/movie_sort_manifest.json`

## Fixed Tool IDs

```bash
ai_nas_personal_inventory
ai_nas_file_search
ai_nas_folder_summary
ai_nas_duplicate_report
ai_nas_movie_sort_enhanced
```

兼容旧脚本的 `_probe` 后缀 alias 也保留。

## Narration Points

- 这不是 NAS OS 替代。
- 便宜 NAS 继续负责存储基础能力。
- S100P 负责本地 Dream 7B 服务和 AI-NAS 任务执行。
- OpenClaw 把自然语言转成固定 allowlisted tool 调用。
- 当前已经覆盖高端 AI NAS 智能层的 P0 demo 路径。
- 差距仍然包括生产级 OCR、生产级 CLIP/semantic embedding、完整图片语义识别、移动 App、权限感知搜索和成熟产品 UI；当前已具备 OCR/embedding 状态记录、轻量 fallback 报告和有界照片语义搜索。
