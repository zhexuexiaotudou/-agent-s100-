# YOLO Index Production Runbook

## Scope

This runbook covers the S100P-local YOLO visual index route for multimodal search v2. The production runtime is the S100P OpenClaw service on port 8765. A PC may be used only as SSH, browser, or recording entry.

## Runtime

- OpenClaw default service: `openclaw-gateway.service`
- API base on S100P: `http://127.0.0.1:8765`
- YOLO backend: `dnn_node_example` with the local S100P HBM model
- Runtime DB: `/mnt/nas/openclaw/reports/yolo_index/runtime/yolo_index.db`
- Evidence root: `/mnt/nas/openclaw/reports/yolo_index/evidence/`

## Commands

```bash
cd /mnt/nas/openclaw
python3 -m py_compile src/yolo_index/*.py
python3 -m pytest tests/test_yolo_*.py
bash scripts/production/check_yolo_index_status.sh
bash scripts/production/rebuild_yolo_index.sh
AI_NAS_OPERATOR_APPROVED_S100P_YOLO_DEPLOYMENT=1 bash scripts/production/enable_yolo_index_service.sh
```

Use a bounded fixture root for first rebuilds:

```bash
export DIGUA_YOLO_FIXTURE_ROOT=/mnt/nas/openclaw/yolo_v2_fixture
export DIGUA_YOLO_MAX_FILES=80
bash scripts/production/rebuild_yolo_index.sh
```

## Acceptance

- `/api/yolo-index/status` returns `ok: true`, `cloud_used: false`, `raw_path_rows: 0`.
- At least one image asset, one video keyframe, and one YOLO detection are indexed.
- Chinese and English object queries return redacted results with object labels, confidence, normalized bbox, timestamp for videos, and evidence refs.
- The UI at `/multimodal-search` shows YOLO status and object-filtered results without raw filesystem paths.

## Boundaries

- No model weights, HBM files, runtime DBs, private media, redaction maps, API keys, or secrets are committed.
- No cloud vision, face identity, sensitive attribute inference, employee monitoring, camera monitoring, or file mutation route is added.
- Qwen remains without tool execution authority.
