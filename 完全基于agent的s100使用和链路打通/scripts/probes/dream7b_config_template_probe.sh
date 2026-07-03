#!/usr/bin/env bash
set -euo pipefail

report_dir="${1:-/root/.openclaw/workspace/reports/models}"

case "$report_dir" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_dir" >&2
    exit 2
    ;;
esac

mkdir -p "$report_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$report_dir/dream7b_config_template_$stamp.md"
json="$report_dir/dream7b_config_template_$stamp.json"
target_config="/root/.openclaw/workspace/config/dream7b_deployment.json"

config_status="missing"
if [[ -f "$target_config" ]]; then
  config_status="present"
fi

model_dir_status="missing"
if [[ -d /root/.openclaw/workspace/models ]]; then
  model_dir_status="present"
fi

nas_model_status="skipped_not_mounted"
nas_fstype="$(findmnt -rn -o FSTYPE --target /mnt/nas/openclaw 2>/dev/null | head -1 || true)"
case "$nas_fstype" in
  nfs|nfs4|cifs|smb3)
    if [[ -d /mnt/nas/openclaw/models ]]; then
      nas_model_status="present"
    else
      nas_model_status="mounted_missing_models_dir"
    fi
    ;;
  "")
    nas_model_status="not_mounted"
    ;;
  *)
    nas_model_status="skipped_not_real_nas_mount:$nas_fstype"
    ;;
esac

python3 - "$json" "$stamp" "$config_status" "$model_dir_status" "$nas_model_status" <<'PY'
import json
import sys
from datetime import datetime

json_path, stamp, config_status, model_dir_status, nas_model_status = sys.argv[1:]
payload = {
    "version": 1,
    "generated_at": datetime.now().astimezone().isoformat(),
    "stamp": stamp,
    "mode": "read-only template artifact; not a deployment config",
    "target_runtime_config": "/root/.openclaw/workspace/config/dream7b_deployment.json",
    "signals": {
        "runtime_config": config_status,
        "local_model_dir": model_dir_status,
        "nas_model_dir": nas_model_status,
    },
    "config_template": {
        "version": 1,
        "description": "Copy deliberately to the runtime config path only after local model files are installed or mounted.",
        "model": {
            "path": "/root/.openclaw/workspace/models/dream7b",
            "format": "auto",
            "runtime": "auto",
        },
        "smoke_test": {
            "prompt": "Respond with exactly: OK",
            "max_new_tokens": 16,
            "timeout_seconds": 120,
        },
        "operator": {
            "name": "",
            "confirmed_at": "",
            "notes": "Keep model path under /mnt/nas/openclaw/models, /root/.openclaw/workspace/models, or /home/sunrise/models.",
        },
    },
    "read_only_contract": [
        "does not write target runtime config",
        "does not download model files",
        "does not start model server",
        "does not run inference",
    ],
}
with open(json_path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
PY

{
  echo "# B-003 Dream 7B Config Template"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- mode: read-only template artifact; not a deployment config"
  echo "- report: $report"
  echo "- json: $json"
  echo "- target_runtime_config: $target_config"
  echo
  echo "## Current Signals"
  echo
  echo "| Signal | Value |"
  echo "| --- | --- |"
  echo "| runtime_config | $config_status |"
  echo "| local_model_dir | $model_dir_status |"
  echo "| nas_model_dir | $nas_model_status |"
  echo
  echo "## Runtime Config Template"
  echo
  echo "This is intentionally not written to the runtime config path."
  echo
  echo '```json'
  cat <<'JSON'
{
  "version": 1,
  "description": "Copy deliberately to the runtime config path only after local model files are installed or mounted.",
  "model": {
    "path": "/root/.openclaw/workspace/models/dream7b",
    "format": "auto",
    "runtime": "auto"
  },
  "smoke_test": {
    "prompt": "Respond with exactly: OK",
    "max_new_tokens": 16,
    "timeout_seconds": 120
  },
  "operator": {
    "name": "",
    "confirmed_at": "",
    "notes": "Keep model path under /mnt/nas/openclaw/models, /root/.openclaw/workspace/models, or /home/sunrise/models."
  }
}
JSON
  echo '```'
  echo
  echo "## Boundary"
  echo
  echo "- This probe does not write $target_config."
  echo "- This probe does not download model files."
  echo "- This probe does not start a model server."
  echo "- This probe does not run inference."
  echo "- B-003 Dream 7B remains blocked until model files and runtime config exist, then the bounded smoke probe passes."
} > "$report"

echo "$report"
