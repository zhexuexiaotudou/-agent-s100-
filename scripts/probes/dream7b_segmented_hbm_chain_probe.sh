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
run_dir="$report_dir/dream7b_segmented_hbm_chain_$stamp"
input_dir="$run_dir/inputs"
mkdir -p "$run_dir" "$input_dir"

python3 - "$input_dir" <<'PY'
import sys
from pathlib import Path

input_dir = Path(sys.argv[1])
input_dir.joinpath("tokens_i32_1x16.bin").write_bytes(bytes(1 * 16 * 4))
with input_dir.joinpath("pos_i32_16.bin").open("wb") as fh:
    for item in range(16):
        fh.write(int(item).to_bytes(4, "little", signed=True))
PY

segments=(
  "seg00_04|dream7b_segment_0_4_seq16_q8.hbm|dream_segment_00_04|tokens|229376"
  "seg04_07|dream7b_segment_4_7_seq16_q8.hbm|dream_segment_04_07|hidden|229376"
  "seg07_14|dream7b_segment_7_14_seq16_q8.hbm|dream_segment_07_14|hidden|229376"
  "seg14_21|dream7b_segment_14_21_seq16_q8.hbm|dream_segment_14_21|hidden|229376"
  "seg21_24|dream7b_segment_21_24_seq16_q8.hbm|dream_segment_21_24|hidden|229376"
  "seg24_28|dream7b_segment_24_28_seq16_q8.hbm|dream_segment_24_28|hidden|9732096"
)

hidden_file=""
results_tsv="$run_dir/results.tsv"
printf 'segment\tmodel_name\tmodel_file\tinput_kind\toutput_file\toutput_bytes\tinfer_rc\tinfer_time_ms\n' > "$results_tsv"
verdict="ok_dream7b_segmented_hbm_chain"

for spec in "${segments[@]}"; do
  IFS='|' read -r segment file model_name input_kind expected_bytes <<<"$spec"
  model_file="$hbm_dir/$file"
  segment_dir="$run_dir/$segment"
  mkdir -p "$segment_dir"

  if [[ ! -f "$model_file" ]]; then
    echo "Missing segment HBM: $model_file" | tee "$segment_dir/missing.log"
    printf '%s\t%s\t%s\t%s\tmissing\t0\t127\t\n' "$segment" "$model_name" "$model_file" "$input_kind" >> "$results_tsv"
    verdict="failed_missing_segment"
    break
  fi

  if [[ "$input_kind" == "tokens" ]]; then
    input_file="$input_dir/tokens_i32_1x16.bin,$input_dir/pos_i32_16.bin"
  else
    if [[ -z "$hidden_file" || ! -f "$hidden_file" ]]; then
      echo "Missing previous hidden file before $segment" | tee "$segment_dir/missing_hidden.log"
      printf '%s\t%s\t%s\t%s\tmissing_hidden\t0\t126\t\n' "$segment" "$model_name" "$model_file" "$input_kind" >> "$results_tsv"
      verdict="failed_missing_hidden"
      break
    fi
    input_file="$hidden_file,$input_dir/pos_i32_16.bin"
  fi

  infer_rc=0
  /usr/hobot/bin/hrt_model_exec infer \
    --model_file "$model_file" \
    --model_name "$model_name" \
    --input_file "$input_file" \
    --frame_count 1 \
    --enable_dump true \
    --dequantize_process true \
    --dump_format bin \
    --dump_path "$segment_dir" \
    > "$segment_dir/infer.log" 2>&1 || infer_rc=$?

  output_file="$segment_dir/model_infer_output_0__output_0.bin"
  output_bytes=0
  if [[ -f "$output_file" ]]; then
    output_bytes="$(stat -c '%s' "$output_file")"
  fi
  infer_time="$(grep -Eo 'Infer time: [0-9.]+ ms' "$segment_dir/infer.log" | tail -1 | awk '{print $3}' || true)"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$segment" "$model_name" "$model_file" "$input_kind" "$output_file" "$output_bytes" "$infer_rc" "$infer_time" >> "$results_tsv"

  if [[ "$infer_rc" -ne 0 || "$output_bytes" != "$expected_bytes" ]]; then
    verdict="failed_segment_chain"
    break
  fi

  hidden_file="$output_file"
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
with open(summary_json, "w", encoding="utf-8") as fh:
    json.dump(
        {
            "generated_at": datetime.now().astimezone().isoformat(),
            "verdict": verdict,
            "run_dir": run_dir,
            "hbm_dir": hbm_dir,
            "segments": rows,
        },
        fh,
        ensure_ascii=False,
        indent=2,
    )
    fh.write("\n")
PY

{
  echo "# Dream 7B Segmented S100 HBM Chain"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- verdict: $verdict"
  echo "- hbm_dir: $hbm_dir"
  echo "- run_dir: $run_dir"
  echo "- summary_json: $summary_json"
  echo
  echo "## Segment Chain"
  echo
  echo "| Segment | Model | Input | Output bytes | infer rc | infer ms |"
  echo "| --- | --- | --- | ---: | ---: | ---: |"
  tail -n +2 "$results_tsv" | while IFS=$'\t' read -r segment model_name model_file input_kind output_file output_bytes infer_rc infer_time; do
    echo "| $segment | $model_name | $input_kind | $output_bytes | $infer_rc | ${infer_time:-unknown} |"
  done
  echo
  echo "## Notes"
  echo
  echo "- This chains six Dream 7B HBM segments with dequantized F32 hidden dumps between segments."
  echo "- This is a CLI proof of the full forward path on BPU, not the final production runtime."
  echo "- The final output is dequantized logits with expected size 1*16*152064*4 bytes."
} > "$summary_md"

echo "$summary_md"
[[ "$verdict" == "ok_dream7b_segmented_hbm_chain" ]]
