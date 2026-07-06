# Multimodal Live CLIP Delivery

The multimodal search service now separates production semantic embeddings from
the older 16-dimensional local feature fallback.

Production delivery requires:

- local CLIP/SigLIP/Chinese-CLIP/OpenCLIP model files
- `vector_dim >= 128`
- `production_semantic=true`
- at least five live image embedding rows
- `cloud_used=false`
- `raw_path_rows=0`

S100P runtime configuration:

```text
DIGUA_CLIP_BACKEND=clip
DIGUA_CLIP_MODEL_DIR=/mnt/nas/openclaw/models/ai_nas_clip_vit_base_patch32
DIGUA_CLIP_DEVICE=cpu
DIGUA_CLIP_REQUIRE_PRODUCTION=1
```

Gate:

```bash
python3 gates/stage6_multimodal_live_clip_gate.py \
  --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas \
  --personal-root /mnt/nas/openclaw/Personal
```
