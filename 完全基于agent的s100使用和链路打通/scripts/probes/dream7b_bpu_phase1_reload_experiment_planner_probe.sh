#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
nas_hbm_root="${DREAM7B_BPU_PHASE1_NAS_HBM_ROOT:-/mnt/nas/openclaw/models/dream7b-hbm}"
compile_venv="${DREAM7B_BPU_PHASE1_COMPILE_VENV:-/opt/digua/dream-s100-oellm-venv}"
compile_model_dir="${DREAM7B_BPU_PHASE1_COMPILE_MODEL_DIR:-/opt/digua/dream_hf}"
compile_output_root="${DREAM7B_BPU_PHASE1_COMPILE_OUTPUT_ROOT:-/mnt/f/Project/Digua/tmp/dream7b-resplit-hbm/phase1-topload}"
publish_hbm_dir="${DREAM7B_BPU_PHASE1_PUBLISH_HBM_DIR:-/mnt/nas/openclaw/models/dream7b-hbm/phase1-topload-seq16}"
phase1_specs="${DREAM7B_BPU_PHASE1_SPECS:-2:3 3:4 4:5 5:7}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

case "$nas_hbm_root" in
  /mnt/nas/openclaw/models/dream7b-hbm|/mnt/nas/openclaw/models/dream7b-hbm/*|/home/sunrise/.cache/openclaw/dream7b-hbm|/home/sunrise/.cache/openclaw/dream7b-hbm/*) ;;
  *)
    echo "Refusing HBM root outside approved Dream 7B model directories: $nas_hbm_root" >&2
    exit 2
    ;;
esac

case "$publish_hbm_dir" in
  /mnt/nas/openclaw/models/dream7b-hbm/*|/home/sunrise/.cache/openclaw/dream7b-hbm/*) ;;
  *)
    echo "Refusing publish HBM dir outside approved Dream 7B model directories: $publish_hbm_dir" >&2
    exit 2
    ;;
esac

case "$compile_output_root" in
  /opt/digua/dream7b-segments-seq16-resplit|/opt/digua/dream7b-segments-seq16-resplit/*|/mnt/f/Project/Digua/tmp/dream7b-resplit-hbm|/mnt/f/Project/Digua/tmp/dream7b-resplit-hbm/*) ;;
  *)
    echo "Refusing compile output root outside approved Dream 7B resplit directories: $compile_output_root" >&2
    exit 2
    ;;
esac

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_phase1_reload_experiment_planner_$stamp"
mkdir -p "$run_dir"

python3 - \
  "$run_dir" \
  "$report_root" \
  "$nas_hbm_root" \
  "$compile_venv" \
  "$compile_model_dir" \
  "$compile_output_root" \
  "$publish_hbm_dir" \
  "$phase1_specs" <<'PY'
import glob
import json
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
report_root = Path(sys.argv[2])
nas_hbm_root = Path(sys.argv[3])
compile_venv = Path(sys.argv[4])
compile_model_dir = Path(sys.argv[5])
compile_output_root = Path(sys.argv[6])
publish_hbm_dir = Path(sys.argv[7])
phase1_specs = sys.argv[8].split()


def latest_json(pattern):
    paths = [Path(item) for item in glob.glob(str(report_root / pattern))]
    paths = [item for item in paths if item.is_file()]
    if not paths:
        return None, {}
    path = max(paths, key=lambda item: item.stat().st_mtime)
    return path, json.loads(path.read_text(encoding="utf-8"))


def hbm_name(start, end):
    return f"dream7b_segment_{start}_{end}_seq16_q8.hbm"


def seg_dir_name(start, end):
    return f"seg{start:02d}_{end:02d}"


def spec_record(spec):
    start_s, end_s = spec.split(":", 1)
    start = int(start_s)
    end = int(end_s)
    rel = Path(seg_dir_name(start, end)) / hbm_name(start, end)
    return {
        "spec": spec,
        "segment": seg_dir_name(start, end),
        "expected_publish_hbm": str(publish_hbm_dir / rel),
        "publish_hbm_exists": (publish_hbm_dir / rel).is_file(),
        "publish_hbm_size_bytes": (publish_hbm_dir / rel).stat().st_size if (publish_hbm_dir / rel).is_file() else 0,
        "compile_output_hbm": str(compile_output_root / rel),
        "compile_output_hbm_exists": (compile_output_root / rel).is_file(),
        "compile_output_hbm_size_bytes": (compile_output_root / rel).stat().st_size if (compile_output_root / rel).is_file() else 0,
    }


window_path, window = latest_json("dream7b_bpu_resplit_window_cost_*/resplit_window_cost_probe.json")
promotion_path, promotion = latest_json("dream7b_bpu_promotion_blocker_diagnosis_*/promotion_blocker_diagnosis_probe.json")
default_path, default = latest_json("dream7b_bpu_cross_job_default_service_telemetry_*/default_service_telemetry_probe.json")
candidate_path, candidate = latest_json("dream7b_bpu_selected_pair_cross_job_queue_telemetry_*/cross_job_queue_telemetry_probe.json")
triplet_path, triplet = latest_json("dream7b_bpu_single_segment_triplet_residency_*/single_segment_triplet_residency_probe.json")

