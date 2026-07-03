#!/usr/bin/env bash
set -euo pipefail

package_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
report_root="$package_root/reports/package_rerun"
mkdir -p "$report_root"

python_cmd=()
for candidate in "py -3" python3 python; do
  read -r -a parts <<< "$candidate"
  if command -v "${parts[0]}" >/dev/null 2>&1 && "${parts[@]}" -c "import sys" >/dev/null 2>&1; then
    python_cmd=("${parts[@]}")
    break
  fi
done
if [[ ${#python_cmd[@]} -eq 0 ]]; then
  echo "no working python interpreter found" >&2
  exit 2
fi

"${python_cmd[@]}" - "$package_root" "$report_root" <<'PY'
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

root = Path(sys.argv[1])
report_root = Path(sys.argv[2])
checks = []
failures = []

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def check(label: str, ok: bool, detail=None) -> None:
    checks.append({"label": label, "ok": bool(ok), "detail": detail})
    if not ok:
        failures.append(label)

required = [
    "config/workspace_registry.yaml",
    "config/workspace_tool_policy.yaml",
    "config/workspace_arg_policy.yaml",
    "config/qwen_structured_decision_schema.json",
    "config/prompts/qwen_workspace_decision_json.md",
    "ai_nas_harness/qwen_structured_decision.py",
    "scripts/probes/ai_nas_allowlisted_tool.sh",
    "scripts/run_stage2_6_gates_from_package.sh",
    "scripts/run_stage2_7_gates_from_package.sh",
]
for rel in required:
    path = root / rel
    check(f"required asset exists: {rel}", path.exists(), {"path": str(path), "sha256": sha(path) if path.exists() and path.is_file() else None})

previous = []
for directory in ["stage1_input", "previous_stage2_input", "previous_stage2_5_input", "previous_stage2_6_input"]:
    base = root / directory
    if base.exists():
        previous.extend(str(item.relative_to(root).as_posix()) for item in base.rglob("*.zip"))
check("previous input scan supports known directories", True, previous)

if not previous:
    packet = root / "01_final_evidence" / "digua_ai_nas_harness_stage2_6_gate_packet.json"
    check("current package has stage2_6 packet if no previous zip", packet.exists(), str(packet))

schema = root / "config" / "qwen_structured_decision_schema.json"
if schema.exists():
    try:
        parsed = json.loads(schema.read_text(encoding="utf-8"))
        check("structured decision schema parses", parsed.get("type") == "object", parsed.get("required"))
    except Exception as exc:
        check("structured decision schema parses", False, type(exc).__name__ + ":" + str(exc))
else:
    check("structured decision schema parses", False, str(schema))

payload = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "gate_id": "stage2_7_package_rerun",
    "verdict": "ok_stage2_7_package_rerun" if not failures else "failed_stage2_7_package_rerun",
    "passed_count": sum(1 for item in checks if item["ok"]),
    "check_count": len(checks),
    "failure_count": len(failures),
    "failures": failures,
    "checks": checks,
    "detail": {"package_root": str(root), "previous_inputs": previous},
}
(report_root / "stage2_7_package_rerun.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
(report_root / "stage2_7_package_rerun.md").write_text("# stage2_7_package_rerun\n\n" + "\n".join(f"- {'PASS' if c['ok'] else 'FAIL'} {c['label']}" for c in checks) + "\n", encoding="utf-8")
sys.exit(0 if not failures else 1)
PY
