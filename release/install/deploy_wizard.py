#!/usr/bin/env python3
"""Interactive, secret-safe deployment guide for an S100P + NAS appliance."""
from __future__ import annotations

import argparse
import getpass
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


MODEL_PROMPTS = {
    "DIGUA_QWEN_MODEL_DIR": "Qwen model directory",
    "QWEN25_RUNTIME_BIN": "S100P Qwen runtime executable",
    "QWEN25_RUNTIME_CONFIG": "Qwen runtime config JSON",
    "QWEN25_RUNTIME_LIB_DIR": "Qwen runtime library directory",
    "QWEN25_ACTIVE_HBM_PATH": "Qwen HBM file",
    "DIGUA_CLIP_MODEL_DIR": "CLIP model directory (optional)",
    "DIGUA_YOLO_MODEL_PATH": "YOLO HBM file (optional)",
    "DIGUA_OCR_MODEL_DIR": "OCR model directory (optional)",
    "DIGUA_ASR_MODEL_DIR": "ASR model directory (optional)",
}


def ask(label: str, default: str = "", required: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"{label}{suffix}: ").strip() or default
        if value or not required:
            return value
        print("This value is required.")


def load_config(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("config must be a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Guided Digua AI-NAS clean installation")
    parser.add_argument("--config", type=Path, help="JSON answers for repeatable/non-interactive installs")
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--simulate-root", type=Path, help="Build a non-production clean install sandbox")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    cfg = load_config(args.config)
    interactive = not args.non_interactive

    def value(key: str, label: str, default: str = "", required: bool = True) -> str:
        configured = str(cfg.get(key) or os.environ.get(key) or default)
        return ask(label, configured, required) if interactive else configured

    print("\nDigua AI-NAS deployment guide")
    print("Stages: device preflight -> verified NAS mount -> model paths -> app/venv -> services -> admin bootstrap -> authenticated verification")
    if args.simulate_root:
        print("SIMULATION MODE: no S100P/NAS/systemd claim will be made.")

    protocol = value("nas_protocol", "NAS protocol (nfs/smb)", "nfs")
    if protocol not in {"nfs", "smb", "cifs", "local"}:
        raise SystemExit(f"unsupported NAS protocol: {protocol}")
    nas_host = value("nas_host", "NAS IP/hostname", "", protocol != "local")
    nas_share = value("nas_share", "NAS export/share", "", protocol != "local")
    mount_point = value("mount_point", "S100P mount point", "/mnt/nas/openclaw")
    personal_root = value("personal_root", "Digua Personal root", f"{mount_point}/Personal")
    install_root = value("install_root", "Application install root", "/opt/digua-ai-nas")
    systemd_mode = value("systemd_mode", "systemd mode", "system")
    service_user = value("service_user", "Unprivileged service user", os.environ.get("SUDO_USER") or getpass.getuser())
    credentials_file = value("credentials_file", "Existing SMB credentials file (chmod 600)", "", protocol in {"smb", "cifs"})
    admin_username = value("admin_username", "Initial administrator username", "admin")
    password_env = str(cfg.get("password_env") or "DIGUA_ADMIN_PASSWORD")
    password = os.environ.get(password_env, "")
    if not password and interactive:
        password = getpass.getpass("Initial administrator password (min 8 chars; never written to report): ")
    if not password:
        raise SystemExit(f"administrator password missing; set {password_env}")

    env = dict(os.environ)
    env[password_env] = password
    model_values = cfg.get("models") if isinstance(cfg.get("models"), dict) else {}
    for name, label in MODEL_PROMPTS.items():
        default = str(model_values.get(name) or env.get(name) or "")
        required = name in {"DIGUA_QWEN_MODEL_DIR", "QWEN25_RUNTIME_BIN", "QWEN25_RUNTIME_CONFIG", "QWEN25_RUNTIME_LIB_DIR", "QWEN25_ACTIVE_HBM_PATH"}
        configured = ask(label, default, required) if interactive else default
        if required and not configured:
            raise SystemExit(f"required model setting missing: {name}")
        if configured:
            env[name] = configured

    installer = Path(__file__).with_name("install_s100p.sh")
    command = ["bash", str(installer), "--nas-protocol", protocol, "--nas-host", nas_host, "--nas-share", nas_share, "--mount-point", mount_point, "--personal-root", personal_root, "--install-root", install_root, "--systemd-mode", systemd_mode, "--service-user", service_user, "--admin-username", admin_username, "--password-env", password_env]
    if credentials_file:
        command += ["--credentials-file", credentials_file]
    if args.simulate_root:
        command += ["--simulate-root", str(args.simulate_root), "--skip-pip"]
    if args.dry_run:
        command.append("--dry-run")
    if protocol == "local":
        command.append("--allow-local-storage")
    wheelhouse = str(cfg.get("wheelhouse") or "")
    if wheelhouse:
        command += ["--wheelhouse", wheelhouse]

    print("\nPre-flight summary (secrets redacted):")
    print(json.dumps({"protocol": protocol, "nas_host": nas_host, "nas_share": nas_share, "mount_point": mount_point, "personal_root": personal_root, "install_root": install_root, "systemd_mode": systemd_mode, "service_user": service_user, "simulation": bool(args.simulate_root), "admin_username": admin_username, "model_paths_configured": sorted(name for name in MODEL_PROMPTS if env.get(name))}, ensure_ascii=False, indent=2))
    if interactive and not args.yes and input("Continue? [y/N]: ").strip().lower() not in {"y", "yes"}:
        print("Cancelled before mutation.")
        return 2
    completed = subprocess.run(command, env=env, check=False)
    if completed.returncode == 0:
        print("\nInstaller completed. Simulation results are evidence of orchestration only; connect S100P/NAS before production acceptance.")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
