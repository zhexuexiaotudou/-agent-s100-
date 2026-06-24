#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path

from ai_nas_acl_mapping_readiness_probe import (
    DEFAULT_MAPPING_CONFIGS,
    evaluate_readiness as evaluate_acl_readiness,
    mapping_configs,
    sample_entries,
    tool_paths as acl_tool_paths,
)
from ai_nas_common import (
    DEFAULT_PERSONAL_ROOT,
    DEFAULT_REPORT_ROOT,
    DEFAULT_SQLITE_INDEX_PATH,
    ensure_report_dir,
    iso_now,
    ocr_engine_status,
    safe_write_json,
    safe_write_text,
    sqlite_index_status,
)
from ai_nas_embedding_backend_readiness_probe import (
    IMAGE_MODEL_ENV,
    TEXT_MODEL_ENV,
    configured_image_model_dir,
    configured_text_model_dir,
    model_dir_status,
    try_clip_smoke,
    try_sentence_transformer_smoke,
    try_transformers_text_embedding_smoke,
)
from ai_nas_embedding_runtime_contract_probe import (
    module_status as embedding_module_status,
    text_fallback_smoke,
    visual_fallback_smoke,
)
from ai_nas_model_service_resilience_probe import (
    DEFAULT_HEALTH_URLS,
    DEFAULT_SERVICES,
    candidate_unit_paths,
    check_health_url,
    parse_unit_file,
    run_command,
)
from ai_nas_ocr_runtime_contract_probe import (
    command_status as ocr_command_status,
    install_manifest as ocr_install_manifest,
    module_status as ocr_module_status,
)


TOOL_ID = "ai_nas_production_dependency_bundle"


def current_repo_root() -> Path:
    resolved = Path(__file__).resolve()
    for parent in [resolved.parent, *resolved.parents]:
        if (parent / "scripts" / "probes").exists() or (parent / "scripts" / "tool_allowlist.json").exists():
            return parent
    return Path.cwd()


def dependency_item(
    dep_id: str,
    label: str,
    ready: bool,
    blockers: list[str],
    evidence: dict,
    operator_steps: list[str],
) -> dict:
    return {
        "id": dep_id,
        "label": label,
        "ready": bool(ready),
        "blockers": blockers,
        "evidence": evidence,
        "operator_steps": operator_steps,
    }


