# Dream 7B on S100 BPU Adapter Status

Date: 2026-06-01

## Current conclusion

Dream 7B cannot be used through the official `xlm_infer` chat runtime as-is. The S100 LLM SDK exposes model types for InternVL, DeepSeek, Qwen, InternLM, Omni, Qwen-VL, and Qwen2.5, but not Dream. Dream also uses `diffusion_generate()`, which repeatedly denoises a full masked sequence, while `xlm_infer` is built around autoregressive prefill/decode.

The shortest viable experiment is not `xlm_infer`. It is:

1. Use Dream HF safetensors as the input model.
2. Compile Dream through the official DeepSeek/Qwen text skeleton because Dream's decoder weight names and config fields match that skeleton closely.
3. Treat the produced HBM as a fixed-length full-sequence forward/logits graph.
4. Implement Dream's diffusion sampling loop on the host side and call the HBM graph once per denoise step.

## Evidence already checked

- Dream HF config:
  - `architectures`: `DreamModel`
  - `model_type`: `Dream`
  - `num_hidden_layers`: `28`
  - `hidden_size`: `3584`
  - `intermediate_size`: `18944`
  - `num_attention_heads`: `28`
  - `num_key_value_heads`: `4`
  - `rope_theta`: `1000000.0`
  - `mask_token_id`: `151666`
- Dream generation code is full-sequence diffusion:
  - pads input with `mask_token_id`
  - loops over `steps`
  - calls `self(x, attention_mask, tok_idx).logits`
  - samples and transfers masked tokens by confidence
- S100 SDK status:
  - `oellm_build` model registry has no Dream builder.
  - `xlm_model_type` has no Dream enum.
  - official DeepSeek skeleton compiles prefill/decode HBM graphs with external mask and cache inputs.
- Dream HF weight map contains the expected decoder keys:
  - `model.embed_tokens.weight`
  - `model.layers.*.self_attn.{q,k,v,o}_proj.*`
  - `model.layers.*.mlp.{gate,up,down}_proj.weight`
  - `model.layers.*.{input,post_attention}_layernorm.weight`
  - `model.norm.weight`
  - `lm_head.weight`

## Files now on S100P/NAS

Dream HF model directory:

```text
/mnt/nas/openclaw/models/dream7b-hf
```

Downloaded files:

```text
config.json
configuration_dream.py
generation_config.json
generation_utils.py
merges.txt
model-00001-of-00004.safetensors
model-00002-of-00004.safetensors
model-00003-of-00004.safetensors
model-00004-of-00004.safetensors
model.safetensors.index.json
modeling_dream.py
tokenization_dream.py
tokenizer_config.json
vocab.json
SHA256SUMS
```

Download source used:

```text
https://hf-mirror.com/Dream-org/Dream-v0-Instruct-7B/resolve/main
```

## Local helper scripts

Static compatibility probe:

```text
F:\Project\Digua\scripts\probes\dream_s100_adapter_probe.py
```

Dream HF downloader for S100P/NAS:

```text
F:\Project\Digua\scripts\probes\download_dream_hf_to_s100p.sh
```

First HBM compile attempt script:

```text
F:\Project\Digua\scripts\probes\compile_dream_with_deepseek_skeleton.sh
```

## Current blocker

HBM compilation requires an x86_64 Linux environment with Python 3.10. The SDK compiler wheel is:

```text
hbdk4_compiler-...-cp310-cp310-manylinux_2_17_x86_64.whl
```

The final product boundary is S100P + NAS + OpenClaw. Windows is only a control terminal for now and should not be part of the shipped runtime.

S100P is `aarch64`, so it cannot run the x86_64 `hbdk4_compiler` wheel natively. It can run the final ARM64 service/container and the compiled HBM runtime, but it is not the native compile host for Dream-to-HBM.

NAS is reachable from S100P at:

```text
169.254.143.37:/OpenClawWorkspace -> /mnt/nas/openclaw
```

The NAS is confirmed as QNAP/QTS and provides SMB/NFS/Web management ports. The SMB account can read/write the model share, but the current QTS Web API login attempt with that account returns `authPassed=0`, so NAS CPU architecture and Container Station status are still not confirmed through the management API. This must be confirmed with a QTS admin session or another reliable NAS-side shell/API path.

## S100P Docker status

S100P Docker is installed and verified on the S100P itself:

```text
Docker version: 20.10.12-0ubuntu4
Architecture: aarch64
Service: active
Docker root: /var/lib/docker
Verified image: local/busybox-static:offline
```

Important compatibility notes:

- `docker.io 29.1.3-0ubuntu3~22.04.2` panics during `dockerd` startup on this S100P.
- `docker.io 20.10.12-0ubuntu4` works after switching Docker networking to legacy iptables.
- `docker.io` is held with `apt-mark hold docker.io` to avoid accidental upgrade back to the failing version.
- Docker Hub pull timed out from S100P, so offline images or a configured registry mirror should be used for repeatable deployment.
- A container can read Dream HF files from the NAS mount:

```text
/mnt/nas/openclaw/models/dream7b-hf/config.json
```

## Next executable step

Confirm whether the QNAP NAS is x86_64 and whether Container Station/Docker is available. If yes, use the NAS as the native x86_64 HBM compile host and write outputs back to:

```text
/mnt/nas/openclaw/models/dream7b-hbm
```

Then run:

```bash
SDK_OELLM_BUILD=/path/to/D-Robotics_LLM_S100_1.0.0_SDK/oellm_build \
DREAM_MODEL_DIR=/mnt/nas/openclaw/models/dream7b-hf \
OUTPUT_DIR=/mnt/nas/openclaw/models/dream7b-hbm \
MARCH=nash-e \
CHUNK_SIZE=256 \
CACHE_LEN=256 \
bash scripts/probes/compile_dream_with_deepseek_skeleton.sh
```

If the NAS is not x86_64, it remains the storage/service host, but Dream-to-HBM compilation needs one temporary x86_64 Linux build host to produce the `.hbm` artifacts. The produced `.hbm` should still live on the NAS and run on S100P; Windows should not be part of the runtime product.

If this compiles, the next step is a direct HBM forward probe with zero/full attention mask on S100P, not `xlm_infer`.
