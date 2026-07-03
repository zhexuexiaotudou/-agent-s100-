#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
import subprocess
from datetime import datetime
from pathlib import Path


def latest(pattern: str) -> tuple[Path | None, dict]:
    paths = [Path(item) for item in glob.glob(pattern)]
    if not paths:
        return None, {}
    paths.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    path = paths[0]
    return path, json.loads(path.read_text(encoding="utf-8"))


def run(*args: str) -> str:
    proc = subprocess.run(args, text=True, capture_output=True)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report_root", nargs="?", default="/mnt/nas/openclaw/reports/models")
    parser.add_argument("--personal-report-root", default="/mnt/nas/openclaw/reports/personal-data-sort")
    args = parser.parse_args()

    root = Path(args.report_root)
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = root / f"dream7b_default_promotion_acceptance_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    promotion_path, promotion = latest(str(root / "dream7b_bpu_segment_major_default_promotion_*" / "segment_major_default_promotion_probe.json"))
    soak_path, soak = latest(str(root / "dream7b_bpu_segment_major_candidate_soak_*" / "segment_major_candidate_soak_probe.json"))
    personal_path, personal = latest(str(Path(args.personal_report_root) / "personal_data_sort_*" / "personal_data_sort.json"))
    health_path = root / "dream7b_default_health" / "latest_status.json"
    health = json.loads(health_path.read_text(encoding="utf-8")) if health_path.is_file() else {}

    exec_start = run("systemctl", "show", "dream7b-bpu-batch-queue.service", "-p", "ExecStart", "--value")
    active = run("systemctl", "is-active", "dream7b-bpu-batch-queue.service")
    enabled = run("systemctl", "is-enabled", "dream7b-bpu-batch-queue.service")

    errors: list[str] = []
    checks = {
        "promotion_ok": promotion.get("verdict") == "ok_dream7b_bpu_segment_major_default_promotion_probe",
        "default_service_replaced": promotion.get("default_service_replaced") is True,
        "rollback_verified": promotion.get("rollback_verified") is True,
        "default_service_active": active == "active",
        "default_service_enabled": enabled == "enabled",
        "execstart_segment_major_24x256": "dream7b_bpu_segment_major_load_once_queue_runner.py" in exec_start
        and "--max-batch-size 256" in exec_start,
        "post_promotion_soak_ok": soak.get("verdict") == "ok_dream7b_bpu_segment_major_candidate_soak_probe",
        "post_promotion_soak_30min": int(soak.get("elapsed_sec") or 0) >= 1800,
        "post_promotion_soak_two_iterations": int(soak.get("iteration_count") or 0) >= 2,
        "post_promotion_avg_bpu_ge_90": float(soak.get("avg_bpu_loading") or 0.0) >= 90.0,
        "post_promotion_failed_jobs_zero": int(soak.get("failed_job_count") or 0) == 0,
        "openclaw_copy_sort_ok": personal.get("verdict") == "ok_personal_data_sort_probe",
        "openclaw_copy_sort_20_files": int(personal.get("copy_count") or 0) == 20,
        "openclaw_copy_sort_non_destructive": personal.get("delete_or_move_performed") is False
        and personal.get("upload_performed") is True,
        "health_snapshot_present": health_path.is_file(),
        "health_segment_major_default": health.get("segment_major_default") is True,
    }
    for name, passed in checks.items():
        if not passed:
            errors.append(name)

    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_default_promotion_acceptance_probe" if not errors else "failed_dream7b_default_promotion_acceptance_probe",
        "decision": "dream7b_24x256_segment_major_default_accepted" if not errors else "dream7b_24x256_segment_major_default_blocked",
        "run_dir": str(run_dir),
        "promotion_json": str(promotion_path) if promotion_path else "",
        "post_promotion_soak_json": str(soak_path) if soak_path else "",
        "personal_sort_json": str(personal_path) if personal_path else "",
        "health_status_json": str(health_path) if health_path.is_file() else "",
        "active": active,
        "enabled": enabled,
        "avg_bpu_loading": soak.get("avg_bpu_loading"),
        "failed_job_count": soak.get("failed_job_count"),
        "elapsed_sec": soak.get("elapsed_sec"),
        "iteration_count": soak.get("iteration_count"),
        "load_to_run_ratio": soak.get("avg_load_to_run_ratio"),
        "copy_count": personal.get("copy_count"),
        "checks": checks,
        "errors": errors,
    }

    json_path = run_dir / "default_promotion_acceptance_probe.json"
    md_path = run_dir / "default_promotion_acceptance_probe.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Dream 7B Default Promotion Acceptance",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- decision: {payload['decision']}",
        f"- avg_bpu_loading: {payload['avg_bpu_loading']}",
        f"- failed_job_count: {payload['failed_job_count']}",
        f"- elapsed_sec: {payload['elapsed_sec']}",
        f"- iteration_count: {payload['iteration_count']}",
        f"- personal_copy_count: {payload['copy_count']}",
        f"- promotion_json: {payload['promotion_json']}",
        f"- post_promotion_soak_json: {payload['post_promotion_soak_json']}",
        f"- personal_sort_json: {payload['personal_sort_json']}",
        "",
        "## Errors",
        "",
    ]
    lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(md_path)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
