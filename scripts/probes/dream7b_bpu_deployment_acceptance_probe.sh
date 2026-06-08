#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
min_batch_capacity="${DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_CAPACITY:-16}"
min_systemd_batch_requests="${DREAM7B_BPU_ACCEPTANCE_MIN_SYSTEMD_BATCH_REQUESTS:-16}"
min_systemd_telemetry_requests="${DREAM7B_BPU_ACCEPTANCE_MIN_SYSTEMD_TELEMETRY_REQUESTS:-48}"
min_batch_generate_count="${DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_GENERATE_COUNT:-16}"
min_batch_generate_sustained_round_count="${DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_GENERATE_SUSTAINED_ROUND_COUNT:-3}"
min_long_repeat_count="${DREAM7B_BPU_ACCEPTANCE_MIN_LONG_REPEAT_COUNT:-6}"
max_long_repeat_wall_spread_ratio="${DREAM7B_BPU_ACCEPTANCE_MAX_LONG_REPEAT_WALL_SPREAD_RATIO:-0.10}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

if ! [[ "$min_batch_capacity" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_CAPACITY must be a positive integer." >&2
  exit 2
fi
if ! [[ "$min_systemd_batch_requests" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_ACCEPTANCE_MIN_SYSTEMD_BATCH_REQUESTS must be a positive integer." >&2
  exit 2
fi
if ! [[ "$min_systemd_telemetry_requests" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_ACCEPTANCE_MIN_SYSTEMD_TELEMETRY_REQUESTS must be a positive integer." >&2
  exit 2
fi
if ! [[ "$min_batch_generate_count" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_GENERATE_COUNT must be a positive integer." >&2
  exit 2
fi
if ! [[ "$min_batch_generate_sustained_round_count" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_GENERATE_SUSTAINED_ROUND_COUNT must be a positive integer." >&2
  exit 2
fi
if ! [[ "$min_long_repeat_count" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_ACCEPTANCE_MIN_LONG_REPEAT_COUNT must be a positive integer." >&2
  exit 2
fi
if ! [[ "$max_long_repeat_wall_spread_ratio" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "DREAM7B_BPU_ACCEPTANCE_MAX_LONG_REPEAT_WALL_SPREAD_RATIO must be a non-negative number." >&2
  exit 2
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_deployment_acceptance_$stamp"
mkdir -p "$run_dir"

python3 - \
  "$run_dir" \
  "$report_root" \
  "$min_batch_capacity" \
  "$min_systemd_batch_requests" \
  "$min_systemd_telemetry_requests" \
  "$min_batch_generate_count" \
  "$min_batch_generate_sustained_round_count" \
  "$min_long_repeat_count" \
  "$max_long_repeat_wall_spread_ratio" <<'PY'
import glob
import json
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
report_root = Path(sys.argv[2])
min_batch_capacity = int(sys.argv[3])
min_systemd_batch_requests = int(sys.argv[4])
min_systemd_telemetry_requests = int(sys.argv[5])
min_batch_generate_count = int(sys.argv[6])
min_batch_generate_sustained_round_count = int(sys.argv[7])
min_long_repeat_count = int(sys.argv[8])
max_long_repeat_wall_spread_ratio = float(sys.argv[9])
errors = []
warnings = []
checks = []


def latest_json(pattern):
    paths = [Path(item) for item in glob.glob(str(report_root / pattern))]
    paths = [item for item in paths if item.is_file()]
    if not paths:
        return None, None
    path = max(paths, key=lambda item: item.stat().st_mtime)
    return path, json.loads(path.read_text(encoding="utf-8"))


def add_check(name, path, ok, details):
    row = {
        "name": name,
        "ok": bool(ok),
        "path": str(path) if path else "",
        "details": details,
    }
    checks.append(row)
    if not ok:
        errors.append(f"{name} failed: {details}")


systemd_path, systemd = latest_json("dream7b_bpu_batch_queue_systemd_*/systemd_probe.json")
if systemd is None:
    add_check("systemd_service", systemd_path, False, {"reason": "missing systemd_probe.json"})
else:
    ok = (
        systemd.get("verdict") == "ok_dream7b_bpu_batch_queue_systemd_probe"
        and systemd.get("service_status") == "active"
        and systemd.get("service_enabled") == "enabled"
        and systemd.get("max_batch_size_required") == 16
        and systemd.get("drain_all_required") is True
        and "--max-batch-size 16" in (systemd.get("exec_start") or "")
        and "--drain-all" in (systemd.get("exec_start") or "")
        and not systemd.get("errors")
    )
    add_check(
        "systemd_service",
        systemd_path,
        ok,
        {
            "verdict": systemd.get("verdict"),
            "service_status": systemd.get("service_status"),
            "service_enabled": systemd.get("service_enabled"),
            "max_batch_size_required": systemd.get("max_batch_size_required"),
            "drain_all_required": systemd.get("drain_all_required"),
        },
    )

capacity_path, capacity = latest_json("dream7b_bpu_batch_capacity_*/batch_capacity_probe.json")
if capacity is None:
    add_check("batch_capacity", capacity_path, False, {"reason": "missing batch_capacity_probe.json"})
else:
    entries = capacity.get("entries") or []
    batch16 = [item for item in entries if item.get("batch_count") == min_batch_capacity]
    batch16_entry = batch16[-1] if batch16 else {}
    ok = (
        capacity.get("verdict") == "ok_dream7b_bpu_batch_capacity_probe"
        and int(capacity.get("max_passing_count") or 0) >= min_batch_capacity
        and bool(batch16_entry.get("ok"))
        and batch16_entry.get("execution_mode") == "pair_window_batch"
        and batch16_entry.get("window_execution_mode") == "window-batch"
        and batch16_entry.get("child_process_count") == 0
        and batch16_entry.get("final_shape_count") == min_batch_capacity
        and not capacity.get("errors")
    )
    add_check(
        "batch_capacity",
        capacity_path,
        ok,
        {
            "verdict": capacity.get("verdict"),
            "max_passing_count": capacity.get("max_passing_count"),
            "batch_count": batch16_entry.get("batch_count"),
            "amortized_wall_ms_per_forward": batch16_entry.get("amortized_wall_ms_per_forward"),
        },
    )

hbm_inventory_path, hbm_inventory = latest_json("dream7b_bpu_hbm_artifact_inventory_*/hbm_artifact_inventory_probe.json")
if hbm_inventory is None:
    add_check("hbm_artifact_inventory", hbm_inventory_path, False, {"reason": "missing hbm_artifact_inventory_probe.json"})
else:
    ok = (
        hbm_inventory.get("verdict") == "ok_dream7b_bpu_hbm_artifact_inventory_probe"
        and hbm_inventory.get("expected_artifact_count") == 14
        and hbm_inventory.get("expected_base_count") == 6
        and hbm_inventory.get("expected_fine_count") == 8
        and hbm_inventory.get("nas_existing_count") == 14
        and hbm_inventory.get("local_existing_count") == 14
        and hbm_inventory.get("size_match_count") == 14
        and hbm_inventory.get("manifest_expected_count") == 12
        and hbm_inventory.get("manifest_verified_count") == 12
        and hbm_inventory.get("required_manifest_expected_count") == 12
        and not hbm_inventory.get("errors")
    )
    add_check(
        "hbm_artifact_inventory",
        hbm_inventory_path,
        ok,
        {
            "verdict": hbm_inventory.get("verdict"),
            "expected_artifact_count": hbm_inventory.get("expected_artifact_count"),
            "nas_existing_count": hbm_inventory.get("nas_existing_count"),
            "local_existing_count": hbm_inventory.get("local_existing_count"),
            "size_match_count": hbm_inventory.get("size_match_count"),
            "manifest_verified_count": hbm_inventory.get("manifest_verified_count"),
        },
    )

systemd_batch_path, systemd_batch = latest_json("dream7b_bpu_batch_queue_systemd_batch_*/systemd_batch_probe.json")
if systemd_batch is None:
    add_check("systemd_batch", systemd_batch_path, False, {"reason": "missing systemd_batch_probe.json"})
else:
    ok = (
        systemd_batch.get("verdict") == "ok_dream7b_bpu_batch_queue_systemd_batch_probe"
        and systemd_batch.get("job_status") == "done"
        and int(systemd_batch.get("request_count") or 0) >= min_systemd_batch_requests
        and int(systemd_batch.get("processed_count") or 0) >= min_systemd_batch_requests
        and systemd_batch.get("accepted_count") == systemd_batch.get("processed_count")
        and systemd_batch.get("deferred_count") == 0
        and systemd_batch.get("max_batch_size") == 16
        and systemd_batch.get("batch_run_count") == 1
        and systemd_batch.get("batch_count") == systemd_batch.get("processed_count")
        and systemd_batch.get("execution_mode") == "pair_window_batch"
        and systemd_batch.get("window_execution_mode") == "window-batch"
        and systemd_batch.get("child_process_count") == 0
        and not systemd_batch.get("errors")
    )
    add_check(
        "systemd_batch",
        systemd_batch_path,
        ok,
        {
            "verdict": systemd_batch.get("verdict"),
            "processed_count": systemd_batch.get("processed_count"),
            "batch_count": systemd_batch.get("batch_count"),
            "amortized_wall_ms_per_processed_request": systemd_batch.get("amortized_wall_ms_per_processed_request"),
        },
    )

systemd_drain_path, systemd_drain = latest_json("dream7b_bpu_batch_queue_systemd_drain_*/systemd_drain_probe.json")
if systemd_drain is None:
    add_check("systemd_drain", systemd_drain_path, False, {"reason": "missing systemd_drain_probe.json"})
else:
    ok = (
        systemd_drain.get("verdict") == "ok_dream7b_bpu_batch_queue_systemd_drain_probe"
        and systemd_drain.get("job_status") == "done"
        and int(systemd_drain.get("request_count") or 0) >= min_systemd_batch_requests
        and systemd_drain.get("drain_all") is True
        and systemd_drain.get("max_batch_size") == 16
        and systemd_drain.get("processed_count") == systemd_drain.get("request_count")
        and systemd_drain.get("accepted_count") == systemd_drain.get("request_count")
        and systemd_drain.get("deferred_count") == 0
        and systemd_drain.get("batch_counts") == [16]
        and not systemd_drain.get("errors")
    )
    add_check(
        "systemd_drain",
        systemd_drain_path,
        ok,
        {
            "verdict": systemd_drain.get("verdict"),
            "request_count": systemd_drain.get("request_count"),
            "batch_counts": systemd_drain.get("batch_counts"),
            "amortized_wall_ms_per_processed_request": systemd_drain.get("amortized_wall_ms_per_processed_request"),
        },
    )

systemd_canary_path, systemd_canary = latest_json("dream7b_bpu_batch_queue_systemd_canary_*/systemd_canary_probe.json")
if systemd_canary is None:
    add_check("systemd_canary", systemd_canary_path, False, {"reason": "missing systemd_canary_probe.json"})
else:
    ok = (
        systemd_canary.get("verdict") == "ok_dream7b_bpu_batch_queue_systemd_canary_probe"
        and systemd_canary.get("service_status_before") == "active"
        and systemd_canary.get("service_enabled_before") == "enabled"
        and systemd_canary.get("service_status_after") == "active"
        and systemd_canary.get("service_enabled_after") == "enabled"
        and systemd_canary.get("job_status") == "done"
        and int(systemd_canary.get("request_count") or 0) >= 1
        and systemd_canary.get("request_count") == systemd_canary.get("processed_count")
        and systemd_canary.get("request_count") == systemd_canary.get("accepted_count")
        and systemd_canary.get("deferred_count") == 0
        and systemd_canary.get("skipped_count") == 0
        and systemd_canary.get("drain_all") is True
        and systemd_canary.get("max_batch_size") == 16
        and systemd_canary.get("batch_run_count") == 1
        and systemd_canary.get("batch_count") == systemd_canary.get("request_count")
        and systemd_canary.get("result_count") == systemd_canary.get("request_count")
        and systemd_canary.get("execution_mode") == "pair_window_batch"
        and systemd_canary.get("window_execution_mode") == "window-batch"
        and systemd_canary.get("child_process_count") == 0
        and systemd_canary.get("bpu_lock_path") == "/run/lock/dream7b_bpu_batch_queue_runner.lock"
        and all(item == [1, 16, 152064] for item in (systemd_canary.get("final_shapes") or []))
        and not systemd_canary.get("errors")
    )
    add_check(
        "systemd_canary",
        systemd_canary_path,
        ok,
        {
            "verdict": systemd_canary.get("verdict"),
            "job_status": systemd_canary.get("job_status"),
            "request_count": systemd_canary.get("request_count"),
            "processed_count": systemd_canary.get("processed_count"),
            "final_shapes": systemd_canary.get("final_shapes"),
            "amortized_wall_ms_per_processed_request": systemd_canary.get("amortized_wall_ms_per_processed_request"),
        },
    )

text_queue_run_path, text_queue_run = latest_json("dream7b_bpu_text_queue_run_*/text_queue_run.json")
if text_queue_run is None:
    add_check("text_queue_run", text_queue_run_path, False, {"reason": "missing text_queue_run.json"})
else:
    tokenizer = text_queue_run.get("tokenizer") or {}
    submit = text_queue_run.get("submit") or {}
    topk_last_position = text_queue_run.get("topk_last_position") or []
    topk_last_position_decoded = text_queue_run.get("topk_last_position_decoded") or []
    ok = (
        text_queue_run.get("verdict") == "ok_dream7b_bpu_text_queue_run"
        and text_queue_run.get("submit_cmd") == "dream7b-bpu-text-queue-submit"
        and text_queue_run.get("submit_verdict") == "ok_dream7b_bpu_text_queue_submit"
        and submit.get("verdict") == "ok_dream7b_bpu_text_queue_submit"
        and submit.get("job_name") == text_queue_run.get("job_name")
        and submit.get("request_id") == text_queue_run.get("request_id")
        and submit.get("queue_dir") == text_queue_run.get("queue_dir")
        and submit.get("tokenizer_json") == text_queue_run.get("tokenizer_json")
        and text_queue_run.get("job_status") == "done"
        and text_queue_run.get("processed_count") == 1
        and text_queue_run.get("accepted_count") == 1
        and text_queue_run.get("deferred_count") == 0
        and text_queue_run.get("skipped_count") == 0
        and text_queue_run.get("batch_run_count") == 1
        and text_queue_run.get("batch_count") == 1
        and text_queue_run.get("result_count") == 1
        and text_queue_run.get("execution_mode") == "pair_window_batch"
        and text_queue_run.get("window_execution_mode") == "window-batch"
        and text_queue_run.get("child_process_count") == 0
        and text_queue_run.get("bpu_lock_path") == "/run/lock/dream7b_bpu_batch_queue_runner.lock"
        and text_queue_run.get("final_shape") == [1, 16, 152064]
        and len(topk_last_position) > 0
        and len(topk_last_position_decoded) == len(topk_last_position)
        and all("token_id" in item and "token_text" in item for item in topk_last_position_decoded)
        and bool(text_queue_run.get("durable_results_jsonl"))
        and float(text_queue_run.get("total_wall_ms") or 0.0) > 0.0
        and float(text_queue_run.get("amortized_wall_ms_per_processed_request") or 0.0) > 0.0
        and tokenizer.get("tokenizer_dir") == "/mnt/nas/openclaw/models/dream7b/tokenizer"
        and tokenizer.get("fit_mode") in ("exact", "truncate-left", "pad-right")
        and tokenizer.get("seq_len") == 16
        and int(tokenizer.get("original_token_count") or 0) > 0
        and tokenizer.get("token_count") == 16
        and not text_queue_run.get("errors")
    )
    add_check(
        "text_queue_run",
        text_queue_run_path,
        ok,
        {
            "verdict": text_queue_run.get("verdict"),
            "submit_cmd": text_queue_run.get("submit_cmd"),
            "submit_verdict": text_queue_run.get("submit_verdict"),
            "job_status": text_queue_run.get("job_status"),
            "request_id": text_queue_run.get("request_id"),
            "tokenizer_dir": tokenizer.get("tokenizer_dir"),
            "fit_mode": tokenizer.get("fit_mode"),
            "original_token_count": tokenizer.get("original_token_count"),
            "token_count": tokenizer.get("token_count"),
            "final_shape": text_queue_run.get("final_shape"),
            "topk_last_position": topk_last_position,
            "topk_last_position_decoded": topk_last_position_decoded,
            "amortized_wall_ms_per_processed_request": text_queue_run.get("amortized_wall_ms_per_processed_request"),
        },
    )

text_queue_path, text_queue = latest_json("dream7b_bpu_text_queue_systemd_*/text_queue_systemd_probe.json")
if text_queue is None:
    add_check("text_queue_systemd", text_queue_path, False, {"reason": "missing text_queue_systemd_probe.json"})
else:
    tokenizer = text_queue.get("tokenizer") or {}
    submit = text_queue.get("submit") or {}
    topk_last_position = text_queue.get("topk_last_position") or []
    topk_last_position_decoded = text_queue.get("topk_last_position_decoded") or []
    ok = (
        text_queue.get("verdict") == "ok_dream7b_bpu_text_queue_systemd_probe"
        and text_queue.get("run_cmd") == "dream7b-bpu-text-queue-run"
        and text_queue.get("run_verdict") == "ok_dream7b_bpu_text_queue_run"
        and text_queue.get("submit_cmd") == "dream7b-bpu-text-queue-submit"
        and text_queue.get("submit_verdict") == "ok_dream7b_bpu_text_queue_submit"
        and submit.get("verdict") == "ok_dream7b_bpu_text_queue_submit"
        and submit.get("job_name") == text_queue.get("job_name")
        and submit.get("request_id") == text_queue.get("request_id")
        and submit.get("queue_dir") == text_queue.get("queue_dir")
        and submit.get("tokenizer_json") == text_queue.get("tokenizer_json")
        and submit.get("seq_len") == 16
        and submit.get("fit_mode") in ("exact", "truncate-left", "pad-right")
        and not submit.get("errors")
        and text_queue.get("service_status_before") == "active"
        and text_queue.get("service_enabled_before") == "enabled"
        and text_queue.get("service_status_after") == "active"
        and text_queue.get("service_enabled_after") == "enabled"
        and text_queue.get("job_status") == "done"
        and text_queue.get("processed_count") == 1
        and text_queue.get("accepted_count") == 1
        and text_queue.get("deferred_count") == 0
        and text_queue.get("skipped_count") == 0
        and text_queue.get("batch_run_count") == 1
        and text_queue.get("batch_count") == 1
        and text_queue.get("result_count") == 1
        and text_queue.get("execution_mode") == "pair_window_batch"
        and text_queue.get("window_execution_mode") == "window-batch"
        and text_queue.get("child_process_count") == 0
        and text_queue.get("bpu_lock_path") == "/run/lock/dream7b_bpu_batch_queue_runner.lock"
        and text_queue.get("final_shape") == [1, 16, 152064]
        and len(topk_last_position) > 0
        and len(topk_last_position_decoded) == len(topk_last_position)
        and all("token_id" in item and "token_text" in item for item in topk_last_position_decoded)
        and bool(text_queue.get("durable_results_jsonl"))
        and float(text_queue.get("total_wall_ms") or 0.0) > 0.0
        and float(text_queue.get("amortized_wall_ms_per_processed_request") or 0.0) > 0.0
        and tokenizer.get("tokenizer_dir") == "/mnt/nas/openclaw/models/dream7b/tokenizer"
        and tokenizer.get("fit_mode") in ("exact", "truncate-left", "pad-right")
        and tokenizer.get("seq_len") == 16
        and int(tokenizer.get("original_token_count") or 0) > 0
        and tokenizer.get("token_count") == 16
        and not text_queue.get("errors")
    )
    add_check(
        "text_queue_systemd",
        text_queue_path,
        ok,
        {
            "verdict": text_queue.get("verdict"),
            "run_cmd": text_queue.get("run_cmd"),
            "run_verdict": text_queue.get("run_verdict"),
            "submit_cmd": text_queue.get("submit_cmd"),
            "submit_verdict": text_queue.get("submit_verdict"),
            "job_status": text_queue.get("job_status"),
            "request_id": text_queue.get("request_id"),
            "tokenizer_dir": tokenizer.get("tokenizer_dir"),
            "fit_mode": tokenizer.get("fit_mode"),
            "original_token_count": tokenizer.get("original_token_count"),
            "token_count": tokenizer.get("token_count"),
            "final_shape": text_queue.get("final_shape"),
            "topk_last_position": topk_last_position,
            "topk_last_position_decoded": topk_last_position_decoded,
            "amortized_wall_ms_per_processed_request": text_queue.get("amortized_wall_ms_per_processed_request"),
        },
    )

diffusion_generate_path, diffusion_generate = latest_json("dream7b_bpu_diffusion_generate_*/generation.json")
if diffusion_generate is None:
    add_check("diffusion_generate", diffusion_generate_path, False, {"reason": "missing generation.json"})
else:
    history = diffusion_generate.get("history") or []
    ok = (
        diffusion_generate.get("verdict") == "ok_dream7b_bpu_diffusion_generate"
        and diffusion_generate.get("forward_cmd") == "dream7b-bpu-fine-forward"
        and diffusion_generate.get("seq_len") == 16
        and int(diffusion_generate.get("steps") or 0) >= 1
        and int(diffusion_generate.get("executed_step_count") or 0) == len(history)
        and int(diffusion_generate.get("executed_step_count") or 0) >= 1
        and diffusion_generate.get("remaining_mask_positions") == []
        and bool(diffusion_generate.get("decoded_final"))
        and diffusion_generate.get("boundary") == "bounded_seq16_generation_entrypoint_not_complete_production_text_service"
        and all(item.get("forward_verdict") == "ok_dream7b_segmented_hbm_python_forward" for item in history)
        and all(item.get("forward_execution_mode") == "pair_in_process" for item in history)
        and all(item.get("forward_window_execution_mode") == "in-process" for item in history)
        and all(item.get("forward_child_process_count") == 0 for item in history)
        and all(item.get("forward_final_shape") == [1, 16, 152064] for item in history)
        and not diffusion_generate.get("errors")
    )
    add_check(
        "diffusion_generate",
        diffusion_generate_path,
        ok,
        {
            "verdict": diffusion_generate.get("verdict"),
            "forward_cmd": diffusion_generate.get("forward_cmd"),
            "seq_len": diffusion_generate.get("seq_len"),
            "steps": diffusion_generate.get("steps"),
            "executed_step_count": diffusion_generate.get("executed_step_count"),
            "remaining_mask_positions": diffusion_generate.get("remaining_mask_positions"),
            "decoded_final": diffusion_generate.get("decoded_final"),
            "boundary": diffusion_generate.get("boundary"),
        },
    )

diffusion_generate_telemetry_path, diffusion_generate_telemetry = latest_json("dream7b_bpu_diffusion_generate_telemetry_*/generation_telemetry_probe.json")
if diffusion_generate_telemetry is None:
    add_check("diffusion_generate_telemetry", diffusion_generate_telemetry_path, False, {"reason": "missing generation_telemetry_probe.json"})
else:
    metrics = diffusion_generate_telemetry.get("generation_metrics") or {}
    ok = (
        diffusion_generate_telemetry.get("verdict") == "ok_dream7b_bpu_diffusion_generate_telemetry_probe"
        and diffusion_generate_telemetry.get("generate_cmd") == "dream7b-bpu-diffusion-generate"
        and diffusion_generate_telemetry.get("generation_status") == 0
        and float(diffusion_generate_telemetry.get("max_bpu_loading") or 0.0) > 0.0
        and int(diffusion_generate_telemetry.get("nonzero_bpu_loading_sample_count") or 0) > 0
        and metrics.get("verdict") == "ok_dream7b_bpu_diffusion_generate"
        and metrics.get("forward_cmd") == "dream7b-bpu-fine-forward"
        and metrics.get("seq_len") == 16
        and int(metrics.get("executed_step_count") or 0) >= 1
        and metrics.get("remaining_mask_positions") == []
        and bool(metrics.get("decoded_final"))
        and metrics.get("boundary") == "bounded_seq16_generation_entrypoint_not_complete_production_text_service"
        and all(item == "ok_dream7b_segmented_hbm_python_forward" for item in (metrics.get("history_forward_verdicts") or []))
        and all(item == "pair_in_process" for item in (metrics.get("history_forward_execution_modes") or []))
        and all(item == "in-process" for item in (metrics.get("history_forward_window_execution_modes") or []))
        and all(item == 0 for item in (metrics.get("history_forward_child_process_counts") or []))
        and all(item == [1, 16, 152064] for item in (metrics.get("history_forward_final_shapes") or []))
        and not diffusion_generate_telemetry.get("errors")
    )
    add_check(
        "diffusion_generate_telemetry",
        diffusion_generate_telemetry_path,
        ok,
        {
            "verdict": diffusion_generate_telemetry.get("verdict"),
            "generate_cmd": diffusion_generate_telemetry.get("generate_cmd"),
            "generation_status": diffusion_generate_telemetry.get("generation_status"),
            "max_bpu_loading": diffusion_generate_telemetry.get("max_bpu_loading"),
            "avg_bpu_loading": diffusion_generate_telemetry.get("avg_bpu_loading"),
            "nonzero_bpu_loading_sample_count": diffusion_generate_telemetry.get("nonzero_bpu_loading_sample_count"),
            "generation_verdict": metrics.get("verdict"),
            "forward_cmd": metrics.get("forward_cmd"),
            "seq_len": metrics.get("seq_len"),
            "executed_step_count": metrics.get("executed_step_count"),
            "remaining_mask_positions": metrics.get("remaining_mask_positions"),
            "decoded_final": metrics.get("decoded_final"),
            "boundary": metrics.get("boundary"),
        },
    )

diffusion_batch_generate_telemetry_path, diffusion_batch_generate_telemetry = latest_json("dream7b_bpu_diffusion_batch_generate_telemetry_*/batch_generation_telemetry_probe.json")
if diffusion_batch_generate_telemetry is None:
    add_check("diffusion_batch_generate_telemetry", diffusion_batch_generate_telemetry_path, False, {"reason": "missing batch_generation_telemetry_probe.json"})
else:
    metrics = diffusion_batch_generate_telemetry.get("generation_metrics") or {}
    batch_count = int(metrics.get("batch_count") or 0)
    ok = (
        diffusion_batch_generate_telemetry.get("verdict") == "ok_dream7b_bpu_diffusion_batch_generate_telemetry_probe"
        and diffusion_batch_generate_telemetry.get("generate_cmd") == "dream7b-bpu-diffusion-batch-generate"
        and diffusion_batch_generate_telemetry.get("generation_status") == 0
        and int(diffusion_batch_generate_telemetry.get("batch_count") or 0) >= min_batch_generate_count
        and float(diffusion_batch_generate_telemetry.get("max_bpu_loading") or 0.0) > 0.0
        and int(diffusion_batch_generate_telemetry.get("nonzero_bpu_loading_sample_count") or 0) > 0
        and metrics.get("verdict") == "ok_dream7b_bpu_diffusion_batch_generate"
        and metrics.get("forward_cmd") == "dream7b-bpu-fine-batch-forward"
        and batch_count >= min_batch_generate_count
        and metrics.get("seq_len") == 16
        and int(metrics.get("executed_step_count") or 0) >= 1
        and all(item == batch_count for item in (metrics.get("forward_batch_counts") or []))
        and all(not item.get("remaining_mask_positions") for item in (metrics.get("remaining_mask_positions_by_batch") or []))
        and len(metrics.get("decoded_final_by_batch") or []) == batch_count
        and metrics.get("boundary") == "bounded_seq16_batch_generation_entrypoint_not_complete_production_text_service"
        and all(item == "ok_dream7b_segmented_hbm_python_forward" for item in (metrics.get("history_forward_verdicts") or []))
        and all(item == "pair_window_batch" for item in (metrics.get("history_forward_execution_modes") or []))
        and all(item == "window-batch" for item in (metrics.get("history_forward_window_execution_modes") or []))
        and all(item == 0 for item in (metrics.get("history_forward_child_process_counts") or []))
        and all(item == batch_count for item in (metrics.get("history_forward_batch_counts") or []))
        and all(item == [[1, 16, 152064] for _ in range(batch_count)] for item in (metrics.get("history_forward_final_shapes") or []))
        and not diffusion_batch_generate_telemetry.get("errors")
    )
    add_check(
        "diffusion_batch_generate_telemetry",
        diffusion_batch_generate_telemetry_path,
        ok,
        {
            "verdict": diffusion_batch_generate_telemetry.get("verdict"),
            "generate_cmd": diffusion_batch_generate_telemetry.get("generate_cmd"),
            "generation_status": diffusion_batch_generate_telemetry.get("generation_status"),
            "batch_count": diffusion_batch_generate_telemetry.get("batch_count"),
            "max_bpu_loading": diffusion_batch_generate_telemetry.get("max_bpu_loading"),
            "avg_bpu_loading": diffusion_batch_generate_telemetry.get("avg_bpu_loading"),
            "nonzero_bpu_loading_sample_count": diffusion_batch_generate_telemetry.get("nonzero_bpu_loading_sample_count"),
            "generation_verdict": metrics.get("verdict"),
            "forward_cmd": metrics.get("forward_cmd"),
            "seq_len": metrics.get("seq_len"),
            "executed_step_count": metrics.get("executed_step_count"),
            "forward_batch_counts": metrics.get("forward_batch_counts"),
            "boundary": metrics.get("boundary"),
        },
    )

diffusion_batch_generate_sustained_path, diffusion_batch_generate_sustained = latest_json("dream7b_bpu_diffusion_batch_generate_sustained_*/batch_generation_sustained_probe.json")
if diffusion_batch_generate_sustained is None:
    add_check("diffusion_batch_generate_sustained", diffusion_batch_generate_sustained_path, False, {"reason": "missing batch_generation_sustained_probe.json"})
else:
    round_count = int(diffusion_batch_generate_sustained.get("round_count") or 0)
    batch_count = int(diffusion_batch_generate_sustained.get("batch_count") or 0)
    generation_statuses = diffusion_batch_generate_sustained.get("generation_statuses") or []
    generation_batch_counts = diffusion_batch_generate_sustained.get("generation_batch_counts") or []
    generation_forward_batch_counts_by_round = diffusion_batch_generate_sustained.get("generation_forward_batch_counts_by_round") or []
    ok = (
        diffusion_batch_generate_sustained.get("verdict") == "ok_dream7b_bpu_diffusion_batch_generate_sustained_probe"
        and diffusion_batch_generate_sustained.get("generate_cmd") == "dream7b-bpu-diffusion-batch-generate"
        and round_count >= min_batch_generate_sustained_round_count
        and batch_count >= min_batch_generate_count
        and int(diffusion_batch_generate_sustained.get("successful_generation_count") or 0) >= min_batch_generate_sustained_round_count
        and int(diffusion_batch_generate_sustained.get("expected_total_batch_items") or 0) == round_count * batch_count
        and int(diffusion_batch_generate_sustained.get("actual_total_batch_items") or 0) == round_count * batch_count
        and all(item == 0 for item in generation_statuses)
        and all(item == batch_count for item in generation_batch_counts)
        and all(all(count == batch_count for count in (counts or [])) for counts in generation_forward_batch_counts_by_round)
        and int(diffusion_batch_generate_sustained.get("total_forward_call_count") or 0) >= round_count
        and float(diffusion_batch_generate_sustained.get("max_bpu_loading") or 0.0) > 0.0
        and int(diffusion_batch_generate_sustained.get("nonzero_bpu_loading_sample_count") or 0) > 0
        and not diffusion_batch_generate_sustained.get("errors")
    )
    add_check(
        "diffusion_batch_generate_sustained",
        diffusion_batch_generate_sustained_path,
        ok,
        {
            "verdict": diffusion_batch_generate_sustained.get("verdict"),
            "generate_cmd": diffusion_batch_generate_sustained.get("generate_cmd"),
            "round_count": diffusion_batch_generate_sustained.get("round_count"),
            "batch_count": diffusion_batch_generate_sustained.get("batch_count"),
            "successful_generation_count": diffusion_batch_generate_sustained.get("successful_generation_count"),
            "expected_total_batch_items": diffusion_batch_generate_sustained.get("expected_total_batch_items"),
            "actual_total_batch_items": diffusion_batch_generate_sustained.get("actual_total_batch_items"),
            "generation_statuses": generation_statuses,
            "generation_batch_counts": generation_batch_counts,
            "generation_executed_step_counts": diffusion_batch_generate_sustained.get("generation_executed_step_counts"),
            "generation_forward_batch_counts_by_round": generation_forward_batch_counts_by_round,
            "total_forward_call_count": diffusion_batch_generate_sustained.get("total_forward_call_count"),
            "max_bpu_loading": diffusion_batch_generate_sustained.get("max_bpu_loading"),
            "avg_bpu_loading": diffusion_batch_generate_sustained.get("avg_bpu_loading"),
            "nonzero_bpu_loading_sample_count": diffusion_batch_generate_sustained.get("nonzero_bpu_loading_sample_count"),
        },
    )

systemd_telemetry_path, systemd_telemetry = latest_json("dream7b_bpu_batch_queue_systemd_telemetry_*/systemd_telemetry_probe.json")
if systemd_telemetry is None:
    add_check("systemd_telemetry", systemd_telemetry_path, False, {"reason": "missing systemd_telemetry_probe.json"})
else:
    ok = (
        systemd_telemetry.get("verdict") == "ok_dream7b_bpu_batch_queue_systemd_telemetry_probe"
        and int(systemd_telemetry.get("processed_request_count") or 0) >= min_systemd_telemetry_requests
        and systemd_telemetry.get("failed_job_count") == 0
        and systemd_telemetry.get("deferred_request_count") == 0
        and all(item == 16 for item in (systemd_telemetry.get("batch_counts") or []))
        and float(systemd_telemetry.get("max_bpu_loading") or 0.0) > 0.0
        and int(systemd_telemetry.get("nonzero_bpu_loading_sample_count") or 0) > 0
        and not systemd_telemetry.get("errors")
    )
    add_check(
        "systemd_telemetry",
        systemd_telemetry_path,
        ok,
        {
            "verdict": systemd_telemetry.get("verdict"),
            "processed_request_count": systemd_telemetry.get("processed_request_count"),
            "batch_counts": systemd_telemetry.get("batch_counts"),
            "max_bpu_loading": systemd_telemetry.get("max_bpu_loading"),
            "avg_bpu_loading": systemd_telemetry.get("avg_bpu_loading"),
        },
    )

long_repeat_path, long_repeat = latest_json("dream7b_bpu_fine_forward_long_repeat_*/long_repeat_probe.json")
if long_repeat is None:
    add_check("long_repeat", long_repeat_path, False, {"reason": "missing long_repeat_probe.json"})
else:
    results = long_repeat.get("results") or []
    wall_spread_ratio = float(long_repeat.get("wall_spread_ratio") or 0.0)
    report_max_wall_spread_ratio = float(long_repeat.get("max_wall_spread_ratio") or 0.0)
    ok = (
        long_repeat.get("verdict") == "ok_dream7b_bpu_fine_forward_long_repeat_probe"
        and int(long_repeat.get("repeat_count") or 0) >= min_long_repeat_count
        and long_repeat.get("repeat_status") == 0
        and long_repeat.get("failure_count") == 0
        and report_max_wall_spread_ratio > 0.0
        and report_max_wall_spread_ratio <= max_long_repeat_wall_spread_ratio
        and wall_spread_ratio <= max_long_repeat_wall_spread_ratio
        and all(item.get("execution_mode") == "pair_in_process" for item in results)
        and all(item.get("window_execution_mode") == "in-process" for item in results)
        and all(item.get("child_process_count") == 0 for item in results)
        and all(item.get("segment_count") == 10 for item in results)
        and all(item.get("final_shape") == [1, 16, 152064] for item in results)
        and not long_repeat.get("errors")
    )
    add_check(
        "long_repeat",
        long_repeat_path,
        ok,
        {
            "verdict": long_repeat.get("verdict"),
            "repeat_count": long_repeat.get("repeat_count"),
            "failure_count": long_repeat.get("failure_count"),
            "median_wall_ms": long_repeat.get("median_wall_ms"),
            "wall_spread_ratio": long_repeat.get("wall_spread_ratio"),
            "max_wall_spread_ratio": long_repeat.get("max_wall_spread_ratio"),
        },
    )

retention_path, retention = latest_json("dream7b_bpu_batch_queue_retention_*/queue_retention_probe.json")
if retention is None:
    add_check("queue_retention", retention_path, False, {"reason": "missing queue_retention_probe.json"})
else:
    ok = (
        retention.get("verdict") == "ok_dream7b_bpu_batch_queue_retention_probe"
        and retention.get("policy_mode") == "report_only"
        and retention.get("pending_stale_count") == 0
        and retention.get("processing_stale_count") == 0
        and (retention.get("archive_plan") or {}).get("apply_supported") is False
        and not retention.get("errors")
    )
    add_check(
        "queue_retention",
        retention_path,
        ok,
        {
            "verdict": retention.get("verdict"),
            "policy_mode": retention.get("policy_mode"),
            "queue_counts": retention.get("queue_counts"),
            "pending_stale_count": retention.get("pending_stale_count"),
            "processing_stale_count": retention.get("processing_stale_count"),
            "apply_supported": (retention.get("archive_plan") or {}).get("apply_supported"),
        },
    )

utilization_gap_path, utilization_gap = latest_json("dream7b_bpu_utilization_gap_*/utilization_gap_probe.json")
if utilization_gap is None:
    add_check("utilization_gap", utilization_gap_path, False, {"reason": "missing utilization_gap_probe.json"})
else:
    runtime_telemetry = utilization_gap.get("runtime_telemetry") or {}
    systemd_telemetry = utilization_gap.get("systemd_telemetry") or {}
    selected_pair_candidate_service_telemetry = utilization_gap.get("selected_pair_candidate_service_telemetry") or {}
    selected_pair_candidate_service_telemetry_comparison = selected_pair_candidate_service_telemetry.get("comparison_to_default_systemd_telemetry") or {}
    selected_pair_cross_job_reuse = utilization_gap.get("selected_pair_cross_job_reuse") or {}
    selected_pair_cross_job_comparison = selected_pair_cross_job_reuse.get("comparison_to_selected_pair_candidate_service") or {}
    sustained_generation = utilization_gap.get("sustained_generation") or {}
    batch_generate_telemetry = utilization_gap.get("batch_generate_telemetry") or {}
    ok = (
        utilization_gap.get("verdict") == "ok_dream7b_bpu_utilization_gap_probe"
        and int(utilization_gap.get("min_batch_count") or 0) >= min_batch_capacity
        and int(utilization_gap.get("min_sustained_round_count") or 0) >= min_batch_generate_sustained_round_count
        and int(utilization_gap.get("min_sustained_total_items") or 0) >= min_systemd_telemetry_requests
        and runtime_telemetry.get("batch_count") == min_batch_capacity
        and int(systemd_telemetry.get("processed_request_count") or 0) >= min_systemd_telemetry_requests
        and selected_pair_candidate_service_telemetry.get("service_name") == "dream7b-bpu-selected-pair-candidate.service"
        and int(selected_pair_candidate_service_telemetry.get("processed_request_count") or 0) >= min_systemd_telemetry_requests
        and selected_pair_candidate_service_telemetry.get("batch_counts") == [16, 16, 16]
        and selected_pair_candidate_service_telemetry.get("expected_window_execution_mode") == "selected-pair-resident"
        and selected_pair_candidate_service_telemetry.get("expected_child_process_count") == 2
        and selected_pair_candidate_service_telemetry_comparison.get("candidate_wall_time_improved_vs_default_systemd") is True
        and int(selected_pair_cross_job_reuse.get("job_count") or 0) >= min_batch_generate_sustained_round_count
        and int(selected_pair_cross_job_reuse.get("batch_count") or 0) >= min_batch_capacity
        and int(selected_pair_cross_job_reuse.get("processed_forward_count") or 0) >= min_systemd_telemetry_requests
        and selected_pair_cross_job_reuse.get("selected_pair") == [1, 8]
        and selected_pair_cross_job_reuse.get("selected_segments") == ["seg02_04", "seg24_26"]
        and selected_pair_cross_job_reuse.get("selected_pair_covers_all_segments") is True
        and selected_pair_cross_job_comparison.get("cross_job_load_time_improved") is True
        and selected_pair_cross_job_comparison.get("cross_job_wall_time_improved") is False
        and int(sustained_generation.get("round_count") or 0) >= min_batch_generate_sustained_round_count
        and int(sustained_generation.get("batch_count") or 0) >= min_batch_capacity
        and int(sustained_generation.get("actual_total_batch_items") or 0) >= min_systemd_telemetry_requests
        and int(batch_generate_telemetry.get("batch_count") or 0) >= min_batch_capacity
        and float(utilization_gap.get("max_observed_bpu_loading") or 0.0) > 0.0
        and not utilization_gap.get("errors")
    )
    add_check(
        "utilization_gap",
        utilization_gap_path,
        ok,
        {
            "verdict": utilization_gap.get("verdict"),
            "diagnosis": utilization_gap.get("diagnosis"),
            "next_optimization_target": utilization_gap.get("next_optimization_target"),
            "max_observed_bpu_loading": utilization_gap.get("max_observed_bpu_loading"),
            "avg_observed_bpu_loading_across_reports": utilization_gap.get("avg_observed_bpu_loading_across_reports"),
            "runtime_batch_count": runtime_telemetry.get("batch_count"),
            "runtime_load_to_run_ratio": runtime_telemetry.get("load_to_run_ratio"),
            "systemd_processed_request_count": systemd_telemetry.get("processed_request_count"),
            "systemd_load_to_run_ratio": systemd_telemetry.get("load_to_run_ratio"),
            "selected_pair_candidate_service_processed_request_count": selected_pair_candidate_service_telemetry.get("processed_request_count"),
            "selected_pair_candidate_service_load_to_run_ratio": selected_pair_candidate_service_telemetry.get("load_to_run_ratio"),
            "selected_pair_candidate_service_wall_delta_ratio_vs_default_systemd": selected_pair_candidate_service_telemetry_comparison.get("wall_ms_delta_ratio_vs_default_systemd"),
            "selected_pair_candidate_service_avg_bpu_loading_delta_vs_default_systemd": selected_pair_candidate_service_telemetry_comparison.get("avg_bpu_loading_delta_vs_default_systemd"),
            "selected_pair_candidate_service_wall_time_improved_vs_default_systemd": selected_pair_candidate_service_telemetry_comparison.get("candidate_wall_time_improved_vs_default_systemd"),
            "selected_pair_candidate_service_avg_bpu_loading_not_worse_than_default_systemd": selected_pair_candidate_service_telemetry_comparison.get("candidate_avg_bpu_loading_not_worse_than_default_systemd"),
            "selected_pair_cross_job_processed_forward_count": selected_pair_cross_job_reuse.get("processed_forward_count"),
            "selected_pair_cross_job_load_to_run_ratio": selected_pair_cross_job_reuse.get("load_to_run_ratio"),
            "selected_pair_cross_job_wall_delta_ratio_vs_candidate_service": selected_pair_cross_job_comparison.get("wall_ms_delta_ratio"),
            "selected_pair_cross_job_load_delta_ratio_vs_candidate_service": selected_pair_cross_job_comparison.get("load_ms_delta_ratio"),
            "selected_pair_cross_job_wall_time_improved": selected_pair_cross_job_comparison.get("cross_job_wall_time_improved"),
            "selected_pair_cross_job_load_time_improved": selected_pair_cross_job_comparison.get("cross_job_load_time_improved"),
            "sustained_round_count": sustained_generation.get("round_count"),
            "sustained_actual_total_batch_items": sustained_generation.get("actual_total_batch_items"),
            "batch_generate_batch_count": batch_generate_telemetry.get("batch_count"),
            "warnings": utilization_gap.get("warnings"),
        },
    )

persistent_pair_cache_path, persistent_pair_cache = latest_json("dream7b_bpu_persistent_pair_cache_*/persistent_pair_cache_probe.json")
if persistent_pair_cache is None:
    add_check("persistent_pair_cache", persistent_pair_cache_path, False, {"reason": "missing persistent_pair_cache_probe.json"})
else:
    ok = (
        persistent_pair_cache.get("verdict") == "ok_dream7b_bpu_persistent_pair_cache_probe"
        and int(persistent_pair_cache.get("pair_worker_count") or 0) == 5
        and int(persistent_pair_cache.get("launched_pair_worker_count") or 0) >= 1
        and int(persistent_pair_cache.get("ready_pair_worker_count") or 0) >= 1
        and "all_pair_workers_ready" in persistent_pair_cache
        and persistent_pair_cache.get("next_optimization_target")
        and not persistent_pair_cache.get("errors")
    )
    add_check(
        "persistent_pair_cache",
        persistent_pair_cache_path,
        ok,
        {
            "verdict": persistent_pair_cache.get("verdict"),
            "pair_worker_count": persistent_pair_cache.get("pair_worker_count"),
            "launched_pair_worker_count": persistent_pair_cache.get("launched_pair_worker_count"),
            "ready_pair_worker_count": persistent_pair_cache.get("ready_pair_worker_count"),
            "failed_pair_worker_count": persistent_pair_cache.get("failed_pair_worker_count"),
            "ready_pair_indexes": persistent_pair_cache.get("ready_pair_indexes"),
            "failed_pair_indexes": persistent_pair_cache.get("failed_pair_indexes"),
            "launch_stopped_reason": persistent_pair_cache.get("launch_stopped_reason"),
            "all_pair_workers_ready": persistent_pair_cache.get("all_pair_workers_ready"),
            "next_optimization_target": persistent_pair_cache.get("next_optimization_target"),
        },
    )

held_pair_matrix_path, held_pair_matrix = latest_json("dream7b_bpu_held_pair_residency_matrix_*/held_pair_residency_matrix_probe.json")
if held_pair_matrix is None:
    add_check("held_pair_residency_matrix", held_pair_matrix_path, False, {"reason": "missing held_pair_residency_matrix_probe.json"})
else:
    ok = (
        held_pair_matrix.get("verdict") == "ok_dream7b_bpu_held_pair_residency_matrix_probe"
        and int(held_pair_matrix.get("pair_worker_count") or 0) == 5
        and int(held_pair_matrix.get("ready_holder_pair_count") or 0) == 5
        and int(held_pair_matrix.get("matrix_entry_count") or 0) == 20
        and int(held_pair_matrix.get("failed_pair_edge_count") or 0) == 20
        and int(held_pair_matrix.get("max_resident_pair_count_observed") or 0) == 1
        and held_pair_matrix.get("next_optimization_target")
        and not held_pair_matrix.get("errors")
    )
    add_check(
        "held_pair_residency_matrix",
        held_pair_matrix_path,
        ok,
        {
            "verdict": held_pair_matrix.get("verdict"),
            "pair_worker_count": held_pair_matrix.get("pair_worker_count"),
            "ready_holder_pair_count": held_pair_matrix.get("ready_holder_pair_count"),
            "ready_holder_pair_indexes": held_pair_matrix.get("ready_holder_pair_indexes"),
            "matrix_entry_count": held_pair_matrix.get("matrix_entry_count"),
            "successful_pair_edge_count": held_pair_matrix.get("successful_pair_edge_count"),
            "failed_pair_edge_count": held_pair_matrix.get("failed_pair_edge_count"),
            "max_resident_pair_count_observed": held_pair_matrix.get("max_resident_pair_count_observed"),
            "next_optimization_target": held_pair_matrix.get("next_optimization_target"),
        },
    )

single_segment_matrix_path, single_segment_matrix = latest_json("dream7b_bpu_single_segment_residency_matrix_*/single_segment_residency_matrix_probe.json")
if single_segment_matrix is None:
    add_check("single_segment_residency_matrix", single_segment_matrix_path, False, {"reason": "missing single_segment_residency_matrix_probe.json"})
else:
    ok = (
        single_segment_matrix.get("verdict") == "ok_dream7b_bpu_single_segment_residency_matrix_probe"
        and int(single_segment_matrix.get("segment_count") or 0) == 10
        and int(single_segment_matrix.get("ready_holder_segment_count") or 0) == 10
        and int(single_segment_matrix.get("matrix_entry_count") or 0) == 90
        and int(single_segment_matrix.get("successful_segment_edge_count") or 0) + int(single_segment_matrix.get("failed_segment_edge_count") or 0) == 90
        and int(single_segment_matrix.get("max_resident_segment_count_observed") or 0) >= 1
        and single_segment_matrix.get("next_optimization_target")
        and not single_segment_matrix.get("errors")
    )
    add_check(
        "single_segment_residency_matrix",
        single_segment_matrix_path,
        ok,
        {
            "verdict": single_segment_matrix.get("verdict"),
            "segment_count": single_segment_matrix.get("segment_count"),
            "ready_holder_segment_count": single_segment_matrix.get("ready_holder_segment_count"),
            "matrix_entry_count": single_segment_matrix.get("matrix_entry_count"),
            "successful_segment_edge_count": single_segment_matrix.get("successful_segment_edge_count"),
            "failed_segment_edge_count": single_segment_matrix.get("failed_segment_edge_count"),
            "max_resident_segment_count_observed": single_segment_matrix.get("max_resident_segment_count_observed"),
            "next_optimization_target": single_segment_matrix.get("next_optimization_target"),
        },
    )

persistent_segment_cache_path, persistent_segment_cache = latest_json("dream7b_bpu_persistent_segment_cache_*/persistent_segment_cache_probe.json")
if persistent_segment_cache is None:
    add_check("persistent_segment_cache", persistent_segment_cache_path, False, {"reason": "missing persistent_segment_cache_probe.json"})
else:
    ok = (
        persistent_segment_cache.get("verdict") == "ok_dream7b_bpu_persistent_segment_cache_probe"
        and int(persistent_segment_cache.get("segment_worker_count") or 0) == 10
        and int(persistent_segment_cache.get("launched_segment_worker_count") or 0) >= 1
        and int(persistent_segment_cache.get("ready_segment_worker_count") or 0) >= 1
        and "all_segment_workers_ready" in persistent_segment_cache
        and int(persistent_segment_cache.get("max_resident_segment_count_observed") or 0) >= 1
        and persistent_segment_cache.get("next_optimization_target")
        and not persistent_segment_cache.get("errors")
    )
    add_check(
        "persistent_segment_cache",
        persistent_segment_cache_path,
        ok,
        {
            "verdict": persistent_segment_cache.get("verdict"),
            "segment_worker_count": persistent_segment_cache.get("segment_worker_count"),
            "launched_segment_worker_count": persistent_segment_cache.get("launched_segment_worker_count"),
            "ready_segment_worker_count": persistent_segment_cache.get("ready_segment_worker_count"),
            "failed_segment_worker_count": persistent_segment_cache.get("failed_segment_worker_count"),
            "ready_segment_indexes": persistent_segment_cache.get("ready_segment_indexes"),
            "failed_segment_indexes": persistent_segment_cache.get("failed_segment_indexes"),
            "all_segment_workers_ready": persistent_segment_cache.get("all_segment_workers_ready"),
            "launch_stopped_reason": persistent_segment_cache.get("launch_stopped_reason"),
            "max_resident_segment_count_observed": persistent_segment_cache.get("max_resident_segment_count_observed"),
            "next_optimization_target": persistent_segment_cache.get("next_optimization_target"),
        },
    )

single_segment_triplet_path, single_segment_triplet = latest_json("dream7b_bpu_single_segment_triplet_residency_*/single_segment_triplet_residency_probe.json")
if single_segment_triplet is None:
    add_check("single_segment_triplet_residency", single_segment_triplet_path, False, {"reason": "missing single_segment_triplet_residency_probe.json"})
else:
    ok = (
        single_segment_triplet.get("verdict") == "ok_dream7b_bpu_single_segment_triplet_residency_probe"
        and int(single_segment_triplet.get("segment_count") or 0) == 10
        and int(single_segment_triplet.get("total_triplet_combination_count") or 0) == 120
        and int(single_segment_triplet.get("tested_triplet_combination_count") or 0) == 120
        and int(single_segment_triplet.get("successful_triplet_count") or 0) + int(single_segment_triplet.get("failed_triplet_count") or 0) == 120
        and int(single_segment_triplet.get("successful_triplet_count") or 0) >= 1
        and int(single_segment_triplet.get("max_resident_segment_count_observed") or 0) >= 3
        and single_segment_triplet.get("next_optimization_target")
        and not single_segment_triplet.get("errors")
    )
    add_check(
        "single_segment_triplet_residency",
        single_segment_triplet_path,
        ok,
        {
            "verdict": single_segment_triplet.get("verdict"),
            "segment_count": single_segment_triplet.get("segment_count"),
            "total_triplet_combination_count": single_segment_triplet.get("total_triplet_combination_count"),
            "tested_triplet_combination_count": single_segment_triplet.get("tested_triplet_combination_count"),
            "successful_triplet_count": single_segment_triplet.get("successful_triplet_count"),
            "failed_triplet_count": single_segment_triplet.get("failed_triplet_count"),
            "successful_triplets": single_segment_triplet.get("successful_triplets"),
            "max_resident_segment_count_observed": single_segment_triplet.get("max_resident_segment_count_observed"),
            "next_optimization_target": single_segment_triplet.get("next_optimization_target"),
        },
    )

seeded_quad_path, seeded_quad = latest_json("dream7b_bpu_seeded_quad_residency_*/seeded_quad_residency_probe.json")
if seeded_quad is None:
    add_check("seeded_quad_residency", seeded_quad_path, False, {"reason": "missing seeded_quad_residency_probe.json"})
else:
    ok = (
        seeded_quad.get("verdict") == "ok_dream7b_bpu_seeded_quad_residency_probe"
        and int(seeded_quad.get("segment_count") or 0) == 10
        and int(seeded_quad.get("source_successful_triplet_count") or 0) >= 1
        and int(seeded_quad.get("seeded_quad_candidate_count") or 0) >= 1
        and int(seeded_quad.get("tested_seeded_quad_count") or 0) == int(seeded_quad.get("seeded_quad_candidate_count") or 0)
        and int(seeded_quad.get("successful_seeded_quad_count") or 0) + int(seeded_quad.get("failed_seeded_quad_count") or 0) == int(seeded_quad.get("tested_seeded_quad_count") or 0)
        and int(seeded_quad.get("max_resident_segment_count_observed") or 0) >= 3
        and seeded_quad.get("next_optimization_target")
        and not seeded_quad.get("errors")
    )
    add_check(
        "seeded_quad_residency",
        seeded_quad_path,
        ok,
        {
            "verdict": seeded_quad.get("verdict"),
            "segment_count": seeded_quad.get("segment_count"),
            "source_successful_triplet_count": seeded_quad.get("source_successful_triplet_count"),
            "seeded_quad_candidate_count": seeded_quad.get("seeded_quad_candidate_count"),
            "tested_seeded_quad_count": seeded_quad.get("tested_seeded_quad_count"),
            "successful_seeded_quad_count": seeded_quad.get("successful_seeded_quad_count"),
            "failed_seeded_quad_count": seeded_quad.get("failed_seeded_quad_count"),
            "successful_seeded_quads": seeded_quad.get("successful_seeded_quads"),
            "max_resident_segment_count_observed": seeded_quad.get("max_resident_segment_count_observed"),
            "next_optimization_target": seeded_quad.get("next_optimization_target"),
        },
    )

persistent_triplet_topology_path, persistent_triplet_topology = latest_json("dream7b_bpu_persistent_triplet_topology_*/persistent_triplet_topology_probe.json")
if persistent_triplet_topology is None:
    add_check("persistent_triplet_topology", persistent_triplet_topology_path, False, {"reason": "missing persistent_triplet_topology_probe.json"})
else:
    tested_triplet_topology_count = int(persistent_triplet_topology.get("tested_triplet_topology_count") or 0)
    stable_triplet_topology_count = int(persistent_triplet_topology.get("stable_triplet_topology_count") or 0)
    failed_triplet_topology_count = int(persistent_triplet_topology.get("failed_triplet_topology_count") or 0)
    ok = (
        persistent_triplet_topology.get("verdict") == "ok_dream7b_bpu_persistent_triplet_topology_probe"
        and int(persistent_triplet_topology.get("segment_count") or 0) == 10
        and int(persistent_triplet_topology.get("source_successful_triplet_count") or 0) >= 1
        and tested_triplet_topology_count >= 1
        and stable_triplet_topology_count >= 1
        and stable_triplet_topology_count + failed_triplet_topology_count == tested_triplet_topology_count
        and int(persistent_triplet_topology.get("max_resident_segment_count_observed") or 0) >= 3
        and persistent_triplet_topology.get("selected_topology")
        and persistent_triplet_topology.get("selection_rule")
        and persistent_triplet_topology.get("next_optimization_target")
        and not persistent_triplet_topology.get("errors")
    )
    add_check(
        "persistent_triplet_topology",
        persistent_triplet_topology_path,
        ok,
        {
            "verdict": persistent_triplet_topology.get("verdict"),
            "segment_count": persistent_triplet_topology.get("segment_count"),
            "source_successful_triplet_count": persistent_triplet_topology.get("source_successful_triplet_count"),
            "tested_triplet_topology_count": persistent_triplet_topology.get("tested_triplet_topology_count"),
            "stable_triplet_topology_count": persistent_triplet_topology.get("stable_triplet_topology_count"),
            "failed_triplet_topology_count": persistent_triplet_topology.get("failed_triplet_topology_count"),
            "hold_seconds": persistent_triplet_topology.get("hold_seconds"),
            "stable_triplets": persistent_triplet_topology.get("stable_triplets"),
            "failed_triplets": persistent_triplet_topology.get("failed_triplets"),
            "selected_topology": persistent_triplet_topology.get("selected_topology"),
            "selection_rule": persistent_triplet_topology.get("selection_rule"),
            "max_resident_segment_count_observed": persistent_triplet_topology.get("max_resident_segment_count_observed"),
            "next_optimization_target": persistent_triplet_topology.get("next_optimization_target"),
        },
    )

window3_forward_path, window3_forward = latest_json("dream7b_bpu_window3_forward_feasibility_*/window3_forward_feasibility_probe.json")
if window3_forward is None:
    add_check("window3_forward_feasibility", window3_forward_path, False, {"reason": "missing window3_forward_feasibility_probe.json"})
else:
    ok = (
        window3_forward.get("verdict") == "ok_dream7b_bpu_window3_forward_feasibility_probe"
        and int(window3_forward.get("window_size") or 0) == 3
        and window3_forward.get("child_window_mode") == "pair"
        and window3_forward.get("child_runtime_mode") == "packed"
        and window3_forward.get("window_execution_mode") == "window-batch"
        and window3_forward.get("direct_window3_forward_supported") is False
        and window3_forward.get("expected_window3_failure_observed") is True
        and window3_forward.get("stderr_contains_memory_alloc_failure") is True
        and window3_forward.get("next_optimization_target")
        and not window3_forward.get("errors")
    )
    add_check(
        "window3_forward_feasibility",
        window3_forward_path,
        ok,
        {
            "verdict": window3_forward.get("verdict"),
            "returncode": window3_forward.get("returncode"),
            "direct_window3_forward_supported": window3_forward.get("direct_window3_forward_supported"),
            "expected_window3_failure_observed": window3_forward.get("expected_window3_failure_observed"),
            "stderr_contains_memory_alloc_failure": window3_forward.get("stderr_contains_memory_alloc_failure"),
            "window_size": window3_forward.get("window_size"),
            "child_window_mode": window3_forward.get("child_window_mode"),
            "child_runtime_mode": window3_forward.get("child_runtime_mode"),
            "window_execution_mode": window3_forward.get("window_execution_mode"),
            "next_optimization_target": window3_forward.get("next_optimization_target"),
        },
    )

selected_triplet_forward_path, selected_triplet_forward = latest_json("dream7b_bpu_selected_triplet_forward_path_*/selected_triplet_forward_path_probe.json")
if selected_triplet_forward is None:
    add_check("selected_triplet_forward_path", selected_triplet_forward_path, False, {"reason": "missing selected_triplet_forward_path_probe.json"})
else:
    selected_details = selected_triplet_forward.get("selected") or {}
    comparison_details = selected_triplet_forward.get("comparison") or {}
    ok = (
        selected_triplet_forward.get("verdict") == "ok_dream7b_bpu_selected_triplet_forward_path_probe"
        and selected_triplet_forward.get("selected_triplet_forward_supported") is False
        and selected_triplet_forward.get("reboot_or_disconnect_observed") is True
        and selected_triplet_forward.get("expected_reboot_guard_observed") is True
        and selected_details.get("selected_topology") == [0, 1, 8]
        and selected_details.get("selected_worker_count") == 3
        and comparison_details.get("warm_path_load_improved") is False
        and comparison_details.get("total_path_load_improved") is False
        and selected_triplet_forward.get("next_optimization_target")
        and not selected_triplet_forward.get("errors")
    )
    add_check(
        "selected_triplet_forward_path",
        selected_triplet_forward_path,
        ok,
        {
            "verdict": selected_triplet_forward.get("verdict"),
            "selected_triplet_forward_supported": selected_triplet_forward.get("selected_triplet_forward_supported"),
            "reboot_or_disconnect_observed": selected_triplet_forward.get("reboot_or_disconnect_observed"),
            "expected_reboot_guard_observed": selected_triplet_forward.get("expected_reboot_guard_observed"),
            "source_incomplete_run_dir": selected_triplet_forward.get("source_incomplete_run_dir"),
            "selected_topology": selected_details.get("selected_topology"),
            "selected_worker_count": selected_details.get("selected_worker_count"),
            "warm_path_load_improved": comparison_details.get("warm_path_load_improved"),
            "total_path_load_improved": comparison_details.get("total_path_load_improved"),
            "next_optimization_target": selected_triplet_forward.get("next_optimization_target"),
        },
    )

selected_pair_telemetry_path, selected_pair_telemetry = latest_json("dream7b_bpu_selected_pair_telemetry_*/selected_pair_telemetry_probe.json")
if selected_pair_telemetry is None:
    add_check("selected_pair_telemetry", selected_pair_telemetry_path, False, {"reason": "missing selected_pair_telemetry_probe.json"})
else:
    selected_pair_details = selected_pair_telemetry.get("selected") or {}
    selected_pair_comparison = selected_pair_telemetry.get("comparison_to_default_runtime_telemetry") or {}
    ok = (
        selected_pair_telemetry.get("verdict") == "ok_dream7b_bpu_selected_pair_telemetry_probe"
        and int(selected_pair_telemetry.get("batch_count") or 0) >= min_batch_capacity
        and float(selected_pair_telemetry.get("max_bpu_loading") or 0.0) > 0.0
        and float(selected_pair_telemetry.get("avg_bpu_loading") or 0.0) > 0.0
        and selected_pair_details.get("selected_pair") == [1, 8]
        and selected_pair_details.get("selected_pair_covers_all_segments") is True
        and selected_pair_details.get("final_shapes") == [[1, 16, 152064] for _ in range(int(selected_pair_telemetry.get("batch_count") or 0))]
        and selected_pair_comparison.get("selected_wall_time_improved_vs_default_runtime") is True
        and selected_pair_comparison.get("wall_ms_delta_ratio_vs_default_runtime") is not None
        and selected_pair_telemetry.get("next_optimization_target")
        and not selected_pair_telemetry.get("errors")
    )
    add_check(
        "selected_pair_telemetry",
        selected_pair_telemetry_path,
        ok,
        {
            "verdict": selected_pair_telemetry.get("verdict"),
            "batch_count": selected_pair_telemetry.get("batch_count"),
            "selected_pair": selected_pair_details.get("selected_pair"),
            "selected_segments": selected_pair_details.get("selected_segments"),
            "selected_pair_covers_all_segments": selected_pair_details.get("selected_pair_covers_all_segments"),
            "selected_wall_ms": selected_pair_details.get("wall_ms"),
            "selected_forward_load_ms": selected_pair_details.get("forward_load_ms"),
            "selected_run_ms": selected_pair_details.get("run_ms"),
            "max_bpu_loading": selected_pair_telemetry.get("max_bpu_loading"),
            "avg_bpu_loading": selected_pair_telemetry.get("avg_bpu_loading"),
            "wall_ms_delta_vs_default_runtime": selected_pair_comparison.get("wall_ms_delta_vs_default_runtime"),
            "wall_ms_delta_ratio_vs_default_runtime": selected_pair_comparison.get("wall_ms_delta_ratio_vs_default_runtime"),
            "avg_bpu_loading_delta_vs_default_runtime": selected_pair_comparison.get("avg_bpu_loading_delta_vs_default_runtime"),
            "selected_wall_time_improved_vs_default_runtime": selected_pair_comparison.get("selected_wall_time_improved_vs_default_runtime"),
            "selected_avg_bpu_loading_improved_vs_default_runtime": selected_pair_comparison.get("selected_avg_bpu_loading_improved_vs_default_runtime"),
            "next_optimization_target": selected_pair_telemetry.get("next_optimization_target"),
        },
    )

selected_pair_candidate_service_path, selected_pair_candidate_service = latest_json("dream7b_bpu_selected_pair_candidate_service_*/selected_pair_candidate_service_probe.json")
if selected_pair_candidate_service is None:
    add_check("selected_pair_candidate_service", selected_pair_candidate_service_path, False, {"reason": "missing selected_pair_candidate_service_probe.json"})
else:
    ok = (
        selected_pair_candidate_service.get("verdict") == "ok_dream7b_bpu_selected_pair_candidate_service_probe"
        and selected_pair_candidate_service.get("service_name") == "dream7b-bpu-selected-pair-candidate.service"
        and selected_pair_candidate_service.get("service_status_before") == "active"
        and selected_pair_candidate_service.get("service_enabled_before") == "enabled"
        and selected_pair_candidate_service.get("service_status_after") == "active"
        and selected_pair_candidate_service.get("service_enabled_after") == "enabled"
        and selected_pair_candidate_service.get("job_status") == "done"
        and selected_pair_candidate_service.get("forward_command") == "dream7b-bpu-selected-pair-batch-forward"
        and selected_pair_candidate_service.get("request_count") == min_batch_capacity
        and selected_pair_candidate_service.get("processed_count") == min_batch_capacity
        and selected_pair_candidate_service.get("accepted_count") == min_batch_capacity
        and selected_pair_candidate_service.get("deferred_count") == 0
        and selected_pair_candidate_service.get("skipped_count") == 0
        and selected_pair_candidate_service.get("max_batch_size") == 16
        and selected_pair_candidate_service.get("batch_run_count") == 1
        and selected_pair_candidate_service.get("batch_count") == min_batch_capacity
        and selected_pair_candidate_service.get("result_count") == min_batch_capacity
        and selected_pair_candidate_service.get("execution_mode") == "pair_window_batch"
        and selected_pair_candidate_service.get("window_execution_mode") == "selected-pair-resident"
        and selected_pair_candidate_service.get("child_process_count") == 2
        and selected_pair_candidate_service.get("bpu_lock_path") == "/run/lock/dream7b_bpu_batch_queue_runner.lock"
        and selected_pair_candidate_service.get("selected_pair_candidate") is True
        and selected_pair_candidate_service.get("selected_pair") == [1, 8]
        and selected_pair_candidate_service.get("selected_segments") == ["seg02_04", "seg24_26"]
        and selected_pair_candidate_service.get("selected_pair_covers_all_segments") is True
        and selected_pair_candidate_service.get("default_service_replaced") is False
        and all(item == [1, 16, 152064] for item in (selected_pair_candidate_service.get("final_shapes") or []))
        and not selected_pair_candidate_service.get("errors")
    )
    add_check(
        "selected_pair_candidate_service",
        selected_pair_candidate_service_path,
        ok,
        {
            "verdict": selected_pair_candidate_service.get("verdict"),
            "service_name": selected_pair_candidate_service.get("service_name"),
            "job_status": selected_pair_candidate_service.get("job_status"),
            "forward_command": selected_pair_candidate_service.get("forward_command"),
            "request_count": selected_pair_candidate_service.get("request_count"),
            "processed_count": selected_pair_candidate_service.get("processed_count"),
            "batch_count": selected_pair_candidate_service.get("batch_count"),
            "execution_mode": selected_pair_candidate_service.get("execution_mode"),
            "window_execution_mode": selected_pair_candidate_service.get("window_execution_mode"),
            "child_process_count": selected_pair_candidate_service.get("child_process_count"),
            "selected_pair_candidate": selected_pair_candidate_service.get("selected_pair_candidate"),
            "selected_pair": selected_pair_candidate_service.get("selected_pair"),
            "selected_segments": selected_pair_candidate_service.get("selected_segments"),
            "default_service_replaced": selected_pair_candidate_service.get("default_service_replaced"),
            "amortized_wall_ms_per_processed_request": selected_pair_candidate_service.get("amortized_wall_ms_per_processed_request"),
            "next_optimization_target": selected_pair_candidate_service.get("next_optimization_target"),
        },
    )

selected_pair_candidate_service_telemetry_path, selected_pair_candidate_service_telemetry = latest_json("dream7b_bpu_selected_pair_candidate_service_telemetry_*/systemd_telemetry_probe.json")
if selected_pair_candidate_service_telemetry is None:
    add_check("selected_pair_candidate_service_telemetry", selected_pair_candidate_service_telemetry_path, False, {"reason": "missing selected_pair_candidate_service_telemetry systemd_telemetry_probe.json"})
else:
    comparison = selected_pair_candidate_service_telemetry.get("comparison_to_default_systemd_telemetry") or {}
    ok = (
        selected_pair_candidate_service_telemetry.get("verdict") == "ok_dream7b_bpu_batch_queue_systemd_telemetry_probe"
        and selected_pair_candidate_service_telemetry.get("service_name") == "dream7b-bpu-selected-pair-candidate.service"
        and selected_pair_candidate_service_telemetry.get("service_status_before") == "active"
        and selected_pair_candidate_service_telemetry.get("service_enabled_before") == "enabled"
        and selected_pair_candidate_service_telemetry.get("service_status_after") == "active"
        and selected_pair_candidate_service_telemetry.get("service_enabled_after") == "enabled"
        and selected_pair_candidate_service_telemetry.get("expected_forward_command") == "dream7b-bpu-selected-pair-batch-forward"
        and selected_pair_candidate_service_telemetry.get("expected_window_execution_mode") == "selected-pair-resident"
        and selected_pair_candidate_service_telemetry.get("expected_child_process_count") == 2
        and selected_pair_candidate_service_telemetry.get("job_count") == 3
        and selected_pair_candidate_service_telemetry.get("request_count") == min_batch_capacity
        and selected_pair_candidate_service_telemetry.get("processed_request_count") == 48
        and selected_pair_candidate_service_telemetry.get("accepted_request_count") == 48
        and selected_pair_candidate_service_telemetry.get("deferred_request_count") == 0
        and selected_pair_candidate_service_telemetry.get("result_count") == 48
        and selected_pair_candidate_service_telemetry.get("batch_counts") == [16, 16, 16]
        and selected_pair_candidate_service_telemetry.get("max_bpu_loading", 0) > 0
        and selected_pair_candidate_service_telemetry.get("nonzero_bpu_loading_sample_count", 0) > 0
        and comparison.get("candidate_wall_time_improved_vs_default_systemd") is True
        and comparison.get("default_systemd_telemetry_path")
        and not selected_pair_candidate_service_telemetry.get("errors")
    )
    add_check(
        "selected_pair_candidate_service_telemetry",
        selected_pair_candidate_service_telemetry_path,
        ok,
        {
            "verdict": selected_pair_candidate_service_telemetry.get("verdict"),
            "service_name": selected_pair_candidate_service_telemetry.get("service_name"),
            "processed_request_count": selected_pair_candidate_service_telemetry.get("processed_request_count"),
            "batch_counts": selected_pair_candidate_service_telemetry.get("batch_counts"),
            "amortized_wall_ms_per_processed_request": selected_pair_candidate_service_telemetry.get("amortized_wall_ms_per_processed_request"),
            "avg_bpu_loading": selected_pair_candidate_service_telemetry.get("avg_bpu_loading"),
            "max_bpu_loading": selected_pair_candidate_service_telemetry.get("max_bpu_loading"),
            "comparison_to_default_systemd_telemetry": comparison,
        },
    )

selected_pair_cross_job_reuse_path, selected_pair_cross_job_reuse = latest_json("dream7b_bpu_selected_pair_cross_job_reuse_*/selected_pair_cross_job_reuse_probe.json")
if selected_pair_cross_job_reuse is None:
    add_check("selected_pair_cross_job_reuse", selected_pair_cross_job_reuse_path, False, {"reason": "missing selected_pair_cross_job_reuse_probe.json"})
else:
    comparison = selected_pair_cross_job_reuse.get("comparison_to_selected_pair_candidate_service") or {}
    cross_job_metrics = selected_pair_cross_job_reuse.get("cross_job_metrics") or {}
    candidate_metrics = selected_pair_cross_job_reuse.get("candidate_service_metrics") or {}
    ok = (
        selected_pair_cross_job_reuse.get("verdict") == "ok_dream7b_bpu_selected_pair_cross_job_reuse_probe"
        and selected_pair_cross_job_reuse.get("job_count") == 3
        and selected_pair_cross_job_reuse.get("batch_count") == min_batch_capacity
        and selected_pair_cross_job_reuse.get("processed_forward_count") == min_systemd_telemetry_requests
        and selected_pair_cross_job_reuse.get("selected_pair") == [1, 8]
        and selected_pair_cross_job_reuse.get("selected_segments") == ["seg02_04", "seg24_26"]
        and selected_pair_cross_job_reuse.get("selected_pair_covers_all_segments") is True
        and selected_pair_cross_job_reuse.get("selected_worker_count") == 2
        and candidate_metrics.get("processed_request_count") == min_systemd_telemetry_requests
        and candidate_metrics.get("batch_counts") == [16, 16, 16]
        and comparison.get("cross_job_reuses_selected_pair_workers_once") is True
        and comparison.get("candidate_service_reloads_selected_pair_per_batch") is True
        and comparison.get("cross_job_load_time_improved") is True
        and comparison.get("cross_job_wall_time_improved") is False
        and cross_job_metrics.get("amortized_wall_ms_per_forward") is not None
        and cross_job_metrics.get("amortized_total_load_ms_per_forward") is not None
        and not selected_pair_cross_job_reuse.get("errors")
    )
    add_check(
        "selected_pair_cross_job_reuse",
        selected_pair_cross_job_reuse_path,
        ok,
        {
            "verdict": selected_pair_cross_job_reuse.get("verdict"),
            "job_count": selected_pair_cross_job_reuse.get("job_count"),
            "batch_count": selected_pair_cross_job_reuse.get("batch_count"),
            "processed_forward_count": selected_pair_cross_job_reuse.get("processed_forward_count"),
            "selected_pair": selected_pair_cross_job_reuse.get("selected_pair"),
            "selected_segments": selected_pair_cross_job_reuse.get("selected_segments"),
            "resident_load_once_amortized_ms_per_forward": selected_pair_cross_job_reuse.get("resident_load_once_amortized_ms_per_forward"),
            "cross_job_amortized_wall_ms_per_forward": cross_job_metrics.get("amortized_wall_ms_per_forward"),
            "cross_job_amortized_total_load_ms_per_forward": cross_job_metrics.get("amortized_total_load_ms_per_forward"),
            "candidate_amortized_wall_ms_per_processed_request": candidate_metrics.get("amortized_wall_ms_per_processed_request"),
            "candidate_amortized_load_ms_per_processed_request": candidate_metrics.get("amortized_load_ms_per_processed_request"),
            "wall_ms_delta_ratio": comparison.get("wall_ms_delta_ratio"),
            "load_ms_delta_ratio": comparison.get("load_ms_delta_ratio"),
            "cross_job_wall_time_improved": comparison.get("cross_job_wall_time_improved"),
            "cross_job_load_time_improved": comparison.get("cross_job_load_time_improved"),
            "next_optimization_target": selected_pair_cross_job_reuse.get("next_optimization_target"),
        },
    )

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_deployment_acceptance_probe" if not errors else "failed_dream7b_bpu_deployment_acceptance_probe",
    "report_root": str(report_root),
    "run_dir": str(run_dir),
    "min_batch_capacity": min_batch_capacity,
    "min_systemd_batch_requests": min_systemd_batch_requests,
    "min_systemd_telemetry_requests": min_systemd_telemetry_requests,
    "min_batch_generate_count": min_batch_generate_count,
    "min_batch_generate_sustained_round_count": min_batch_generate_sustained_round_count,
    "min_long_repeat_count": min_long_repeat_count,
    "max_long_repeat_wall_spread_ratio": max_long_repeat_wall_spread_ratio,
    "check_count": len(checks),
    "passed_check_count": sum(1 for item in checks if item["ok"]),
    "checks": checks,
    "warnings": warnings,
    "errors": errors,
}
(run_dir / "deployment_acceptance_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
check_lines = [
    f"| {item['name']} | {item['ok']} | {item['path']} | `{json.dumps(item['details'], ensure_ascii=False)}` |"
    for item in checks
]
warning_lines = [f"- {item}" for item in warnings] if warnings else ["- none"]
error_lines = [f"- {item}" for item in errors] if errors else ["- none"]
(run_dir / "deployment_acceptance_probe.md").write_text(
    "\n".join([
        "# Dream 7B BPU Deployment Acceptance Probe",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- report_root: {payload['report_root']}",
        f"- run_dir: {payload['run_dir']}",
        f"- check_count: {payload['check_count']}",
        f"- passed_check_count: {payload['passed_check_count']}",
        f"- min_batch_capacity: {payload['min_batch_capacity']}",
        f"- min_systemd_batch_requests: {payload['min_systemd_batch_requests']}",
        f"- min_systemd_telemetry_requests: {payload['min_systemd_telemetry_requests']}",
        f"- min_batch_generate_count: {payload['min_batch_generate_count']}",
        f"- min_batch_generate_sustained_round_count: {payload['min_batch_generate_sustained_round_count']}",
        f"- min_long_repeat_count: {payload['min_long_repeat_count']}",
        f"- max_long_repeat_wall_spread_ratio: {payload['max_long_repeat_wall_spread_ratio']}",
        "",
        "## Checks",
        "",
        "| name | ok | path | details |",
        "| --- | --- | --- | --- |",
        *check_lines,
        "",
        "## Warnings",
        "",
        *warning_lines,
        "",
        "## Errors",
        "",
        *error_lines,
        "",
    ]) + "\n",
    encoding="utf-8",
)
print(run_dir / "deployment_acceptance_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
