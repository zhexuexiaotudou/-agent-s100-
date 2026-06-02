#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
nas_hbm_dir="${2:-/mnt/nas/openclaw/models/dream7b-hbm/segments6}"
local_hbm_dir="${3:-/home/sunrise/.cache/openclaw/dream7b-hbm/segments6}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

case "$nas_hbm_dir" in
  /mnt/nas/openclaw/models/dream7b-hbm/segments6|/mnt/nas/openclaw/models/dream7b-hbm/segments6/) ;;
  *)
    echo "Refusing NAS HBM path outside approved Dream 7B HBM directory: $nas_hbm_dir" >&2
    exit 2
    ;;
esac

case "$local_hbm_dir" in
  /home/sunrise/.cache/openclaw/dream7b-hbm/segments6|/home/sunrise/.cache/openclaw/dream7b-hbm/segments6/) ;;
  *)
    echo "Refusing local HBM cache path outside approved cache directory: $local_hbm_dir" >&2
    exit 2
    ;;
esac

if ! command -v dream7b-bpu-forward >/dev/null 2>&1; then
  echo "Missing deployed S100P command: dream7b-bpu-forward" >&2
  exit 4
fi

if [[ ! -d "$nas_hbm_dir" ]]; then
  echo "Missing NAS HBM directory: $nas_hbm_dir" >&2
  exit 4
fi

mkdir -p "$report_root" "$local_hbm_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_hbm_cache_perf_$stamp"
mkdir -p "$run_dir"

sync_log="$run_dir/cache_sync.log"
{
  echo "started_at=$(date --iso-8601=seconds)"
  echo "nas_hbm_dir=$nas_hbm_dir"
  echo "local_hbm_dir=$local_hbm_dir"
  time cp -u "$nas_hbm_dir"/dream7b_segment_*_seq16_q8.hbm "$local_hbm_dir"/
  cp -u "$nas_hbm_dir"/manifest.sha256 "$local_hbm_dir"/ 2>/dev/null || true
  echo "local_size=$(du -sh "$local_hbm_dir" | awk '{print $1}')"
  echo "finished_at=$(date --iso-8601=seconds)"
} > "$sync_log" 2>&1

run_forward() {
  local label="$1"
  local hbm_dir="$2"
  local out_dir="$run_dir/$label"
  local stdout="$run_dir/$label.stdout"
  local stderr="$run_dir/$label.stderr"
  local start_ns end_ns
  start_ns="$(date +%s%N)"
  DREAM7B_BPU_HBM_DIR="$hbm_dir" \
    dream7b-bpu-forward \
      --tokens "1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16" \
      --top-k 5 \
      --output-dir "$out_dir" > "$stdout" 2> "$stderr"
  end_ns="$(date +%s%N)"
  python3 - "$out_dir/summary.json" "$start_ns" "$end_ns" "$label" <<'PY'
import json
import sys
from pathlib import Path

summary_path, start_ns, end_ns, label = sys.argv[1:5]
data = json.loads(Path(summary_path).read_text(encoding="utf-8"))
load_ms = sum(float(item["load_ms"]) for item in data["segments"])
run_ms = sum(float(item["run_ms"]) for item in data["segments"])
wall_ms = (int(end_ns) - int(start_ns)) / 1_000_000.0
payload = {
    "label": label,
    "summary": summary_path,
    "hbm_dir": data["hbm_dir"],
    "wall_ms": round(wall_ms, 3),
    "load_ms": round(load_ms, 3),
    "run_ms": round(run_ms, 3),
    "load_to_run_ratio": round(load_ms / run_ms, 3) if run_ms else None,
    "segment_count": len(data["segments"]),
}
print(json.dumps(payload, ensure_ascii=False))
PY
}

nas_result="$(run_forward nas "$nas_hbm_dir")"
local_result="$(run_forward local "$local_hbm_dir")"

python3 - "$run_dir" "$sync_log" "$nas_result" "$local_result" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
sync_log = Path(sys.argv[2])
nas = json.loads(sys.argv[3])
local = json.loads(sys.argv[4])
load_speedup = nas["load_ms"] / local["load_ms"] if local["load_ms"] else None
wall_speedup = nas["wall_ms"] / local["wall_ms"] if local["wall_ms"] else None
payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_hbm_cache_perf_probe",
    "run_dir": str(run_dir),
    "cache_sync_log": str(sync_log),
    "nas": nas,
    "local": local,
    "load_speedup_local_vs_nas": round(load_speedup, 3) if load_speedup else None,
    "wall_speedup_local_vs_nas": round(wall_speedup, 3) if wall_speedup else None,
    "notes": [
        "This compares HBM load/run cost from NAS NFS versus a S100P local cache.",
        "It does not change the default production HBM path; set DREAM7B_BPU_HBM_DIR to use the local cache.",
    ],
}
(run_dir / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Dream 7B BPU HBM Cache Performance",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- cache_sync_log: {payload['cache_sync_log']}",
    f"- load_speedup_local_vs_nas: {payload['load_speedup_local_vs_nas']}",
    f"- wall_speedup_local_vs_nas: {payload['wall_speedup_local_vs_nas']}",
    "",
    "## Results",
    "",
    "| Path | Wall ms | HBM load ms | BPU run ms | Load/run ratio |",
    "| --- | ---: | ---: | ---: | ---: |",
    f"| NAS | {nas['wall_ms']:.3f} | {nas['load_ms']:.3f} | {nas['run_ms']:.3f} | {nas['load_to_run_ratio']:.3f} |",
    f"| Local cache | {local['wall_ms']:.3f} | {local['load_ms']:.3f} | {local['run_ms']:.3f} | {local['load_to_run_ratio']:.3f} |",
    "",
    "## Paths",
    "",
    f"- NAS HBM: {nas['hbm_dir']}",
    f"- Local HBM: {local['hbm_dir']}",
    f"- NAS summary: {nas['summary']}",
    f"- Local summary: {local['summary']}",
    "",
    "## Boundary",
    "",
    "- Local cache reduces HBM file load latency but does not remove per-step HBM load/release overhead.",
    "- The next optimization target is persistent host-side orchestration or a different segment residency strategy.",
]
(run_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "summary.md")
PY
