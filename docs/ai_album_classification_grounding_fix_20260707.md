# AI 相册分类 grounding 修正记录

日期：2026-07-07

## 问题

AI 相册页面把同一批 4 张图片同时显示在“人物/服装、票据、合同、资料、宠物、车辆、红色衣服、白色上衣”等多个分类下。用户指出这些图明显不符合这些分类。

经实测确认，问题不是用户查询方式，而是分类实现存在假阳性：

- `src/smart_classification/rule_engine.py` 把 `modalities=["image"]` 当作命中证据，因此所有图片都会命中允许 image 的分类。
- `match_rule` 把旧的 `category_names` 放进匹配文本中，导致错误分类在重建后继续自我污染。
- `SmartClassificationService.rebuild()` 先重建 AI Space，再清理/写入 smart memberships，导致 AI Space 参与分类时带着上一轮错误分类。
- Stage 11 gate 只验证分类 UI 能显示，没有验证分类是否有真实证据。

## 修正

- 模态现在只作为过滤条件，不作为分类证据。
- 分类规则不再读取 `category_names`，避免循环污染。
- smart classification rebuild 顺序改为：
  1. ensure defaults
  2. 清空旧 memberships
  3. 重建无分类污染的 AI Space
  4. 基于 object/person/title/OCR/transcript 等证据写入 memberships
  5. 再重建 AI Space，让正确分类回写到 asset views
  6. 生成智能命名
- 旧的 system 内置残留分类会被禁用，`categories()` 只返回 enabled 分类。
- AI 相册侧栏只展示 item_count > 0 的智能分类。
- Stage 11 gate 增加：
  - 非“待整理”分类不能全量吞掉所有素材。
  - 无 object/person 证据的 asset 不能声明人物、服装、宠物、车辆、票据、合同、课程等标签。

## S100P 实机结果

运行环境：

- Host: `sunrise@192.168.127.10`
- UI: `http://127.0.0.1:8765/ai-album`
- Service: `openclaw-gateway.service`
- Runtime path: `/mnt/nas/openclaw`

部署后执行：

```text
POST /api/smart-classification/rebuild
```

重建结果：

- `inserted_memberships=4`
- `membership_count=4`
- `hit_category_count=1`
- 唯一命中分类：`待整理=4`
- `人物照片=0`
- `白色上衣=0`
- `红色衣服=0`
- `宠物动物=0`
- `车辆交通=0`
- `票据发票=0`
- `合同资料=0`

AI Space asset 结果：

- 4 个 asset 均为 `modality=image`
- `object_labels=[]`
- `person_attrs=[]`
- `category_names=["待整理"]`

Person / YOLO 查询结果：

- `/api/yolo-index/status`
  - `backend.available=true`
  - `indexed_count=2`
  - `detection_count=0`
  - `degraded_reason=no_yolo_detections_indexed`
- `/api/yolo-index/search` query `person`
  - `results=0`
  - `degraded_reason=no_matching_yolo_detection`
- `/api/person-attribute/status`
  - `person_detection_count=0`
  - `attribute_count=0`
  - `degraded_reason=person_attributes_missing`
- `/api/person-attribute/search` query `找出有人的图片`
  - `results=0`
  - `degraded_reason=no_matching_person_attribute`

Browser UI 验收：

- 分类侧栏只显示：
  - `全部分类 4`
  - `待整理 4`
- Tabs:
  - `全部 4`
  - `照片 4`
  - `人物/服装 0`
  - `票据 0`
  - `合同 0`
  - `资料 0`
  - `视频 0`
- 4 张卡片标签均为：
  - `待整理`
  - `photo`

Gate:

- `reports/stage11_ai_album_ui_gate.json`
- Verdict: `ok_stage11_ai_album_ui_gate`
- `suspicious_full_categories=[]`
- `bad_evidence_free_asset_count=0`

## 当前产品解释

“查找有人的图片”查不到，是因为当前索引没有任何 `person` 检测结果或 person attribute 证据。系统现在不会再用“图片”这个模态本身冒充人物、服装、宠物、车辆或合同分类。

