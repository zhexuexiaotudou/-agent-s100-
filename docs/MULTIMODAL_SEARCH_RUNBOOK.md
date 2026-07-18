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

For image queries, `top_k` only controls how many candidates may be evaluated.
It must not be used as an expected result count. Inspect `relevance_policy` in
the response and accept the dynamic `selected_count`, including zero.

## Assistant image relevance smoke

After deploying the portal and multimodal search files, authenticate through
the normal local identity flow and submit these assistant prompts as UTF-8 JSON:

| Prompt | Expected route and invariant |
| --- | --- |
| `找出有花或者有建筑的照片` | `local_multimodal_search`; result count equals `relevance_policy.selected_count`, is not padded to eight, and retained previews visibly contain a flower or building/city scene |
| `找出月球基地里的紫色潜艇照片` | `local_multimodal_search`; zero results with `unsupported_chinese_visual_concept` |
| `找出有人的照片` | `local_yolo_search`; person results still come from `yolo_object_index` |

On Windows PowerShell, pass `[Text.Encoding]::UTF8.GetBytes($json)` as the
request body. Older PowerShell may otherwise send Chinese JSON with the wrong
encoding and create a false routing failure. Confirm the server-side prompt
hash against the intended UTF-8 text before diagnosing an assistant routing
regression.

Production deployment must preserve exact file parity for the portal script,
feature flags, planner, retriever, and search API. Compare SHA-256 hashes before
restarting `openclaw-gateway.service`; an active service alone does not prove
that all relevance-policy files were replaced.

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
- If an image query returns the candidate cap or unrelated images below the
  configured gates, hold as `hold_due_to_image_relevance_policy_failure`.
- If raw paths, cloud usage, biometric inference, or Qwen execution authority appear, hold as `hold_due_to_security_boundary_violation`.
