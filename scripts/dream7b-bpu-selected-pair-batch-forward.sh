#!/usr/bin/env bash
set -euo pipefail

tokens_batch_json="${DREAM7B_BPU_SELECTED_PAIR_BATCH_FORWARD_TOKENS_BATCH_JSON:-}"
output_dir="${DREAM7B_BPU_SELECTED_PAIR_BATCH_FORWARD_OUTPUT_DIR:-}"
top_k="${DREAM7B_BPU_SELECTED_PAIR_BATCH_FORWARD_TOP_K:-3}"
report_root="${DREAM7B_BPU_SELECTED_PAIR_BATCH_FORWARD_REPORT_ROOT:-}"
probe_cmd="${DREAM7B_BPU_SELECTED_PAIR_BATCH_FORWARD_PROBE_CMD:-dream7b-bpu-selected-pair-forward-path-probe}"
timeout_sec="${DREAM7B_BPU_SELECTED_PAIR_BATCH_FORWARD_TIMEOUT_SEC:-900}"
triplet_json="${DREAM7B_BPU_SELECTED_PAIR_BATCH_FORWARD_TRIPLET_JSON:-}"

usage() {
  cat >&2 <<'USAGE'
usage: dream7b-bpu-selected-pair-batch-forward --tokens-batch-json FILE --top-k N --output-dir DIR

Runs the selected-pair resident Dream 7B BPU forward candidate with the same
basic command interface as dream7b-bpu-fine-batch-forward. It writes a
runner-compatible summary.json to --output-dir and keeps the detailed
selected-pair probe report under --output-dir/selected_pair_reports.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tokens-batch-json)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      tokens_batch_json="$2"
      shift 2
      ;;
    --tokens-batch-json=*)
      tokens_batch_json="${1#--tokens-batch-json=}"
      shift
      ;;
    --top-k)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      top_k="$2"
      shift 2
      ;;
    --top-k=*)
      top_k="${1#--top-k=}"
      shift
      ;;
    --output-dir)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      output_dir="$2"
      shift 2
      ;;
    --output-dir=*)
      output_dir="${1#--output-dir=}"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unsupported argument for selected-pair batch forward: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$tokens_batch_json" || -z "$output_dir" ]]; then
  usage
  exit 2
fi

case "$tokens_batch_json" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing tokens batch JSON outside approved report directories: $tokens_batch_json" >&2
    exit 2
    ;;
esac
case "$output_dir" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $output_dir" >&2
    exit 2
    ;;
esac
if [[ ! -f "$tokens_batch_json" ]]; then
  echo "Missing --tokens-batch-json file: $tokens_batch_json" >&2
  exit 2
fi
if ! [[ "$top_k" =~ ^[0-9]+$ ]]; then
  echo "--top-k must be a non-negative integer." >&2
  exit 2
fi
if ! [[ "$timeout_sec" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_SELECTED_PAIR_BATCH_FORWARD_TIMEOUT_SEC must be a positive integer." >&2
  exit 2
fi
if ! command -v "$probe_cmd" >/dev/null 2>&1; then
  echo "Missing deployed command: $probe_cmd" >&2
  exit 4
fi

if [[ -z "$triplet_json" ]]; then
  triplet_json="$(
    python3 - <<'PY'
import glob
from pathlib import Path

paths = [Path(item) for item in glob.glob("/mnt/nas/openclaw/reports/models/dream7b_bpu_single_segment_triplet_residency_*/single_segment_triplet_residency_probe.json")]
paths = [item for item in paths if item.is_file()]
if not paths:
    raise SystemExit("missing global single-segment triplet residency report")
print(max(paths, key=lambda item: item.stat().st_mtime))
PY
  )"
fi
case "$triplet_json" in
  /tmp/*|/mnt/nas/openclaw/reports/models/dream7b_bpu_single_segment_triplet_residency_*/*|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing selected-pair triplet JSON outside approved report directories: $triplet_json" >&2
    exit 2
    ;;
esac
if [[ ! -f "$triplet_json" ]]; then
  echo "Missing selected-pair triplet JSON: $triplet_json" >&2
  exit 2
fi

mkdir -p "$output_dir"
if [[ -z "$report_root" ]]; then
  report_root="$output_dir/selected_pair_reports"
fi
mkdir -p "$report_root"

batch_count="$(
  python3 - "$tokens_batch_json" <<'PY'
import json
import sys
from pathlib import Path

rows = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if not isinstance(rows, list) or not rows:
    raise SystemExit("tokens batch JSON must contain a non-empty list")
print(len(rows))
PY
)"

probe_stdout="$output_dir/selected_pair_probe.stdout"
probe_stderr="$output_dir/selected_pair_probe.stderr"
set +e
DREAM7B_BPU_SELECTED_PAIR_ONLY=1 \
DREAM7B_BPU_SELECTED_PAIR_TRIPLET_JSON="$triplet_json" \
DREAM7B_BPU_SELECTED_PAIR_TOKENS_BATCH_JSON="$tokens_batch_json" \
DREAM7B_BPU_SELECTED_PAIR_BATCH_COUNT="$batch_count" \
DREAM7B_BPU_SELECTED_PAIR_TOP_K="$top_k" \
DREAM7B_BPU_SELECTED_PAIR_TIMEOUT_SEC="$timeout_sec" \
  "$probe_cmd" "$report_root" > "$probe_stdout" 2> "$probe_stderr"
