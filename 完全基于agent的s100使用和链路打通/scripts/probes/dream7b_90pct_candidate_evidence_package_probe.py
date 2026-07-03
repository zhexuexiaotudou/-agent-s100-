#!/usr/bin/env python3
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


APPROVED_REPORT_PREFIXES = (
    "/tmp/",
    "/mnt/nas/openclaw/reports",
    "/mnt/nas/openclaw/reports/",
    "/root/.openclaw/workspace/reports",
    "/root/.openclaw/workspace/reports/",
)


def is_approved(path: Path) -> bool:
    text = str(path)
    return any(text == prefix.rstrip("/") or text.startswith(prefix) for prefix in APPROVED_REPORT_PREFIXES)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def copy_artifact(src: Path, dst_dir: Path) -> str:
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    shutil.copy2(src, dst)
    return str(dst)


def metric(payload: dict, key: str):
    return payload.get(key, "")


def service_active(service_name: str) -> bool:
    result = subprocess.run(
        ["systemctl", "is-active", "--quiet", service_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def main() -> int:
    report_root = Path(sys.argv[1] if len(sys.argv) > 1 else "/mnt/nas/openclaw/reports/models")
    consistency_dir = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/project_docs_consistency_dream7b_90pct_default_candidate")
    repo_root = Path(sys.argv[3] if len(sys.argv) > 3 else ".").resolve()
    if not is_approved(report_root):
        raise ValueError(f"Refusing report root outside approved report directories: {report_root}")

    stamp = sys.argv[4] if len(sys.argv) > 4 else ""
    if not stamp:
        stamp = __import__("os").environ.get("DREAM7B_90PCT_EVIDENCE_PACKAGE_STAMP", "")
    if not stamp:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = report_root / f"dream7b_90pct_candidate_evidence_package_{stamp}"
    artifacts_dir = run_dir / "artifacts"
    run_dir.mkdir(parents=True, exist_ok=True)

    evidence = {
        "service_24x256": Path("/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_candidate_service_telemetry_20260612-161133/segment_major_candidate_service_telemetry_probe.json"),
        "soak_30min_24x256": Path("/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_candidate_soak_20260612-162823/segment_major_candidate_soak_probe.json"),
        "soak_2h_24x256": Path("/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_candidate_soak_20260612-171402/segment_major_candidate_soak_probe.json"),
        "openclaw_local_dream": Path("/mnt/nas/openclaw/reports/models/dream7b_openclaw_candidate_validation_20260612-172108/openclaw_candidate_validation_probe.json"),
        "docs_consistency": consistency_dir / "summary.json",
        "handoff_doc": repo_root / "docs/dream7b_s100p_90pct_default_candidate_handoff_2026-06-12.md",
        "route_doc": repo_root / "docs/dream7b_s100p_90pct_utilization_route_2026-06-12.md",
    }

    errors: list[str] = []
    copied: dict[str, str] = {}
    parsed: dict[str, dict] = {}
    for name, path in evidence.items():
        if not path.is_file():
            errors.append(f"missing evidence: {name}: {path}")
            continue
        copied[name] = copy_artifact(path, artifacts_dir / name)
        if path.suffix == ".json":
            try:
                parsed[name] = read_json(path)
            except Exception as exc:
                errors.append(f"failed to parse json evidence {name}: {type(exc).__name__}: {exc}")

    service = parsed.get("service_24x256", {})
    soak30 = parsed.get("soak_30min_24x256", {})
    soak2h = parsed.get("soak_2h_24x256", {})
    openclaw = parsed.get("openclaw_local_dream", {})
    consistency = parsed.get("docs_consistency", {})

    primary_service_active = service_active("dream7b-bpu-segment-major-load-once-candidate-24job-b256.service")
    fallback_service_active = service_active("dream7b-bpu-segment-major-load-once-candidate-24job.service")
    default_service_active = service_active("dream7b-bpu-batch-queue.service")

    gates = {
        "service_24x256_reaches_90": metric(service, "avg_bpu_loading") != "" and float(metric(service, "avg_bpu_loading")) >= 90.0,
        "soak_30min_reaches_90": metric(soak30, "avg_bpu_loading") != "" and float(metric(soak30, "elapsed_sec")) >= 1800.0 and float(metric(soak30, "avg_bpu_loading")) >= 90.0 and int(metric(soak30, "failed_job_count")) == 0 and float(metric(soak30, "avg_load_to_run_ratio")) <= 0.03,
        "soak_2h_reaches_90": metric(soak2h, "avg_bpu_loading") != "" and float(metric(soak2h, "elapsed_sec")) >= 7200.0 and float(metric(soak2h, "avg_bpu_loading")) >= 90.0 and float(metric(soak2h, "min_iteration_avg_bpu_loading")) >= 89.5 and int(metric(soak2h, "failed_job_count")) == 0 and float(metric(soak2h, "avg_load_to_run_ratio")) <= 0.03,
        "services_active": primary_service_active and fallback_service_active and default_service_active,
        "openclaw_local_dream_ok": openclaw.get("verdict") == "ok_dream7b_openclaw_candidate_validation_probe" and openclaw.get("primary_model") == "dream7b-local/Dream7B-S100P-local" and openclaw.get("errors") == [],
        "docs_consistency_ok": consistency.get("verdict") == "ok_project_docs_consistency_probe" and consistency.get("errors") == [],
    }
    for name, ok in gates.items():
        if not ok:
            errors.append(f"gate failed: {name}")

    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_90pct_candidate_evidence_package_probe" if not errors else "failed_dream7b_90pct_candidate_evidence_package_probe",
        "run_dir": str(run_dir),
        "candidate_service": "dream7b-bpu-segment-major-load-once-candidate-24job-b256.service",
        "fallback_service": "dream7b-bpu-segment-major-load-once-candidate-24job.service",
        "default_service": "dream7b-bpu-batch-queue.service",
        "default_service_replaced": False,
        "service_status": {
            "dream7b-bpu-segment-major-load-once-candidate-24job-b256.service": "active" if primary_service_active else "inactive",
            "dream7b-bpu-segment-major-load-once-candidate-24job.service": "active" if fallback_service_active else "inactive",
            "dream7b-bpu-batch-queue.service": "active" if default_service_active else "inactive",
        },
        "gates": gates,
        "metrics": {
            "service_24x256_avg_bpu_loading": metric(service, "avg_bpu_loading"),
            "service_24x256_load_to_run_ratio": metric(service, "load_to_run_ratio"),
            "soak_30min_avg_bpu_loading": metric(soak30, "avg_bpu_loading"),
            "soak_30min_failed_job_count": metric(soak30, "failed_job_count"),
            "soak_30min_avg_load_to_run_ratio": metric(soak30, "avg_load_to_run_ratio"),
            "soak_2h_elapsed_sec": metric(soak2h, "elapsed_sec"),
            "soak_2h_iteration_count": metric(soak2h, "iteration_count"),
            "soak_2h_avg_bpu_loading": metric(soak2h, "avg_bpu_loading"),
            "soak_2h_min_iteration_avg_bpu_loading": metric(soak2h, "min_iteration_avg_bpu_loading"),
            "soak_2h_failed_job_count": metric(soak2h, "failed_job_count"),
            "soak_2h_avg_load_to_run_ratio": metric(soak2h, "avg_load_to_run_ratio"),
            "openclaw_primary_model": openclaw.get("primary_model", ""),
        },
        "artifacts": copied,
        "errors": errors,
    }
    (run_dir / "evidence_package_manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Dream 7B S100P 90 Percent Candidate Evidence Package",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- candidate_service: {payload['candidate_service']}",
        f"- fallback_service: {payload['fallback_service']}",
        f"- default_service_replaced: {payload['default_service_replaced']}",
        "",
        "## Service Status",
        "",
    ]
    lines.extend(f"- {name}: {status}" for name, status in payload["service_status"].items())
    lines.extend([
        "",
        "## Gates",
        "",
    ])
    lines.extend(f"- {name}: {ok}" for name, ok in gates.items())
    lines.extend(["", "## Metrics", ""])
    lines.extend(f"- {key}: {value}" for key, value in payload["metrics"].items())
    lines.extend(["", "## Artifacts", ""])
    lines.extend(f"- {name}: {path}" for name, path in copied.items())
    lines.extend(["", "## Errors", ""])
    lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
    (run_dir / "evidence_package_manifest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(run_dir / "evidence_package_manifest.md")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
