#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tarfile
import time
import zipfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INCLUDE_ROOTS = [
    "release",
    "deploy/product_access",
    "config",
    "requirements.txt",
    "src",
    "web",
    "demo_corpus/README.md",
    "demo_corpus/recipes",
    "demo_corpus/scripts",
    "demo_corpus/licenses",
    "demo_corpus/manifests",
    "demo_corpus/samples_generated",
    "gates/stage10_common.py",
    "gates/stage10_open_visual_corpus_license_gate.py",
    "gates/stage10_open_visual_corpus_download_gate.py",
    "gates/stage10_demo_corpus_index_gate.py",
    "gates/stage10_gold_query_multimodal_gate.py",
    "gates/stage10_auto_organizer_real_image_gate.py",
    "gates/stage10_yolo_bbox_recording_gate.py",
    "gates/stage10_demo_corpus_recording_readiness_gate.py",
    "gates/stage10_release_preflight_gate.py",
    "gates/stage10_release_installer_dry_run_gate.py",
    "gates/stage10_release_clean_install_gate.py",
    "gates/stage10_release_nas_mount_gate.py",
    "gates/stage10_release_product_smoke_gate.py",
    "gates/stage10_release_upgrade_rollback_gate.py",
    "gates/stage10_release_package_integrity_gate.py",
    "gates/stage10_release_product_delivery_gate.py",
    "scripts/build_release.py",
    "scripts/metrics_detector.py",
    "scripts/product_smoke_test.py",
    "scripts/qwen25_openai_gateway.py",
    "scripts/digua-access",
    "scripts/digua-doctor",
    "scripts/probes/ai_nas_operator_portal_server.py",
    "scripts/probes/ai_nas_operator_portal_contract_probe.py",
    "scripts/probes/ai_nas_app_ecosystem.py",
    "scripts/probes/ai_nas_backup.py",
    "scripts/probes/ai_nas_common.py",
    "scripts/probes/ai_nas_identity.py",
    "scripts/probes/ai_nas_media.py",
    "scripts/probes/ai_nas_ops.py",
    "scripts/probes/ai_nas_snapshot.py",
    "scripts/probes/safety_attack_probe.py",
    "scripts/probes/nas_web_os_portal.html",
    "configs/systemd/openclaw-gateway.service",
    "configs/systemd/qwen25-local-openai-gateway.service",
    "configs/systemd/digua-ai-index-worker.service",
    "configs/product_feature_flags.json",
    "configs/auto_organizer_feature_flags.json",
    "LICENSE",
]
FORBIDDEN_SUFFIXES = {
    ".hbm",
    ".hbo",
    ".onnx",
    ".safetensors",
    ".bin",
    ".gguf",
    ".pt",
    ".pth",
    ".sqlite",
    ".sqlite3",
    ".db",
    ".npy",
    ".npz",
    ".jpg",
    ".jpeg",
    ".png",
    ".mp4",
    ".mov",
    ".mkv",
    ".wav",
    ".mp3",
}
ALLOWED_MEDIA_ROOTS = {"demo_corpus/samples_generated"}
FORBIDDEN_PARTS = {"downloaded", "models", "secrets", "credentials", "__pycache__", ".pytest_cache", "node_modules"}
FORBIDDEN_NAME_MARKERS = {"redaction_map", ".env", "secret", "credential", "apikey", "api_key", "tokenizer.json", "vocab.json", "merges.txt"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a Digua AI-NAS S100P release package.")
    parser.add_argument("--version", default=(REPO_ROOT / "release" / "VERSION").read_text(encoding="utf-8").strip() if (REPO_ROOT / "release" / "VERSION").exists() else "0.1.0")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "dist")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    package_name = f"digua-ai-nas-s100p-{args.version}"
    files = collect_files()
    forbidden = []
    included = []
    for path in files:
        reason = forbidden_reason(path)
        if reason:
            forbidden.append({"path": path.relative_to(REPO_ROOT).as_posix(), "reason": reason})
        else:
            included.append(path)

    tar_path = args.out / f"{package_name}.tar.gz"
    zip_path = args.out / f"{package_name}.zip"
    with tarfile.open(tar_path, "w:gz") as tf:
        for path in included:
            tf.add(path, arcname=f"{package_name}/{path.relative_to(REPO_ROOT).as_posix()}")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in included:
            zf.write(path, f"{package_name}/{path.relative_to(REPO_ROOT).as_posix()}")

    sha_lines = [f"{sha256_file(tar_path)}  {tar_path.name}", f"{sha256_file(zip_path)}  {zip_path.name}"]
    sha_path = args.out / f"{package_name}.sha256"
    sha_path.write_text("\n".join(sha_lines) + "\n", encoding="utf-8")
    manifest = {
        "ok": not forbidden,
        "version": args.version,
        "git_commit": git_commit(),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "package_name": package_name,
        "tar_gz": str(tar_path),
        "zip": str(zip_path),
        "sha256": {tar_path.name: sha256_file(tar_path), zip_path.name: sha256_file(zip_path)},
        "install_entrypoint": "release/install/install_s100p.sh",
        "included_components": [
            "application_source",
            "web_ui",
            "openclaw",
            "qwen_gateway",
            "multimodal",
            "ai_space",
            "auto_organizer",
            "assistant_trace",
            "demo_corpus_scripts",
            "stage10_gates",
            "product_access_facade",
            "lan_mdns_and_first_claim",
            "tailscale_and_cloudflare_adapters",
        ],
        "excluded_components": ["model_weights", "third_party_images", "private_user_data", "secrets"],
        "file_count": len(included),
        "files": [path.relative_to(REPO_ROOT).as_posix() for path in included],
        "forbidden_file_count": len(forbidden),
        "forbidden_files": forbidden,
        "self_check": {
            "no_model_weights": not any(item["reason"] == "model_or_binary_suffix" for item in forbidden),
            "no_third_party_images": not any("demo_corpus/downloaded" in item["path"] for item in forbidden),
            "no_private_user_data": not any("Personal" in item["path"] for item in forbidden),
            "no_secrets": not any(item["reason"] == "secret_or_credential_name" for item in forbidden),
        },
    }
    manifest_path = args.out / "release_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(manifest_path)
    print(tar_path)
    print(zip_path)
    print(sha_path)
    return 0 if manifest["ok"] else 1