segments = [
    "seg00_02",
    "seg02_04",
    "seg04_07",
    "seg07_10",
    "seg10_14",
    "seg14_17",
    "seg17_21",
    "seg21_24",
    "seg24_26",
    "seg26_28",
]

pair_thirds = {}
for values in triplet.get("successful_triplets") or []:
    if not isinstance(values, list) or len(values) != 3:
        continue
    values = tuple(sorted(int(item) for item in values))
    for i in range(3):
        for j in range(i + 1, 3):
            pair = tuple(sorted((values[i], values[j])))
            thirds = set(values) - set(pair)
            pair_thirds.setdefault(pair, set()).update(thirds)

all_segments = set(range(len(segments)))


def pair_coverage(pair):
    pair = tuple(pair)
    thirds = pair_thirds.get(pair, set())
    covered = set(pair) | thirds
    return {
        "pair": list(pair),
        "pair_segments": [segments[index] for index in pair if 0 <= index < len(segments)],
        "thirds": sorted(thirds),
        "covered_count": len(covered),
        "segment_count": len(segments),
        "covers_all_segments": covered == all_segments,
    }


compile_env = {
    "compile_venv": str(compile_venv),
    "compile_python": str(compile_venv / "bin/python"),
    "compile_python_exists": (compile_venv / "bin/python").is_file(),
    "compile_python_executable": (compile_venv / "bin/python").is_file() and bool((compile_venv / "bin/python").stat().st_mode),
    "model_dir": str(compile_model_dir),
    "model_config": str(compile_model_dir / "config.json"),
    "model_config_exists": (compile_model_dir / "config.json").is_file(),
    "compile_output_root": str(compile_output_root),
    "compile_output_root_exists": compile_output_root.exists(),
}

compile_specs = [spec_record(spec) for spec in phase1_specs]
missing_specs = [item["spec"] for item in compile_specs if not item["publish_hbm_exists"]]

top_ratio_window = (window or {}).get("top_load_to_run_ratio_window") or {}
top_load_window = (window or {}).get("top_load_window") or {}

experiments = [
    {
        "name": "prefix_selected_pair_override",
        "goal": "test whether the highest load/run prefix window can be kept resident across jobs without new HBM artifacts",
        "target_window": top_ratio_window.get("resident_segments"),
        "selected_pair_indexes": [0, 1],
        "coverage": pair_coverage((0, 1)),
        "feasible_now": pair_coverage((0, 1))["covers_all_segments"],
        "blocker": "selected pair [0,1] does not cover all fine-adjacent segments through successful triplets" if not pair_coverage((0, 1))["covers_all_segments"] else "",
    },
    {
        "name": "topload_selected_pair_override",
        "goal": "test whether the top absolute-load window can be held as selected-pair anchors without new HBM artifacts",
        "target_window": top_load_window.get("resident_segments"),
        "selected_pair_indexes": [1, 2],
        "coverage": pair_coverage((1, 2)),
        "feasible_now": pair_coverage((1, 2))["covers_all_segments"],
        "blocker": "selected pair [1,2] does not cover all fine-adjacent segments through successful triplets" if not pair_coverage((1, 2))["covers_all_segments"] else "",
    },
    {
        "name": "phase1_topload_resplit_compile",
        "goal": "compile finer HBM shards for seg02_04 and seg04_07 so the top absolute-load window can be remeasured with smaller load units",
        "target_specs": phase1_specs,
        "compile_specs": compile_specs,
        "missing_specs": missing_specs,
        "feasible_now": not missing_specs,
        "blocker": "missing HBM artifacts and no compile environment on this host" if missing_specs and (not compile_env["compile_python_exists"] or not compile_env["model_config_exists"]) else ("missing HBM artifacts; compile on approved x86 Linux builder" if missing_specs else ""),
    },
]

phase1_gate = {
    "baseline_avg_bpu_loading": default.get("avg_bpu_loading"),
    "baseline_load_to_run_ratio": default.get("load_to_run_ratio"),
    "candidate_avg_bpu_loading": candidate.get("avg_bpu_loading"),
    "candidate_load_to_run_ratio": candidate.get("load_to_run_ratio"),
    "target_avg_bpu_loading": 15.0,
    "target_load_to_run_ratio": 7.0,
}

