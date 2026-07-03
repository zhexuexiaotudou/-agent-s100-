#!/usr/bin/env bash
set -euo pipefail

nas_root="${1:-/mnt/nas/openclaw}"
report_dir="${2:-$nas_root/reports/baseline-status}"

case "$nas_root" in
  /mnt/nas/openclaw|/mnt/nas/openclaw/*|/root/.openclaw/workspace|/root/.openclaw/workspace/*|/tmp/*) ;;
  *)
    echo "Refusing NAS/workspace root outside approved paths: $nas_root" >&2
    exit 2
    ;;
esac

case "$report_dir" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing report directory outside approved paths: $report_dir" >&2
    exit 2
    ;;
esac

mkdir -p "$report_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$report_dir/baseline_evidence_manifest_$stamp.md"
json="$report_dir/baseline_evidence_manifest_$stamp.json"

python3 - "$nas_root" "$report" "$json" <<'PY'
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

nas_root = Path(sys.argv[1])
report = Path(sys.argv[2])
json_path = Path(sys.argv[3])


def latest(relative_glob):
    files = sorted(
        nas_root.glob(relative_glob),
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
        reverse=True,
    )
    return files[0] if files else None


def read(path):
    if not path:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def table_paths(text):
    paths = set()
    for match in re.finditer(r"(/mnt/nas/openclaw/[^\s|`]+|/root/\.openclaw/workspace/[^\s|`]+)", text):
        value = match.group(1).rstrip(".,;)")
        if "*" not in value:
            paths.add(value)
    return paths


def under_root(raw_path):
    try:
        Path(raw_path).relative_to(nas_root)
        return True
    except ValueError:
        return False


def digest(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


primary = {
    "baseline_status": latest("reports/baseline-status/baseline_status_[0-9]*.md"),
    "nas_link_blocker": latest("logs/probes/nas_link_blocker_[0-9]*.md"),
    "infrastructure_gate": latest("reports/infrastructure/infrastructure_gate_[0-9]*.md"),
    "baseline_gap_decision": latest("reports/baseline-status/baseline_gap_decision_[0-9]*.md"),
    "baseline_acceptance": latest("reports/baseline-status/baseline_acceptance_[0-9]*.md"),
    "baseline_acceptance_trend": latest("reports/baseline-status/baseline_acceptance_trend_[0-9]*.md"),
    "baseline_next_action_queue": latest("reports/baseline-status/baseline_next_action_queue_[0-9]*.md"),
    "teacher_briefing": latest("reports/teacher/teacher_baseline_briefing_[0-9]*.md"),
    "overnight_status": latest("reports/baseline-status/overnight_baseline_*_status.md"),
    "overnight_summary": latest("reports/baseline-status/overnight_baseline_*_summary.md"),
    "stability_summary": latest("reports/stability/stability_summary_[0-9]*.md"),
    "stability_checkpoint": latest("reports/stability/stability_checkpoint_[0-9]*.md"),
    "dream7b_readiness": latest("reports/models/dream7b_readiness_[0-9]*.md"),
    "dream7b_config_template": latest("reports/models/dream7b_config_template_[0-9]*.md"),
    "dream7b_smoke": latest("reports/models/dream7b_smoke_[0-9]*.md"),
    "home_assistant_template": latest("reports/home-assistant/home_assistant_config_template_[0-9]*.md"),
    "home_assistant": latest("logs/probes/home_assistant_status_[0-9]*.md"),
    "external_input_gate": latest("reports/external-inputs/external_input_gate_[0-9]*.md"),
    "control_template": latest("reports/control/control_action_template_[0-9]*.md"),
    "control_policy": latest("logs/probes/control_action_policy_[0-9]*.md"),
    "operator_review_gate": latest("reports/review-gates/operator_review_gate_[0-9]*.md"),
    "sandbox_status": latest("logs/probes/sandbox_status_[0-9]*.md"),
    "sandbox_smoke": latest("logs/probes/sandbox_isolation_smoke_[0-9]*.md"),
    "log_diagnosis": latest("logs/probes/log_diagnosis_[0-9]*.md"),
    "security_audit": latest("logs/probes/security_audit_[0-9]*.md"),
    "service_convergence": latest("reports/security/service_convergence_decision_[0-9]*.md"),
    "service_confirmation_template": latest("reports/security/service_confirmation_template_[0-9]*.md"),
    "service_execution_preflight": latest("reports/security/service_execution_preflight_[0-9]*.md"),
    "document_index": latest("reports/document_index_[0-9]*.md"),
    "document_daily_summary": latest("reports/daily-summary/document_daily_summary_[0-9]*.md"),
    "image_caption": latest("reports/image-captions/image_caption_index_[0-9]*.md"),
    "vision_readiness": latest("reports/image-captions/vision_caption_readiness_[0-9]*.md"),
    "experiment_report": latest("reports/experiments/experiment_report_[0-9]*.md"),
    "dataset_card": latest("robot_datasets/*/DATASET_CARD.md"),
    "dataset_card_inventory": latest("reports/robot-datasets/dataset_card_inventory_[0-9]*.md"),
    "browser_smoke": latest("reports/browser-smoke/browser_smoke_[0-9]*.md"),
    "rosbag_session": latest("logs/probes/rosbag_session_[0-9]*.md"),
    "rosbag_capture_request": latest("reports/rosbag/rosbag_named_capture_request_[0-9]*.md"),
    "rosbag_named_capture": latest("logs/probes/rosbag_named_capture_[0-9]*.md"),
}

