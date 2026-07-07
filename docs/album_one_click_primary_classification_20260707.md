# 相册一键主分类整理验收记录（2026-07-07）

## 目标

相册入口不再区分普通相册和 AI 相册。网页端每次打开相册时读取本地 NAS 图片索引和主分类整理状态，显示：

- 总图片数
- 已整理数
- 待整理数
- 主分类分布
- 一键整理按钮

一键整理只处理没有主分类的图片；已经有主分类的图片跳过。强制重分类只用于验收或管理员维护，不作为普通页面默认动作。

## 主分类集合

本次将相册图片收敛为 8 个互斥主类，每张图片只保留一个相册主分类：

1. 人物生活
2. 动物
3. 自然风景
4. 城市建筑
5. 交通工具
6. 食物饮品
7. 文档截图
8. 其他图片

识别顺序：

1. 优先使用已有 YOLO / 人物属性 / 标题或摘要证据。
2. 如果 S100P 本地 CLIP 网关可用，使用本地 CLIP 文本-图片相似度。
3. 如果没有可用视觉语义证据，归入“其他图片”，并在结果里标记为 fallback。

## 代码路径

- `scripts/probes/ai_nas_operator_portal_server.py`
  - 新增 `GET /api/ai-album/organize-status`
  - 新增 `POST /api/ai-album/organize-now`
  - 新增 8 类相册主分类常量和一图一类写入逻辑
  - 接入本地 `ai_nas_embedding_adapter.py` + 18182 CLIP 网关
- `src/smart_classification/service.py`
  - `rebuild()` 保留 `preserve_memberships_on_rebuild` 分类 membership
  - 避免智能分类重建抹掉相册主分类结果
- `web/static/digua_ai_nas_v2.js`
  - 相册页改为主分类状态优先
  - 新增一键整理按钮和整理状态面板
  - 预览图改成首屏优先 + IntersectionObserver 懒加载
- `web/static/digua_ai_nas_v2.css`
  - 新增相册整理状态面板样式
- `web/ai_nas_desktop_v2.html`
  - 静态资源版本更新为 `20260707-album-organize2`

## S100P 实机环境

- SSH: `sunrise@192.168.127.10`
- Web portal: `http://127.0.0.1:8765/ui#media`
- Portal PID: `1850054`
- CLIP gateway PID: `1844230`
- CLIP endpoint: `http://127.0.0.1:18182/embed`
- CLIP model: `/mnt/nas/openclaw/models/ai_nas_clip_vit_base_patch32`
- Report root: `/mnt/nas/openclaw/reports/qwen25_ai_nas`
- Personal root: `/mnt/nas/openclaw/Personal`

## 验收结果

本次对 100 张 NAS 图片执行强制主分类重排，全部走本地 CLIP：

```json
{
  "processed_count": 100,
  "method_counts": {
    "clip_similarity": 100,
    "fallback_other": 0,
    "evidence_rules": 0
  },
  "organized_count": 100,
  "pending_count": 0,
  "categories": {
    "人物生活": 15,
    "动物": 9,
    "自然风景": 27,
    "城市建筑": 11,
    "交通工具": 25,
    "食物饮品": 4,
    "文档截图": 6,
    "其他图片": 3
  }
}
```

网页端实机验证：

- 相册页显示 `总图片 100`
- 相册页显示 `已整理 100`
- 相册页显示 `待整理 0`
- 分类 chips 显示 8 个主类及计数
- 图片卡片显示大小、时间、主分类标签，不显示文件名
- 控制台无应用 error/warn
- 预览图不再一次性请求全部 100 张，改为首屏和滚动懒加载

## 边界

- 本功能只写智能分类 membership，不移动、不重命名、不删除图片文件。
- 18182 CLIP 网关是本地 S100P 服务；未启用云视觉。
- 如果 CLIP 网关不可用，一键整理仍可完成，但证据不足的图片会归入“其他图片”，并在 `method_counts.fallback_other` 中体现。
- 当前分类是主类整理，不做人脸识别、身份识别或敏感属性推断。
