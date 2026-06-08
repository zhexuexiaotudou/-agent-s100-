#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
model_report_root="${DREAM7B_BPU_SEGMENT_CAPACITY_MODEL_REPORT_ROOT:-/mnt/nas/openclaw/reports/models}"
base_hbm_dir="${DREAM7B_BPU_SEGMENT_CAPACITY_BASE_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/segments6}"
fine_hbm_dir="${DREAM7B_BPU_SEGMENT_CAPACITY_FINE_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16}"

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

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_segment_capacity_planner_$stamp"
mkdir -p "$run_dir"

python3 - \
  "$run_dir" \
  "$model_report_root" \
  "$base_hbm_dir" \
  "$fine_hbm_dir" <<'PY'
import collections
import glob
import json
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
model_report_root = Path(sys.argv[2])
base_hbm_dir = Path(sys.argv[3])
fine_hbm_dir = Path(sys.argv[4])

errors = []
warnings = []


def latest_json(pattern):
    paths = [Path(item) for item in glob.glob(str(model_report_root / pattern))]
    paths = [item for item in paths if item.is_file()]
    if not paths:
        return None, {}
    path = max(paths, key=lambda item: item.stat().st_mtime)
    return path, json.loads(path.read_text(encoding="utf-8"))


def mib(value):
    return round(float(value) / 1048576.0, 3)


segments = [
    {"segment_index": 0, "segment": "seg00_02", "layer_start": 0, "layer_end": 2, "model_file": fine_hbm_dir / "seg00_02/dream7b_segment_0_2_seq16_q8.hbm"},
    {"segment_index": 1, "segment": "seg02_04", "layer_start": 2, "layer_end": 4, "model_file": fine_hbm_dir / "seg02_04/dream7b_segment_2_4_seq16_q8.hbm"},
    {"segment_index": 2, "segment": "seg04_07", "layer_start": 4, "layer_end": 7, "model_file": base_hbm_dir / "dream7b_segment_4_7_seq16_q8.hbm"},
    {"segment_index": 3, "segment": "seg07_10", "layer_start": 7, "layer_end": 10, "model_file": fine_hbm_dir / "seg07_10/dream7b_segment_7_10_seq16_q8.hbm"},
    {"segment_index": 4, "segment": "seg10_14", "layer_start": 10, "layer_end": 14, "model_file": fine_hbm_dir / "seg10_14/dream7b_segment_10_14_seq16_q8.hbm"},
    {"segment_index": 5, "segment": "seg14_17", "layer_start": 14, "layer_end": 17, "model_file": fine_hbm_dir / "seg14_17/dream7b_segment_14_17_seq16_q8.hbm"},
    {"segment_index": 6, "segment": "seg17_21", "layer_start": 17, "layer_end": 21, "model_file": fine_hbm_dir / "seg17_21/dream7b_segment_17_21_seq16_q8.hbm"},
    {"segment_index": 7, "segment": "seg21_24", "layer_start": 21, "layer_end": 24, "model_file": base_hbm_dir / "dream7b_segment_21_24_seq16_q8.hbm"},
    {"segment_index": 8, "segment": "seg24_26", "layer_start": 24, "layer_end": 26, "model_file": fine_hbm_dir / "seg24_26/dream7b_segment_24_26_seq16_q8.hbm"},
    {"segment_index": 9, "segment": "seg26_28", "layer_start": 26, "layer_end": 28, "model_file": fine_hbm_dir / "seg26_28/dream7b_segment_26_28_seq16_q8.hbm"},
]

inventory = []
for item in segments:
    model_file = Path(item["model_file"])
    exists = model_file.is_file()
    size_bytes = model_file.stat().st_size if exists else None
    if not exists:
        errors.append(f"missing HBM segment file: {model_file}")
    inventory.append({
        "segment_index": item["segment_index"],
        "segment": item["segment"],
        "layer_start": item["layer_start"],
        "layer_end": item["layer_end"],
        "layer_count": item["layer_end"] - item["layer_start"],
        "model_file": str(model_file),
        "exists": exists,
        "size_bytes": size_bytes,
        "size_mib": mib(size_bytes) if size_bytes is not None else None,
    })

inventory_by_index = {item["segment_index"]: item for item in inventory}

single_path, single = latest_json("dream7b_bpu_single_segment_residency_matrix_*/single_segment_residency_matrix_probe.json")
persistent_path, persistent = latest_json("dream7b_bpu_persistent_segment_cache_*/persistent_segment_cache_probe.json")
triplet_path, triplet = latest_json("dream7b_bpu_single_segment_triplet_residency_*/single_segment_triplet_residency_probe.json")
quad_path, quad = latest_json("dream7b_bpu_seeded_quad_residency_*/seeded_quad_residency_probe.json")
topology_path, topology = latest_json("dream7b_bpu_persistent_triplet_topology_*/persistent_triplet_topology_probe.json")
cross_job_path, cross_job = latest_json("dream7b_bpu_selected_pair_cross_job_reuse_*/selected_pair_cross_job_reuse_probe.json")

