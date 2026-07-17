#!/usr/bin/env python3
"""Interactive, secret-safe deployment guide for an S100P + NAS appliance."""
from __future__ import annotations

import argparse
import getpass
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from discover_nas import discover


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


def load_discovery(path: Path | None, explicit_host: str = "") -> dict[str, Any]:
    if path:
        payload = json.loads(path.read_text(encoding="utf-8"))
        safety = payload.get("safety") or {}
        if payload.get("schema") != "digua_nas_discovery_v1":
            raise ValueError("discovery JSON has an unsupported schema")
        if any(safety.get(key) is not False for key in ("credentials_attempted", "mount_performed", "state_changed")):
            raise ValueError("discovery JSON does not prove a read-only, credential-free run")
        return payload
    return discover([explicit_host] if explicit_host else [])


def show_discovery(payload: dict[str, Any]) -> None:
    print("\nRead-only NAS discovery (no login, mount, or subnet scan):")
    candidates = payload.get("candidates") or []
    if not candidates:
        print("  No NAS candidate was found. Enter the NAS IP/hostname manually.")
    for index, item in enumerate(candidates, start=1):
        services = ",".join(item.get("services") or []) or "no supported service detected"
        print(f"  {index}. {item.get('host')} [{item.get('vendor_hint')}] services={services}")
        if item.get("nfs_exports"):
            print(f"     NFS exports: {', '.join(item['nfs_exports'])}")
        if item.get("smb_guest_shares"):
            print(f"     guest-visible SMB shares: {', '.join(item['smb_guest_shares'])}")
    required = payload.get("user_required") or []
    if required:
        print("  User confirmation still required: " + ", ".join(required))


def candidate_defaults(payload: dict[str, Any], interactive: bool) -> tuple[str, str, str]:
    candidates = payload.get("candidates") or []
    recommended = payload.get("recommendation") or {}
    chosen = None
    if interactive and candidates:
        default = "1" if len(candidates) == 1 else ""
        selection = ask("Select NAS candidate number, or leave blank for manual entry", default, required=False)
        if selection:
            if not selection.isdigit() or not 1 <= int(selection) <= len(candidates):
                raise SystemExit("invalid NAS candidate selection")
            chosen = candidates[int(selection) - 1]
    elif recommended.get("automatic_selection_safe"):
        chosen = next((item for item in candidates if item.get("host") == recommended.get("host")), None)
    if not chosen:
        return str(recommended.get("host") or ""), str(recommended.get("protocol") or ""), str(recommended.get("share") or "")
    services = set(chosen.get("services") or [])
    protocol = "nfs" if "nfs" in services else ("smb" if "smb" in services else "")
    shares = chosen.get("nfs_exports") if protocol == "nfs" else chosen.get("smb_guest_shares")
    preferred = [item for item in (shares or []) if "openclaw" in str(item).lower()]
    share = str((preferred or shares or [""])[0])
    return str(chosen.get("host") or ""), protocol, share


