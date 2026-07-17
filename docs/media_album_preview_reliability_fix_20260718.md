# 相册缩略图与原图预览可靠性修复（2026-07-18）

## 基线与问题

- 修改基线：2026-07-09 版本提交 `9d57e1ec`。
- S100P 媒体库只读核对：101 张图片均为有效 RGB JPEG，文件存在，真实 MIME 与扩展名一致。
- 当天预览访问日志中的 `/api/media/preview` 请求均为 HTTP 200，因此问题不属于文件缺失、权限 404 或错误 MIME。
- 7.9 前端把相册网格中的原图全部读取为 Blob 并常驻缓存。当前 101 张图片压缩体积合计约 12.23 MB，但浏览器按 RGBA 解码后约占 377.3 MB；其中最大图片为 6000×3376，单张解码约 81 MB。
- 旧前端在图片解码失败时没有 `onerror`/解码验证，也会把尚未成功解码的对象 URL 当成可用原图交给查看器，表现为部分缩略图一直不显示，双击后仍为空白。

## 修复

- 相册、AI 相册和助手搜图卡片改用 `variant=thumbnail` 预览。
- 服务端用 Pillow 按 EXIF 方向生成最长边 480 px 的浏览器安全缩略图；Pillow 不可用或转换失败时保留原始预览兼容路径。
- 缩放滤镜同时兼容 S100P 的 Pillow 9.0.1（`Image.LANCZOS`）和新版 Pillow（`Image.Resampling.LANCZOS`）。首次板端验收发现旧版属性不存在并触发原图回退，后续补丁据此加入双版本选择。
- 大图查看器继续读取原图，不复用网格缩略图。
- 前端在缓存 Blob 前检查非空图片 MIME，在显示前执行浏览器解码验证；失败时清理缓存并自动重试一次。
- 相册列表、相册详情和摘要按同一个预览 ACL 过滤，避免页面列出调用者无法读取的图片。

## 本地验证

- `python -m py_compile scripts/probes/ai_nas_media.py scripts/probes/ai_nas_operator_portal_server.py`
- `python -m pytest -q tests/test_copilot_local_qwen_chat.py`：48 项及 8 个 subtests 通过。
- `python -m pytest -q`：238 项及 11 个 subtests 通过；同时覆盖助手身份快路径、日期文档检索、
  云端失败回落和相册预览 ACL，防止相册修复再次覆盖 AI 助手编排。
- `node --check web/static/digua_ai_nas_v2.js`：通过。
- Media Center gate：12/12 通过，结论 `ok_nas_media_center_gate`。
- 真实 7.9 本机页面：两张缩略图均为 480×280、`complete=true`、`hidden=false`；双击后的原图为 720×420、`complete=true`；页面无 warning/error。

## 集成回归与最终生产验收

- PR #72 首次合并后发现 Pillow 9.0.1 兼容问题；后续预览分支虽修复缩放滤镜，却基于
  `codex/rollback-to-20260709` 部署了整份旧门户文件，覆盖了当天已验收的 AI 助手自动路由、
  身份快路径和日期文档检索。实机表现为“你是谁”也可能被错误送往云端并收到 401。
- [PR #77](https://github.com/zhexuexiaotudou/-agent-s100-/pull/77) 将相册修复重新移植到当前
  `main`，保留大文件流式传输、现代媒体 ACL、AI 助手自动编排和前端异步详情展示。合并提交为
  `5a56931644ac987ce33227510541b9b2d99d8de3`；4 项 GitHub Actions 全部通过。
- 2026-07-18 07:12 CST 部署到 `sunrise@192.168.127.10` 的用户级门户
  `openclaw-gateway.service`（回环 `127.0.0.1:8765`）。线上后端、媒体模块和前端 JS 的
  SHA-256 分别为 `23963ba3475bd29d16b45a0083035da0a9a8c3eda1d7088167acd1d6b2adfa4a`、
  `6bb2590bd4ffef0807cc999f79a9a162c50e42e19ae785f3efed2d3704b54ae4` 和
  `8e599aafb36729b48c45932d91c406707e8747052b2207ad1b213cfe5f7ba410`。
- 实机媒体列表返回 5 张可见图片；首张的 `variant=thumbnail` 请求为 HTTP 200、`image/jpeg`、
  29,230 bytes。实机助手同时复测身份确定性回答、本地 5 月 20 日日记检索和 MiniMax
  `cloud_overflow_chat`，均返回 HTTP 200；浏览器 `/ui` 登录后提交“你是谁”也显示正确本地身份。
- 回滚点：`/mnt/nas/openclaw/deployment/backups/restore-assistant-5a569316-20260718-071038`。