def collect_files() -> list[Path]:
    files: list[Path] = []
    for rel in DEFAULT_INCLUDE_ROOTS:
        path = REPO_ROOT / rel
        if path.is_file():
            if not ignored_candidate(path):
                files.append(path)
        elif path.is_dir():
            files.extend(p for p in path.rglob("*") if p.is_file() and not ignored_candidate(p))
    return sorted(set(files))


def forbidden_reason(path: Path) -> str | None:
    rel = path.relative_to(REPO_ROOT).as_posix()
    parts = set(Path(rel).parts)
    if parts & FORBIDDEN_PARTS:
        return "forbidden_path_part"
    lower = rel.lower()
    if lower.endswith(".env.example"):
        return None
    if any(marker in lower for marker in FORBIDDEN_NAME_MARKERS):
        return "secret_or_credential_name"
    suffix = path.suffix.lower()
    if suffix in FORBIDDEN_SUFFIXES:
        if any(rel.startswith(root + "/") for root in ALLOWED_MEDIA_ROOTS):
            return None
        return "model_or_binary_suffix" if suffix not in {".jpg", ".jpeg", ".png", ".mp4", ".mov", ".mkv", ".wav", ".mp3"} else "media_file_not_packaged_by_default"
    return None


def ignored_candidate(path: Path) -> bool:
    rel = path.relative_to(REPO_ROOT).as_posix()
    parts = set(Path(rel).parts)
    if rel.startswith("demo_corpus/manifests/") and rel.endswith("_report.json"):
        return True
    return bool(parts & {"__pycache__", ".pytest_cache", "node_modules"})


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        completed = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True, capture_output=True, check=False)
        return completed.stdout.strip() if completed.returncode == 0 else "unknown"
    except OSError:
        return "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
