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
- `python -m unittest tests.test_copilot_local_qwen_chat`：24/24 通过。
- `node --check web/static/digua_ai_nas_v2.js`：通过。
- Media Center gate：12/12 通过，结论 `ok_nas_media_center_gate`。
- 真实 7.9 本机页面：两张缩略图均为 480×280、`complete=true`、`hidden=false`；双击后的原图为 720×420、`complete=true`；页面无 warning/error。

## 生产交付结果

- PR #72 通过 2/2 CI 后合并为 `4be5b0c8`；Pillow 9 兼容跟进 PR #75 通过 CI 后合并为 `aad939da`。
- S100P 部署版本：`aad939da60a4f9be61098ae62a6ca6f92f4a1302`，`openclaw-gateway.service` 重启后为 `active`，回环与 LAN UI 入口均返回 HTTP 200。
- 板端 Pillow 9.0.1 直接函数验收：6000×3376 原图生成 480×270 JPEG，`transformed=true`。
- 对当前 101 张图片逐张请求 `variant=thumbnail`：101/101 HTTP 200 且可解码，失败 0，最长边不超过 480 px；缩略图总响应体约 3.17 MB。
- 抽查体积最大的 5 张原图：5/5 HTTP 200 且保持原始尺寸；6000×3376 大图未被查看器路径降采样。
- 实机查询 `找出踢足球的照片` 返回 8 个 `local_multimodal_search` 结果，8/8 预览均为当前 `/api/media/preview`，`preview_resolution=content_digest_relinked`，未降级、未上云。

## 部署与回滚

- 第一阶段部署前备份：`/mnt/nas/openclaw/reports/deploy_backups/20260718T0655_4be5b0c8_album_preview`。
- Pillow 9 跟进部署前备份：`/mnt/nas/openclaw/reports/deploy_backups/20260718T0700_aad939da_pillow9`。
- 三个运行文件和跟进服务文件均在替换前记录 SHA-256；回滚时从对应备份恢复并重启 `openclaw-gateway.service`。

## 已知边界

- 自动化验收直接使用受控门户服务 `127.0.0.1:8765` 的现有有效管理员会话。相同 Bearer 请求通过统一 80 端口时返回 401，属于外层入口认证/请求头策略差异，不是图片文件、缩略图或媒体 ACL 故障。
- 网关仍为 loopback-only，未扩大 NAS 或公网权限。
