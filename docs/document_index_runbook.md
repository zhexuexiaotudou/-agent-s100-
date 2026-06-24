# 文档索引 Runbook

本文用于推进 B-002：对 NAS 文档生成索引和基础摘要，先做轻量、可审计的文本文件索引。

## 目标

第一版只索引文本类文件：

```text
.md .txt .json .yaml .yml .csv
```

暂不在第一版解析 Office、PDF、图片 OCR。复杂文件后续可以走单独任务。

## 执行入口

通过白名单 runner 执行：

```bash
scripts/run_allowlisted_tool.sh index_documents /mnt/nas/openclaw/documents /mnt/nas/openclaw/reports
```

NAS 未挂载时，可先用 `/tmp` 做 smoke test：

```bash
scripts/run_allowlisted_tool.sh index_documents /tmp/openclaw-doc-test /tmp/openclaw-probe-test
```

OpenClaw Gateway 已接入 `s100p-allowlisted-tools` 插件后，也可以通过窄工具入口执行：

```text
s100p_run_probe tool_id=index_documents
```

该插件路径固定读取 `/root/.openclaw/workspace/documents`，固定写入 `/root/.openclaw/workspace/reports`，不接受任意 shell 或任意路径。

## 输出

输出文件形如：

```text
document_index_YYYYmmdd-HHMMSS.md
```

内容包括：

- 相对路径。
- 文件大小。
- 修改时间。
- SHA256。
- 前 160 字符 preview。

## 安全边界

- 输入目录只允许 `/tmp/*`、`/mnt/nas/openclaw/documents` 或 `/root/.openclaw/workspace/documents`。
- 输出目录只允许 `/tmp/*`、`/mnt/nas/openclaw/reports`、`/mnt/nas/openclaw/logs/probes/*`、`/root/.openclaw/workspace/reports` 或 `/root/.openclaw/workspace/logs/probes/*`。
- 不读取 `/root`、`/home`、`/mnt/nas` 根目录或 NAS 其他共享。
- 不写入源文档目录。

## 验收

```bash
bash -n scripts/probes/index_documents.sh
bash scripts/run_allowlisted_tool.sh index_documents /tmp/openclaw-doc-test /tmp/openclaw-probe-test
```

成功判据：

- 生成 `document_index_*.md`。
- 报告里包含 `indexed_files`。
- 报告包含示例文档的相对路径、SHA256 和 preview。
- 输入 `/root` 必须被拒绝。

## 2026-05-27 验证记录

在 S100P 板端通过临时 HTTP 只读服务拉取当前脚本后执行 smoke test：

```text
MANIFEST_INDEX_OK
REPORT=/tmp/openclaw-probe-test/document_index_20260527-025409.md
# Document Index
- indexed_files: 2
| Path | Size | Modified | SHA256 | Preview |
| `alpha.md` | 58 | ... | `f5f28215419910f268ccdb13a3656e1781e5f9b6331dd1ef5f6a2a22f1aa3fda` | # Alpha This is the first OpenClaw document for indexing. |
| `sub/beta.txt` | 38 | ... | `19de2e3402e464a80f25887bc4aeadceb6dbca8ebb16628d39e38269972c98fa` | Beta note for S100P and NAS baseline. |
Refusing input path outside approved document directories: /root
INDEX_DOCUMENTS_OK
```

验证覆盖：

- `index_documents` 已在 `scripts/tool_allowlist.json` 中登记。
- `scripts/probes/index_documents.sh` 语法检查通过。
- 示例 Markdown 和 TXT 文件能生成索引。
- 报告包含 `indexed_files`、相对路径、SHA256 和 preview。
- 非批准输入路径 `/root` 被拒绝。

## 2026-05-27 OpenClaw 插件验证记录

NAS 尚未挂载时，先用 `/root/.openclaw/workspace` 作为本地 fallback 工作区。通过 OpenClaw agent 的真实工具调用执行：

```text
toolCall name: s100p_run_probe
arguments: {"tool_id":"index_documents"}
report: /root/.openclaw/workspace/reports/document_index_20260527-034707.md
indexed_files: 2
input: /root/.openclaw/workspace/documents
```

报告索引了两个 fallback 文件：

```text
baseline-note.md
robot-log.txt
```

这证明 B-002 的文档索引链路已经能通过 OpenClaw 窄插件入口执行。NAS 路径 `/mnt/nas/openclaw/documents` 的验收仍等待 NAS 挂载完成后复测。
