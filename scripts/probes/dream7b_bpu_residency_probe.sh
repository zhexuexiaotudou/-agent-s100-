#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
hbm_dir="${2:-/home/sunrise/.cache/openclaw/dream7b-hbm/segments6}"
venv="${DREAM7B_BPU_VENV:-/mnt/nas/openclaw/runtimes/hbm-runtime-venv}"
combo_timeout="${DREAM7B_BPU_RESIDENCY_TIMEOUT:-120}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

case "$hbm_dir" in
  /mnt/nas/openclaw/models/dream7b-hbm/segments6|/mnt/nas/openclaw/models/dream7b-hbm/segments6/|/home/sunrise/.cache/openclaw/dream7b-hbm/segments6|/home/sunrise/.cache/openclaw/dream7b-hbm/segments6/) ;;
  *)
    echo "Refusing HBM path outside approved Dream 7B HBM directories: $hbm_dir" >&2
    exit 2
    ;;
esac

if [[ ! -x "$venv/bin/python" ]]; then
  echo "Missing Dream 7B BPU runtime venv: $venv" >&2
  exit 4
fi

if [[ ! -d "$hbm_dir" ]]; then
  echo "Missing Dream 7B segmented HBM directory: $hbm_dir" >&2
  exit 4
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_residency_$stamp"
mkdir -p "$run_dir"

"$venv/bin/python" - "$hbm_dir" "$run_dir" "$combo_timeout" <<'PY'
import itertools
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

hbm_dir = Path(sys.argv[1])
run_dir = Path(sys.argv[2])
combo_timeout = int(sys.argv[3])

segments = [
    ("seg00_04", "dream7b_segment_0_4_seq16_q8.hbm"),
    ("seg04_07", "dream7b_segment_4_7_seq16_q8.hbm"),
    ("seg07_14", "dream7b_segment_7_14_seq16_q8.hbm"),
    ("seg14_21", "dream7b_segment_14_21_seq16_q8.hbm"),
    ("seg21_24", "dream7b_segment_21_24_seq16_q8.hbm"),
    ("seg24_28", "dream7b_segment_24_28_seq16_q8.hbm"),
]

for _, file_name in segments:
    path = hbm_dir / file_name
    if not path.exists():
        raise SystemExit(f"missing HBM segment: {path}")

child_code = r"""
import json
import os
import sys
import time
from pathlib import Path

from hbm_runtime import HB_HBMRuntime

combo = json.loads(os.environ["DREAM7B_RESIDENCY_COMBO"])
hbm_dir = Path(os.environ["DREAM7B_RESIDENCY_HBM_DIR"])
runtimes = []
events = []
started = time.perf_counter()
for segment_id, file_name in combo:
    path = hbm_dir / file_name
    t0 = time.perf_counter()
    runtime = HB_HBMRuntime(str(path))
    t1 = time.perf_counter()
    runtimes.append(runtime)
    events.append({
        "segment": segment_id,
        "file": str(path),
        "load_ms": round((t1 - t0) * 1000, 3),
    })
print(json.dumps({
    "loaded": [item[0] for item in combo],
    "events": events,
    "total_ms": round((time.perf_counter() - started) * 1000, 3),
    "runtime_version": HB_HBMRuntime.version,
}, ensure_ascii=False))
"""

def run_combo(combo):
    label = "__".join(item[0] for item in combo)
    out_path = run_dir / f"{label}.stdout"
    err_path = run_dir / f"{label}.stderr"
    env = dict(**__import__("os").environ)
    env["DREAM7B_RESIDENCY_COMBO"] = json.dumps(combo)
    env["DREAM7B_RESIDENCY_HBM_DIR"] = str(hbm_dir)
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
            "segments": [item[0] for item in combo],
            "segment_count": len(combo),
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
            "segments": [item[0] for item in combo],
            "segment_count": len(combo),
            "returncode": None,
            "ok": False,
            "timeout": True,
            "stdout": str(out_path),
            "stderr": str(err_path),
            "stderr_preview": (exc.stderr or "")[-1000:],
        }

results = []
for segment in segments:
    results.append(run_combo([segment]))
for combo in itertools.combinations(segments, 2):
    results.append(run_combo(list(combo)))

successful_pairs = [item for item in results if item["ok"] and item["segment_count"] == 2]
failed_pairs = [item for item in results if not item["ok"] and item["segment_count"] == 2]
single_failures = [item for item in results if not item["ok"] and item["segment_count"] == 1]

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_residency_probe" if not single_failures else "blocked_dream7b_bpu_residency_probe",
    "hbm_dir": str(hbm_dir),
    "combo_timeout_seconds": combo_timeout,
    "single_failures": single_failures,
    "successful_pair_count": len(successful_pairs),
    "failed_pair_count": len(failed_pairs),
    "successful_pairs": [
        {
            "segments": item["segments"],
            "total_ms": item.get("parsed", {}).get("total_ms"),
            "events": item.get("parsed", {}).get("events"),
        }
        for item in successful_pairs
    ],
    "failed_pairs": [
        {
            "segments": item["segments"],
            "returncode": item["returncode"],
            "timeout": item.get("timeout", False),
            "stderr_preview": item.get("stderr_preview", ""),
        }
        for item in failed_pairs
    ],
    "results": results,
    "notes": [
        "This tests whether multiple Dream 7B HBM segments can be held resident in one process.",
        "It is a load-residency probe; it does not run inference for resident pairs.",
        "Use this evidence before implementing a persistent host-side segment orchestrator.",
    ],
}

(run_dir / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
lines = [
    "# Dream 7B BPU Segment Residency Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- hbm_dir: {payload['hbm_dir']}",
    f"- successful_pair_count: {payload['successful_pair_count']}",
    f"- failed_pair_count: {payload['failed_pair_count']}",
    "",
    "## Successful Pairs",
    "",
    "| Segments | Total load ms |",
    "| --- | ---: |",
]
if successful_pairs:
    for item in payload["successful_pairs"]:
        lines.append(f"| {', '.join(item['segments'])} | {item['total_ms']} |")
else:
    lines.append("| none |  |")
lines.extend([
    "",
    "## Failed Pairs",
    "",
    "| Segments | Return code | Timeout |",
    "| --- | ---: | --- |",
])
if failed_pairs:
    for item in payload["failed_pairs"]:
        lines.append(f"| {', '.join(item['segments'])} | {item['returncode']} | {item['timeout']} |")
else:
    lines.append("| none |  |  |")
lines.extend([
    "",
    "## Boundary",
    "",
    "- Pair residency success does not by itself prove a useful production residency plan.",
    "- Pair residency failure means that persistent all-segment orchestration is not viable with the current split.",
])
(run_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "summary.md")
PY
