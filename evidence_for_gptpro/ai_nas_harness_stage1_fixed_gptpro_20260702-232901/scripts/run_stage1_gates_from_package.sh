#!/usr/bin/env bash
set -euo pipefail

pkg_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export AI_NAS_REPO_ROOT="${AI_NAS_REPO_ROOT:-$pkg_root}"
export AI_NAS_PRODUCTION_CONTEXT_ROOT="${AI_NAS_PRODUCTION_CONTEXT_ROOT:-$pkg_root/production_context}"

if command -v py >/dev/null 2>&1; then
  py -3 "$pkg_root/gates/run_harness_stage1_gates.py" --report-root "$pkg_root/reports"
elif command -v python3 >/dev/null 2>&1; then
  python3 "$pkg_root/gates/run_harness_stage1_gates.py" --report-root "$pkg_root/reports"
else
  python "$pkg_root/gates/run_harness_stage1_gates.py" --report-root "$pkg_root/reports"
fi
