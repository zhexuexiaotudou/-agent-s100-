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
    "deployment/qwen25-local-openai-gateway.service.candidate",
    "deployment/qwen25-local-openai-gateway.apply_rollback.md",
    "operator_approval/qwen_systemd_apply_approved.json",
    "gates/stage2_10_gates.py",
    "scripts/run_stage2_10_gates_from_package.sh",
    "scripts/probes/ai_nas_allowlisted_tool.sh",
    "reports/9000_stage2_10_baseline_lock.json",
    "reports/9010_operator_approval_hard_gate.json",
    "reports/9020_qwen_persistence_apply_verify_restart_gate.json",
    "reports/9030_qwen_persistence_rollback_verify_gate.json",
    "reports/9040_post_persistence_policy_first_readonly_shadow_soak_gate.json",
    "reports/9050_stage2_10_stage3_go_no_go_gate.json",
    "01_final_evidence/digua_ai_nas_harness_stage2_10_gate_packet.json",
    "docs/STAGE2_10_DECISION.md",
    "docs/STAGE3_READONLY_SHADOW_DRYRUN_PLAN_V5.md",
]
for rel in required:
    path = root / rel
    check(f"required asset exists: {rel}", path.exists(), {"path": str(path), "sha256": sha(path) if path.exists() and path.is_file() else None})

previous = []
for directory in ["previous_stage2_9_input"]:
    base = root / directory
    if base.exists():
        previous.extend(str(item.relative_to(root).as_posix()) for item in base.rglob("*.zip"))
check("previous stage input scan supports stage2_9", True, previous)

packet = root / "01_final_evidence" / "digua_ai_nas_harness_stage2_10_gate_packet.json"
if packet.exists():
    data = json.loads(packet.read_text(encoding="utf-8"))
    verdict = data.get("final_verdict")
    check("stage2_10 packet verdict present", bool(verdict), verdict)
    blob = json.dumps(data, ensure_ascii=False).lower()
    check("stage2_10 does not claim qwen autonomous loop", "qwen-driven autonomous" not in blob and "autonomous agent loop ready" not in blob, verdict)
    check("stage2_10 stage3 scope is readonly policy-first when present", data.get("stage3_scope_if_allowed") in {None, "Stage 3 Readonly Shadow Dry-Run, Policy-First Mode"}, data.get("stage3_scope_if_allowed"))
else:
    check("stage2_10 packet verdict present", False, str(packet))

rollback = root / "deployment" / "qwen25-local-openai-gateway.apply_rollback.md"
if rollback.exists():
    text = rollback.read_text(encoding="utf-8", errors="replace")
    check("rollback doc has apply command", "systemctl enable --now qwen25-local-openai-gateway.service" in text, None)
    check("rollback doc has rollback command", "systemctl disable --now qwen25-local-openai-gateway.service" in text, None)
    check("rollback doc has preconditions", "Preconditions" in text and "18080" in text, None)

payload = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "gate_id": "stage2_10_package_rerun",
    "verdict": "ok_stage2_10_package_rerun" if not failures else "failed_stage2_10_package_rerun",
    "passed_count": sum(1 for item in checks if item["ok"]),
    "check_count": len(checks),
    "failure_count": len(failures),
    "failures": failures,
    "checks": checks,
    "detail": {"package_root": str(root), "previous_inputs": previous},
}
(report_root / "stage2_10_package_rerun.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
(report_root / "stage2_10_package_rerun.md").write_text("# stage2_10_package_rerun\n\n" + "\n".join(f"- {'PASS' if c['ok'] else 'FAIL'} {c['label']}" for c in checks) + "\n", encoding="utf-8")
sys.exit(0 if not failures else 1)
PY
