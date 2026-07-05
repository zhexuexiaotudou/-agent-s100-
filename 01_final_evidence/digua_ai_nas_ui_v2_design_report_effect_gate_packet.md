# Digua AI-NAS UI v2 design report effect gate packet

- verdict: `B_ready_on_temp_service_default_8765_rollout_pending_operator_approval`
- ok: `True`
- live url: `http://127.0.0.1:8767/ui`
- production 8765 rollout: `not performed`
- report_count: `51`
- document retrieval: `sqlite_fts_first`, embedding=`False`, cloud=`False`
- playwright screenshots: `5` desktop, `2` mobile

## Verification

- `py -m py_compile` changed Python files: passed
- bundled Node `--check` UI JS: passed
- S100P `bash -n` service scripts: passed
- `py -m pytest tests -q`: 74 passed
- `SELF_CHECK.py`: passed
- root `pytest -q`: not used as pass/fail because existing `tmp/` packages and hardware probes break collection.

## Known Differences

- 当前实测文件管理页展示真实 NAS Personal root 路径和文件夹，不再使用 mockup 示例文件名。
- 文档问答为 SQLite FTS-first 本地召回，未声明完整 embedding RAG。
- 生产 8765 默认服务未切换；验证使用 18766 远端临时服务和本机 8767 tunnel。
- SQLite 库存索引文件当前 degraded，但页面/API 已按只读降级处理，operation log 使用独立 DB。

## Next Steps

- 获得操作者批准后再用 enable_ui_v2_default_service.sh 切换生产 8765。
- 将 report 列表按类型和时间做服务端分页，避免大 evidence root 时首次扫描变慢。
- 补充 DOCX/PDF 更完整文本抽取和可选 embedding feature flag。
- 把 tmp 历史打包目录排除出默认 pytest collection。
