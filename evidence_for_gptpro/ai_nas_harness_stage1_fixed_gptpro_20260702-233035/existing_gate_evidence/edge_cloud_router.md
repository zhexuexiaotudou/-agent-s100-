# AI-NAS Edge Cloud Router

- verdict: `ok_ai_nas_edge_cloud_router`
- generated_at: `2026-07-02T22:49:43.375656+08:00`
- qwen_classifier_enabled: `False`
- qwen_structured_json_required: `True`
- execute_cloud: `True`
- cloud_endpoint_kind: `controlled_cloud_endpoint`
- route_counts: `{'local': 2, 'cloud': 1}`
- classifier_counts: `{'policy_only_qwen_disabled': 3}`
- cloud_call_count: `1`
- privacy_query_sent_to_cloud: `False`
- failures: `[]`

## Audit Events

- `simple_local` route `local` privacy `high` complexity `simple` classifier `policy_only_qwen_disabled` local_tool `ai_nas_case_packet` reason `privacy-sensitive query must stay on device`
- `privacy_local` route `local` privacy `high` complexity `simple` classifier `policy_only_qwen_disabled` local_tool `ai_nas_case_packet` reason `privacy-sensitive query must stay on device`
- `complex_cloud` route `cloud` privacy `none` complexity `complex` classifier `policy_only_qwen_disabled` local_tool `None` reason `non-private complex query can be sent to cloud for broader reasoning`

## Guardrail

- The original user query is sent to the local Qwen gateway before routing.
- Structured Qwen JSON is the primary route signal when available.
- Policy is used only as a privacy guardrail or fallback after Qwen structured-output failure.
- Privacy-sensitive queries are never sent to cloud in this probe.
- `--use-local-cloud-stub` starts a controlled HTTP endpoint for cloud-call acceptance without external credentials.