def main() -> int:
    parser = argparse.ArgumentParser(description="Guided Digua AI-NAS clean installation")
    parser.add_argument("--config", type=Path, help="JSON answers for repeatable/non-interactive installs")
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--simulate-root", type=Path, help="Build a non-production clean install sandbox")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--discover-only", action="store_true", help="Print a secret-free NAS discovery report and exit")
    parser.add_argument("--discovery-json", type=Path, help="Use a previously reviewed digua_nas_discovery_v1 report")
    parser.add_argument(
        "--product-access",
        action="store_true",
        help="After a real install, enable LAN access and generate the one-time claim QR/access card",
    )
    args = parser.parse_args()
    cfg = load_config(args.config)
    interactive = not args.non_interactive

    def value(key: str, label: str, default: str = "", required: bool = True) -> str:
        configured = str(cfg.get(key) or os.environ.get(f"DIGUA_{key.upper()}") or os.environ.get(key) or default)
        return ask(label, configured, required) if interactive else configured

    print("\nDigua AI-NAS deployment guide")
    print("Stages: NAS discovery -> user scope approval -> verified mount -> model provider -> app/venv -> services -> admin bootstrap -> authenticated verification")
    if args.simulate_root:
        print("SIMULATION MODE: no S100P/NAS/systemd claim will be made.")

    configured_host = str(
        cfg.get("nas_host")
        or os.environ.get("DIGUA_NAS_HOST")
        or os.environ.get("nas_host")
        or ""
    )
    discovery_payload: dict[str, Any] = {}
    if args.discovery_json or args.discover_only or (interactive and not args.simulate_root):
        discovery_payload = load_discovery(args.discovery_json, configured_host)
        show_discovery(discovery_payload)
    if args.discover_only:
        print(json.dumps(discovery_payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    discovered_host, discovered_protocol, discovered_share = candidate_defaults(discovery_payload, interactive) if discovery_payload else ("", "", "")

    protocol = value("nas_protocol", "NAS protocol (nfs/smb)", discovered_protocol or "nfs")
    if protocol not in {"nfs", "smb", "cifs", "local"}:
        raise SystemExit(f"unsupported NAS protocol: {protocol}")
    nas_host = value("nas_host", "NAS IP/hostname", discovered_host, protocol != "local")
    share_default = discovered_share if not discovered_protocol or discovered_protocol == protocol else ""
    nas_share = value("nas_share", "Dedicated NAS export/share", share_default, protocol != "local")
    mount_point = value("mount_point", "S100P mount point", "/mnt/nas/openclaw")
    personal_root = value("personal_root", "Digua Personal root", f"{mount_point}/Personal")
    install_root = value("install_root", "Application install root", "/opt/digua-ai-nas")
    systemd_mode = value("systemd_mode", "systemd mode", "system")
    service_user = value("service_user", "Unprivileged service user", os.environ.get("SUDO_USER") or getpass.getuser())
    credentials_file = value("credentials_file", "Existing SMB credentials file (chmod 600)", "", protocol in {"smb", "cifs"})
    admin_username = value("admin_username", "Initial administrator username", "admin")
    password_env = str(cfg.get("password_env") or "DIGUA_ADMIN_PASSWORD")
    claim_mode = bool(cfg.get("claim_mode", True))
    password = os.environ.get(password_env, "")
    if not claim_mode and not password and interactive:
        password = getpass.getpass("Initial administrator password (min 8 chars; never written to report): ")
    if not claim_mode and not password:
        raise SystemExit(f"administrator password missing; set {password_env}")

    env = dict(os.environ)
    env[password_env] = password
    model_mode = value("model_mode", "Model provider (local/cloud)", "local").lower()
    if model_mode not in {"local", "cloud"}:
        raise SystemExit(f"unsupported model provider: {model_mode}")
    env["DIGUA_MODEL_MODE"] = model_mode
    model_values = cfg.get("models") if isinstance(cfg.get("models"), dict) else {}
    cloud_base_url = ""
    cloud_model = ""
    cloud_key_env = str(cfg.get("cloud_api_key_env") or "DIGUA_CLOUD_API_KEY")
    allow_insecure_cloud = bool(cfg.get("allow_insecure_cloud_endpoint", False))
    if bool(cfg.get("cloud_private_raw_egress", False)):
        raise SystemExit("cloud_private_raw_egress cannot be enabled by the deployment guide")
    if model_mode == "local":
        for name, label in MODEL_PROMPTS.items():
            default = str(model_values.get(name) or env.get(name) or "")
            required = name in {"DIGUA_QWEN_MODEL_DIR", "QWEN25_RUNTIME_BIN", "QWEN25_RUNTIME_CONFIG", "QWEN25_RUNTIME_LIB_DIR", "QWEN25_ACTIVE_HBM_PATH"}
            configured = ask(label, default, required) if interactive else default
            if required and not configured:
                raise SystemExit(f"required model setting missing: {name}")
            if configured:
                env[name] = configured
    else:
        cloud_base_url = value("cloud_base_url", "OpenAI-compatible API base URL", "")
        cloud_model = value("cloud_model", "Cloud model ID", "")
        if not cloud_base_url.startswith("https://") and not (allow_insecure_cloud and cloud_base_url.startswith("http://")):
            raise SystemExit("cloud API base URL must use HTTPS")
        cloud_key = env.get(cloud_key_env, "")
        if not cloud_key and interactive:
            cloud_key = getpass.getpass("Cloud API key (stored only in a protected S100P file): ")
        if not cloud_key:
            raise SystemExit(f"cloud API key missing; set {cloud_key_env}")
        env["DIGUA_CLOUD_API_KEY"] = cloud_key
        env["DIGUA_CLOUD_BASE_URL"] = cloud_base_url
        env["DIGUA_CLOUD_MODEL"] = cloud_model
        for name in ("DIGUA_CLIP_MODEL_DIR", "DIGUA_YOLO_MODEL_PATH", "DIGUA_OCR_MODEL_DIR", "DIGUA_ASR_MODEL_DIR"):
            if model_values.get(name):
                env[name] = str(model_values[name])

    installer = Path(__file__).with_name("install_s100p.sh")
    command = ["bash", str(installer), "--nas-protocol", protocol, "--nas-host", nas_host, "--nas-share", nas_share, "--mount-point", mount_point, "--personal-root", personal_root, "--install-root", install_root, "--systemd-mode", systemd_mode, "--service-user", service_user, "--admin-username", admin_username, "--password-env", password_env, "--model-mode", model_mode]
    if model_mode == "cloud":
        command += ["--cloud-base-url", cloud_base_url, "--cloud-model", cloud_model]
        if allow_insecure_cloud:
            command.append("--allow-insecure-cloud-endpoint")
    if credentials_file:
        command += ["--credentials-file", credentials_file]
    discovery_report: Path | None = None
    if discovery_payload:
        discovery_dir = (args.simulate_root / "tmp") if args.simulate_root else Path("/tmp")
        discovery_dir.mkdir(parents=True, exist_ok=True)
        fd, report_name = tempfile.mkstemp(prefix="digua-nas-discovery-", suffix=".json", dir=discovery_dir)
        discovery_report = Path(report_name)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(discovery_payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        command += ["--discovery-report", str(discovery_report)]
    if args.simulate_root:
        command += ["--simulate-root", str(args.simulate_root), "--skip-pip"]
    if args.dry_run:
        command.append("--dry-run")
    if protocol == "local":
        command.append("--allow-local-storage")
    if claim_mode:
        command.append("--defer-admin-claim")
    wheelhouse = str(cfg.get("wheelhouse") or "")
    if wheelhouse:
        command += ["--wheelhouse", wheelhouse]

    print("\nPre-flight summary (secrets redacted):")
    print(json.dumps({"protocol": protocol, "nas_host": nas_host, "nas_share": nas_share, "mount_point": mount_point, "personal_root": personal_root, "install_root": install_root, "systemd_mode": systemd_mode, "service_user": service_user, "simulation": bool(args.simulate_root), "claim_mode": claim_mode, "admin_username": None if claim_mode else admin_username, "discovery_used": bool(discovery_payload), "allowed_scope_requires_confirmation": True, "model_mode": model_mode, "cloud_base_url": cloud_base_url, "cloud_model": cloud_model, "cloud_api_key_present": bool(env.get("DIGUA_CLOUD_API_KEY")), "cloud_private_raw_egress": False, "model_paths_configured": sorted(name for name in MODEL_PROMPTS if env.get(name))}, ensure_ascii=False, indent=2))
    if interactive and not args.yes and input("Continue? [y/N]: ").strip().lower() not in {"y", "yes"}:
        print("Cancelled before mutation.")
        return 2
    try:
        completed = subprocess.run(command, env=env, check=False)
    finally:
        if discovery_report:
            discovery_report.unlink(missing_ok=True)
    if completed.returncode == 0:
        print("\nInstaller completed. Simulation results are evidence of orchestration only; connect S100P/NAS before production acceptance.")
        if args.product_access and not args.simulate_root and not args.dry_run:
            access_db = Path(env.get("DIGUA_ACCESS_DB", "/var/lib/digua-ai-nas/product_access.sqlite3"))
            identity_db = Path(env.get("DIGUA_IDENTITY_DB", "/var/lib/digua-ai-nas/identity.sqlite3"))
            configure_lan = Path(__file__).with_name("configure_lan_access.sh")
            product_python = Path(install_root) / "venv" / "bin" / "python"
            product_app = Path(install_root) / "app"
            post_steps = [
                ["bash", str(configure_lan), "--apply", "--install-root", install_root, "--access-db", str(access_db)],
                [str(product_python), "-m", "src.product_access.cli", "--access-db", str(access_db), "--identity-db", str(identity_db), "claim-create", "--qr-out", "/var/lib/digua-ai-nas/claim-qr.svg"],
                [str(product_python), "-m", "src.product_access.cli", "--access-db", str(access_db), "--identity-db", str(identity_db), "card", "--output", "/var/lib/digua-ai-nas/access-card.html"],
            ]
            for post_step in post_steps:
                post = subprocess.run(post_step, cwd=product_app if post_step[0] == str(product_python) else None, env=env, check=False)
                if post.returncode:
                    print(f"Product access finalization failed ({post.returncode}): {post_step[0]}", file=sys.stderr)
                    return post.returncode
            print("Product access is ready. Open http://digua.local/setup on the same LAN.")
        elif claim_mode:
            print("On the S100P console run: digua-access claim-create")
            print("Then open http://digua.local/setup from a phone on the same LAN.")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
