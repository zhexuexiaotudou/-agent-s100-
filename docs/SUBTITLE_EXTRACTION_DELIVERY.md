# Subtitle Extraction Delivery

Subtitle Extraction provides local transcript storage, SRT/VTT artifact writing,
FTS search, and summary stubs. Product delivery requires a real local ASR backend.

API:

- `GET /api/subtitle/status`
- `POST /api/subtitle/extract`
- `GET /api/subtitle/transcript/<asset_id>`
- `POST /api/subtitle/search`
- `POST /api/subtitle/summarize`

UI:

- `/subtitle-extraction`

Environment:

```text
DIGUA_ASR_BACKEND=whisper_cpp|faster_whisper|vosk|fixture
DIGUA_ASR_MODEL_DIR=<local_model_path>
DIGUA_ASR_DEVICE=cpu|cuda|s100p_future
DIGUA_ASR_REQUIRE_REAL=1
```

`fixture` is only for CI and cannot pass the product gate.

Gate:

```bash
python3 gates/stage7_subtitle_extraction_gate.py \
  --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas \
  --personal-root /mnt/nas/openclaw/Personal
```
