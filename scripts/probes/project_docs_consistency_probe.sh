#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/tmp/project_docs_consistency}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

mkdir -p "$report_root"

required_files=(
  "README.md"
  "docs/project_reference.md"
  "docs/documentation_audit_runbook.md"
  "docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md"
  "scripts/dream7b-bpu-forward.sh"
  "scripts/dream7b-bpu-fine-forward.sh"
  "scripts/dream7b-bpu-text-forward.sh"
  "scripts/probes/dream7b_segmented_hbm_python_forward.py"
  "scripts/probes/dream7b_bpu_diffusion_loop_probe.sh"
  "scripts/startup_link_check/link-check.config.json"
  "scripts/tool_allowlist.json"
)

required_readme_strings=(
  "docs/project_reference.md"
  "docs/documentation_audit_runbook.md"
  "scripts/probes/project_docs_consistency_probe.sh"
)

required_reference_strings=(
  "dream7b-bpu-forward"
  "dream7b-bpu-fine-forward"
  "dream7b-bpu-text-forward"
  "dream7b-bpu-diffusion-loop-probe"
  "DREAM7B_BPU_FINE_CHILD_RUNTIME_MODE"
  "--child-runtime-mode"
  "scripts/startup_link_check/link-check.config.json"
  "scripts/tool_allowlist.json"
  "docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_loop_20260603-171725/summary.md"
)

errors=()

for path in "${required_files[@]}"; do
  if [[ ! -e "$path" ]]; then
    errors+=("missing file: $path")
  fi
done

if [[ -f README.md ]]; then
  for text in "${required_readme_strings[@]}"; do
    if ! grep -F -- "$text" README.md >/dev/null; then
      errors+=("README.md missing string: $text")
    fi
  done
fi

if [[ -f docs/project_reference.md ]]; then
  for text in "${required_reference_strings[@]}"; do
    if ! grep -F -- "$text" docs/project_reference.md >/dev/null; then
      errors+=("docs/project_reference.md missing string: $text")
    fi
  done
fi

if [[ -f scripts/probes/dream7b_segmented_hbm_python_forward.py ]]; then
  if ! grep -F -- "--child-runtime-mode" scripts/probes/dream7b_segmented_hbm_python_forward.py >/dev/null; then
    errors+=("dream7b_segmented_hbm_python_forward.py missing --child-runtime-mode")
  fi
fi

if [[ -f scripts/dream7b-bpu-fine-forward.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_FINE_CHILD_RUNTIME_MODE" scripts/dream7b-bpu-fine-forward.sh >/dev/null; then
    errors+=("dream7b-bpu-fine-forward.sh missing DREAM7B_BPU_FINE_CHILD_RUNTIME_MODE")
  fi
fi

summary_json="$report_root/summary.json"
summary_md="$report_root/summary.md"

python3 - "$summary_json" "$summary_md" "${errors[@]}" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

summary_json = Path(sys.argv[1])
summary_md = Path(sys.argv[2])
errors = list(sys.argv[3:])
payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_project_docs_consistency_probe" if not errors else "failed_project_docs_consistency_probe",
    "errors": errors,
}
summary_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
lines = [
    "# Project Documentation Consistency Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    "",
    "## Errors",
    "",
]
if errors:
    lines.extend(f"- {item}" for item in errors)
else:
    lines.append("- none")
summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(summary_md)
if errors:
    raise SystemExit("; ".join(errors))
PY
