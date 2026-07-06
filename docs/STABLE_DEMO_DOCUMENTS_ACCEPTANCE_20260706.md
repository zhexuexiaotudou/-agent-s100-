# Stable Demo Documents NAS Acceptance

Date: 2026-07-06

## Scope

Source package:

- `C:/Users/zhexu/Downloads/digua_stable_demo_documents.zip`
- SHA256: `dd243ce6197ab77a4b5c8380d27423a6c4d7e72a528be634958d99e9877d071d`
- Synthetic demo data only, per package README.

S100P environment:

- SSH target: `sunrise@192.168.127.10`
- NAS mount: `/mnt/nas/openclaw`
- Gateway tested through board-local `http://127.0.0.1:8765`
- Qwen health was checked through board-local `http://127.0.0.1:18080/health`

## NAS Placement

Primary extracted demo corpus:

- `/mnt/nas/openclaw/Personal/DemoDocs/digua_stable_demo_documents`

ACL-compatible document mirror:

- `/mnt/nas/openclaw/Personal/Documents/DemoDocs/digua_stable_demo_documents`

Auto Organizer staged upload samples:

- `/mnt/nas/openclaw/Personal/Uploads/stage_demo_docs`

The mirror was used because `DemoDocs/...` is not covered by the current
document read ACL. No ACL was expanded. The mirror operation was no-overwrite
and no-delete.

## Evidence

Local evidence copies:

- `reports/stable_demo_documents_20260706/stable_demo_documents_before_20260706-213942.json`
- `reports/stable_demo_documents_20260706/stable_demo_documents_ingest_20260706-214116.json`
- `reports/stable_demo_documents_20260706/stable_demo_documents_documents_mirror_20260706-134931.json`
- `reports/stable_demo_documents_20260706/stable_demo_documents_rebuild_20260706-215222.json`
- `reports/stable_demo_documents_20260706/stable_demo_documents_after_20260706-214533.json`
- `reports/stable_demo_documents_20260706/stable_demo_documents_after_documents_acl_20260706-215243.json`
- `reports/stable_demo_documents_20260706/stable_demo_documents_keyword_probe_20260706-215509.json`
- `reports/stable_demo_documents_20260706/stable_demo_documents_keyword_probe_20260706-215631.json`

Board-side originals remain under:

- `/mnt/nas/openclaw/reports/qwen25_ai_nas/`

## Results

Ingest:

- `copied_count=22`
- `skipped_existing_count=0`
- `ok=true`

ACL-compatible mirror:

- `copied_count=22`
- `skipped_existing_count=0`
- `mismatched_existing_count=0`
- `ok=true`

Index rebuild after adding the document mirror:

- `roots_count=6`
- `multimodal_indexed_assets=55`
- `multimodal_counts={"document": 19, "image": 36}`
- `text_chunks=10`
- `image_embeddings=36`
- `ai_space_asset_count=42`
- `smart_membership_count=817`
- `ok=true`

Auto Organizer on staged uploads:

- `plan_ok=true`
- `execute_ok=true`
- `rollback_verified=true`
- `item_count=3`
- `fallback_used=false`
- `resolution_source=ai_space+smart_naming+smart_classification`

Document RAG and OCR:

- Natural-sentence probe through `Documents/DemoDocs/...` grounded the
  `OpenClaw 周会` screenshot query and matched all 5 expected terms for that
  item.
- Keyword-style probe passed all 5 demo queries:
  `document_rag_ok_queries=5/5`, `ocr_ok_queries=5/5`,
  `document_rag_expected_term_hits=21`, `ocr_expected_term_hits=21`.

Recommended stable demo prompts:

- `发票 金额 日期 303.69`
- `合同 付款条款 30% 70% 3840 8960`
- `课程资料`
- `收据 128.80 校园文具店`
- `OpenClaw 周会 S100P Qwen AI Space Auto Organizer Demo`

## Demo Impact

This corpus improves the demo when used through the authorized
`Documents/DemoDocs/...` mirror:

- AI Space has more visible document and image assets.
- Auto Organizer can show an AI-index based plan, execution, and rollback on
  neutral upload names.
- Document RAG and OCR can answer invoice, contract, course, receipt, and
  meeting-screenshot examples with grounded evidence when the prompt uses
  stable keywords.

## Boundary

Do not present broad natural-language document questions as fully stable yet.
The current SQLite FTS path is sensitive to Chinese tokenization. For example,
separate terms such as `电机学`, `变压器`, and `相量图` did not directly match
the course note, while `课程资料` did retrieve the course note and its expected
content. The demo script should use the stable prompts above unless the query
tokenization strategy is improved.
