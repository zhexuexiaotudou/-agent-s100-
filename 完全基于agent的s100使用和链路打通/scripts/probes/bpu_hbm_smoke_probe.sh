#!/usr/bin/env bash
set -euo pipefail

report_dir="${1:-/mnt/nas/openclaw/reports/bpu}"
model_file="${2:-/opt/hobot/model/s100/basic/resnet18_224x224_nv12.hbm}"
frame_count="${BPU_FRAME_COUNT:-2000}"
thread_num="${BPU_THREAD_NUM:-8}"
core_id="${BPU_CORE_ID:-0}"
monitor_delay_ms="${BPU_MONITOR_DELAY_MS:-100}"
monitor_samples="${BPU_MONITOR_SAMPLES:-200}"

case "$report_dir" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_dir" >&2
    exit 2
    ;;
esac

case "$model_file" in
  /opt/hobot/model/s100/*|/mnt/nas/openclaw/models/*|/root/.openclaw/workspace/models/*|/tmp/*) ;;
  *)
    echo "Refusing model path outside approved model locations: $model_file" >&2
    exit 2
    ;;
esac

if [[ ! -f "$model_file" ]]; then
  echo "Model file not found: $model_file" >&2
  exit 3
fi

if [[ ! -x /usr/hobot/bin/hrt_model_exec ]]; then
  echo "Missing /usr/hobot/bin/hrt_model_exec" >&2
  exit 4
fi

if [[ ! -x /usr/hobot/bin/hrt_ucp_monitor ]]; then
  echo "Missing /usr/hobot/bin/hrt_ucp_monitor" >&2
  exit 4
fi

mkdir -p "$report_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_dir/bpu_hbm_smoke_$stamp"
mkdir -p "$run_dir" /tmp/bpu_hbm_smoke

y_bin="/tmp/bpu_hbm_smoke/input_y_224x224.bin"
uv_bin="/tmp/bpu_hbm_smoke/input_uv_112x112.bin"
python3 - <<'PY'
from pathlib import Path
Path("/tmp/bpu_hbm_smoke/input_y_224x224.bin").write_bytes(bytes([128]) * (224 * 224))
Path("/tmp/bpu_hbm_smoke/input_uv_112x112.bin").write_bytes(bytes([128]) * (112 * 112 * 2))
PY

core_num="$(cat /sys/devices/system/bpu/core_num 2>/dev/null || echo unknown)"
bpu_freq="$(cat /sys/class/devfreq/28108000.bpu/cur_freq 2>/dev/null || echo unknown)"
bpu_governor="$(cat /sys/class/devfreq/28108000.bpu/governor 2>/dev/null || echo unknown)"

/usr/hobot/bin/hrt_model_exec model_info \
  --model_file "$model_file" \
  > "$run_dir/model_info.log" 2>&1

/usr/hobot/bin/hrt_model_exec infer \
  --model_file "$model_file" \
  --input_file "$y_bin,$uv_bin" \
  --frame_count 1 \
  --enable_dump true \
  --dump_format txt \
  --dump_path "$run_dir/infer_dump" \
  > "$run_dir/infer.log" 2>&1

start_ms="$(date +%s%3N)"
/usr/hobot/bin/hrt_ucp_monitor \
  -b -e bpu -d "$monitor_delay_ms" -n "$monitor_samples" \
  > "$run_dir/monitor.log" 2>&1 &
monitor_pid=$!

perf_rc=0
/usr/hobot/bin/hrt_model_exec perf \
  --model_file "$model_file" \
  --input_file "$y_bin,$uv_bin" \
  --frame_count "$frame_count" \
  --thread_num "$thread_num" \
  --core_id "$core_id" \
  --profile_path "$run_dir/profile" \
  > "$run_dir/perf.log" 2>&1 || perf_rc=$?
end_ms="$(date +%s%3N)"
wait "$monitor_pid" || true

elapsed_ms="$((end_ms - start_ms))"
infer_time_ms="$(grep -Eo 'Infer time: [0-9.]+ ms' "$run_dir/infer.log" | tail -1 | awk '{print $3}' || true)"
avg_latency_ms="$(grep -Eo 'Average[[:space:]]+latency[[:space:]]+is: [0-9.]+ ms' "$run_dir/perf.log" | tail -1 | awk '{print $(NF-1)}' || true)"
fps="$(grep -Eo 'Frame[[:space:]]+rate[[:space:]]+is: [0-9.]+ FPS' "$run_dir/perf.log" | tail -1 | awk '{print $(NF-1)}' || true)"
program_run_ms="$(grep -Eo 'Program run time: [0-9.]+ ms' "$run_dir/perf.log" | tail -1 | awk '{print $(NF-1)}' || true)"
max_loading="$(grep -Eo 'BPU[0-9][[:space:]]+[0-9.]+[[:space:]]*' "$run_dir/monitor.log" | awk '{ if ($2+0 > max) max=$2+0 } END { if (max == "") print "unknown"; else printf "%.1f", max }')"
model_name="$(grep -E '^\[model name\]:' "$run_dir/model_info.log" | head -1 | sed 's/^\[model name\]: *//' || true)"
march="$(grep -Eo '"MARCH": "[^"]+"' "$run_dir/model_info.log" | head -1 | sed 's/"MARCH": "//; s/"$//' || true)"
model_core_num="$(grep -Eo '"CORE_NUM": [0-9]+' "$run_dir/model_info.log" | head -1 | awk '{print $2}' || true)"

verdict="ok_bpu_hbm_smoke"
if [[ "$perf_rc" -ne 0 ]]; then
  verdict="failed_perf_exit_$perf_rc"
fi

json="$run_dir/summary.json"
report="$run_dir/summary.md"
python3 - "$json" <<PY
import json
payload = {
    "generated_at": "$(date -Is)",
    "verdict": "$verdict",
    "run_dir": "$run_dir",
    "model_file": "$model_file",
    "model_name": "$model_name",
    "model_march": "$march",
    "model_core_num": "$model_core_num",
    "system_bpu_core_num": "$core_num",
    "system_bpu_cur_freq_hz": "$bpu_freq",
    "system_bpu_governor": "$bpu_governor",
    "core_id": "$core_id",
    "frame_count": int("$frame_count"),
    "thread_num": int("$thread_num"),
    "elapsed_ms": int("$elapsed_ms"),
    "infer_time_ms": "$infer_time_ms",
    "average_latency_ms": "$avg_latency_ms",
    "fps": "$fps",
    "program_run_ms": "$program_run_ms",
    "max_bpu_loading_percent": "$max_loading",
    "logs": {
        "model_info": "$run_dir/model_info.log",
        "infer": "$run_dir/infer.log",
        "perf": "$run_dir/perf.log",
        "monitor": "$run_dir/monitor.log",
        "profile": "$run_dir/profile",
    },
}
with open("$json", "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
PY

{
  echo "# S100P BPU HBM Smoke"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- verdict: $verdict"
  echo "- run_dir: $run_dir"
  echo "- summary_json: $json"
  echo
  echo "## Hardware"
  echo
  echo "| Check | Value |"
  echo "| --- | --- |"
  echo "| System BPU cores exposed | $core_num |"
  echo "| BPU current frequency Hz | $bpu_freq |"
  echo "| BPU governor | $bpu_governor |"
  echo "| hrt_model_exec core_id | $core_id |"
  echo
  echo "## Model"
  echo
  echo "| Check | Value |"
  echo "| --- | --- |"
  echo "| Model file | $model_file |"
  echo "| Model name | ${model_name:-unknown} |"
  echo "| MARCH | ${march:-unknown} |"
  echo "| Model CORE_NUM | ${model_core_num:-unknown} |"
  echo
  echo "## Results"
  echo
  echo "| Metric | Value |"
  echo "| --- | --- |"
  echo "| Single-frame infer time ms | ${infer_time_ms:-unknown} |"
  echo "| Perf frame count | $frame_count |"
  echo "| Perf threads | $thread_num |"
  echo "| Perf elapsed wall ms | $elapsed_ms |"
  echo "| Program run time ms | ${program_run_ms:-unknown} |"
  echo "| Average latency ms | ${avg_latency_ms:-unknown} |"
  echo "| Frame rate FPS | ${fps:-unknown} |"
  echo "| Max BPU loading percent sampled | $max_loading |"
  echo
  echo "## Evidence Files"
  echo
  echo "- model_info: $run_dir/model_info.log"
  echo "- infer: $run_dir/infer.log"
  echo "- perf: $run_dir/perf.log"
  echo "- monitor: $run_dir/monitor.log"
  echo "- profile: $run_dir/profile"
  echo
  echo "## Interpretation"
  echo
  echo "- This proves the S100P BPU path is usable for compiled S100/Nash-E .hbm models."
  echo "- This does not mean Dream 7B is using BPU; the current Dream 7B GGUF runtime remains CPU-only."
  echo "- A model can only consume the 128 TOPS path after it is converted/compiled into an S100-compatible .hbm or supported by the S100 LLM toolchain."
} > "$report"

echo "$report"
exit "$perf_rc"
