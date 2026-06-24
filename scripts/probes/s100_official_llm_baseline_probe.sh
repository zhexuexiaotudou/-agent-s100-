#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
sdk_root="${S100_OFFICIAL_LLM_SDK_ROOT:-/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK}"
dream_report_root="${S100_OFFICIAL_LLM_DREAM_REPORT_ROOT:-/mnt/nas/openclaw/reports/models}"
official_doc_url="${S100_OFFICIAL_LLM_DOC_URL:-https://developer.d-robotics.cc/rdk_doc/rdk_s/Advanced_development/toolchain_development/LLM_Toolchain/}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

case "$sdk_root" in
  /mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK|/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/|/opt/D-Robotics_LLM_S100_1.0.0_SDK|/opt/D-Robotics_LLM_S100_1.0.0_SDK/) ;;
  *)
    echo "Refusing SDK path outside approved S100 official LLM SDK directories: $sdk_root" >&2
    exit 2
    ;;
esac

case "$dream_report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing Dream report path outside approved report directories: $dream_report_root" >&2
    exit 2
    ;;
esac

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/s100_official_llm_baseline_$stamp"
mkdir -p "$run_dir"

python3 - \
  "$run_dir" \
  "$sdk_root" \
  "$dream_report_root" \
  "$official_doc_url" <<'PY'
import json
import re
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
sdk_root = Path(sys.argv[2])
dream_report_root = Path(sys.argv[3])
official_doc_url = sys.argv[4]

runtime_root = sdk_root / "oellm_runtime"
build_root = sdk_root / "oellm_build"
config_root = runtime_root / "config"
example_root = runtime_root / "example"
model_root = runtime_root / "model"
resolve_model_path = model_root / "resolve_model_nash-m.txt"
qwen_multichat_config_path = example_root / "oellm_multichat" / "qwen_multichat_config.json"

errors = []
warnings = []


def latest_json(pattern):
    paths = [path for path in dream_report_root.glob(pattern) if path.is_file()]
    if not paths:
        return None, None
    path = max(paths, key=lambda item: item.stat().st_mtime)
    return path, json.loads(path.read_text(encoding="utf-8"))


def read_json(path):
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def config_dirs():
    if not config_root.is_dir():
        return []
    return sorted(path.name for path in config_root.iterdir() if path.is_dir() and path.name.endswith("_config"))


def parse_resolve_model(path):
    if not path.is_file():
        return {"models": [], "hbm_urls": [], "raw_line_count": 0}
    models = []
    hbm_urls = []
    current_model = None
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("wget "):
            url = stripped.split(None, 1)[1]
            row = {"model": current_model, "url": url, "filename": url.rsplit("/", 1)[-1]}
            hbm_urls.append(row)
            continue
        if stripped == "md5" or stripped.startswith("context size "):
            continue
        if re.match(r"^[A-Za-z0-9_.-]+", stripped):
            current_model = stripped
            if stripped not in models:
                models.append(stripped)
    return {"models": models, "hbm_urls": hbm_urls, "raw_line_count": len(lines)}


def hbm_presence_from_urls(rows):
    result = []
    for row in rows:
        filename = row.get("filename") or ""
        if not filename.endswith(".hbm") and filename != "embed_tokens.bin":
            continue
        path = model_root / filename
        result.append(
            {
                "model": row.get("model"),
                "filename": filename,
                "expected_path": str(path),
                "exists": path.is_file(),
                "size_bytes": path.stat().st_size if path.is_file() else 0,
            }
        )
    return result


