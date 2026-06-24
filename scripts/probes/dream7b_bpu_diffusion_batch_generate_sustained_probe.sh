#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
round_count="${DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_ROUND_COUNT:-3}"
batch_count="${DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_BATCH_COUNT:-16}"
generate_cmd="${DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_CMD:-dream7b-bpu-diffusion-batch-generate}"
monitor_delay_ms="${DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_MONITOR_DELAY_MS:-100}"
monitor_sample_count="${DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_MONITOR_SAMPLE_COUNT:-2400}"
timeout_sec="${DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_TIMEOUT_SEC:-900}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

if ! [[ "$round_count" =~ ^[1-9][0-9]*$ ]] || (( round_count > 4 )); then
  echo "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_ROUND_COUNT must be an integer from 1 to 4." >&2
  exit 2
fi
if ! [[ "$batch_count" =~ ^[1-9][0-9]*$ ]] || (( batch_count > 16 )); then
  echo "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_BATCH_COUNT must be an integer from 1 to 16." >&2
  exit 2
fi
if ! [[ "$monitor_delay_ms" =~ ^[0-9]+$ ]] || (( monitor_delay_ms < 100 || monitor_delay_ms > 10000 )); then
  echo "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_MONITOR_DELAY_MS must be an integer from 100 to 10000." >&2
  exit 2
