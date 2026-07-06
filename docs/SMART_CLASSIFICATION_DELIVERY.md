# Smart Classification Delivery

Smart Classification creates virtual collections. It does not move, delete, or
rename original files.

API:

- `GET /api/smart-classification/status`
- `POST /api/smart-classification/categories`
- `GET /api/smart-classification/categories`
- `POST /api/smart-classification/rebuild`
- `GET /api/smart-classification/category/<category_id>/items`
- `POST /api/smart-classification/category/<category_id>/materialize-copy-plan`

UI:

- `/smart-classification`

Physical organization must go through:

```text
smart category -> proposed copy plan -> preview -> dry-run -> typed approval -> execute via Harness -> rollback manifest
```

Gate:

```bash
python3 gates/stage7_smart_classification_gate.py \
  --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas \
  --personal-root /mnt/nas/openclaw/Personal
```
