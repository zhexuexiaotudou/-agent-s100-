# Baseline Progress: NAS-backed Core Artifacts

Date: 2026-05-28

本文记录 `/mnt/nas/openclaw` 上已经具备一组完整的 smoke baseline 产物：
文档索引、浏览器截图、ROS bag session、dataset card，以及汇总这些产物的实验报告。

## Verdict

| Baseline | 当前状态 | 证据 |
| --- | --- | --- |
| B-002 文档索引和摘要 | doing | NAS-backed 文档索引已跑通；每日摘要仍未做。 |
| A-007 Browser automation smoke test | verified | Headless Chromium 打开本地页面，截图保存到 NAS，PNG magic 校验通过。 |
| A-009 ROS bag 采集工具 | doing | NAS-backed start/status/stop self-test 已跑通；长时间命名采集策略仍未定。 |
| B-004 机器人数据集 card | verified | ROS bag session 自动生成 `DATASET_CARD.md`，并和 bag 文件写入 NAS。 |
| B-007 周报/实验报告生成 | verified | NAS-backed 实验报告已汇总 logs/probes、文档索引、浏览器截图、ROS bag 和 dataset card。 |

## NAS Permissions Fix

首次以 `sunrise` 创建 NAS 子目录时遇到：

```text
mkdir: cannot create directory '/mnt/nas/openclaw/documents/baseline_reports': Permission denied
mkdir: cannot create directory '/mnt/nas/openclaw/reports/browser-smoke': Permission denied
```

原因是 NAS 顶层子目录为 `root:root 755`。已执行一次性修复：

```bash
sudo mkdir -p /mnt/nas/openclaw/documents/baseline_reports \
  /mnt/nas/openclaw/reports/browser-smoke \
  /mnt/nas/openclaw/robot_datasets \
  /mnt/nas/openclaw/logs/probes
sudo chown -R sunrise:sunrise \
  /mnt/nas/openclaw/documents \
  /mnt/nas/openclaw/reports \
  /mnt/nas/openclaw/robot_datasets \
  /mnt/nas/openclaw/logs
```

修复后：

```text
/mnt/nas/openclaw/documents      sunrise:sunrise
/mnt/nas/openclaw/logs           sunrise:sunrise
/mnt/nas/openclaw/reports        sunrise:sunrise
/mnt/nas/openclaw/robot_datasets sunrise:sunrise
```

## B-002 Document Index

先把本次 baseline 进展文档作为 NAS 文档样本：

```text
/mnt/nas/openclaw/documents/baseline_reports/baseline_progress_2026-05-28_nas_backed_reports.md
```

输出：

```text
/mnt/nas/openclaw/reports/document_index_20260528-182111.md
```

关键字段：

```text
input_dir: /mnt/nas/openclaw/documents
indexed_files: 1
SHA256: eca40c04fd0930622e238ad3a931c119be88b52c2cdbab704f16b677306d1fdc
```

B-002 继续保持 `doing`，因为当前只验证了索引，没有实现每日摘要。

## A-007 Browser Smoke

输出：

```text
/mnt/nas/openclaw/reports/browser-smoke/browser_smoke_20260528-182111.md
/mnt/nas/openclaw/reports/browser-smoke/browser_smoke_20260528-182111.png
```

关键字段：

```text
browser_cmd: /usr/bin/chromium-browser
browser_version: Chromium 148.0.7778.167 snap
visible_marker: yes
screenshot_status: captured
png_magic: 89504e470d0a1a0a
verdict: ok
PNG: 780 x 493, 8-bit/color RGB
```

A-007 可以标为 `verified`：浏览器自动化已经能打开测试网页、截图并保存到 NAS。

## A-009 And B-004 ROS Bag Session

输出：

```text
/mnt/nas/openclaw/logs/probes/rosbag_session_20260528-182117.md
/mnt/nas/openclaw/robot_datasets/rosbag_session_20260528-182117/
/mnt/nas/openclaw/robot_datasets/rosbag_session_20260528-182117/DATASET_CARD.md
```

关键字段：

```text
topics_requested: /rosout /parameter_events
start_status: started
status_after_start: running
stop_status: sent_sigint
record_exit: 0
metadata_exists: yes
verdict: ok
```

生成文件：

```text
DATASET_CARD.md
metadata.yaml
rosbag_session_20260528-182117_0.db3
```

Dataset card 关键字段：

```text
capture_type: rosbag_start_stop_selftest
dataset_id: rosbag_session_20260528-182117
bag_dir: /mnt/nas/openclaw/robot_datasets/rosbag_session_20260528-182117
duration_seconds: 4
topics: /rosout /parameter_events
verdict: ok
```

B-004 可以标为 `verified`：每次 ROS bag session 会在同一 dataset 目录下自动生成
`DATASET_CARD.md`。A-009 仍保持 `doing`，因为当前是 4 秒 bounded self-test，
还需要后续定义可审计的长时间命名采集策略。

## B-007 Experiment Report

`experiment_report_probe.sh` 已修正两点：

1. `rosbag_session_*` 也计入 ROS bag datasets。
2. 当 NAS 核心产物齐全时，不再提示继续填充 smoke artifacts。

最终输出：

```text
/mnt/nas/openclaw/reports/experiments/experiment_report_20260528-182242.md
```

摘要：

```text
workspace: /mnt/nas/openclaw
nas_backed_mode: verified
Probe reports: 3
Experiment reports: 3
Browser smoke screenshots: 1
Document indexes: 1
ROS bag datasets: 1
Dataset cards: 1
```

当前阻塞项变为：

```text
NAS-backed core report artifacts are present: logs/probes, document index, browser screenshot, ROS bag session, and dataset card.
```

B-007 可以标为 `verified`：已经能从 NAS 日志、探针、文档索引、浏览器截图、ROS 数据集和 dataset card 生成 Markdown 实验报告。

## Remaining Work Without User Approval

- 继续做 NAS-backed `baseline_status_probe` 汇总。
- 继续补 B-003 图片 metadata caption 到 NAS。
- 继续补 B-010 security audit 到 NAS。

## Deferred Because It Needs External/User Action

- A-006 Docker/Podman/runc sandbox runtime 选择。
- 飞书 contact scope `99991672` 权限申请。
- 长时间 ROS bag 采集策略和保留周期。
