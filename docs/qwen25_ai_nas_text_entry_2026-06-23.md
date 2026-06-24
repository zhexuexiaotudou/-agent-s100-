# Qwen2.5 AI-NAS Text Entry Deployment 2026-06-23

## Status

- Final display model: `Qwen2.5-1.5B-Instruct-S100P-official`
- Gateway service: `qwen25-local-openai-gateway.service`
- Gateway URL on S100P: `http://127.0.0.1:18080`
- OpenAI-compatible base URL: `http://127.0.0.1:18080/v1`
- Deployment state: `active` and `enabled` under `systemctl --user`
- AI-NAS route: Chinese natural-language request to OpenAI-compatible gateway, then allowlisted NAS tools, then Markdown/JSON evidence reports.

## Model Boundary

The requested priority HBM exists and was rechecked:

```text
/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/oellm_runtime/model/Qwen2.5_1.5B_Instruct_1024.hbm
```

Current 1024 runtime probe:

```text
/mnt/nas/openclaw/reports/models/s100_official_qwen_runtime_20260623-004222/official_qwen_runtime_probe.json
```

Result: the official 1024 HBM loads and initializes prefill/decode, but runtime completion is blocked by current S100P BPU/common-buffer allocation failure:

- `hbm_load_success_observed: true`
- `init_model_success_observed: true`
- `runtime_completed: false`
- `runtime_returncode: -11`
- `memory_alloc_failure_observed: true`

For the runnable local text entry, the active official Qwen2.5 profile is the previously validated 512/128 HBM:

```text
/mnt/nas/openclaw/models/s100-official-qwen-fullflow/cache_len_512_chunk_128/qwen2_5-1_5b_chunk_128_cache_512_q8.hbm
```

## Files Added

- `scripts/qwen25_openai_gateway.py`
- `scripts/probes/qwen25_ai_nas_acceptance_packet.py`
- `configs/qwen25_official_route_policy.json`
- `configs/qwen25_512_multichat_config.json`
- `configs/systemd/qwen25-local-openai-gateway.service`
- `docs/qwen25_ai_nas_text_entry_2026-06-23.md`

Remote deployment copies are under:

- `/mnt/nas/openclaw/scripts/qwen25_openai_gateway.py`
- `/mnt/nas/openclaw/scripts/probes/qwen25_ai_nas_acceptance_packet.py`
- `/mnt/nas/openclaw/configs/qwen25_official_route_policy.json`
- `/mnt/nas/openclaw/configs/qwen25_512_multichat_config.json`
- `/home/sunrise/.config/systemd/user/qwen25-local-openai-gateway.service`

## Run Commands

Service status:

```bash
systemctl --user status qwen25-local-openai-gateway.service --no-pager
```

Health:

```bash
curl -sS http://127.0.0.1:18080/health
```

Models:

```bash
curl -sS http://127.0.0.1:18080/v1/models
```

Chinese AI-NAS demo request:

```bash
curl -sS http://127.0.0.1:18080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"Qwen2.5-1.5B-Instruct-S100P-official","messages":[{"role":"user","content":"请在 NAS 中检索 2024 装修付款相关发票、合同、收据和聊天截图，生成摘要和 Markdown/JSON 证据报告。"}],"temperature":0,"max_tokens":256}'
```

Acceptance packet from Windows:

```powershell
py -3 scripts\probes\qwen25_ai_nas_acceptance_packet.py
```

## Final Evidence

Latest acceptance packet:

```text
/mnt/nas/openclaw/reports/models/qwen25_ai_nas_acceptance_20260623-004939/qwen25_ai_nas_acceptance.json
/mnt/nas/openclaw/reports/models/qwen25_ai_nas_acceptance_20260623-004939/qwen25_ai_nas_acceptance.md
```

Gateway turn evidence:

```text
/mnt/nas/openclaw/reports/qwen25_gateway/qwen25_gateway_turn_20260623-004937-991771/qwen25_gateway_turn.json
/mnt/nas/openclaw/reports/qwen25_gateway/qwen25_gateway_turn_20260623-004937-991771/qwen25_gateway_turn.md
```

Returned AI-NAS evidence files:

```text
/mnt/nas/openclaw/reports/qwen25_ai_nas/personal_inventory_20260623-004938-276624/personal_inventory.json
/mnt/nas/openclaw/reports/qwen25_ai_nas/evidence_report_20260623-004938-543390/evidence_report.json
/mnt/nas/openclaw/reports/qwen25_ai_nas/case_packet_20260623-004939-110493/case_packet.json
/mnt/nas/openclaw/reports/qwen25_ai_nas/folder_rag_20260623-004939-340603/folder_rag.json
```

Acceptance result:

- `verdict: ok_qwen25_ai_nas_acceptance_packet`
- `health.status: 200`
- `models.status: 200`
- `chat.status: 200`
- `chat.elapsed_ms: 1372.682`
- `gateway_turn.verdict: ok_qwen25_ai_nas_gateway_turn`
- `folder_rag.answer_status: grounded_answer`
- `errors: []`

## Remaining Risks

- The requested 1024 HBM is present and official, but it is not the active runtime profile because it currently fails at BPU/common-buffer allocation after successful HBM/model initialization.
- Generic chat through `oellm_multichat` is available through the gateway code path, but the final acceptance target here is the AI-NAS evidence flow, not broad chat-quality evaluation.
- The OpenClaw user-facing layer still needs a separate routing update if the competition demo must enter through an existing OpenClaw UI rather than direct OpenAI-compatible HTTP.