probe_status="$?"
set -e
if [[ "$probe_status" -ne 0 ]]; then
  echo "Selected-pair forward probe failed with status $probe_status: $probe_stderr" >&2
  exit "$probe_status"
fi

python3 - \
  "$output_dir" \
  "$tokens_batch_json" \
  "$top_k" \
  "$probe_stdout" \
  "$probe_stderr" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

output_dir = Path(sys.argv[1])
tokens_batch_json = Path(sys.argv[2])
top_k = int(sys.argv[3])
probe_stdout = Path(sys.argv[4])
probe_stderr = Path(sys.argv[5])

probe_md = ""
for line in probe_stdout.read_text(encoding="utf-8", errors="replace").splitlines()[::-1]:
    line = line.strip()
    if line.endswith("selected_pair_forward_path_probe.md"):
        probe_md = line
        break
if not probe_md:
    raise SystemExit(f"could not parse selected_pair_forward_path_probe.md from {probe_stdout}")
probe_json = Path(probe_md).with_suffix(".json")
probe_payload = json.loads(probe_json.read_text(encoding="utf-8"))
selected_summary_path = Path(probe_payload["selected_summary_json"])
selected_summary = json.loads(selected_summary_path.read_text(encoding="utf-8"))
selected = probe_payload.get("selected") or {}

summary = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_segmented_hbm_python_forward",
    "selected_pair_candidate": True,
    "source_probe_json": str(probe_json),
    "source_selected_summary_json": str(selected_summary_path),
    "source_tokens_batch_json": str(tokens_batch_json),
    "execution_mode": "pair_window_batch",
    "window_execution_mode": "selected-pair-resident",
    "child_process_count": int(selected.get("selected_worker_count") or 0),
    "segment_plan": "fine-adjacent",
    "batch_count": selected_summary.get("batch_count"),
    "seq_len": 16,
    "top_k": top_k,
    "selected_pair": selected.get("selected_pair"),
    "selected_segments": selected.get("selected_segments"),
    "selected_pair_covers_all_segments": selected.get("selected_pair_covers_all_segments"),
    "selected_resident_load_ms": selected.get("selected_resident_load_ms"),
    "load_ms": selected.get("selected_total_load_ms"),
    "warm_load_ms": selected.get("forward_load_ms"),
    "run_ms": selected.get("run_ms"),
    "wall_ms": selected.get("wall_ms"),
    "load_share": selected_summary.get("load_share_including_resident_load"),
    "warm_load_share": selected_summary.get("warm_load_share_excluding_resident_load"),
    "amortized_load_ms_per_forward": selected_summary.get("amortized_total_load_ms_per_forward"),
    "amortized_warm_load_ms_per_forward": selected_summary.get("amortized_warm_load_ms_per_forward"),
    "amortized_run_ms_per_forward": selected_summary.get("amortized_run_ms_per_forward"),
    "amortized_wall_ms_per_forward": selected_summary.get("amortized_wall_ms_per_forward"),
    "final_shape": selected_summary.get("final_shape"),
    "final_shapes": selected_summary.get("final_shapes"),
    "topk_last_position_by_batch": selected_summary.get("topk_last_position_by_batch"),
    "warnings": probe_payload.get("warnings") or [],
    "errors": probe_payload.get("errors") or [],
    "probe_stdout": str(probe_stdout),
    "probe_stderr": str(probe_stderr),
}
if summary["errors"]:
    summary["verdict"] = "failed_dream7b_segmented_hbm_python_forward"
if summary["selected_pair_covers_all_segments"] is not True:
    summary["verdict"] = "failed_dream7b_segmented_hbm_python_forward"
    summary["errors"].append("selected_pair_covers_all_segments is not true")

(output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
lines = [
    "# Dream 7B BPU Selected Pair Batch Forward",
    "",
    f"- generated_at: {summary['generated_at']}",
    f"- verdict: {summary['verdict']}",
    f"- selected_pair_candidate: {summary['selected_pair_candidate']}",
    f"- batch_count: {summary['batch_count']}",
    f"- selected_pair: {summary['selected_pair']}",
    f"- selected_segments: {summary['selected_segments']}",
    f"- selected_pair_covers_all_segments: {summary['selected_pair_covers_all_segments']}",
    f"- load_ms: {summary['load_ms']}",
    f"- warm_load_ms: {summary['warm_load_ms']}",
    f"- run_ms: {summary['run_ms']}",
    f"- wall_ms: {summary['wall_ms']}",
    f"- source_probe_json: {summary['source_probe_json']}",
    "",
    "## Warnings",
    "",
]
lines.extend(f"- {item}" for item in summary["warnings"]) if summary["warnings"] else lines.append("- none")
lines.extend(["", "## Errors", ""])
lines.extend(f"- {item}" for item in summary["errors"]) if summary["errors"] else lines.append("- none")
(output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(output_dir / "summary.json")
if summary["verdict"] != "ok_dream7b_segmented_hbm_python_forward":
    raise SystemExit(json.dumps(summary["errors"], ensure_ascii=False))
PY
