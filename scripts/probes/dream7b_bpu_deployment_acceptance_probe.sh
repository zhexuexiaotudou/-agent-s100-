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
