#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${S100P_PROJECT_DIR:-/mnt/nas/openclaw}"
REPORT_ROOT="${DIGUA_REPORT_ROOT:-/mnt/nas/openclaw/reports/qwen25_ai_nas}"
FIXTURE_ROOT="${DIGUA_YOLO_FIXTURE_ROOT:-/mnt/nas/openclaw/yolo_v2_fixture}"
MAX_FILES="${DIGUA_YOLO_MAX_FILES:-80}"
INCLUDE_VIDEO="${DIGUA_YOLO_INCLUDE_VIDEO:-1}"

cd "${PROJECT_DIR}"
python3 - "$REPORT_ROOT" "$FIXTURE_ROOT" "$MAX_FILES" "$INCLUDE_VIDEO" <<'PY'
import json
import sys
from pathlib import Path

from src.openclaw.routes.yolo_index_routes import yolo_route_response

report_root = Path(sys.argv[1])
fixture_root = Path(sys.argv[2])
max_files = int(sys.argv[3])
include_video = sys.argv[4] not in {"0", "false", "False"}

status, payload = yolo_route_response(
    "/api/yolo-index/rebuild",
    method="POST",
    payload={"roots": [str(fixture_root)], "max_files": max_files, "include_video": include_video},
    report_root=report_root,
    personal_root=fixture_root,
)
payload["http_status"] = status
print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
raise SystemExit(0 if status == 200 and payload.get("ok") else 1)
PY