def unique(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def text_embedding_dependency(text_model_dir: Path | None) -> dict:
    modules = embedding_module_status(["sentence_transformers", "transformers", "torch"])
    model = model_dir_status(text_model_dir, ["config.json", "modules.json", "sentence_bert_config.json", "tokenizer.json", "pytorch_model.bin", "model.safetensors"])
    production_smoke = try_sentence_transformer_smoke(text_model_dir)
    hf_production_smoke = try_transformers_text_embedding_smoke(text_model_dir)
    fallback = text_fallback_smoke()
    blockers = []
    if not (
        modules.get("sentence_transformers", {}).get("importable")
        or modules.get("transformers", {}).get("importable")
    ):
        blockers.append("sentence_transformers_not_importable")
    if not modules.get("torch", {}).get("importable"):
        blockers.append("torch_not_importable")
    if not model.get("ready"):
        blockers.append("local_text_embedding_model_dir_not_ready")
    if not (production_smoke.get("ok") or hf_production_smoke.get("ok")):
        blockers.append("production_text_embedding_smoke_not_ready")
    return dependency_item(
        "text_embedding_runtime",
        "Production text embedding runtime and local model",
        not blockers,
        blockers,
        {
            "module_status": modules,
            "model_dir": model,
            "smoke": production_smoke,
            "hf_smoke": hf_production_smoke,
            "fallback_smoke": fallback,
            "env": {TEXT_MODEL_ENV: os.environ.get(TEXT_MODEL_ENV)},
        },
        [
            "Install sentence-transformers and torch into the OpenClaw Python runtime.",
            f"Pre-provision a local sentence-transformer model and set {TEXT_MODEL_ENV}.",
            "Re-run embedding runtime contract with local_files_only behavior; do not download models during tool execution.",
        ],
    )


def image_clip_dependency(image_model_dir: Path | None, fixture_image: Path) -> dict:
    modules = embedding_module_status(["transformers", "clip", "open_clip", "torch", "PIL"])
    model = model_dir_status(image_model_dir, ["config.json", "preprocessor_config.json", "open_clip_config.json"])
    production_smoke = try_clip_smoke(image_model_dir)
    fallback = visual_fallback_smoke(fixture_image)
    blockers = []
    if not modules.get("torch", {}).get("importable"):
        blockers.append("torch_not_importable")
    if not (
        modules.get("transformers", {}).get("importable")
        or modules.get("clip", {}).get("importable")
        or modules.get("open_clip", {}).get("importable")
    ):
        blockers.append("clip_or_transformers_runtime_not_importable")
    if not model.get("ready"):
        blockers.append("local_image_clip_model_dir_not_ready")
    if not production_smoke.get("ok"):
        blockers.append("production_image_clip_smoke_not_ready")
    return dependency_item(
        "image_clip_runtime",
        "Production image CLIP runtime and local model",
        not blockers,
        blockers,
        {
            "module_status": modules,
            "model_dir": model,
            "smoke": production_smoke,
            "fallback_smoke": fallback,
            "env": {IMAGE_MODEL_ENV: os.environ.get(IMAGE_MODEL_ENV)},
        },
        [
            "Install a CLIP-capable runtime such as transformers, clip, or open_clip plus torch.",
            f"Pre-provision a local CLIP model directory and set {IMAGE_MODEL_ENV}.",
            "Keep face recognition disabled until a separate privacy and compliance review approves it.",
        ],
    )


def ocr_dependency() -> dict:
    runtime = ocr_engine_status()
    modules = ocr_module_status(["pytesseract", "fitz", "PIL", "cv2", "numpy"])
    commands = {
        "tesseract_version": ocr_command_status(["tesseract", "--version"])
        if runtime.get("tesseract_cli")
        else {"ok": False, "error": "tesseract CLI not found on PATH"},
    }
    manifest = ocr_install_manifest(runtime, modules)
    blockers = []
    if not runtime.get("tesseract_cli"):
        blockers.append("tesseract_cli_not_found")
    if not runtime.get("ocr_ready"):
        blockers.append("production_ocr_runtime_not_ready")
    return dependency_item(
        "ocr_runtime",
        "OCR runtime for scanned PDFs and images",
        not blockers,
        blockers,
        {
            "runtime": runtime,
            "module_status": modules,
            "command_status": commands,
            "install_manifest": manifest,
        },
        [
            "Install Tesseract OCR and make the tesseract CLI discoverable on PATH.",
            "Install tesseract-ocr and language data into the OpenClaw runtime; pytesseract is optional when CLI stdout OCR smoke passes.",
            "Keep scanned files explicitly blocked or failed when OCR is unavailable; never invent extracted content.",
        ],
    )


def acl_dependency(personal_root: Path, mapping_config: list[Path]) -> dict:
    tools = acl_tool_paths()
    samples, failures = sample_entries(personal_root)
    configs = mapping_configs(mapping_config or DEFAULT_MAPPING_CONFIGS)
    readiness = evaluate_acl_readiness(personal_root, samples, failures, tools, configs)
    blockers = list(readiness.get("blockers") or [])
    return dependency_item(
        "nas_acl_user_mapping",
        "NAS Personal root and real ACL/user mapping",
        bool(readiness.get("production_nas_acl_ready")),
        blockers,
        {
            "personal_root": str(personal_root),
            "tools": tools,
            "mapping_configs": configs,
            "sample_count": len(samples),
            "stat_failure_count": len(failures),
            "sample_entries_preview": samples[:8],
            "stat_failures_preview": failures[:8],
            "readiness": readiness,
        },
        [
            "Mount the NAS Personal root from the AI appliance runtime.",
            "Install ACL and identity tooling such as getfacl, id/getent, and SMB mapping tools where applicable.",
            "Provide a principal-to-NAS-user/group mapping config before replacing local permission overlays.",
        ],
    )


def model_service_dependency(repo_root: Path, services: list[str], health_urls: list[str], unit_files: list[Path]) -> dict:
    systemctl_checks = []
    for service in services:
        user_active = run_command(["systemctl", "--user", "is-active", service])
        user_enabled = run_command(["systemctl", "--user", "is-enabled", service])
        system_active = run_command(["systemctl", "is-active", service])
        system_enabled = run_command(["systemctl", "is-enabled", service])
        systemctl_checks.append(
            {
                "service": service,
                "user": {"is_active": user_active, "is_enabled": user_enabled},
                "system": {"is_active": system_active, "is_enabled": system_enabled},
                "is_active": user_active if user_active.get("ok") else system_active,
                "is_enabled": user_enabled if user_enabled.get("ok") else system_enabled,
                "active_scope": "user" if user_active.get("ok") else ("system" if system_active.get("ok") else None),
                "enabled_scope": "user" if user_enabled.get("ok") else ("system" if system_enabled.get("ok") else None),
            }
        )
    health = [check_health_url(url) for url in health_urls]
    units = [parse_unit_file(path) for path in candidate_unit_paths(repo_root, unit_files)]
    blockers = []
    if not any(item.get("ok") for item in health):
        blockers.append("no_model_or_openclaw_health_endpoint_ok")
    if not any(check["is_active"].get("ok") for check in systemctl_checks):
        blockers.append("no_systemd_service_active")
    if not any(unit.get("has_restart_policy") for unit in units):
        blockers.append("restart_policy_not_verified")
    return dependency_item(
        "model_openclaw_service_recovery",
        "Model/OpenClaw service health, systemd policy, and recovery evidence",
        not blockers,
        blockers,
        {
            "health": health,
            "systemctl_checks": systemctl_checks,
            "unit_files": units,
            "service_names": services,
            "health_urls": health_urls,
        },
        [
            "Expose local health endpoints for the model gateway and OpenClaw gateway.",
            "Run the model queue and gateway under systemd user or system services with Restart policy.",
            "Perform an operator-approved kill/restart recovery drill and attach the manifest/report before production claims.",
        ],
    )


def build_summary(dependencies: list[dict]) -> dict:
    blockers = {item["id"]: item["blockers"] for item in dependencies if item["blockers"]}
    return {
        "dependency_count": len(dependencies),
        "ready_count": sum(1 for item in dependencies if item["ready"]),
        "blocked_count": sum(1 for item in dependencies if not item["ready"]),
        "blockers": blockers,
        "external_blockers": [f"{dep_id}:{blocker}" for dep_id, items in blockers.items() for blocker in items],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS read-only production dependency evidence bundle.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--personal-root", type=Path, default=DEFAULT_PERSONAL_ROOT)
    parser.add_argument("--sqlite-index-path", type=Path, default=DEFAULT_SQLITE_INDEX_PATH)
    parser.add_argument("--mapping-config", action="append", type=Path, default=[])
    parser.add_argument("--text-model-dir", type=Path, default=None)
    parser.add_argument("--image-model-dir", type=Path, default=None)
    parser.add_argument("--health-url", action="append", default=[])
    parser.add_argument("--service", action="append", default=[])
    parser.add_argument("--unit-file", action="append", type=Path, default=[])
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "production_dependency_bundle")
    fixture_root = run_dir / "fixture"
    fixture_root.mkdir(parents=True, exist_ok=True)
    text_model_dir = configured_text_model_dir(args.text_model_dir)
    image_model_dir = configured_image_model_dir(args.image_model_dir)
    repo_root = current_repo_root()

    dependencies = [
        text_embedding_dependency(text_model_dir),
        image_clip_dependency(image_model_dir, fixture_root / "clip_fixture.png"),
        ocr_dependency(),
        acl_dependency(args.personal_root, args.mapping_config),
        model_service_dependency(
            repo_root,
            args.service or DEFAULT_SERVICES,
            args.health_url or DEFAULT_HEALTH_URLS,
            args.unit_file,
        ),
    ]
    summary = build_summary(dependencies)
    production_ready = summary["blocked_count"] == 0
    operator_next_steps = unique([step for item in dependencies for step in item["operator_steps"] if not item["ready"]])
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_production_dependency_bundle" if production_ready else "limited_ai_nas_production_dependency_bundle",
        "production_dependencies_ready": production_ready,
        "scope": "read-only external dependency evidence bundle for AI-NAS Copilot Appliance production claims",
        "personal_root": str(args.personal_root),
        "sqlite_index_path": str(args.sqlite_index_path),
        "sqlite_index_status": sqlite_index_status(args.sqlite_index_path) if args.sqlite_index_path.exists() else {"exists": False},
        "dependencies": dependencies,
        "summary": summary,
        "operator_next_steps": operator_next_steps,
        "audit": {
            "source_files_modified": False,
            "personal_source_modified": False,
            "download_performed": False,
            "network_call_performed": "local health endpoints only",
            "service_restart_performed": False,
            "kill_performed": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "permission_change_performed": False,
            "writes": "Markdown/JSON production dependency evidence bundle report plus isolated local image fixture only",
        },
    }

    json_path = run_dir / "production_dependency_bundle.json"
    md_path = run_dir / "production_dependency_bundle.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Production Dependency Bundle",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- production_dependencies_ready: `{production_ready}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- dependency_count: `{summary['dependency_count']}`",
        f"- ready_count: `{summary['ready_count']}`",
        f"- blocked_count: `{summary['blocked_count']}`",
        "- policy: read-only evidence bundle; no installs, downloads, service restarts, kills, deletes, moves, overwrites, or Personal source mutation",
        "",
        "## Dependencies",
        "",
    ]
    for item in dependencies:
        lines.append(f"### {item['label']}")
        lines.append("")
        lines.append(f"- id: `{item['id']}`")
        lines.append(f"- ready: `{item['ready']}`")
        lines.append(f"- blockers: `{item['blockers']}`")
        lines.append("")
    lines.extend(["## Operator Next Steps", ""])
    if not operator_next_steps:
        lines.append("- No external dependency step remains.")
    for step in operator_next_steps:
        lines.append(f"- {step}")
    lines.extend(["", "## External Blockers", ""])
    if not summary["external_blockers"]:
        lines.append("- No external dependency blocker detected.")
    for blocker in summary["external_blockers"]:
        lines.append(f"- {blocker}")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