fi
if ! [[ "$monitor_sample_count" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_MONITOR_SAMPLE_COUNT must be a positive integer." >&2
  exit 2
fi
if ! [[ "$timeout_sec" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SUSTAINED_TIMEOUT_SEC must be a positive integer." >&2
  exit 2
fi

if ! command -v "$generate_cmd" >/dev/null 2>&1; then
  echo "Missing deployed command: $generate_cmd" >&2
  exit 4
fi
if ! command -v hrt_ucp_monitor >/dev/null 2>&1; then
  echo "Missing deployed command: hrt_ucp_monitor" >&2
  exit 4
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_diffusion_batch_generate_sustained_$stamp"
mkdir -p "$run_dir"
monitor_stdout="$run_dir/hrt_ucp_monitor.stdout"
monitor_stderr="$run_dir/hrt_ucp_monitor.stderr"
round_status_tsv="$run_dir/round_status.tsv"
somstatus_before="$run_dir/hrut_somstatus_before.txt"
somstatus_after="$run_dir/hrut_somstatus_after.txt"

printf 'round_index\tstatus\tstart_ms\tend_ms\trun_dir\tstdout\tstderr\n' > "$round_status_tsv"
hrut_somstatus > "$somstatus_before" 2>&1 || true
hrt_ucp_monitor -b -e bpu -d "$monitor_delay_ms" -n "$monitor_sample_count" > "$monitor_stdout" 2> "$monitor_stderr" &
monitor_pid="$!"
sleep 0.3

cleanup_monitor() {
  if kill -0 "$monitor_pid" >/dev/null 2>&1; then
    kill "$monitor_pid" >/dev/null 2>&1 || true
    wait "$monitor_pid" >/dev/null 2>&1 || true
  else
    wait "$monitor_pid" >/dev/null 2>&1 || true
  fi
}
trap cleanup_monitor EXIT

for round_index in $(seq 1 "$round_count"); do
  round_name="$(printf 'generation_round_%02d' "$round_index")"
  generation_dir="$run_dir/$round_name"
  generation_stdout="$run_dir/$round_name.stdout"
  generation_stderr="$run_dir/$round_name.stderr"
  mkdir -p "$generation_dir"
  start_ms="$(date +%s%3N)"
  set +e
  timeout "$timeout_sec" "$generate_cmd" \
    --run-dir "$generation_dir" \
    --batch-count "$batch_count" > "$generation_stdout" 2> "$generation_stderr"
  generation_status="$?"
  set -e
  end_ms="$(date +%s%3N)"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$round_index" \
    "$generation_status" \
    "$start_ms" \
    "$end_ms" \
    "$generation_dir" \
    "$generation_stdout" \
    "$generation_stderr" >> "$round_status_tsv"
  if [[ "$generation_status" != "0" ]]; then
    break
  fi
done

cleanup_monitor
trap - EXIT
hrut_somstatus > "$somstatus_after" 2>&1 || true

python3 - \
  "$run_dir" \
  "$round_status_tsv" \
  "$round_count" \
  "$batch_count" \
  "$generate_cmd" \
  "$monitor_delay_ms" \
  "$monitor_sample_count" \
  "$timeout_sec" <<'PY'
import csv
import json
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
round_status_tsv = Path(sys.argv[2])
round_count = int(sys.argv[3])
batch_count = int(sys.argv[4])
generate_cmd = sys.argv[5]
monitor_delay_ms = int(sys.argv[6])
monitor_sample_count = int(sys.argv[7])
timeout_sec = int(sys.argv[8])
monitor_stdout = run_dir / "hrt_ucp_monitor.stdout"
monitor_stderr = run_dir / "hrt_ucp_monitor.stderr"
somstatus_before = run_dir / "hrut_somstatus_before.txt"
somstatus_after = run_dir / "hrut_somstatus_after.txt"
errors = []

monitor_text = monitor_stdout.read_text(encoding="utf-8", errors="replace") if monitor_stdout.is_file() else ""
monitor_err = monitor_stderr.read_text(encoding="utf-8", errors="replace") if monitor_stderr.is_file() else ""
bpu_loading_samples = [float(item) for item in re.findall(r"\|\s*BPU0\s+([0-9]+(?:[.][0-9]+)?)\s*\|", monitor_text)]
cma_used_values = re.findall(r"\|\s*cma_reserved\s+\S+\s+(\S+)\s+\S+\s*\|", monitor_text)
carveout_used_values = re.findall(r"\|\s*carveout\s+\S+\s+(\S+)\s+\S+\s*\|", monitor_text)
max_bpu_loading = max(bpu_loading_samples) if bpu_loading_samples else 0.0
avg_bpu_loading = statistics.fmean(bpu_loading_samples) if bpu_loading_samples else 0.0
nonzero_bpu_loading_sample_count = sum(1 for item in bpu_loading_samples if item > 0.0)

if not bpu_loading_samples:
    errors.append("hrt_ucp_monitor produced no BPU0 loading samples")
if max_bpu_loading <= 0.0:
    errors.append(f"max_bpu_loading did not exceed zero: {max_bpu_loading}")
if nonzero_bpu_loading_sample_count <= 0:
    errors.append(f"nonzero_bpu_loading_sample_count did not exceed zero: {nonzero_bpu_loading_sample_count}")

round_rows = []
with round_status_tsv.open("r", encoding="utf-8", newline="") as handle:
    reader = csv.DictReader(handle, delimiter="\t")
    for row in reader:
        round_rows.append(row)

if len(round_rows) != round_count:
    errors.append(f"unexpected completed round row count: {len(round_rows)} expected {round_count}")

generation_statuses = []
generation_batch_counts = []
generation_forward_batch_counts_by_round = []
generation_executed_step_counts = []
generation_wall_ms = []
round_summaries = []
successful_generation_count = 0
total_forward_call_count = 0
for row in round_rows:
    round_index = int(row["round_index"])
    status = int(row["status"])
    start_ms = int(row["start_ms"])
    end_ms = int(row["end_ms"])
    generation_dir = Path(row["run_dir"])
    generation_stdout = Path(row["stdout"])
    generation_stderr = Path(row["stderr"])
    generation_json = generation_dir / "batch_generation.json"
    generation_md = generation_dir / "batch_generation.md"
    generation_stderr_excerpt = generation_stderr.read_text(encoding="utf-8", errors="replace")[:500] if generation_stderr.is_file() else ""
    generation_statuses.append(status)
    generation_wall_ms.append(end_ms - start_ms)
    generation = None
    round_errors = []
    if status != 0:
        round_errors.append(f"generation command exited with status {status}")
    if generation_json.is_file():
        generation = json.loads(generation_json.read_text(encoding="utf-8"))
    else:
        round_errors.append(f"missing batch_generation.json: {generation_json}")
    history = []
    if isinstance(generation, dict):
        history = generation.get("history") or []
        generation_batch_counts.append(generation.get("batch_count"))
        generation_forward_batch_counts_by_round.append(generation.get("forward_batch_counts"))
        generation_executed_step_counts.append(generation.get("executed_step_count"))
        total_forward_call_count += len(history)
        if generation.get("verdict") != "ok_dream7b_bpu_diffusion_batch_generate":
            round_errors.append(f"unexpected generation verdict: {generation.get('verdict')}")
        if generation.get("forward_cmd") != "dream7b-bpu-fine-batch-forward":
            round_errors.append(f"unexpected forward_cmd: {generation.get('forward_cmd')}")
        if generation.get("batch_count") != batch_count:
            round_errors.append(f"unexpected batch_count: {generation.get('batch_count')}")
        if generation.get("seq_len") != 16:
            round_errors.append(f"unexpected seq_len: {generation.get('seq_len')}")
        if int(generation.get("executed_step_count") or 0) != len(history):
            round_errors.append(f"executed_step_count does not match history length: {generation.get('executed_step_count')} vs {len(history)}")
        if int(generation.get("executed_step_count") or 0) < 1:
            round_errors.append(f"executed_step_count is below 1: {generation.get('executed_step_count')}")
        remaining = generation.get("remaining_mask_positions_by_batch") or []
        if any(item.get("remaining_mask_positions") for item in remaining):
            round_errors.append(f"remaining_mask_positions_by_batch is not empty: {remaining}")
        if len(generation.get("decoded_final_by_batch") or []) != batch_count:
            round_errors.append(f"unexpected decoded_final_by_batch length: {len(generation.get('decoded_final_by_batch') or [])}")
        if generation.get("boundary") != "bounded_seq16_batch_generation_entrypoint_not_complete_production_text_service":
            round_errors.append(f"unexpected boundary: {generation.get('boundary')}")
        if generation.get("errors"):
            round_errors.append(f"generation errors not empty: {generation.get('errors')}")
        for item in history:
            step = item.get("step")
            if item.get("forward_verdict") != "ok_dream7b_segmented_hbm_python_forward":
                round_errors.append(f"unexpected forward_verdict at step {step}: {item.get('forward_verdict')}")
            if item.get("forward_execution_mode") != "pair_window_batch":
                round_errors.append(f"unexpected forward_execution_mode at step {step}: {item.get('forward_execution_mode')}")
            if item.get("forward_window_execution_mode") != "window-batch":
                round_errors.append(f"unexpected forward_window_execution_mode at step {step}: {item.get('forward_window_execution_mode')}")
            if item.get("forward_child_process_count") != 0:
                round_errors.append(f"unexpected forward_child_process_count at step {step}: {item.get('forward_child_process_count')}")
            if item.get("forward_batch_count") != batch_count:
                round_errors.append(f"unexpected forward_batch_count at step {step}: {item.get('forward_batch_count')}")
            if item.get("forward_final_shapes") != [[1, 16, 152064] for _ in range(batch_count)]:
                round_errors.append(f"unexpected forward_final_shapes at step {step}: {item.get('forward_final_shapes')}")
    if not round_errors:
        successful_generation_count += 1
    errors.extend(f"round {round_index}: {item}" for item in round_errors)
    round_summaries.append(
        {
            "round_index": round_index,
            "status": status,
            "wall_ms": end_ms - start_ms,
            "generation_dir": str(generation_dir),
            "generation_json": str(generation_json),
            "generation_md": str(generation_md),
            "generation_stdout": str(generation_stdout),
            "generation_stderr": str(generation_stderr),
            "generation_stderr_excerpt": generation_stderr_excerpt,
            "verdict": generation.get("verdict") if isinstance(generation, dict) else None,
            "batch_count": generation.get("batch_count") if isinstance(generation, dict) else None,
            "executed_step_count": generation.get("executed_step_count") if isinstance(generation, dict) else None,
            "forward_batch_counts": generation.get("forward_batch_counts") if isinstance(generation, dict) else None,
            "history_forward_verdicts": [item.get("forward_verdict") for item in history],
            "history_forward_execution_modes": [item.get("forward_execution_mode") for item in history],
            "history_forward_window_execution_modes": [item.get("forward_window_execution_mode") for item in history],
            "history_forward_child_process_counts": [item.get("forward_child_process_count") for item in history],
            "history_forward_batch_counts": [item.get("forward_batch_count") for item in history],
            "round_errors": round_errors,
        }
    )

expected_total_batch_items = round_count * batch_count
actual_total_batch_items = successful_generation_count * batch_count
if successful_generation_count != round_count:
    errors.append(f"unexpected successful_generation_count: {successful_generation_count} expected {round_count}")
if any(item != 0 for item in generation_statuses):
    errors.append(f"nonzero generation_statuses: {generation_statuses}")
if any(item != batch_count for item in generation_batch_counts):
    errors.append(f"unexpected generation_batch_counts: {generation_batch_counts}")
if any(any(count != batch_count for count in (counts or [])) for counts in generation_forward_batch_counts_by_round):
    errors.append(f"unexpected generation_forward_batch_counts_by_round: {generation_forward_batch_counts_by_round}")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_diffusion_batch_generate_sustained_probe" if not errors else "failed_dream7b_bpu_diffusion_batch_generate_sustained_probe",
    "run_dir": str(run_dir),
    "round_count": round_count,
    "batch_count": batch_count,
    "generate_cmd": generate_cmd,
    "monitor_delay_ms": monitor_delay_ms,
    "monitor_sample_count": monitor_sample_count,
    "timeout_sec": timeout_sec,
    "successful_generation_count": successful_generation_count,
    "expected_total_batch_items": expected_total_batch_items,
    "actual_total_batch_items": actual_total_batch_items,
    "generation_statuses": generation_statuses,
    "generation_wall_ms": generation_wall_ms,
    "generation_batch_counts": generation_batch_counts,
    "generation_executed_step_counts": generation_executed_step_counts,
    "generation_forward_batch_counts_by_round": generation_forward_batch_counts_by_round,
    "total_forward_call_count": total_forward_call_count,
    "bpu_loading_sample_count": len(bpu_loading_samples),
    "nonzero_bpu_loading_sample_count": nonzero_bpu_loading_sample_count,
    "max_bpu_loading": round(max_bpu_loading, 3),
    "avg_bpu_loading": round(avg_bpu_loading, 3),
    "cma_reserved_used_values": cma_used_values[:10],
    "carveout_used_values": carveout_used_values[:10],
    "monitor_stdout": str(monitor_stdout),
    "monitor_stderr": str(monitor_stderr),
    "monitor_stderr_excerpt": monitor_err[:500],
    "somstatus_before": str(somstatus_before),
    "somstatus_after": str(somstatus_after),
    "rounds": round_summaries,
    "errors": errors,
}
(run_dir / "batch_generation_sustained_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
error_lines = [f"- {item}" for item in errors] if errors else ["- none"]
round_lines = [
    f"| {item['round_index']} | {item['status']} | {item['verdict']} | {item['batch_count']} | {item['executed_step_count']} | {item['forward_batch_counts']} | {item['wall_ms']} | {item['generation_json']} |"
    for item in round_summaries
]
lines = [
    "# Dream 7B BPU Diffusion Batch Generate Sustained Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- run_dir: {payload['run_dir']}",
    f"- round_count: {payload['round_count']}",
    f"- batch_count: {payload['batch_count']}",
    f"- generate_cmd: {payload['generate_cmd']}",
    f"- successful_generation_count: {payload['successful_generation_count']}",
    f"- expected_total_batch_items: {payload['expected_total_batch_items']}",
    f"- actual_total_batch_items: {payload['actual_total_batch_items']}",
    f"- generation_statuses: {payload['generation_statuses']}",
    f"- generation_wall_ms: {payload['generation_wall_ms']}",
    f"- generation_batch_counts: {payload['generation_batch_counts']}",
    f"- generation_executed_step_counts: {payload['generation_executed_step_counts']}",
    f"- generation_forward_batch_counts_by_round: {payload['generation_forward_batch_counts_by_round']}",
    f"- total_forward_call_count: {payload['total_forward_call_count']}",
    f"- monitor_delay_ms: {payload['monitor_delay_ms']}",
    f"- monitor_sample_count: {payload['monitor_sample_count']}",
    f"- bpu_loading_sample_count: {payload['bpu_loading_sample_count']}",
    f"- nonzero_bpu_loading_sample_count: {payload['nonzero_bpu_loading_sample_count']}",
    f"- max_bpu_loading: {payload['max_bpu_loading']}",
    f"- avg_bpu_loading: {payload['avg_bpu_loading']}",
    "",
    "## Rounds",
    "",
    "| round_index | status | verdict | batch_count | executed_step_count | forward_batch_counts | wall_ms | generation_json |",
    "| ---: | ---: | --- | ---: | ---: | --- | ---: | --- |",
    *round_lines,
    "",
    "## Errors",
    "",
    *error_lines,
    "",
]
(run_dir / "batch_generation_sustained_probe.md").write_text("\n".join(lines), encoding="utf-8")
print(run_dir / "batch_generation_sustained_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