def summarize_dream_failures():
    utilization_path, utilization = latest_json("dream7b_bpu_utilization_gap_*/utilization_gap_probe.json")
    selected_path, selected = latest_json("dream7b_bpu_selected_triplet_forward_path_*/selected_triplet_forward_path_probe.json")
    window3_path, window3 = latest_json("dream7b_bpu_window3_forward_feasibility_*/window3_forward_feasibility_probe.json")
    runtime_telemetry = utilization.get("runtime_telemetry") if utilization else {}
    systemd_telemetry = utilization.get("systemd_telemetry") if utilization else {}
    return {
        "utilization_gap_path": str(utilization_path) if utilization_path else "",
        "utilization_gap_verdict": utilization.get("verdict") if utilization else None,
        "diagnosis": utilization.get("diagnosis") if utilization else None,
        "runtime_telemetry.load_to_run_ratio": runtime_telemetry.get("load_to_run_ratio") if runtime_telemetry else None,
        "systemd_telemetry.load_to_run_ratio": systemd_telemetry.get("load_to_run_ratio") if systemd_telemetry else None,
        "avg_observed_bpu_loading_across_reports": utilization.get("avg_observed_bpu_loading_across_reports") if utilization else None,
        "selected_triplet_forward_path": str(selected_path) if selected_path else "",
        "selected_triplet_forward_supported": selected.get("selected_triplet_forward_supported") if selected else None,
        "reboot_or_disconnect_observed": selected.get("reboot_or_disconnect_observed") if selected else None,
        "expected_reboot_guard_observed": selected.get("expected_reboot_guard_observed") if selected else None,
        "window3_forward_path": str(window3_path) if window3_path else "",
        "direct_window3_forward_supported": window3.get("direct_window3_forward_supported") if window3 else None,
        "expected_window3_failure_observed": window3.get("expected_window3_failure_observed") if window3 else None,
        "stderr_contains_memory_alloc_failure": window3.get("stderr_contains_memory_alloc_failure") if window3 else None,
    }


sdk_exists = sdk_root.is_dir()
runtime_exists = runtime_root.is_dir()
build_exists = build_root.is_dir()
resolve = parse_resolve_model(resolve_model_path)
qwen_multichat_config = read_json(qwen_multichat_config_path)
official_hbm_presence = hbm_presence_from_urls(resolve.get("hbm_urls") or [])
qwen_expected_hbm = [item for item in official_hbm_presence if "Qwen" in (item.get("filename") or "")]
qwen_existing_hbm = [item for item in qwen_expected_hbm if item.get("exists")]
dream = summarize_dream_failures()
official_qwen_runtime_path, official_qwen_runtime = latest_json("s100_official_qwen_runtime_*/official_qwen_runtime_probe.json")

if not sdk_exists:
    errors.append("official S100 LLM SDK directory is missing")
if sdk_exists and not runtime_exists:
    errors.append("official S100 LLM runtime directory is missing")
if sdk_exists and not build_exists:
    errors.append("official S100 LLM build directory is missing")
if sdk_exists and not resolve.get("models"):
    errors.append("official resolve_model_nash-m.txt support list is missing or empty")
if not qwen_existing_hbm:
    warnings.append("official Qwen config exists, but no downloaded Qwen .hbm file is present under the SDK runtime model directory")
if not qwen_multichat_config:
    warnings.append("official qwen_multichat_config.json is missing or unreadable")
if not dream.get("diagnosis"):
    warnings.append("latest Dream utilization gap report was not found")

qwen_hbm_path = qwen_multichat_config.get("hbm_path")
qwen_hbm_expected_from_multichat = str((qwen_multichat_config_path.parent / qwen_hbm_path).resolve()) if qwen_hbm_path else ""
qwen_hbm_exists_from_multichat = Path(qwen_hbm_expected_from_multichat).is_file() if qwen_hbm_expected_from_multichat else False
official_qwen_local_runtime_report_present = official_qwen_runtime is not None
official_qwen_memory_alloc_failure_observed = bool((official_qwen_runtime or {}).get("memory_alloc_failure_observed"))
official_qwen_runtime_completed = (official_qwen_runtime or {}).get("runtime_completed")
official_qwen_runtime_returncode = (official_qwen_runtime or {}).get("runtime_returncode")
similar_issue_evidence_available_for_official_qwen = official_qwen_memory_alloc_failure_observed

if official_qwen_local_runtime_report_present:
    comparison_reason = (
        "latest official Qwen runtime report is present; it uses the vendor .hbm and oellm runtime, "
        "and currently shows BPU/common-buffer memory allocation failure after HBM/model load"
        if official_qwen_memory_alloc_failure_observed
        else "latest official Qwen runtime report is present; compare its runtime_completed and captured logs before using it as a clean utilization baseline"
    )
    next_probe_target = "inspect S100P BPU/common-buffer memory pool and official runtime performance-mode prerequisites before using Qwen as a clean 128TOPS utilization baseline"
