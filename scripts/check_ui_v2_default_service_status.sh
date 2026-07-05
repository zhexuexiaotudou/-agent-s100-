#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
base_url="${1:-${DIGUA_UI_V2_BASE_URL:-http://127.0.0.1:8765}}"
report_dir="${DIGUA_UI_V2_REPORT_DIR:-$repo_root/reports}"
mkdir -p "$report_dir"

health_file="$(mktemp)"
harness_file="$(mktemp)"
health_ok=false
harness_ok=false

if curl -fsS "$base_url/api/health" >"$health_file"; then
  health_ok=true
fi

if curl -fsS "$base_url/api/harness/status" >"$harness_file"; then
  harness_ok=true
fi

python3 - "$report_dir" "$base_url" "$health_ok" "$harness_ok" "$health_file" "$harness_file" <<'PY'
import datetime
import json
import pathlib
import sys

report_dir = pathlib.Path(sys.argv[1])
base_url = sys.argv[2]
health_ok = sys.argv[3] == "true"
harness_ok = sys.argv[4] == "true"
health_file = pathlib.Path(sys.argv[5])
harness_file = pathlib.Path(sys.argv[6])

def read_payload(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "error": f"unreadable:{type(exc).__name__}:{exc}"}

payload = {
    "ok": bool(health_ok and harness_ok),
    "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "base_url": base_url,
    "health_ok": health_ok,
    "harness_ok": harness_ok,
    "production_rollout_performed": False,
    "default_port": 8765,
    "health": read_payload(health_file),
    "harness": read_payload(harness_file),
}
json_path = report_dir / "ui_v2_default_service_preflight.json"
md_path = report_dir / "ui_v2_default_service_preflight.md"
json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
md_path.write_text(
    "# UI v2 default service preflight\n\n"
    f"- ok: {payload['ok']}\n"
    f"- base_url: `{base_url}`\n"
    f"- health_ok: {health_ok}\n"
    f"- harness_ok: {harness_ok}\n"
    "- production_rollout_performed: false\n",
    encoding="utf-8",
)
print(json_path)
PY

rm -f "$health_file" "$harness_file"
if [ "$health_ok" != true ] || [ "$harness_ok" != true ]; then
  exit 1
fi
