#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
model_report_root="${DREAM7B_BPU_RESPLIT_WINDOW_COST_MODEL_REPORT_ROOT:-/mnt/nas/openclaw/reports/models}"
min_batch_count="${DREAM7B_BPU_RESPLIT_WINDOW_COST_MIN_BATCH_COUNT:-16}"
expected_window_count="${DREAM7B_BPU_RESPLIT_WINDOW_COST_EXPECTED_WINDOW_COUNT:-7}"
expected_segment_event_count="${DREAM7B_BPU_RESPLIT_WINDOW_COST_EXPECTED_SEGMENT_EVENT_COUNT:-224}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

case "$model_report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing model report path outside approved report directories: $model_report_root" >&2
    exit 2
    ;;
esac

if ! [[ "$min_batch_count" =~ ^[1-9][0-9]*$ ]] || (( min_batch_count > 16 )); then
  echo "DREAM7B_BPU_RESPLIT_WINDOW_COST_MIN_BATCH_COUNT must be an integer from 1 to 16." >&2
  exit 2
fi
if ! [[ "$expected_window_count" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_RESPLIT_WINDOW_COST_EXPECTED_WINDOW_COUNT must be a positive integer." >&2
  exit 2
fi
if ! [[ "$expected_segment_event_count" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_RESPLIT_WINDOW_COST_EXPECTED_SEGMENT_EVENT_COUNT must be a positive integer." >&2
  exit 2
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_resplit_window_cost_$stamp"
mkdir -p "$run_dir"

python3 - \
  "$run_dir" \
  "$model_report_root" \
  "$min_batch_count" \
  "$expected_window_count" \
  "$expected_segment_event_count" <<'PY'
import glob
import json
import sys
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
model_report_root = Path(sys.argv[2])
min_batch_count = int(sys.argv[3])
expected_window_count = int(sys.argv[4])
expected_segment_event_count = int(sys.argv[5])
errors = []
warnings = []


def latest_json(pattern):
    paths = [Path(item) for item in glob.glob(str(model_report_root / pattern))]
    paths = [item for item in paths if item.is_file()]
    if not paths:
        return None, {}
    path = max(paths, key=lambda item: item.stat().st_mtime)
    return path, json.loads(path.read_text(encoding="utf-8"))


def round_float(value):
    if value is None:
        return None
    return round(float(value), 6)


telemetry_path, telemetry = latest_json("dream7b_bpu_resplit_batch_telemetry_*/resplit_batch_telemetry_probe.json")
if not telemetry_path:
    errors.append("missing dream7b_bpu_resplit_batch_telemetry_*/resplit_batch_telemetry_probe.json")
summary_path = None
summary = {}
if telemetry:
    summary_path = Path(telemetry.get("forward_summary") or "")
    if not summary_path.is_file():
        errors.append(f"missing forward summary from resplit telemetry: {summary_path}")
    else:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))

segments = summary.get("segments") or []
batch_count = int(summary.get("batch_count") or telemetry.get("batch_count") or 0)
total_load_ms = float(summary.get("load_ms") or 0.0)
total_run_ms = float(summary.get("run_ms") or 0.0)
total_wall_ms = float(summary.get("wall_ms") or 0.0)
window_records = OrderedDict()

for item in segments:
    resident_segments = item.get("resident_segments")
    if not isinstance(resident_segments, list) or not resident_segments:
        errors.append(f"segment event missing resident_segments: {item.get('segment')}")
        continue
    window_key = tuple(str(part) for part in resident_segments)
    if window_key not in window_records:
        window_records[window_key] = {
            "resident_segments": list(window_key),
            "segment_sources": [],
            "event_count": 0,
            "batch_indexes": set(),
            "load_ms": 0.0,
            "packed_load_ms": 0.0,
            "run_ms": 0.0,
            "segments": OrderedDict(),
        }
    record = window_records[window_key]
    record["event_count"] += 1
    if "batch_index" in item:
        record["batch_indexes"].add(int(item.get("batch_index")))
    source = item.get("source")
    if source not in record["segment_sources"]:
        record["segment_sources"].append(source)
    load_ms = float(item.get("load_ms") or 0.0)
    packed_load_ms = float(item.get("packed_load_ms") or 0.0)
    run_ms = float(item.get("run_ms") or 0.0)
    record["load_ms"] += load_ms
    record["packed_load_ms"] = max(record["packed_load_ms"], packed_load_ms)
    record["run_ms"] += run_ms
    segment_name = str(item.get("segment"))
    if segment_name not in record["segments"]:
        record["segments"][segment_name] = {
            "segment": segment_name,
            "source": source,
            "event_count": 0,
            "run_ms": 0.0,
        }
    record["segments"][segment_name]["event_count"] += 1
    record["segments"][segment_name]["run_ms"] += run_ms

window_costs = []
for index, (window_key, record) in enumerate(window_records.items()):
    event_count = int(record["event_count"])
    batch_indexes = sorted(record["batch_indexes"])
    load_ms = float(record["load_ms"])
    run_ms = float(record["run_ms"])
    packed_load_ms = float(record["packed_load_ms"])
    load_share = load_ms / total_load_ms if total_load_ms else None
    run_share = run_ms / total_run_ms if total_run_ms else None
    total_window_ms = load_ms + run_ms
    load_to_run_ratio = load_ms / run_ms if run_ms else None
    window_costs.append(
        {
            "window_index": index,
            "resident_segments": list(window_key),
            "segment_sources": list(record["segment_sources"]),
            "event_count": event_count,
            "batch_count": len(batch_indexes),
            "batch_indexes": batch_indexes,
            "load_ms": round_float(load_ms),
            "packed_load_ms": round_float(packed_load_ms),
            "run_ms": round_float(run_ms),
            "total_window_ms": round_float(total_window_ms),
            "load_share": round_float(load_share),
            "run_share": round_float(run_share),
            "load_to_run_ratio": round_float(load_to_run_ratio),
            "amortized_load_ms_per_forward": round_float(load_ms / batch_count) if batch_count else None,
            "amortized_run_ms_per_forward": round_float(run_ms / batch_count) if batch_count else None,
            "segments": [
                {
                    **segment,
                    "run_ms": round_float(segment["run_ms"]),
                    "amortized_run_ms_per_forward": round_float(segment["run_ms"] / batch_count) if batch_count else None,
                }
                for segment in record["segments"].values()
            ],
        }
    )

ranked_by_load = sorted(window_costs, key=lambda item: float(item["load_ms"] or 0.0), reverse=True)
ranked_by_ratio = sorted(window_costs, key=lambda item: float(item["load_to_run_ratio"] or 0.0), reverse=True)
ranked_by_total = sorted(window_costs, key=lambda item: float(item["total_window_ms"] or 0.0), reverse=True)
top_load = ranked_by_load[0] if ranked_by_load else {}
top_ratio = ranked_by_ratio[0] if ranked_by_ratio else {}
top_total = ranked_by_total[0] if ranked_by_total else {}

if telemetry.get("verdict") != "ok_dream7b_bpu_resplit_batch_telemetry_probe":
    errors.append(f"unexpected resplit telemetry verdict: {telemetry.get('verdict')}")
if summary.get("verdict") != "ok_dream7b_segmented_hbm_python_forward":
    errors.append(f"unexpected forward summary verdict: {summary.get('verdict')}")
if summary.get("segment_plan") != "resplit-adjacent":
    errors.append(f"unexpected segment_plan: {summary.get('segment_plan')}")
if summary.get("execution_mode") != "pair_window_batch":
    errors.append(f"unexpected execution_mode: {summary.get('execution_mode')}")
if summary.get("window_execution_mode") != "window-batch":
    errors.append(f"unexpected window_execution_mode: {summary.get('window_execution_mode')}")
if summary.get("child_process_count") != 0:
    errors.append(f"unexpected child_process_count: {summary.get('child_process_count')}")
if batch_count < min_batch_count:
    errors.append(f"batch_count below {min_batch_count}: {batch_count}")
if len(segments) != expected_segment_event_count:
    errors.append(f"segment event count expected {expected_segment_event_count}, got {len(segments)}")
if len(window_costs) != expected_window_count:
    errors.append(f"window count expected {expected_window_count}, got {len(window_costs)}")
expected_events_per_window = batch_count * 2 if batch_count else None
for item in window_costs:
    if expected_events_per_window is not None and item["event_count"] != expected_events_per_window:
        errors.append(f"window {item['resident_segments']} event_count expected {expected_events_per_window}, got {item['event_count']}")
    if item["batch_count"] != batch_count:
        errors.append(f"window {item['resident_segments']} batch_count expected {batch_count}, got {item['batch_count']}")
    if float(item["load_ms"] or 0.0) <= 0.0:
        errors.append(f"window {item['resident_segments']} load_ms did not exceed zero")
    if float(item["run_ms"] or 0.0) <= 0.0:
        errors.append(f"window {item['resident_segments']} run_ms did not exceed zero")

if total_load_ms <= total_run_ms:
    warnings.append("resplit batch summary is not load dominated; check whether a newer runtime changed the bottleneck")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_resplit_window_cost_probe" if not errors else "failed_dream7b_bpu_resplit_window_cost_probe",
    "run_dir": str(run_dir),
    "model_report_root": str(model_report_root),
    "resplit_batch_telemetry_path": str(telemetry_path) if telemetry_path else None,
    "forward_summary_path": str(summary_path) if summary_path else None,
    "batch_count": batch_count,
    "segment_plan": summary.get("segment_plan"),
    "execution_mode": summary.get("execution_mode"),
    "window_execution_mode": summary.get("window_execution_mode"),
    "child_process_count": summary.get("child_process_count"),
    "segment_event_count": len(segments),
    "window_count": len(window_costs),
    "expected_window_count": expected_window_count,
    "expected_segment_event_count": expected_segment_event_count,
    "total_load_ms": round_float(total_load_ms),
    "total_run_ms": round_float(total_run_ms),
    "total_wall_ms": round_float(total_wall_ms),
    "load_to_run_ratio": round_float(total_load_ms / total_run_ms) if total_run_ms else None,
    "amortized_load_ms_per_forward": round_float(total_load_ms / batch_count) if batch_count else None,
    "amortized_run_ms_per_forward": round_float(total_run_ms / batch_count) if batch_count else None,
    "window_costs": window_costs,
    "ranked_by_load": ranked_by_load,
    "ranked_by_load_to_run_ratio": ranked_by_ratio,
    "ranked_by_total_window_ms": ranked_by_total,
    "top_load_window": top_load,
    "top_load_to_run_ratio_window": top_ratio,
    "top_total_window": top_total,
    "next_optimization_target": (
        "reduce packed HBM load cost for top ranked resplit windows before expecting sustained 128TOPS-level average utilization"
    ),
    "warnings": warnings,
    "errors": errors,
}

json_path = run_dir / "resplit_window_cost_probe.json"
md_path = run_dir / "resplit_window_cost_probe.md"
json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Dream 7B BPU Resplit Window Cost Probe",
    "",
    f"- verdict: {payload['verdict']}",
    f"- resplit_batch_telemetry_path: {payload['resplit_batch_telemetry_path']}",
    f"- forward_summary_path: {payload['forward_summary_path']}",
    f"- batch_count: {payload['batch_count']}",
    f"- segment_plan: {payload['segment_plan']}",
    f"- execution_mode: {payload['execution_mode']}",
    f"- window_execution_mode: {payload['window_execution_mode']}",
    f"- child_process_count: {payload['child_process_count']}",
    f"- segment_event_count: {payload['segment_event_count']}",
    f"- window_count: {payload['window_count']}",
    f"- total_load_ms: {payload['total_load_ms']}",
    f"- total_run_ms: {payload['total_run_ms']}",
    f"- load_to_run_ratio: {payload['load_to_run_ratio']}",
    f"- amortized_load_ms_per_forward: {payload['amortized_load_ms_per_forward']}",
    f"- amortized_run_ms_per_forward: {payload['amortized_run_ms_per_forward']}",
    "",
    "## Top Load Window",
    "",
    f"- resident_segments: {top_load.get('resident_segments')}",
    f"- load_ms: {top_load.get('load_ms')}",
    f"- run_ms: {top_load.get('run_ms')}",
    f"- load_to_run_ratio: {top_load.get('load_to_run_ratio')}",
    f"- load_share: {top_load.get('load_share')}",
    "",
    "## Top Load/Run Ratio Window",
    "",
    f"- resident_segments: {top_ratio.get('resident_segments')}",
    f"- load_ms: {top_ratio.get('load_ms')}",
    f"- run_ms: {top_ratio.get('run_ms')}",
    f"- load_to_run_ratio: {top_ratio.get('load_to_run_ratio')}",
    "",
    "## Window Ranking By Load",
    "",
]
for item in ranked_by_load:
    lines.append(
        "- "
        f"window_index={item['window_index']} "
        f"resident_segments={item['resident_segments']} "
        f"load_ms={item['load_ms']} "
        f"run_ms={item['run_ms']} "
        f"load_to_run_ratio={item['load_to_run_ratio']} "
        f"load_share={item['load_share']}"
    )
lines.extend(
    [
        "",
        f"- next_optimization_target: {payload['next_optimization_target']}",
        "",
        "## Warnings",
        "",
    ]
)
for warning in warnings:
    lines.append(f"- {warning}")
lines.extend(["", "## Errors", ""])
for error in errors:
    lines.append(f"- {error}")
md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

print(md_path)
if errors:
    raise SystemExit(1)
PY
