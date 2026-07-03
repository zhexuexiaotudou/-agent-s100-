# Dream7B S100P Evidence Snapshot

Date: 2026-06-18

## Service Preflight

S100P host: `ubuntu`

`dream7b-default-status` reported:

- `dream7b-bpu-batch-queue.service`: active / enabled
- `segment_major_24x256_default`: `True`
- latest soak: `avg_bpu=93.037`, `failed_jobs=0`
- latest telemetry: `avg_bpu=93.014`, `failed_jobs=0`
- OpenClaw model: `dream7b-local/Dream7B-S100P-local`
- base URL: `http://127.0.0.1:18888/v1`

Gateway checks:

```json
{"ok": true, "model": "Dream7B-S100P-local", "backend": "dream7b-text"}
```

`/v1/models` listed `Dream7B-S100P-local`.

## Performance And Identity Probe

Report:

```text
/mnt/nas/openclaw/reports/ai_nas_mvp/dream7b_perf_identity_20260618-120209-292585/dream7b_perf_identity.json
```

Summary:

- verdict: `ok_dream7b_perf_identity`
- model_id_confirmed: `True`
- failed_case_count: `0`
- TTFT method: first response byte for the current non-stream gateway, so this is an upper bound rather than native token streaming.
- TTFT ms: min `222.695`, avg `34325.965`, p50 `37331.411`, p95 `54905.143`
- prefill tokens/s estimate: avg `12.867`, p50 `0.404`, p95 `50.399`
- decode tokens/s estimate: avg `33.586`, p50 `0.402`, p95 `133.081`

Self-introduction response:

```text
Hello! I'm Dream Dream7 model. How can I assist you today
```

The response object model was `Dream7B-S100P-local`.

## Edge Cloud Router Probe

Report:

```text
/mnt/nas/openclaw/reports/ai_nas_mvp/edge_cloud_router_20260618-120517-950987/edge_cloud_router.json
```

Summary:

- verdict: `ok_ai_nas_edge_cloud_router`
- route_counts: `{'local': 2, 'cloud': 1}`
- privacy_query_sent_to_cloud: `False`
- failures: `[]`

Demo routes:

| Query ID | Route | Privacy | Complexity | Local tool |
| --- | --- | --- | --- | --- |
| `simple_local` | `local` | `high` | `simple` | `ai_nas_case_packet` |
| `privacy_local` | `local` | `high` | `simple` | `ai_nas_case_packet` |
| `complex_cloud` | `cloud` | `none` | `complex` | `None` |

## Dispatcher Checks

S100P allowlisted dispatcher accepted:

```bash
scripts/probes/ai_nas_allowlisted_tool.sh ai_nas_edge_cloud_router
scripts/probes/ai_nas_allowlisted_tool.sh dream7b_perf_identity --mock
```

Windows-side Bash dispatcher validation was not possible because the local WSL image lacks `/bin/bash`; S100P/Linux validation passed.

