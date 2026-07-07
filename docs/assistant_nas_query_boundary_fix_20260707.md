# AI 助手 NAS 查询边界修正记录

日期：2026-07-07

## 背景

用户在 AI 助手中询问 NAS 内图片、视频、文档信息时，页面只返回本地索引 0 结果，并显示“未调用云端，也没有让 Qwen 直接访问或执行 NAS 工具”。这句话本意是安全边界：Qwen 不直接获得 NAS 工具执行权；但产品体验上容易被理解为系统没有查询 NAS。

## 修正边界

- 保持 `qwen_execution_authority=false`：Qwen 只做意图理解和建议。
- NAS 查询由 OpenClaw 本地受控 API 执行，并继续走 ACL、只读、未上云边界。
- “图片/视频/文档信息、情况、概况、统计”类请求优先进入 `local_storage_inventory`，而不是普通聊天或文档 RAG。
- “找出有人的图片”仍先走本地对象/多模态索引；如果索引 0 命中，继续做对应目录的只读 inventory fallback，明确展示 NAS 目录中实际有哪些可见文件。

## 修改

- `scripts/probes/ai_nas_operator_portal_server.py`
  - 新增 inventory 触发词：信息、情况、概况。
  - 新增 `copilot_inventory_path_for_message`：单问图片/视频/文档时定位到 `Photos`、`Videos`、`Documents`；混合查询时盘点个人空间根目录。
  - 调整意图优先级：信息/统计/概况类问题先走 storage inventory，不被 document query 抢走。
  - 本地搜索空结果时新增 `fallback_inventory`，并在 audit 中记录 `read_only_inventory_fallback=true`。

- `web/static/digua_ai_nas_v2.js`
  - 搜索 0 结果且存在 `fallback_inventory` 时，继续渲染“文件盘点”结果卡片。
  - 空结果提示改为“索引未命中，已继续做 NAS 只读盘点”。

## 实机验收

运行环境：

- S100P host: `sunrise@192.168.127.10`
- Service: `openclaw-gateway.service`
- UI: `http://127.0.0.1:8765/ui#assistant`
- Runtime server: `/mnt/nas/openclaw/scripts/probes/ai_nas_operator_portal_server.py`

部署与重启：

```text
scp scripts/probes/ai_nas_operator_portal_server.py sunrise@192.168.127.10:/mnt/nas/openclaw/scripts/probes/ai_nas_operator_portal_server.py
scp web/static/digua_ai_nas_v2.js sunrise@192.168.127.10:/mnt/nas/openclaw/web/static/digua_ai_nas_v2.js
systemctl --user restart openclaw-gateway.service
```

验收结果：

1. `查询nas里面的图片或者视频或者文档的一些信息`
   - `assistant_mode=local_storage_inventory`
   - `nas_action.operation=inventory`
   - 返回：顶层条目 9 个，文件 218 个，文件夹 63 个，主要类型含 TXT、Markdown、CSV、图片、照片、PDF。
   - `cloud_used=false`
   - `qwen_execution_authority=false`

2. `找出有人的图片`
   - `assistant_mode=local_yolo_search`
   - 索引结果：0
   - fallback：`fallback_inventory.ok=true`
   - fallback 路径：`Photos`
   - 返回：顶层条目 3 个，文件 37 个。
   - UI 显示“索引未命中，已继续做 NAS 只读盘点”以及“文件盘点”卡片。
   - `cloud_used=false`
   - `qwen_execution_authority=false`

## 当前边界

这次修正没有放开写权限，也没有允许 Qwen 直接执行 NAS 工具。正确产品语义是：

> Qwen 不直接访问或执行 NAS 工具；OpenClaw 网关在本地权限检查后使用受控只读 API 查询 NAS，并把查询证据展示给用户。