required_reports = [
    ("single_segment_residency_matrix", single_path, single, "ok_dream7b_bpu_single_segment_residency_matrix_probe"),
    ("persistent_segment_cache", persistent_path, persistent, "ok_dream7b_bpu_persistent_segment_cache_probe"),
    ("single_segment_triplet_residency", triplet_path, triplet, "ok_dream7b_bpu_single_segment_triplet_residency_probe"),
    ("seeded_quad_residency", quad_path, quad, "ok_dream7b_bpu_seeded_quad_residency_probe"),
    ("persistent_triplet_topology", topology_path, topology, "ok_dream7b_bpu_persistent_triplet_topology_probe"),
    ("selected_pair_cross_job_reuse", cross_job_path, cross_job, "ok_dream7b_bpu_selected_pair_cross_job_reuse_probe"),
]
for name, path, payload, expected_verdict in required_reports:
    if not path:
        errors.append(f"missing {name} report")
    elif payload.get("verdict") != expected_verdict:
        errors.append(f"unexpected {name} verdict: {payload.get('verdict')}")
    elif payload.get("errors"):
        errors.append(f"{name} report contains errors: {payload.get('errors')}")

successful_triplets = triplet.get("successful_triplets") or []
failed_triplets = triplet.get("failed_triplets") or []
success_appearance = collections.Counter(index for combo in successful_triplets for index in combo)
failed_appearance = collections.Counter(index for combo in failed_triplets for index in combo)
failed_worker_count = collections.Counter()
ready_worker_count = collections.Counter()
for record in triplet.get("combination_records") or []:
    for worker_record in record.get("records") or []:
        segment_index = worker_record.get("segment_index")
        if worker_record.get("status") == "ready":
            ready_worker_count[segment_index] += 1
        elif worker_record.get("status") == "failed":
            failed_worker_count[segment_index] += 1

largest_segments = sorted(
    inventory,
    key=lambda item: (item["size_bytes"] is not None, item["size_bytes"] or 0, -item["segment_index"]),
    reverse=True,
)
smallest_segments = sorted(
    inventory,
    key=lambda item: (item["size_bytes"] is None, item["size_bytes"] or 0, item["segment_index"]),
)

weak_success_segments = [
    item for item in inventory
    if int(success_appearance.get(item["segment_index"], 0)) <= 1
]
recommended_resplit_segments = sorted(
    weak_success_segments,
    key=lambda item: (
        -(item["size_bytes"] or 0),
        -int(failed_worker_count.get(item["segment_index"], 0)),
        item["segment_index"],
    ),
)
recommended_resplit_segments = [
    {
        "segment_index": item["segment_index"],
        "segment": item["segment"],
        "size_bytes": item["size_bytes"],
        "size_mib": item["size_mib"],
        "successful_triplet_appearance_count": int(success_appearance.get(item["segment_index"], 0)),
        "failed_triplet_appearance_count": int(failed_appearance.get(item["segment_index"], 0)),
        "failed_worker_count": int(failed_worker_count.get(item["segment_index"], 0)),
        "reason": "large or weak triplet-residency segment; split before retrying four-resident forward path",
    }
    for item in recommended_resplit_segments
]

recommended_anchor_segments = sorted(
    inventory,
    key=lambda item: (
        -int(success_appearance.get(item["segment_index"], 0)),
        item["size_bytes"] or 0,
        item["segment_index"],
    ),
)[:2]
recommended_anchor_segment_indexes = [item["segment_index"] for item in recommended_anchor_segments]

current_split_quad_supported = int(quad.get("successful_seeded_quad_count") or 0) > 0
max_resident_segment_count_observed = max(
    int(single.get("max_resident_segment_count_observed") or 0),
    int(persistent.get("max_resident_segment_count_observed") or 0),
    int(triplet.get("max_resident_segment_count_observed") or 0),
    int(quad.get("max_resident_segment_count_observed") or 0),
    int(topology.get("max_resident_segment_count_observed") or 0),
)
selected_pair = cross_job.get("selected_pair")
selected_pair_matches_anchor_pair = selected_pair == recommended_anchor_segment_indexes

if not current_split_quad_supported:
    warnings.append("current 10-segment split has no successful seeded quad residency; do not attempt four-resident forward promotion without a new split")
if selected_pair_matches_anchor_pair is not True:
    warnings.append(f"selected_pair {selected_pair} does not match computed anchor pair {recommended_anchor_segment_indexes}")

