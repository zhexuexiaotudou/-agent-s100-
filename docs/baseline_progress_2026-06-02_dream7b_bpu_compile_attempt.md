# Dream 7B S100 BPU Compile Attempt

Date: 2026-06-02

## Goal

Make the existing Dream 7B model use the S100P 128 TOPS BPU, without replacing it with another model.

The required runtime artifact is an S100 `.hbm` model. The current Dream GGUF deployment through `diffuse-cpp` is a CPU inference path and cannot consume BPU TOPS.

## Path Under Test

The shortest Dream-specific path remains:

1. Keep Dream HF weights on NAS: `/mnt/nas/openclaw/models/dream7b-hf`.
2. Use the official S100 LLM SDK `oellm_build` compiler to produce a Dream forward/logits `.hbm`.
3. Keep Dream diffusion sampling on the host side.
4. Call the `.hbm` forward graph from S100P once per denoise step.

This is not an `xlm_infer` chat runtime path because the official runtime has no Dream model type and Dream generation is diffusion, not autoregressive prefill/decode.

## Evidence

NAS Docker is reachable from S100P over TLS:

```text
DOCKER_HOST=tcp://169.254.143.37:2376
Server: Docker Engine - Community 27.1.2-qnap8
OS/Arch: linux/amd64
Operating System: QTS 5.2.9 (20260507)
Architecture: x86_64
Name: tudou
```

The S100 LLM SDK is now staged on NAS:

```text
/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/oellm_build
```

The Dream HF model is present on NAS:

```text
/mnt/nas/openclaw/models/dream7b-hf/config.json
/mnt/nas/openclaw/models/dream7b-hf/model-00001-of-00004.safetensors
```

The NAS compile attempt reached the real `oellm_build` entry point, then failed with `SIGILL`:

```text
Fatal Python error: Illegal instruction
File ".../site-packages/hbdk4/compiler/_mlir_libs/__init__.py", line 78 in _site_initialize
File ".../site-packages/leap_llm/models/deepseek/model.py", line 9 in <module>
File ".../site-packages/leap_llm/apis/model/model_factory.py", line 68 in _build_deepseek_qwen_7b
```

NAS CPU flags do not include `avx` or `avx2`, so the official HBDK compiler library cannot be used on this NAS CPU even though the NAS is x86_64.

QEMU was also tested on the NAS. `torch` imported under QEMU, but `hbdk4.compiler` still failed with `Illegal instruction`, so QEMU is not a practical workaround for this compiler.

## Current Result

Blocked at HBM build host selection, not blocked by S100P runtime or NAS storage.

The current NAS can remain part of the finished product as model storage and container host, and S100P remains the BPU runtime target. But this NAS cannot be the one-time HBDK compile host for Dream because its CPU lacks the required x86 instruction support.

## Next Required Step

Use a one-time x86_64 Linux build host with AVX support to generate:

```text
/mnt/nas/openclaw/models/dream7b-hbm/*.hbm
```

After `.hbm` exists, copy it back to NAS and run the next S100P-side HBM forward probe. Only then can we measure whether Dream is actually consuming BPU loading / 128 TOPS.

Candidate build-host probe:

```bash
REQUIRE_HBDK_IMPORT=1 \
VENV_DIR=/mnt/nas/openclaw/tmp/dream-s100-oellm-venv \
bash scripts/probes/dream7b_bpu_builder_compat_probe.sh
```

Compile command on a compatible AVX Linux host:

```bash
SDK_OELLM_BUILD=/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/oellm_build \
DREAM_MODEL_DIR=/mnt/nas/openclaw/models/dream7b-hf \
OUTPUT_DIR=/mnt/nas/openclaw/models/dream7b-hbm \
MARCH=nash-e \
CHUNK_SIZE=256 \
CACHE_LEN=512 \
W_BITS=8 \
bash scripts/probes/compile_dream_with_deepseek_skeleton.sh
```

## Review

The path is still Dream-specific and does not switch to a different model. The build host may be temporary; it is not part of the runtime product. The finished product boundary remains S100P + NAS + OpenClaw.
