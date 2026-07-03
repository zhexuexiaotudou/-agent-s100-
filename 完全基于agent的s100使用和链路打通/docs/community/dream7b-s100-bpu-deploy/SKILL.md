---
name: dream7b-s100-bpu-deploy
description: Deploy, validate, benchmark, and present Dream7B as a diffusion language model on S100 BPU with OpenClaw and AI-NAS. Use when Codex needs to reproduce the Dream7B S100P deployment path, collect TTFT/prefill/decode evidence, verify model identity, set up local gateway demos, or prepare the BPU diffusion language model story for a developer community post.
---

# Dream7B S100 BPU Deploy

Use this skill to reproduce and explain the Dream7B-on-S100P path as an edge AI deployment, not as a generic Hugging Face chat setup.

## Operating Boundary

- Keep the runtime local to S100P/NAS: Dream7B queue, OpenAI-compatible gateway, OpenClaw gateway, and AI-NAS allowlisted tools.
- Do not expose gateways to the public network.
- Do not claim native official Dream support unless the official SDK registry contains Dream/DreamModel.
- Treat Dream7B as diffusion-style generation. Report standard prefill/decode metrics as gateway-facing comparability estimates unless native phase timing exists.
- Keep privacy tasks on device. Cloud calls are dry-run by default and must never receive private query text.

## Minimum Evidence

Collect these before making any success claim:

```bash
dream7b-default-status
systemctl is-active dream7b-bpu-batch-queue.service
XDG_RUNTIME_DIR=/run/user/0 systemctl --user is-active dream7b-local-openai-gateway.service
XDG_RUNTIME_DIR=/run/user/0 systemctl --user is-active openclaw-gateway.service
curl -s http://127.0.0.1:18888/health
curl -s http://127.0.0.1:18888/v1/models
```

Run the benchmark and identity probe:

```bash
python3 scripts/probes/dream7b_perf_identity_probe.py \
  --base-url http://127.0.0.1:18888 \
  --model Dream7B-S100P-local
```

The report must contain `ttft_ms`, `prefill_tokens_per_s`, `decode_tokens_per_s`, generated text, model ID confirmation, and zero failed prompt cases for a release claim.

## Deployment Story

Present the work in this order:

1. Dream7B is not supported by the official OELLM registry as Dream/DreamModel.
2. Dream7B HF weights are adapted through a DeepSeek/Qwen-like decoder skeleton where compatible.
3. HBM artifacts are segmented and executed on S100 BPU.
4. The host runs the diffusion sampling/control loop and calls the HBM graph repeatedly.
5. A local OpenAI-compatible gateway exposes `Dream7B-S100P-local` to OpenClaw.
6. OpenClaw only reaches fixed allowlisted AI-NAS tools; all actions write Markdown/JSON reports.
7. Performance claims come from benchmark reports and BPU telemetry, not from marketing estimates.

## Demo Flow

Run the three demo lanes:

```bash
python3 scripts/probes/dream7b_perf_identity_probe.py --base-url http://127.0.0.1:18888
python3 scripts/probes/ai_nas_edge_cloud_router_probe.py
python3 scripts/probes/ai_nas_appliance_experience_acceptance_probe.py
```

For OpenClaw live demos, prefer fixed tool IDs:

```bash
scripts/probes/ai_nas_allowlisted_tool.sh ai_nas_personal_inventory
scripts/probes/ai_nas_allowlisted_tool.sh ai_nas_file_search "2024 renovation invoice"
scripts/probes/ai_nas_allowlisted_tool.sh ai_nas_case_packet "2024 renovation payment contract invoice receipt chat screenshot"
scripts/probes/ai_nas_allowlisted_tool.sh ai_nas_duplicate_report
scripts/probes/ai_nas_allowlisted_tool.sh ai_nas_movie_sort_enhanced
```

## Community Post Angle

Use the title pattern:

```text
在 S100 BPU 上部署 Dream7B：首个扩散语言模型端侧部署 skill
```

Emphasize:

- diffusion language model deployment on BPU;
- local privacy and lower cloud token spend;
- cheap NAS + S100P as an AI-NAS intelligence layer;
- audited allowlisted tool execution;
- measured Dream7B performance and 93 percent class BPU service evidence where supported by reports.

Avoid:

- claiming sustained 100 percent BPU average;
- implying cloud is never useful;
- claiming automatic delete/move/overwrite;
- hiding that standard prefill/decode is a compatibility metric for a diffusion model.

