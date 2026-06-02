#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
base_hbm_dir="${2:-/home/sunrise/.cache/openclaw/dream7b-hbm/segments6}"
fine_hbm_dir="${3:-/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16}"
venv="${DREAM7B_BPU_VENV:-/mnt/nas/openclaw/runtimes/hbm-runtime-venv}"
combo_timeout="${DREAM7B_BPU_FINE_RESIDENCY_TIMEOUT:-120}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

case "$base_hbm_dir" in
  /mnt/nas/openclaw/models/dream7b-hbm/segments6|/mnt/nas/openclaw/models/dream7b-hbm/segments6/|/home/sunrise/.cache/openclaw/dream7b-hbm/segments6|/home/sunrise/.cache/openclaw/dream7b-hbm/segments6/) ;;
  *)
    echo "Refusing base HBM path outside approved Dream 7B HBM directories: $base_hbm_dir" >&2
    exit 2
    ;;
esac

case "$fine_hbm_dir" in
  /mnt/nas/openclaw/models/dream7b-hbm/fine-seq16|/mnt/nas/openclaw/models/dream7b-hbm/fine-seq16/|/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16|/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16/) ;;
  *)
    echo "Refusing fine HBM path outside approved Dream 7B HBM directories: $fine_hbm_dir" >&2
    exit 2
    ;;
esac

if [[ ! -x "$venv/bin/python" ]]; then
  echo "Missing Dream 7B BPU runtime venv: $venv" >&2
  exit 4
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_fine_residency_$stamp"
mkdir -p "$run_dir"

"$venv/bin/python" - "$base_hbm_dir" "$fine_hbm_dir" "$run_dir" "$combo_timeout" <<'PY'
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

base_hbm_dir = Path(sys.argv[1])
fine_hbm_dir = Path(sys.argv[2])
run_dir = Path(sys.argv[3])
combo_timeout = int(sys.argv[4])

segments = {
    "seg04_07": base_hbm_dir / "dream7b_segment_4_7_seq16_q8.hbm",
    "seg21_24": base_hbm_dir / "dream7b_segment_21_24_seq16_q8.hbm",
    "seg24_28": base_hbm_dir / "dream7b_segment_24_28_seq16_q8.hbm",
    "seg24_26": fine_hbm_dir / "seg24_26" / "dream7b_segment_24_26_seq16_q8.hbm",
    "seg26_28": fine_hbm_dir / "seg26_28" / "dream7b_segment_26_28_seq16_q8.hbm",
}

for segment_id, path in segments.items():
    if not path.exists():
        raise SystemExit(f"missing HBM segment {segment_id}: {path}")

combos = [
    ["seg24_26"],
    ["seg26_28"],
    ["seg24_26", "seg26_28"],
    ["seg21_24", "seg24_26"],
    ["seg04_07", "seg26_28"],
    ["seg21_24", "seg26_28"],
    ["seg21_24", "seg24_26", "seg26_28"],
    ["seg04_07", "seg21_24", "seg26_28"],
    ["seg24_28", "seg26_28"],
]

child_code = r"""
import json
import os
import sys
import time

from hbm_runtime import HB_HBMRuntime

combo = json.loads(os.environ["DREAM7B_FINE_RESIDENCY_COMBO"])
runtimes = []
events = []
started = time.perf_counter()
for segment_id, path in combo:
    t0 = time.perf_counter()
    runtime = HB_HBMRuntime(path)
    t1 = time.perf_counter()
    runtimes.append(runtime)
    events.append({
        "segment": segment_id,
        "file": path,
        "load_ms": round((t1 - t0) * 1000, 3),
    })
print(json.dumps({
    "loaded": [item[0] for item in combo],
    "events": events,
    "total_ms": round((time.perf_counter() - started) * 1000, 3),
    "runtime_version": HB_HBMRuntime.version,
}, ensure_ascii=False))
"""

def run_combo(segment_ids):
    label = "__".join(segment_ids)
    combo = [(segment_id, str(segments[segment_id])) for segment_id in segment_ids]
    out_path = run_dir / f"{label}.stdout"
    err_path = run_dir / f"{label}.stderr"
    env = dict(os.environ)
    env["DREAM7B_FINE_RESIDENCY_COMBO"] = json.dumps(combo)
    try:
        proc = subprocess.run(
            [sys.executable, "-c", child_code],
            text=True,
            capture_output=True,
            timeout=combo_timeout,
            env=env,
        )
        out_path.write_text(proc.stdout, encoding="utf-8")
        err_path.write_text(proc.stderr, encoding="utf-8")
        parsed = None
        for line in proc.stdout.splitlines()[::-1]:
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                parsed = json.loads(line)
                break
        return {
            "label": label,
            "segments": segment_ids,
            "segment_count": len(segment_ids),
            "returncode": proc.returncode,
            "ok": proc.returncode == 0 and parsed is not None,
            "stdout": str(out_path),
            "stderr": str(err_path),
            "parsed": parsed,
            "stderr_preview": proc.stderr[-1000:],
        }
    except subprocess.TimeoutExpired as exc:
        out_path.write_text(exc.stdout or "", encoding="utf-8")
        err_path.write_text(exc.stderr or "", encoding="utf-8")
        return {
            "label": label,
            "segments": segment_ids,
            "segment_count": len(segment_ids),
            "returncode": None,
            "ok": False,
            "timeout": True,
            "stdout": str(out_path),
            "stderr": str(err_path),
            "stderr_preview": (exc.stderr or "")[-1000:],
        }

results = [run_combo(combo) for combo in combos]
ok_results = [item for item in results if item["ok"]]
failed_results = [item for item in results if not item["ok"]]
critical_pairs = {
    tuple(["seg24_26", "seg26_28"]),
    tuple(["seg21_24", "seg24_26"]),
    tuple(["seg04_07", "seg26_28"]),
    tuple(["seg21_24", "seg26_28"]),
}
ok_pairs = {tuple(item["segments"]) for item in ok_results}
critical_ok = critical_pairs.issubset(ok_pairs)

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_fine_residency_probe" if critical_ok else "blocked_dream7b_bpu_fine_residency_probe",
    "base_hbm_dir": str(base_hbm_dir),
    "fine_hbm_dir": str(fine_hbm_dir),
    "combo_timeout_seconds": combo_timeout,
    "segments": {key: str(value) for key, value in segments.items()},
    "critical_pairs_ok": critical_ok,
    "ok_count": len(ok_results),
    "failed_count": len(failed_results),
    "results": results,
    "notes": [
        "This probes whether finer Dream 7B tail segments lower residency pressure on S100P.",
        "The critical path is whether seg26_28 can coexist with the existing small base segments.",
        "It is a load-residency probe; it does not run inference for resident combinations.",
    ],
}
(run_dir / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Dream 7B BPU Fine Segment Residency Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- base_hbm_dir: {payload['base_hbm_dir']}",
    f"- fine_hbm_dir: {payload['fine_hbm_dir']}",
    f"- critical_pairs_ok: {payload['critical_pairs_ok']}",
    "",
    "## Results",
    "",
    "| Segments | OK | Total load ms |",
    "| --- | --- | ---: |",
]
for item in results:
    parsed = item.get("parsed") or {}
    total_ms = parsed.get("total_ms", "")
    lines.append(f"| {', '.join(item['segments'])} | {item['ok']} | {total_ms} |")
lines.extend([
    "",
    "## Boundary",
    "",
    "- Success here supports continuing the fine-split compile path.",
    "- It does not prove that the whole Dream 7B graph can be resident until the remaining large segments are split and retested.",
])
(run_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "summary.md")
PY
