#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
base_url="${1:-http://127.0.0.1:8765}"
out_dir="${2:-$repo_root/reports/agent_runtime_e2e_smoke}"
mkdir -p "$out_dir"

"$repo_root/scripts/check_agent_runtime_status.sh" "$base_url" "$out_dir"
python3 "$repo_root/tools/build_agent_runtime_deepening.py" --report-root "$out_dir/local_eval" --fixture-root "$out_dir/fixture" --clean-fixture >"$out_dir/e2e_eval_stdout.json"

python3 - "$out_dir" <<'PY'
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
status = json.loads((out / "agent_runtime_live_status_summary.json").read_text(encoding="utf-8"))
eval_stdout = json.loads((out / "e2e_eval_stdout.json").read_text(encoding="utf-8"))
payload = {
    "ok": bool(status.get("ok")) and bool(eval_stdout.get("ok")),
    "live_status": status,
    "local_eval_verdict": eval_stdout.get("verdict"),
    "qwen_execution_authority": False,
    "cloud_private_raw_egress": False,
    "public_mcp_exposed": False,
}
(out / "agent_runtime_e2e_smoke_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload, ensure_ascii=False))
sys.exit(0 if payload["ok"] else 1)
PY
