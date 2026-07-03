#!/usr/bin/env bash
set -euo pipefail

package_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
stage1_zip="$(find "$package_root/stage1_input" "$package_root" -maxdepth 1 -type f \( -name 'ai_nas_harness_stage1_fixed_gptpro_*.zip' -o -name 'ai_nas_harness_stage1_gptpro_*.zip' \) 2>/dev/null | sort | tail -n 1)"

if [[ -z "$stage1_zip" ]]; then
  echo "missing stage1 input package under $package_root/stage1_input" >&2
  exit 2
fi

stage1_extract="$package_root/tmp/stage1_input_extracted"
rm -rf "$stage1_extract"
mkdir -p "$stage1_extract"

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

"${python_cmd[@]}" - "$stage1_zip" "$stage1_extract" <<'PY'
import sys
import zipfile
from pathlib import Path

zip_path = Path(sys.argv[1])
target = Path(sys.argv[2])
with zipfile.ZipFile(zip_path) as zf:
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        if not name or name.endswith("/"):
            continue
        out = target / name
        out.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(info) as src, out.open("wb") as dst:
            dst.write(src.read())
PY

export AI_NAS_PACKAGE_ROOT="$package_root"
export AI_NAS_REPO_ROOT="$package_root"
export AI_NAS_PRODUCTION_CONTEXT_ROOT="$stage1_extract/production_context"
export AI_NAS_HARNESS_SHADOW=1

if [[ -d "$stage1_extract/existing_gate_evidence" ]]; then
  rm -rf "$package_root/existing_gate_evidence"
  cp -R "$stage1_extract/existing_gate_evidence" "$package_root/existing_gate_evidence"
fi

if [[ ! -f "$AI_NAS_PRODUCTION_CONTEXT_ROOT/scripts/probes/ai_nas_allowlisted_tool.sh" ]]; then
  echo "missing dispatcher in extracted production context: $AI_NAS_PRODUCTION_CONTEXT_ROOT/scripts/probes/ai_nas_allowlisted_tool.sh" >&2
  exit 2
fi

mkdir -p "$package_root/reports/package_rerun"
"${python_cmd[@]}" "$package_root/gates/stage2_readiness_gates.py" \
  --report-root "$package_root/reports/package_rerun" \
  --package-zip "$stage1_zip"
