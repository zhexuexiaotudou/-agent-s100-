#!/usr/bin/env bash
set -euo pipefail

venv="${DREAM_S100_VENV:-/opt/digua/dream-s100-oellm-venv}"
model_dir="${DREAM_MODEL_DIR:-/opt/digua/dream_hf}"
output_root="${DREAM_FINE_OUTPUT_ROOT:-/opt/digua/dream7b-segments-seq16-fine}"
seq_len="${DREAM_FINE_SEQ_LEN:-16}"
specs="${DREAM_FINE_SPECS:-26:28}"

source "$venv/bin/activate"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$output_root"

for spec in $specs; do
  s="${spec%:*}"
  e="${spec#*:}"
  dir="$(printf '%s/seg%02d_%02d' "$output_root" "$s" "$e")"
  echo "===COMPILE_FINE_SEGMENT $s $e $dir"
  rm -rf "$dir"
  mkdir -p "$dir"
  python -X faulthandler "$script_dir/compile_dream_segmented_full_forward.py" \
    --model-dir "$model_dir" \
    --output-dir "$dir" \
    --seq-len "$seq_len" \
    --segment-start "$s" \
    --segment-end "$e" \
    --dtype float32 \
    --march nash-e \
    --w-bits 8
  hbo="$(find "$dir" -maxdepth 1 -type f -name '*.hbo' | head -1)"
  if [[ -z "$hbo" ]]; then
    echo "Missing compiled HBO in $dir" >&2
    exit 4
  fi
  hbm="${hbo%.hbo}.hbm"
  python - "$hbo" "$hbm" <<'PY'
import sys
from pathlib import Path

from hbdk4.compiler import link
from hbdk4.compiler.hbm import Hbo

hbo = Path(sys.argv[1])
hbm = Path(sys.argv[2])

try:
    link([Hbo(str(hbo))], str(hbm))
except Exception as exc:
    if not hbm.exists() or hbm.stat().st_size == 0:
        raise
    print(
        "HBM file was written; ignoring post-link load check failure on this host: "
        f"{type(exc).__name__}: {exc}"
    )

if not hbm.exists() or hbm.stat().st_size == 0:
    raise SystemExit(f"missing linked HBM: {hbm}")
print(f"linked_hbm {hbm.stat().st_size} {hbm}")
PY
  find "$dir" -maxdepth 1 -type f -printf '%s %p\n' | sort -n
done
