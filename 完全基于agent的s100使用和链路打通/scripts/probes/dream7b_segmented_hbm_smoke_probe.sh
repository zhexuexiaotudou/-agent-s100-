#!/usr/bin/env bash
set -euo pipefail

report_dir="${1:-/mnt/nas/openclaw/reports/models}"
hbm_dir="${2:-/mnt/nas/openclaw/models/dream7b-hbm/segments6}"

case "$report_dir" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_dir" >&2
    exit 2
    ;;
esac

case "$hbm_dir" in
  /mnt/nas/openclaw/models/dream7b-hbm|/mnt/nas/openclaw/models/dream7b-hbm/*|/root/.openclaw/workspace/models/dream7b-hbm|/root/.openclaw/workspace/models/dream7b-hbm/*|/tmp/dream7b-hbm|/tmp/dream7b-hbm/*) ;;
  *)
    echo "Refusing HBM path outside approved Dream 7B HBM directories: $hbm_dir" >&2
    exit 2
    ;;
esac

if [[ ! -x /usr/hobot/bin/hrt_model_exec ]]; then
  echo "Missing /usr/hobot/bin/hrt_model_exec" >&2
  exit 4
fi

mkdir -p "$report_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_dir/dream7b_segmented_hbm_smoke_$stamp"
input_dir="$run_dir/inputs"
mkdir -p "$run_dir" "$input_dir"

python3 - "$input_dir" <<'PY'
import sys
from pathlib import Path

input_dir = Path(sys.argv[1])
input_dir.mkdir(parents=True, exist_ok=True)
input_dir.joinpath("tokens_i32_1x16.bin").write_bytes(bytes(1 * 16 * 4))
input_dir.joinpath("hidden_f32_16x3584.bin").write_bytes(bytes(16 * 3584 * 4))
with input_dir.joinpath("pos_i32_16.bin").open("wb") as fh:
    for item in range(16):
        fh.write(int(item).to_bytes(4, "little", signed=True))
PY

segments=(
  "seg00_04|dream7b_segment_0_4_seq16_q8.hbm|dream_segment_00_04|tokens"
  "seg04_07|dream7b_segment_4_7_seq16_q8.hbm|dream_segment_04_07|hidden"
  "seg07_14|dream7b_segment_7_14_seq16_q8.hbm|dream_segment_07_14|hidden"
  "seg14_21|dream7b_segment_14_21_seq16_q8.hbm|dream_segment_14_21|hidden"
  "seg21_24|dream7b_segment_21_24_seq16_q8.hbm|dream_segment_21_24|hidden"
  "seg24_28|dream7b_segment_24_28_seq16_q8.hbm|dream_segment_24_28|hidden"
)

results_tsv="$run_dir/results.tsv"
printf 'segment\tmodel_file\tmodel_name\tbytes\tsha256\tmodel_info_rc\tinfer_rc\tinfer_time_ms\n' > "$results_tsv"
verdict="ok_dream7b_segmented_hbm_smoke"

for spec in "${segments[@]}"; do
  IFS='|' read -r segment file model_name input_kind <<<"$spec"
  model_file="$hbm_dir/$file"
  segment_dir="$run_dir/$segment"
  mkdir -p "$segment_dir"

  if [[ ! -f "$model_file" ]]; then
    echo "Missing segment HBM: $model_file" | tee "$segment_dir/missing.log"
    printf '%s\t%s\t%s\t0\tmissing\t127\t127\t\n' "$segment" "$model_file" "$model_name" >> "$results_tsv"
    verdict="failed_missing_segment"
    continue
  fi

  bytes="$(stat -c '%s' "$model_file")"
  sha="$(sha256sum "$model_file" | awk '{print $1}')"

  model_info_rc=0
  /usr/hobot/bin/hrt_model_exec model_info \
    --model_file "$model_file" \
    > "$segment_dir/model_info.log" 2>&1 || model_info_rc=$?

  if [[ "$input_kind" == "tokens" ]]; then
    input_file="$input_dir/tokens_i32_1x16.bin,$input_dir/pos_i32_16.bin"
  else
    input_file="$input_dir/hidden_f32_16x3584.bin,$input_dir/pos_i32_16.bin"
  fi

  infer_rc=0
  /usr/hobot/bin/hrt_model_exec infer \
    --model_file "$model_file" \
    --model_name "$model_name" \
    --input_file "$input_file" \
    --frame_count 1 \
    --enable_dump true \
    --dump_path "$segment_dir/infer_dump" \
    > "$segment_dir/infer.log" 2>&1 || infer_rc=$?

  infer_time="$(grep -Eo 'Infer time: [0-9.]+ ms' "$segment_dir/infer.log" | tail -1 | awk '{print $3}' || true)"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$segment" "$model_file" "$model_name" "$bytes" "$sha" "$model_info_rc" "$infer_rc" "$infer_time" >> "$results_tsv"

  if [[ "$model_info_rc" -ne 0 || "$infer_rc" -ne 0 ]]; then
    verdict="failed_segment_runtime"
  fi
done

summary_json="$run_dir/summary.json"
summary_md="$run_dir/summary.md"
python3 - "$results_tsv" "$summary_json" "$verdict" "$run_dir" "$hbm_dir" <<'PY'
import csv
import json
import sys
from datetime import datetime

results_tsv, summary_json, verdict, run_dir, hbm_dir = sys.argv[1:]
with open(results_tsv, "r", encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh, delimiter="\t"))
payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": verdict,
    "run_dir": run_dir,
    "hbm_dir": hbm_dir,
    "segments": rows,
}
with open(summary_json, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
PY

{
  echo "# Dream 7B Segmented S100 HBM Smoke"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- verdict: $verdict"
  echo "- hbm_dir: $hbm_dir"
  echo "- run_dir: $run_dir"
  echo "- summary_json: $summary_json"
  echo
  echo "## Segment Results"
  echo
  echo "| Segment | Model | Size bytes | model_info rc | infer rc | infer ms |"
  echo "| --- | --- | ---: | ---: | ---: | ---: |"
  tail -n +2 "$results_tsv" | while IFS=$'\t' read -r segment model_file model_name bytes sha model_info_rc infer_rc infer_time; do
    echo "| $segment | $model_name | $bytes | $model_info_rc | $infer_rc | ${infer_time:-unknown} |"
  done
  echo
  echo "## Notes"
  echo
  echo "- This probe verifies the Dream 7B seq16 segmented HBM artifacts load and execute one dummy frame on S100P BPU."
  echo "- It does not verify text quality or a full diffusion sampling loop."
  echo "- Outputs are per-segment because a single linked 7.1GB HBM exceeded S100P ION/BPU memory."
} > "$summary_md"

echo "$summary_md"
[[ "$verdict" == "ok_dream7b_segmented_hbm_smoke" ]]
