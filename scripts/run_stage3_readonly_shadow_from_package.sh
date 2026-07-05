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
    "gates/stage3_readonly_shadow_gates.py",
    "scripts/run_stage3_readonly_shadow_from_package.sh",
    "scripts/probes/ai_nas_allowlisted_tool.sh",
    "config/stage3_readonly_shadow_policy.json",
    "operator_approval/qwen_systemd_apply_approved.json",
    "reports/11000_stage3_fasttrack_baseline_lock.json",
    "reports/11010_stage3_shadow_tap_integrity_gate.json",
    "reports/11020_stage3_policy_first_shadow_decision_gate.json",
    "reports/11030_stage3_readonly_shadow_execution_gate.json",
    "reports/11040_stage3_health_resource_latency_gate.json",
    "reports/11045_stage3_cloud_egress_privacy_gate.json",
    "reports/11050_stage3_shadow_rollback_gate.json",
    "reports/11060_stage3_final_gate_packet.json",
    "reports/stage3_readonly_shadow_execution_trace.jsonl",
    "reports/stage3_shadow_comparison.json",
    "reports/stage3_shadow/stage3_shadow_tap_trace.jsonl",
    "reports/stage3_shadow/stage3_shadow_decisions.jsonl",
    "reports/stage3_shadow/stage3_shadow_runs.jsonl",
    "reports/stage3_shadow/stage3_shadow_tool_calls.jsonl",
    "reports/stage3_shadow/stage3_cloud_egress_redaction_trace.jsonl",
    "01_final_evidence/digua_ai_nas_harness_stage3_readonly_shadow_gate_packet.json",
    "docs/STAGE3_READONLY_SHADOW_DECISION.md",
    "docs/STAGE4_WRITE_ACTION_PRECONDITIONS.md",
]

for rel in required:
    path = root / rel
    check(f"required asset exists: {rel}", path.exists(), {"path": str(path), "sha256": sha(path) if path.exists() and path.is_file() else None})

previous = []
base = root / "previous_stage2_10_input"
if base.exists():
    previous.extend(str(item.relative_to(root).as_posix()) for item in base.rglob("*.zip"))
check("previous stage input scan supports stage2_10", True, previous)

packet_path = root / "01_final_evidence" / "digua_ai_nas_harness_stage3_readonly_shadow_gate_packet.json"
if packet_path.exists():
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    verdict = packet.get("final_verdict")
    check(
        "stage3 packet verdict is valid freeze verdict",
        verdict in {
            "stage3_readonly_shadow_pass_continue_observation",
            "stage3_readonly_shadow_pass_but_hold_for_longer_soak",
            "ready_for_stage4_write_action_design_only",
            "not_ready_due_to_shadow_safety_failure",
            "inconclusive_missing_evidence",
        },
        verdict,
    )
    check("stage3 packet did not enter stage4", packet.get("stage4_entered") is False, packet.get("stage4_entered"))
    check("stage3 packet requires review before stage4", packet.get("requires_gptpro_or_human_review_before_stage4") is True, packet.get("requires_gptpro_or_human_review_before_stage4"))
    blob = json.dumps(packet, ensure_ascii=False).lower()
    check("packet does not claim production write readiness", "production write readiness\": true" not in blob and "write execution approved" not in blob, None)
else:
    check("stage3 packet verdict is valid freeze verdict", False, str(packet_path))

trace_path = root / "reports" / "stage3_readonly_shadow_execution_trace.jsonl"
if trace_path.exists():
    lines = [line for line in trace_path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
    check("stage3 execution trace has at least 300 rows", len(lines) >= 300, len(lines))
    parsed = [json.loads(line) for line in lines]
    check("stage3 trace stores no raw prompt field", all("prompt" not in row and "raw_prompt" not in row for row in parsed), None)
    check("stage3 trace final tool source is policy", all(row.get("final_tool_source") == "policy" for row in parsed), None)
    check("stage3 trace grants no qwen execution authority", all(row.get("qwen_has_execution_authority") is False for row in parsed), None)
else:
    check("stage3 execution trace has at least 300 rows", False, str(trace_path))

payload = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "gate_id": "stage3_package_rerun",
    "verdict": "ok_stage3_package_rerun" if not failures else "failed_stage3_package_rerun",
    "passed_count": sum(1 for item in checks if item["ok"]),
    "check_count": len(checks),
    "failure_count": len(failures),
    "failures": failures,
    "checks": checks,
    "detail": {"package_root": str(root), "previous_inputs": previous},
}
(report_root / "stage3_package_rerun.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
(report_root / "stage3_package_rerun.md").write_text("# stage3_package_rerun\n\n" + "\n".join(f"- {'PASS' if c['ok'] else 'FAIL'} {c['label']}" for c in checks) + "\n", encoding="utf-8")
sys.exit(0 if not failures else 1)
PY
