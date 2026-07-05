# Multimodal Search v1 Runbook

Date: 2026-07-05

## Local Test

```powershell
py -3 -m pytest tests\test_multimodal_search_v1.py -q
py -3 -m pytest tests -q
py -3 SELF_CHECK.py
```

## API Smoke

The route adapter supports these local API paths:

- `GET /api/multimodal-search/status`
- `POST /api/multimodal-index/rebuild`
- `GET /api/multimodal-index/stats`
- `GET /api/multimodal-index/item/{asset_id}`
- `POST /api/multimodal-search/query`
- `POST /api/multimodal-search/eval/run`
- `GET /api/multimodal-search/eval/summary`

The default rebuild payload is:

```json
{"max_files": 5000}
```

The default query payload is:

```json
{"query": "invoice", "modality": "document", "top_k": 10}
```

## S100P Preconditions

Before S100P operation, confirm:

- Host/IP/user: `sunrise@192.168.127.10` unless the current deployment notes say otherwise.
- OpenClaw service is reachable only on the intended local/private route.
- The indexed root is allowlisted and does not give OpenClaw access to the whole NAS.
- Feature flags keep cloud, biometric, Qwen execution, and destructive actions disabled.

## Failure Paths

- If image embedding dependency is unavailable, hold as `hold_due_to_image_embedding_model_unavailable` unless the release is explicitly downgraded.
- If vector store creation/search fails, hold as `hold_due_to_vector_store_failure`.
- If API routes fail, hold as `hold_due_to_search_api_failure`.
- If UI contract or rendered validation fails, hold as `hold_due_to_ui_validation_failure`.
- If raw paths, cloud usage, biometric inference, or Qwen execution authority appear, hold as `hold_due_to_security_boundary_violation`.
