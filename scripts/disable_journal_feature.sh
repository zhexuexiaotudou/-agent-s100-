#!/usr/bin/env sh
set -eu

CONFIG_PATH="${JOURNAL_FEATURE_FLAGS:-configs/journal_feature_flags.json}"
python3 - "$CONFIG_PATH" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
payload["journal_workspace_enabled"] = False
payload["cloud_generation_enabled"] = False
payload["qwen_execution_authority"] = False
payload["real_nas_write_enabled"] = False
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"ok": True, "path": str(path), "journal_workspace_enabled": False}, ensure_ascii=False))
PY
