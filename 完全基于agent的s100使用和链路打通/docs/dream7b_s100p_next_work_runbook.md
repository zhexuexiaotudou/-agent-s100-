# Dream7B S100P Next Work Runbook

This is the execution path for the next report and demo cycle.

## 1. Performance And Identity

Run on S100P:

```bash
cd /root/.openclaw/workspace
python3 scripts/probes/dream7b_perf_identity_probe.py \
  --base-url http://127.0.0.1:18888 \
  --model Dream7B-S100P-local
```

Required report fields:

- `preflight.model_id_confirmed=true`
- `summary.failed_case_count=0`
- `summary.ttft_ms`
- `summary.prefill_tokens_per_s`
- `summary.decode_tokens_per_s`
- generated response text for the self-introduction prompt

Interpretation rule: if `stream_supported_case_count=0`, treat `ttft_ms` as first response byte / non-stream upper bound, not native token streaming.

## 2. Resident Gateway Demo

Preflight:

```bash
dream7b-default-status
systemctl is-active dream7b-bpu-batch-queue.service
XDG_RUNTIME_DIR=/run/user/0 systemctl --user is-active dream7b-local-openai-gateway.service
XDG_RUNTIME_DIR=/run/user/0 systemctl --user is-active openclaw-gateway.service
curl -s http://127.0.0.1:18888/health
curl -s http://127.0.0.1:18789/health
```

Narrative: S100P is the always-on local intelligence gateway. NAS remains storage; Dream7B and OpenClaw provide local reasoning and audited tools.

## 3. OpenClaw AI-NAS Demo

Use fixed tool IDs:

```bash
scripts/probes/ai_nas_allowlisted_tool.sh ai_nas_personal_inventory
scripts/probes/ai_nas_allowlisted_tool.sh ai_nas_file_search "2024 renovation invoice"
scripts/probes/ai_nas_allowlisted_tool.sh ai_nas_case_packet "2024 renovation payment contract invoice receipt chat screenshot"
scripts/probes/ai_nas_allowlisted_tool.sh ai_nas_folder_rag Documents "What payment dates and amounts are in this folder?"
scripts/probes/ai_nas_allowlisted_tool.sh ai_nas_duplicate_report
scripts/probes/ai_nas_allowlisted_tool.sh ai_nas_movie_sort_enhanced
```

Acceptance: every action writes Markdown/JSON evidence, keeps source files unchanged, and reports no delete/no move/no overwrite.

## 4. Edge + Cloud Router Demo

Run:

```bash
python3 scripts/probes/ai_nas_edge_cloud_router_probe.py
```

Optional live local classifier:

```bash
python3 scripts/probes/ai_nas_edge_cloud_router_probe.py --use-dream-classifier
```

Demo cases:

- simple local task -> `route=local`
- private NAS/photo/invoice task -> `route=local`
- non-private complex market/story task -> `route=cloud` dry-run

Acceptance: `privacy_query_sent_to_cloud=false`.

## 5. Release Package

Include:

- `scripts/probes/dream7b_perf_identity_probe.py`
- `scripts/probes/ai_nas_edge_cloud_router_probe.py`
- `scripts/probes/ai_nas_allowlisted_tool.sh`
- `configs/systemd/*.service`
- `docs/community/dream7b-s100-bpu-deploy/SKILL.md`
- latest benchmark and AI-NAS reports

Do not include private NAS contents, keys, tokens, account names, raw personal logs, or oversized generated artifacts.

