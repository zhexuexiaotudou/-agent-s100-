# Dream7B OpenClaw Gateway Fix 2026-06-22

## Current Decision

OpenClaw should continue to use `dream7b-local/Dream7B-S100P-local` through
`http://127.0.0.1:18888/v1`. The local Dream7B gateway now prefers a
`diffuse-resident` backend so the GGUF model stays loaded across requests. If
that resident backend is unavailable, the gateway falls back to the previous
`dream7b-text` CLI path.

The gateway must run under
`/mnt/nas/openclaw/runtimes/dream7b-tokenizer-venv/bin/python`. The resident path
tokenizes prompts inside the gateway process. Running it under system Python
used `transformers 4.30.2`, changed Qwen/Dream chat-template tokenization, and
degraded identity/output quality even though the resident model itself was
healthy. The tokenizer venv provided the verified tokenizer stack
(`transformers 5.9.0` during the 2026-06-22 probe).

The BPU queue-batch service remains the production scheduling and throughput
baseline. It should not be used as the default single-user chat path because a
single-request queue flush still pays the HBM load cost and measured about 26.7s
for one text request on 2026-06-22.

## Fixes Applied

- `configs/systemd/dream7b-local-openai-gateway.service`
  - sets `DREAM7B_OPENAI_INLINE_TOKENIZER=0`
  - sets `DREAM7B_OPENAI_RESIDENT=1`
  - points `DREAM7B_RESIDENT_CMD` at
    `/mnt/nas/openclaw/runtimes/diffuse-cpp/build/diffuse-resident`
  - starts
    `/mnt/nas/openclaw/runtimes/dream7b-tokenizer-venv/bin/python /root/.openclaw/workspace/scripts/dream7b_local_openai_gateway.py`
- `完全基于agent的s100使用和链路打通/scripts/dream7b_local_openai_gateway.py`
  - starts one shared resident `diffuse-resident` subprocess on first real
    Dream7B request
  - serializes resident requests with a lock and falls back to `dream7b-text` on
    resident startup/generation failures
  - calls `dream7b-text` as `[dream7b-text, prompt]`, not `[dream7b-text, "prompt", prompt]`
  - strips OpenClaw sender/timestamp metadata before prompting Dream7B
  - only injects OpenClaw context when the user explicitly asks about OpenClaw
  - normalizes identity prompts to a Dream7B model-identity prompt while still
    invoking the Dream7B backend
  - keeps only machine probe fast paths such as heartbeat/ready; identity and
    local-status questions are not answered by fixed scripted shortcuts

## Verified Remote State

Remote script hash after resident sync:

```text
e41c70185aab63c0c497a8a9c90ed96aac8baf3a103fcce5df5fb0c8119bbec6
```

Remote unit hash:

```text
cb51c05e38a4cd06f7b40519e548a0ffdcee0861f7add26379943343f18c3c63
```

Resident binary hash:

```text
b2f3db6eefde577caf8bedd90fe22dd9c9b79b344b47c64e25a5b0d518893313
```

Health:

```json
{"ok": true, "model": "Dream7B-S100P-local", "backend": "diffuse-resident", "default_steps": 4, "default_max_tokens": 16, "inline_tokenizer_enabled": false, "inline_tokenizer_loaded": true, "resident_enabled": true, "resident_available": true, "resident_running": true, "resident_ready_line": "READY\t18803"}
```

Default-latency probe after tokenizer-venv resident sync:

```text
/mnt/nas/openclaw/reports/models/dream7b_openclaw_default_latency_20260622-122515/default_latency.md
summary non_stream elapsed_ms: min 6617.846, max 12886.105, avg 9751.976
summary stream first_content_ms: min 6594.434, max 12940.614, avg 9767.524
identity non_stream: 12886.105 ms
identity stream first_content_ms: 12940.614 ms
identity content: 我是一个Dream7B-S100P-local模型
math non_stream: 6617.846 ms
math stream first_content_ms: 6594.434 ms
math content: 2
```

Three-question quality probe after tokenizer-venv resident sync:

```text
/mnt/nas/openclaw/reports/models/dream7b_three_question_probe_20260622-122454/three_question_probe.md
identity: 我是一个Dream7B-S100P-local模型
OpenClaw: OpenClaw 是一个网关，对话网关，而不是模型。
math: 2
```

OpenClaw websocket end-to-end probe after tokenizer-venv resident sync:

```text
/mnt/nas/openclaw/reports/models/openclaw_dream7b_ws_probe_20260622-043620/openclaw_dream7b_ws_probe.md
chat.send started: 2026-06-22T04:36:20.273Z
assistant delta: 2026-06-22T04:36:33.392Z
final: 2026-06-22T04:36:33.399Z
assistant content: 我是一个Dream7B-S100P-local模型
elapsed chat.send_to_final: about 13.1s
```

Previous default-latency probe before tokenizer-venv sync:

```text
/mnt/nas/openclaw/reports/models/dream7b_openclaw_default_latency_20260622-120739/default_latency.md
identity non_stream: 15096.115 ms
identity stream first_content_ms: 12856.210 ms
identity content: 我是一个基于语言模型 Dream7B-S。
math non_stream: 8575.804 ms
math stream first_content_ms: 8582.787 ms
math content: 2
```

Earlier default-latency probe before resident sync:

```text
/mnt/nas/openclaw/reports/models/dream7b_openclaw_default_latency_20260622-114752/default_latency.md
identity stream first_content_ms: 16710.084
math stream first_content_ms: 10081.769
```

Queue-batch single-request text probe:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_run_20260622-115956/text_queue_run.json
wrapper result: failed because the file was still pending at 60s
service result: processed later by partial_batch_flush_timeout
service run: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/runs/20260622-120233/segment_major_queue_summary.json
amortized_wall_ms_per_processed_request: 24766.182
```

## Remaining Boundary

This fix removes the per-request `diffuse-cli` process startup, keeps the GGUF
model resident, and fixes the gateway tokenizer/runtime mismatch. It does not
make Dream diffusion generation a fast token-streaming LLM. The remaining delay
is mostly forward compute inside diffuse generation. Default short prompts still
take roughly 6.6-12.9 seconds before first user-visible content after warmup.

The tested BPU diffusion-generation path completed, but decoded text was still
not production-quality:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_generate_20260622-032211/generation.md
```

Therefore the next latency/quality lever is no longer process residency. It is
either lower-level Dream diffusion generation work, a better text-quality BPU
decode path, or a different chat-facing model/runtime. The queue-batch service
should remain active for scheduling/logits telemetry and should not be treated
as a complete chat generator.