else:
    comparison_reason = "no local official Qwen .hbm runtime report is present; available SDK evidence shows a different supported-model runtime layout rather than the custom Dream segmented forward path"
    next_probe_target = "download one official Qwen .hbm listed in resolve_model_nash-m.txt and run the matching oellm runtime example with hrt_ucp_monitor before using it as a utilization baseline"

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_s100_official_llm_baseline_probe" if not errors else "failed_s100_official_llm_baseline_probe",
    "run_dir": str(run_dir),
    "official_doc_url": official_doc_url,
    "sdk_root": str(sdk_root),
    "runtime_root": str(runtime_root),
    "build_root": str(build_root),
    "resolve_model_path": str(resolve_model_path),
    "qwen_multichat_config_path": str(qwen_multichat_config_path),
    "sdk_exists": sdk_exists,
    "runtime_exists": runtime_exists,
    "build_exists": build_exists,
    "config_dir_count": len(config_dirs()),
    "config_dirs": config_dirs(),
    "supported_model_names_from_resolve_model": resolve.get("models"),
    "official_hbm_download_entry_count": len(official_hbm_presence),
    "official_hbm_download_entries": official_hbm_presence,
    "qwen_hbm_download_entries": qwen_expected_hbm,
    "qwen_existing_hbm_count": len(qwen_existing_hbm),
    "qwen_multichat_config": qwen_multichat_config,
    "qwen_hbm_expected_from_multichat": qwen_hbm_expected_from_multichat,
    "qwen_hbm_exists_from_multichat": qwen_hbm_exists_from_multichat,
    "official_qwen_local_runtime_report_present": official_qwen_local_runtime_report_present,
    "official_qwen_latest_runtime_report_path": str(official_qwen_runtime_path) if official_qwen_runtime_path else "",
    "official_qwen_runtime_completed": official_qwen_runtime_completed,
    "official_qwen_runtime_returncode": official_qwen_runtime_returncode,
    "official_qwen_memory_alloc_failure_observed": official_qwen_memory_alloc_failure_observed,
    "official_qwen_hbm_load_success_observed": (official_qwen_runtime or {}).get("hbm_load_success_observed"),
    "official_qwen_init_model_success_observed": (official_qwen_runtime or {}).get("init_model_success_observed"),
    "similar_issue_evidence_available_for_official_qwen": similar_issue_evidence_available_for_official_qwen,
    "comparison_to_dream": {
        "official_qwen_route": "official runtime config points to one precompiled .hbm path plus tokenizer/template config",
        "dream_route": "project-created segmented Dream .hbm chain with repeated load/run/unload across ten fine segments",
        "same_failure_class_as_dream_proven": (official_qwen_runtime or {}).get("same_failure_class_as_dream", False),
        "reason": comparison_reason,
        "dream_failure_summary": dream,
    },
    "next_probe_target": next_probe_target,
    "warnings": warnings,
    "errors": errors,
}

(run_dir / "official_llm_baseline_probe.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
lines = [
    "# S100 Official LLM Baseline Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- sdk_exists: {payload['sdk_exists']}",
    f"- runtime_exists: {payload['runtime_exists']}",
    f"- build_exists: {payload['build_exists']}",
    f"- config_dir_count: {payload['config_dir_count']}",
    f"- official_hbm_download_entry_count: {payload['official_hbm_download_entry_count']}",
    f"- qwen_existing_hbm_count: {payload['qwen_existing_hbm_count']}",
    f"- qwen_hbm_exists_from_multichat: {payload['qwen_hbm_exists_from_multichat']}",
    f"- official_qwen_local_runtime_report_present: {payload['official_qwen_local_runtime_report_present']}",
    f"- official_qwen_latest_runtime_report_path: {payload['official_qwen_latest_runtime_report_path']}",
    f"- official_qwen_runtime_completed: {payload['official_qwen_runtime_completed']}",
    f"- official_qwen_runtime_returncode: {payload['official_qwen_runtime_returncode']}",
    f"- official_qwen_memory_alloc_failure_observed: {payload['official_qwen_memory_alloc_failure_observed']}",
    f"- similar_issue_evidence_available_for_official_qwen: {payload['similar_issue_evidence_available_for_official_qwen']}",
    f"- dream.diagnosis: {dream.get('diagnosis')}",
    f"- dream.selected_triplet_forward_supported: {dream.get('selected_triplet_forward_supported')}",
    f"- dream.reboot_or_disconnect_observed: {dream.get('reboot_or_disconnect_observed')}",
    f"- next_probe_target: {payload['next_probe_target']}",
    "",
    "## Supported Models From resolve_model_nash-m.txt",
    "",
]
lines.extend(f"- {item}" for item in payload["supported_model_names_from_resolve_model"])
lines.extend(["", "## Warnings", ""])
lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- none")
lines.extend(["", "## Errors", ""])
lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
lines.append("")
(run_dir / "official_llm_baseline_probe.md").write_text("\n".join(lines), encoding="utf-8")
print(run_dir / "official_llm_baseline_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
