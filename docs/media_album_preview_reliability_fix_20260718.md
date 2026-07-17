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
- 大图查看器继续读取原图，不复用网格缩略图。
- 前端在缓存 Blob 前检查非空图片 MIME，在显示前执行浏览器解码验证；失败时清理缓存并自动重试一次。
- 相册列表、相册详情和摘要按同一个预览 ACL 过滤，避免页面列出调用者无法读取的图片。

## 本地验证

- `python -m py_compile scripts/probes/ai_nas_media.py scripts/probes/ai_nas_operator_portal_server.py`
- `python -m unittest tests.test_copilot_local_qwen_chat`：23/23 通过。
- `node --check web/static/digua_ai_nas_v2.js`：通过。
- Media Center gate：12/12 通过，结论 `ok_nas_media_center_gate`。
- 真实 7.9 本机页面：两张缩略图均为 480×280、`complete=true`、`hidden=false`；双击后的原图为 720×420、`complete=true`；页面无 warning/error。

## 尚未完成的交付门

- PR CI、合并、S100P 部署和板端 101 张图片的生产页面复验仍待后续门完成；本记录不把本地验证写成板端已部署事实。