compile_command = (
    "DREAM_RESPLIT_OUTPUT_ROOT="
    + str(compile_output_root)
    + " DREAM_RESPLIT_SPECS=\""
    + " ".join(phase1_specs)
    + "\" DREAM_RESPLIT_EXPECTED_SPECS=\""
    + " ".join(phase1_specs)
    + "\" bash scripts/probes/compile_dream_segments_seq16_resplit_probe.sh "
    + "/tmp/dream7b_phase1_topload_compile_reports"
)

validation_commands = [
    "publish generated HBM files to " + str(publish_hbm_dir),
    "add a guarded segment plan using the new shards; do not replace default service",
    "run DREAM7B_BPU_RESPLIT_BATCH_TELEMETRY_EXPECTED_SEGMENT_PLAN=<new-plan> bash scripts/probes/dream7b_bpu_resplit_batch_telemetry_probe.sh /mnt/nas/openclaw/reports/models",
    "run DREAM7B_BPU_RESPLIT_WINDOW_COST_EXPECTED_SEGMENT_PLAN=<new-plan> bash scripts/probes/dream7b_bpu_resplit_window_cost_probe.sh /mnt/nas/openclaw/reports/models",
    "run dream7b-bpu-utilization-gap-probe and deployment/default-deployable acceptance before any promotion claim",
]

errors = []
warnings = []
if not window_path:
    errors.append("missing latest resplit window-cost report")
if not triplet_path:
    errors.append("missing latest triplet residency report")
if missing_specs:
    warnings.append("phase1 top-load split cannot run until missing HBM artifacts are compiled and published")
if not compile_env["compile_python_exists"] or not compile_env["model_config_exists"]:
    warnings.append("current host is not an approved Dream HBM compile host; use x86 Linux builder with HBDK/Dream HF assets")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_phase1_reload_experiment_planner_probe" if not errors else "failed_dream7b_bpu_phase1_reload_experiment_planner_probe",
    "run_dir": str(run_dir),
    "report_root": str(report_root),
    "evidence_paths": {
        "window_cost": str(window_path) if window_path else "",
        "promotion_blocker_diagnosis": str(promotion_path) if promotion_path else "",
        "default_service_telemetry": str(default_path) if default_path else "",
        "candidate_cross_job_telemetry": str(candidate_path) if candidate_path else "",
        "triplet_residency": str(triplet_path) if triplet_path else "",
    },
    "phase1_gate": phase1_gate,
    "window_bottlenecks": {
        "top_load_to_run_ratio_window": top_ratio_window,
        "top_load_window": top_load_window,
    },
    "compile_env": compile_env,
    "experiments": experiments,
    "recommended_next_experiment": "phase1_topload_resplit_compile",
    "compile_command": compile_command,
    "validation_commands": validation_commands,
    "warnings": warnings,
    "errors": errors,
}

(run_dir / "phase1_reload_experiment_planner_probe.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

lines = [
    "# Dream 7B Phase 1 Reload Experiment Planner",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- recommended_next_experiment: {payload['recommended_next_experiment']}",
    f"- default_service_telemetry: {payload['evidence_paths']['default_service_telemetry']}",
    f"- candidate_cross_job_telemetry: {payload['evidence_paths']['candidate_cross_job_telemetry']}",
    f"- triplet_residency: {payload['evidence_paths']['triplet_residency']}",
    "",
    "## Phase 1 Gate",
    "",
]
for key, value in phase1_gate.items():
    lines.append(f"- {key}: {value}")
lines.extend(["", "## Experiments", ""])
for item in experiments:
    lines.append(f"### {item['name']}")
    lines.append("")
    lines.append(f"- feasible_now: {item['feasible_now']}")
    if item.get("blocker"):
        lines.append(f"- blocker: {item['blocker']}")
    if item.get("target_window"):
        lines.append(f"- target_window: {item['target_window']}")
    if item.get("target_specs"):
        lines.append(f"- target_specs: {item['target_specs']}")
        lines.append(f"- missing_specs: {item['missing_specs']}")
    if item.get("coverage"):
        cov = item["coverage"]
        lines.append(f"- coverage: {cov['covered_count']}/{cov['segment_count']}, covers_all={cov['covers_all_segments']}")
    lines.append("")
lines.extend(["## Compile Command", "", "```bash", compile_command, "```", "", "## Validation Commands", ""])
lines.extend(f"- {item}" for item in validation_commands)
lines.extend(["", "## Warnings", ""])
lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- none")
lines.extend(["", "## Errors", ""])
lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")

(run_dir / "phase1_reload_experiment_planner_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "phase1_reload_experiment_planner_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
