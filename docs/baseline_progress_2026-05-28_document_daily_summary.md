# Baseline Progress: B-002 NAS Document Daily Summary

Date: 2026-05-28

本文记录 B-002 从“NAS 文档索引”继续推进到“NAS 文档每日摘要”。该摘要是 deterministic
metadata summary，不调用外部模型，不读取 token，不依赖用户审批。

## Implementation

新增探针：

```text
scripts/probes/document_daily_summary_probe.sh
```

白名单入口：

```bash
scripts/run_allowlisted_tool.sh document_daily_summary_probe \
  /mnt/nas/openclaw/documents \
  /mnt/nas/openclaw/reports/daily-summary
```

同时更新：

```text
scripts/run_allowlisted_tool.sh
scripts/tool_allowlist.json
openclaw-plugins/s100p-allowlisted-tools/index.js
docs/tool_allowlist.md
```

## Runtime Evidence

输出：

```text
/mnt/nas/openclaw/reports/daily-summary/document_daily_summary_20260528-184329.md
/mnt/nas/openclaw/reports/daily-summary/document_daily_summary_20260528-184329.json
```

关键字段：

```text
documents_dir: /mnt/nas/openclaw/documents
mode: deterministic file metadata summary; no external model used
Total documents: 1
Modified last 24h: 1
Total bytes: 4649
Top directory: baseline_reports
File type: .md
```

最新文档：

```text
baseline_reports/baseline_progress_2026-05-28_nas_backed_reports.md
sha256: eca40c04fd0930622e238ad3a931c119be88b52c2cdbab704f16b677306d1fdc
```

## Runner Validation

正向：

```text
document_daily_summary_probe  Read-only deterministic daily document summary
REPORT=/mnt/nas/openclaw/reports/daily-summary/document_daily_summary_20260528-184329.md
```

负向：

```text
Refusing input path outside approved document directories: /root
Tool is not allowlisted: ../../etc/passwd
```

## Updated Reports

Experiment report:

```text
/mnt/nas/openclaw/reports/experiments/experiment_report_20260528-184444.md
Document indexes: 1
Document daily summaries: 1
```

Baseline roll-up:

```text
/mnt/nas/openclaw/reports/baseline-status/baseline_status_20260528-184444.md
Allowlisted tool count: 20
Document daily summaries: 1
B-002: NAS-backed document index and daily summary exist
```

## Baseline Impact

- B-002 can move to `verified` for the deterministic metadata-summary baseline.
- Semantic/LLM daily summaries can be added later if needed, but the current DoD
  of NAS document index plus daily summary is satisfied.