path_labels = {}
for label, path in primary.items():
    if path:
        path_labels[str(path)] = label

for source in [
    primary.get("baseline_acceptance"),
    primary.get("baseline_acceptance_trend"),
    primary.get("teacher_briefing"),
    primary.get("overnight_summary"),
]:
    text = read(source)
    for raw_path in table_paths(text):
        if not under_root(raw_path):
            continue
        path_labels.setdefault(raw_path, "referenced")

entries = []
for raw_path, label in sorted(path_labels.items()):
    path = Path(raw_path)
    item = {
        "label": label,
        "path": raw_path,
        "exists": path.exists(),
        "size_bytes": None,
        "mtime": None,
        "sha256": None,
        "kind": "file",
    }
    if path.exists() and path.is_file():
        stat = path.stat()
        item["size_bytes"] = stat.st_size
        item["mtime"] = datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat()
        item["sha256"] = digest(path)
    elif path.exists() and path.is_dir():
        item["kind"] = "directory"
        stat = path.stat()
        item["mtime"] = datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat()
    entries.append(item)

missing = [entry for entry in entries if not entry["exists"]]
hashed = [entry for entry in entries if entry["sha256"]]

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "mode": "read-only evidence manifest; no system changes executed",
    "nas_root": str(nas_root),
    "report": str(report),
    "entry_count": len(entries),
    "hashed_file_count": len(hashed),
    "missing_count": len(missing),
    "entries": entries,
}

json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

with report.open("w", encoding="utf-8") as out:
    out.write("# Baseline Evidence Manifest\n\n")
    out.write(f"- generated_at: {payload['generated_at']}\n")
    out.write("- mode: read-only evidence manifest; no system changes executed\n")
    out.write(f"- nas_root: {nas_root}\n")
    out.write(f"- report: {report}\n")
    out.write(f"- json: {json_path}\n")
    out.write(f"- entry_count: {len(entries)}\n")
    out.write(f"- hashed_file_count: {len(hashed)}\n")
    out.write(f"- missing_count: {len(missing)}\n\n")

    out.write("## Evidence Files\n\n")
    out.write("| Label | Exists | Size | SHA256 | Path |\n| --- | --- | --- | --- | --- |\n")
    for entry in entries:
        sha = entry["sha256"] or ""
        short_sha = sha[:16] if sha else "missing"
        out.write(
            f"| {entry['label']} | {str(entry['exists']).lower()} | "
            f"{entry['size_bytes'] if entry['size_bytes'] is not None else ''} | "
            f"{short_sha} | {entry['path']} |\n"
        )

    out.write("\n## Missing References\n\n")
    if missing:
        out.write("| Label | Path |\n| --- | --- |\n")
        for entry in missing:
            out.write(f"| {entry['label']} | {entry['path']} |\n")
    else:
        out.write("No missing referenced evidence paths.\n")

print(report)
PY
