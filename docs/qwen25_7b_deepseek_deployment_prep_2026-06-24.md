# Qwen2.5 7B DeepSeek Deployment Prep 2026-06-24

## Purpose

This is the execution package for a DeepSeek-class model to deploy and test the
official `Qwen2.5-7B-Instruct` S100 HBM without disturbing the current
production/demo baseline.

The active baseline remains:

- service: `qwen25-local-openai-gateway.service`
- port: `18080`
- model: `Qwen2.5-1.5B-Instruct-S100P-official`
- profile: `cache_len_512_chunk_128_q8`

The 7B candidate must run as a shadow route:

- service: `qwen25-7b-shadow-openai-gateway.service`
- port: `18081`
- model: `Qwen2.5-7B-Instruct-S100P-official-shadow`
- required gate before promotion: `ok_qwen25_7b_shadow_acceptance_packet`

Do not edit, disable, restart, or replace the 18080 service while testing 7B.

## Files Prepared

- `configs/qwen25_7b_1024_multichat_config.json`
- `configs/qwen25_7b_shadow_route_policy.json`
- `configs/systemd/qwen25-7b-shadow-openai-gateway.service`
- `scripts/probes/qwen25_7b_shadow_acceptance_packet.py`
- `docs/qwen25_7b_deepseek_deployment_prep_2026-06-24.md`

## Official Model Artifact

The S100 LLM SDK model list contains:

```text
Qwen-2.5-7B-Instruct
context size 1024 q8
wget https://d-robotics-aitoolchain.oss-cn-beijing.aliyuncs.com/llm_s100/1.0.0/models/Qwen2.5_7B_Instruct_1024.hbm
```

Expected local staging path:

```text
downloads/s100_official_llm/Qwen2.5_7B_Instruct_1024.hbm
```

Expected S100P runtime path:

```text
/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/oellm_runtime/model/Qwen2.5_7B_Instruct_1024.hbm
```

Expected S100P tokenizer/template directory:

```text
/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/oellm_runtime/config/Qwen2.5_7B_Instruct_config
```

## DeepSeek Execution Steps

Run these in order. Stop on the first failure and preserve the full output.

### 1. Verify Baseline Is Still Healthy

On S100P:

```bash
curl -sS http://127.0.0.1:18080/health
curl -sS http://127.0.0.1:18080/v1/models
```

On Windows:

```powershell
py -3 scripts\probes\qwen25_ai_nas_acceptance_packet.py
```

The baseline must still return `ok_qwen25_ai_nas_acceptance_packet`.

### 2. Stage The 7B HBM

Download on Windows or S100P, then copy to the expected S100P model path.

```bash
cd /mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/oellm_runtime/model
wget https://d-robotics-aitoolchain.oss-cn-beijing.aliyuncs.com/llm_s100/1.0.0/models/Qwen2.5_7B_Instruct_1024.hbm
```

Also download and verify the official checksum file if network access is
available:

```bash
wget https://d-robotics-aitoolchain.oss-cn-beijing.aliyuncs.com/llm_s100/1.0.0/models/md5sum.txt
md5sum -c md5sum.txt | grep Qwen2.5_7B_Instruct_1024.hbm
```

If checksum verification cannot run, record that as a blocker. Do not promote
without a replacement integrity check.

### 3. Copy Prepared Configs To S100P

From Windows:

```powershell
scp -i C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519 configs\qwen25_7b_1024_multichat_config.json sunrise@192.168.127.10:/mnt/nas/openclaw/configs/qwen25_7b_1024_multichat_config.json
scp -i C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519 configs\qwen25_7b_shadow_route_policy.json sunrise@192.168.127.10:/mnt/nas/openclaw/configs/qwen25_7b_shadow_route_policy.json
scp -i C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519 scripts\qwen25_openai_gateway.py sunrise@192.168.127.10:/mnt/nas/openclaw/scripts/qwen25_openai_gateway.py
scp -i C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519 scripts\probes\qwen25_7b_shadow_acceptance_packet.py sunrise@192.168.127.10:/mnt/nas/openclaw/scripts/probes/qwen25_7b_shadow_acceptance_packet.py
scp -i C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519 configs\systemd\qwen25-7b-shadow-openai-gateway.service sunrise@192.168.127.10:/home/sunrise/.config/systemd/user/qwen25-7b-shadow-openai-gateway.service
```

### 4. Start Only The Shadow Service

On S100P:

```bash
systemctl --user daemon-reload
systemctl --user start qwen25-7b-shadow-openai-gateway.service
systemctl --user status qwen25-7b-shadow-openai-gateway.service --no-pager
```

Do not enable it until the shadow acceptance passes.

### 5. Smoke Test The Shadow Route

On S100P:

```bash
curl -sS http://127.0.0.1:18081/health
curl -sS http://127.0.0.1:18081/v1/models
```

Expected health fields:

- `model`: `Qwen2.5-7B-Instruct-S100P-official-shadow`
- `active_hbm.exists`: `true`
- `active_hbm.path` ends with `Qwen2.5_7B_Instruct_1024.hbm`

### 6. Run The Shadow Acceptance Packet

From Windows:

```powershell
py -3 scripts\probes\qwen25_7b_shadow_acceptance_packet.py
```

Expected verdict:

```text
ok_qwen25_7b_shadow_acceptance_packet
```

If the result is partial, do not promote. Use the `errors` list in the JSON as
the next work queue.

### 7. Promotion Boundary

Promotion is allowed only after all are true:

- 18080 baseline still passes `qwen25_ai_nas_acceptance_packet.py`.
- 18081 shadow passes `qwen25_7b_shadow_acceptance_packet.py`.
- No BPU/common-buffer allocation failure is observed in the 7B service logs.
- The 7B gateway returns AI-NAS Markdown/JSON report paths under
  `/mnt/nas/openclaw/reports/qwen25_7b_ai_nas` and
  `/mnt/nas/openclaw/reports/qwen25_7b_gateway`.
- The final decision is recorded in a new doc before changing the baseline
  service.

Promotion should be a separate task. This prep package deliberately does not
change the production 18080 route.

## Rollback

If the shadow service fails:

```bash
systemctl --user stop qwen25-7b-shadow-openai-gateway.service
journalctl --user -u qwen25-7b-shadow-openai-gateway.service --no-pager -n 200
curl -sS http://127.0.0.1:18080/health
```

Keep the failed logs and generated JSON/Markdown reports. Do not delete the HBM
or report directories unless the user explicitly asks for cleanup.

## Known Risks For DeepSeek

- Do not weaken gates or expected verdicts.
- Do not reuse the old 1.5B acceptance packet as proof of 7B success.
- Do not call the 7B route production-ready while it is on port 18081.
- Treat any `-11`, segmentation fault, allocation failure, or missing active
  HBM as a blocker.
- Keep all commands scoped to S100P and `/mnt/nas/openclaw`; do not touch raw NAS
  personal data except through allowlisted AI-NAS tools.
