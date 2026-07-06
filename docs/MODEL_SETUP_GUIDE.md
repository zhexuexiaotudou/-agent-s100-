# Model Setup Guide

The release package does not include model weights. Configure paths through
environment variables or `release/configs/model_manifest.yaml`.

Required production path:

- `DIGUA_QWEN_MODEL_DIR`

Required for full demo:

- `DIGUA_CLIP_MODEL_DIR`
- `DIGUA_YOLO_MODEL_PATH`
- `DIGUA_OCR_MODEL_DIR`

Optional:

- `DIGUA_ASR_MODEL_DIR`

Missing demo models are reported as degraded, not silently marked ready.

