#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
flags_file="${1:-$repo_root/configs/harness_default_service_feature_flags.json}"
mode="${2:---dry-run}"

if [[ ! -f "$flags_file" ]]; then
  echo "flags_file_not_found: $flags_file" >&2
  exit 2
fi

python3 - "$flags_file" "$mode" <<'PY'
import json
import shutil
import sys
from pathlib import Path

path = Path(sys.argv[1])
mode = sys.argv[2]
payload = json.loads(path.read_text(encoding="utf-8"))
updated = dict(payload)
updated["copy_execute_enabled"] = False
updated["copy_rollback_enabled"] = False
updated["readonly_workspaces_enabled"] = True
updated["token_budget_gate_enabled"] = True
if mode == "--apply":
    backup = path.with_suffix(path.suffix + ".stage5_disable_backup")
    shutil.copy2(path, backup)
    path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"ok": True, "mode": mode, "flags_file": str(path), "copy_execute_enabled": updated["copy_execute_enabled"], "copy_rollback_enabled": updated["copy_rollback_enabled"], "readonly_workspaces_enabled": updated["readonly_workspaces_enabled"], "token_budget_gate_enabled": updated["token_budget_gate_enabled"]}, ensure_ascii=False, sort_keys=True))
PY
