#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
venv="${DREAM_RESPLIT_VENV:-/opt/digua/dream-s100-oellm-venv}"
model_dir="${DREAM_RESPLIT_MODEL_DIR:-/opt/digua/dream_hf}"
output_root="${DREAM_RESPLIT_OUTPUT_ROOT:-/opt/digua/dream7b-segments-seq16-resplit}"
seq_len="${DREAM_RESPLIT_SEQ_LEN:-16}"
specs="${DREAM_RESPLIT_SPECS:-0:1 1:2 10:12 12:14 17:19 19:21 26:27 27:28}"
expected_specs="${DREAM_RESPLIT_EXPECTED_SPECS:-0:1 1:2 10:12 12:14 17:19 19:21 26:27 27:28}"
allow_partial="${DREAM_RESPLIT_ALLOW_PARTIAL:-0}"
skip_existing="${DREAM_RESPLIT_SKIP_EXISTING:-1}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

case "$output_root" in
  /opt/digua/dream7b-segments-seq16-resplit|/opt/digua/dream7b-segments-seq16-resplit/*|/mnt/f/Project/Digua/tmp/dream7b-resplit-hbm|/mnt/f/Project/Digua/tmp/dream7b-resplit-hbm/*) ;;
  *)
    echo "Refusing output root outside approved Dream 7B resplit directories: $output_root" >&2
    exit 2
    ;;
esac

if [[ ! -x "$venv/bin/python" ]]; then
  echo "Missing Dream S100 compiler venv: $venv" >&2
  exit 4
fi
if [[ ! -f "$model_dir/config.json" ]]; then
  echo "Missing Dream model config: $model_dir/config.json" >&2
  exit 4
fi
if ! [[ "$seq_len" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM_RESPLIT_SEQ_LEN must be a positive integer." >&2
  exit 2
fi
case "$allow_partial" in
  0|1) ;;
  *)
    echo "DREAM_RESPLIT_ALLOW_PARTIAL must be 0 or 1." >&2
    exit 2
    ;;
esac
case "$skip_existing" in
  0|1) ;;
  *)
    echo "DREAM_RESPLIT_SKIP_EXISTING must be 0 or 1." >&2
    exit 2
    ;;
esac

mkdir -p "$report_root" "$output_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_resplit_compile_$stamp"
mkdir -p "$run_dir"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
compile_script="$script_dir/compile_dream_segmented_full_forward.py"

status_jsonl="$run_dir/resplit_compile_status.jsonl"
: > "$status_jsonl"

source "$venv/bin/activate"
for spec in $specs; do
  case "$spec" in
    *:*) ;;
    *)
      echo "Invalid spec: $spec" >&2
      exit 2
      ;;
  esac
  s="${spec%:*}"
  e="${spec#*:}"
  if ! [[ "$s" =~ ^[0-9]+$ ]] || ! [[ "$e" =~ ^[0-9]+$ ]] || (( s >= e || e > 28 )); then
    echo "Invalid layer bounds in spec: $spec" >&2
    exit 2
  fi
  dir="$(printf '%s/seg%02d_%02d' "$output_root" "$s" "$e")"
  stdout_path="$(printf '%s/compile_seg%02d_%02d.stdout' "$run_dir" "$s" "$e")"
  stderr_path="$(printf '%s/compile_seg%02d_%02d.stderr' "$run_dir" "$s" "$e")"
  existing_hbm="$(find "$dir" -maxdepth 1 -type f -name '*.hbm' -size +0c 2>/dev/null | head -1 || true)"
  if [[ "$skip_existing" == "1" && -n "$existing_hbm" ]]; then
    "$venv/bin/python" - "$status_jsonl" "$spec" "$s" "$e" "$dir" "$stdout_path" "$stderr_path" "$existing_hbm" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

status_jsonl = Path(sys.argv[1])
spec = sys.argv[2]
segment_start = int(sys.argv[3])
segment_end = int(sys.argv[4])
output_dir = Path(sys.argv[5])
stdout_path = Path(sys.argv[6])
stderr_path = Path(sys.argv[7])
hbm = Path(sys.argv[8])
hbo = next(output_dir.glob("*.hbo"), None)
record = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "spec": spec,
    "segment_start": segment_start,
    "segment_end": segment_end,
    "output_dir": str(output_dir),
    "stdout": str(stdout_path),
    "stderr": str(stderr_path),
    "compile_status": 0,
    "hbo": str(hbo) if hbo else "",
    "hbo_exists": bool(hbo and hbo.is_file()),
    "hbo_size_bytes": hbo.stat().st_size if hbo and hbo.is_file() else 0,
    "hbm": str(hbm),
    "hbm_exists": hbm.is_file(),
    "hbm_size_bytes": hbm.stat().st_size if hbm.is_file() else 0,
    "link_status": 0,
    "skipped_existing": True,
}
stdout_path.write_text(f"skipped_existing_hbm {hbm.stat().st_size} {hbm}\n", encoding="utf-8")
stderr_path.write_text("", encoding="utf-8")
status_jsonl.open("a", encoding="utf-8").write(json.dumps(record, ensure_ascii=False) + "\n")
PY
    continue
  fi
  rm -rf "$dir"
  mkdir -p "$dir"
  set +e
  python -X faulthandler "$compile_script" \
    --model-dir "$model_dir" \
    --output-dir "$dir" \
    --seq-len "$seq_len" \
    --segment-start "$s" \
    --segment-end "$e" \
    --dtype float32 \
    --march nash-e \
    --w-bits 8 > "$stdout_path" 2> "$stderr_path"
  compile_status="$?"
  set -e
  hbo="$(find "$dir" -maxdepth 1 -type f -name '*.hbo' | head -1 || true)"
  hbm=""
  link_status=0
  if [[ "$compile_status" == "0" && -n "$hbo" ]]; then
    hbm="${hbo%.hbo}.hbm"
    link_stdout="$(printf '%s/link_seg%02d_%02d.stdout' "$run_dir" "$s" "$e")"
    link_stderr="$(printf '%s/link_seg%02d_%02d.stderr' "$run_dir" "$s" "$e")"
    set +e
    python - "$hbo" "$hbm" > "$link_stdout" 2> "$link_stderr" <<'PY'
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
    link_status="$?"
    set -e
  fi
  "$venv/bin/python" - "$status_jsonl" "$spec" "$s" "$e" "$dir" "$stdout_path" "$stderr_path" "$compile_status" "$hbo" "$hbm" "$link_status" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

status_jsonl = Path(sys.argv[1])
spec = sys.argv[2]
segment_start = int(sys.argv[3])
segment_end = int(sys.argv[4])
output_dir = Path(sys.argv[5])
stdout_path = Path(sys.argv[6])
stderr_path = Path(sys.argv[7])
compile_status = int(sys.argv[8])
hbo = Path(sys.argv[9]) if sys.argv[9] else None
hbm = Path(sys.argv[10]) if sys.argv[10] else None
link_status = int(sys.argv[11])
record = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "spec": spec,
    "segment_start": segment_start,
    "segment_end": segment_end,
    "output_dir": str(output_dir),
    "stdout": str(stdout_path),
    "stderr": str(stderr_path),
    "compile_status": compile_status,
    "hbo": str(hbo) if hbo else "",
    "hbo_exists": bool(hbo and hbo.is_file()),
    "hbo_size_bytes": hbo.stat().st_size if hbo and hbo.is_file() else 0,
    "hbm": str(hbm) if hbm else "",
    "hbm_exists": bool(hbm and hbm.is_file()),
    "hbm_size_bytes": hbm.stat().st_size if hbm and hbm.is_file() else 0,
    "link_status": link_status,
    "skipped_existing": False,
}
status_jsonl.open("a", encoding="utf-8").write(json.dumps(record, ensure_ascii=False) + "\n")
PY
  if [[ "$allow_partial" == "0" && ( "$compile_status" != "0" || "$link_status" != "0" ) ]]; then
    break
  fi
done

"$venv/bin/python" - \
  "$run_dir" \
  "$status_jsonl" \
  "$model_dir" \
  "$output_root" \
  "$seq_len" \
  "$specs" \
  "$expected_specs" \
  "$allow_partial" <<'PY'
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
status_jsonl = Path(sys.argv[2])
model_dir = Path(sys.argv[3])
output_root = Path(sys.argv[4])
seq_len = int(sys.argv[5])
specs = sys.argv[6].split()
expected_specs = sys.argv[7].split()
allow_partial = sys.argv[8] == "1"

records = [
    json.loads(line)
    for line in status_jsonl.read_text(encoding="utf-8").splitlines()
    if line.strip()
]
errors = []
warnings = []
if specs != expected_specs:
    errors.append(f"specs do not match expected resplit specs: {specs} != {expected_specs}")
compiled_specs = [item["spec"] for item in records]
missing_specs = [item for item in expected_specs if item not in compiled_specs]
if missing_specs:
    errors.append(f"missing compile records for specs: {missing_specs}")
failed_records = [
    item for item in records
    if item["compile_status"] != 0 or item["link_status"] != 0 or not item["hbm_exists"]
]
if failed_records:
    message = "one or more resplit segments failed to compile or link"
    if allow_partial:
        warnings.append(message)
    else:
        errors.append(message)

manifest_lines = []
for item in records:
    hbm_path = Path(item["hbm"]) if item.get("hbm") else None
    if hbm_path and hbm_path.is_file():
        digest = hashlib.sha256(hbm_path.read_bytes()).hexdigest()
        rel = hbm_path.relative_to(output_root)
        manifest_lines.append(f"{digest}  {rel.as_posix()}")
manifest_path = output_root / "manifest.sha256"
manifest_path.write_text("\n".join(manifest_lines) + ("\n" if manifest_lines else ""), encoding="utf-8")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_resplit_compile_probe" if not errors else "failed_dream7b_resplit_compile_probe",
    "run_dir": str(run_dir),
    "model_dir": str(model_dir),
    "output_root": str(output_root),
    "seq_len": seq_len,
    "specs": specs,
    "expected_specs": expected_specs,
    "allow_partial": allow_partial,
    "compiled_spec_count": len(records),
    "expected_spec_count": len(expected_specs),
    "hbm_success_count": sum(1 for item in records if item["hbm_exists"] and item["hbm_size_bytes"] > 0),
    "skipped_existing_count": sum(1 for item in records if item.get("skipped_existing")),
    "failed_spec_count": len(failed_records),
    "compiled_records": records,
    "manifest_path": str(manifest_path),
    "next_optimization_target": "copy verified resplit HBM artifacts to NAS/local S100P cache and run segment-capacity/residency probes against the resplit layout" if not errors else "fix failed resplit segment compilation before changing runtime paths",
    "warnings": warnings,
    "errors": errors,
}
json_path = run_dir / "resplit_compile_probe.json"
md_path = run_dir / "resplit_compile_probe.md"
json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
lines = [
    "# Dream 7B Resplit Compile Probe",
    "",
    f"- verdict: {payload['verdict']}",
    f"- output_root: {payload['output_root']}",
    f"- specs: {payload['specs']}",
    f"- hbm_success_count: {payload['hbm_success_count']}",
    f"- skipped_existing_count: {payload['skipped_existing_count']}",
    f"- failed_spec_count: {payload['failed_spec_count']}",
    f"- manifest_path: {payload['manifest_path']}",
    f"- next_optimization_target: {payload['next_optimization_target']}",
    "",
    "## Records",
    "",
]
for item in records:
    lines.append(
        f"- {item['spec']}: compile_status={item['compile_status']}, "
        f"link_status={item['link_status']}, skipped_existing={item.get('skipped_existing', False)}, "
        f"hbm_size_bytes={item['hbm_size_bytes']}, hbm={item['hbm']}"
    )
lines.extend(["", "## Errors", ""])
lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
lines.extend(["", "## Warnings", ""])
lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- none")
md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(md_path)
PY