recommended_resplit_indexes = [item["segment_index"] for item in recommended_resplit_segments]
next_optimization_target = (
    "recompile or split weak residency segments "
    f"{recommended_resplit_indexes[:4]} into smaller HBM shards before attempting four-resident forward path or default-service promotion"
)

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_segment_capacity_planner_probe" if not errors else "failed_dream7b_bpu_segment_capacity_planner_probe",
    "run_dir": str(run_dir),
    "model_report_root": str(model_report_root),
    "base_hbm_dir": str(base_hbm_dir),
    "fine_hbm_dir": str(fine_hbm_dir),
    "segment_count": len(inventory),
    "hbm_segment_inventory": inventory,
    "total_segment_hbm_size_bytes": sum(item["size_bytes"] or 0 for item in inventory),
    "largest_segment_indexes_by_size": [item["segment_index"] for item in largest_segments],
    "smallest_segment_indexes_by_size": [item["segment_index"] for item in smallest_segments],
    "residency_reports": {
        "single_segment_residency_matrix": str(single_path) if single_path else None,
        "persistent_segment_cache": str(persistent_path) if persistent_path else None,
        "single_segment_triplet_residency": str(triplet_path) if triplet_path else None,
        "seeded_quad_residency": str(quad_path) if quad_path else None,
        "persistent_triplet_topology": str(topology_path) if topology_path else None,
        "selected_pair_cross_job_reuse": str(cross_job_path) if cross_job_path else None,
    },
    "current_split_capacity": {
        "single_segment_pair_matrix_complete": int(single.get("matrix_entry_count") or 0) == 90,
        "single_segment_pair_successful_edge_count": single.get("successful_segment_edge_count"),
        "persistent_segment_cache_ready_count": persistent.get("ready_segment_worker_count"),
        "persistent_segment_cache_failed_count": persistent.get("failed_segment_worker_count"),
        "max_resident_segment_count_observed": max_resident_segment_count_observed,
        "successful_triplet_count": triplet.get("successful_triplet_count"),
        "failed_triplet_count": triplet.get("failed_triplet_count"),
        "successful_seeded_quad_count": quad.get("successful_seeded_quad_count"),
        "failed_seeded_quad_count": quad.get("failed_seeded_quad_count"),
        "current_split_quad_residency_supported": current_split_quad_supported,
        "selected_topology": topology.get("selected_topology"),
        "selected_pair": selected_pair,
        "selected_pair_matches_anchor_pair": selected_pair_matches_anchor_pair,
    },
    "triplet_success_appearance_by_segment_index": {str(index): int(success_appearance.get(index, 0)) for index in sorted(inventory_by_index)},
    "triplet_failed_appearance_by_segment_index": {str(index): int(failed_appearance.get(index, 0)) for index in sorted(inventory_by_index)},
    "triplet_failed_worker_count_by_segment_index": {str(index): int(failed_worker_count.get(index, 0)) for index in sorted(inventory_by_index)},
    "triplet_ready_worker_count_by_segment_index": {str(index): int(ready_worker_count.get(index, 0)) for index in sorted(inventory_by_index)},
    "recommended_anchor_segment_indexes": recommended_anchor_segment_indexes,
    "recommended_anchor_segments": [
        {
            "segment_index": item["segment_index"],
            "segment": item["segment"],
            "size_bytes": item["size_bytes"],
            "size_mib": item["size_mib"],
            "successful_triplet_appearance_count": int(success_appearance.get(item["segment_index"], 0)),
        }
        for item in recommended_anchor_segments
    ],
    "recommended_resplit_segment_indexes": recommended_resplit_indexes,
    "recommended_resplit_segments": recommended_resplit_segments,
    "next_optimization_target": next_optimization_target,
    "warnings": warnings,
    "errors": errors,
}

json_path = run_dir / "segment_capacity_planner_probe.json"
md_path = run_dir / "segment_capacity_planner_probe.md"
json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Dream 7B BPU Segment Capacity Planner Probe",
    "",
    f"- verdict: {payload['verdict']}",
    f"- segment_count: {payload['segment_count']}",
    f"- max_resident_segment_count_observed: {payload['current_split_capacity']['max_resident_segment_count_observed']}",
    f"- successful_triplet_count: {payload['current_split_capacity']['successful_triplet_count']}",
    f"- successful_seeded_quad_count: {payload['current_split_capacity']['successful_seeded_quad_count']}",
    f"- current_split_quad_residency_supported: {payload['current_split_capacity']['current_split_quad_residency_supported']}",
    f"- selected_pair: {payload['current_split_capacity']['selected_pair']}",
    f"- recommended_anchor_segment_indexes: {payload['recommended_anchor_segment_indexes']}",
    f"- recommended_resplit_segment_indexes: {payload['recommended_resplit_segment_indexes']}",
    f"- next_optimization_target: {payload['next_optimization_target']}",
    "",
    "## Evidence",
    "",
]
for name, path in payload["residency_reports"].items():
    lines.append(f"- {name}: {path}")
lines.extend(["", "## Warnings", ""])
if warnings:
    lines.extend(f"- {item}" for item in warnings)
else:
    lines.append("- none")
lines.extend(["", "## Errors", ""])
if errors:
    lines.extend(f"- {item}" for item in errors)
else:
    lines.append("- none")
md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(md_path)
PY
