from __future__ import annotations

import json
import shlex
import shutil
import subprocess
from pathlib import Path


def _run(command: list[str], timeout: int = 15) -> dict:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
        return {"ok": completed.returncode == 0, "exit_code": completed.returncode, "stdout": completed.stdout[-8000:], "stderr": completed.stderr[-4000:]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": f"{type(exc).__name__}:{exc}"}


class TailscaleServeAdapter:
    def __init__(self, target: str = "http://127.0.0.1:8781") -> None:
        self.target = target

    def inspect(self) -> dict:
        binary = shutil.which("tailscale")
        if not binary:
            return {"available": False, "enabled": False, "reason": "tailscale_cli_missing"}
        version = _run([binary, "version"])
        help_result = _run([binary, "serve", "--help"])
        status = _run([binary, "serve", "status", "--json"])
        parsed = None
        if status.get("ok"):
            try:
                parsed = json.loads(status.get("stdout") or "{}")
            except json.JSONDecodeError:
                parsed = None
        return {"available": True, "version": version, "serve_help_ok": help_result.get("ok"), "status": parsed, "raw_status": status}

    def plan(self) -> dict:
        return {
            "channel": "tailscale",
            "private_only": True,
            "funnel_allowed": False,
            "target": self.target,
            "preflight": ["tailscale version", "tailscale serve --help", "tailscale status --json"],
            "apply": ["tailscale", "serve", "--bg", self.target],
            "verify": ["tailscale", "serve", "status", "--json"],
            "rollback": ["tailscale", "serve", "reset"],
        }

    def apply(self, *, confirm: str) -> dict:
        if confirm != "ENABLE PRIVATE TAILSCALE SERVE":
            return {"ok": False, "error": "confirmation_required", "plan": self.plan()}
        binary = shutil.which("tailscale")
        if not binary:
            return {"ok": False, "error": "tailscale_cli_missing"}
        help_result = _run([binary, "serve", "--help"])
        if not help_result.get("ok"):
            return {"ok": False, "error": "tailscale_serve_help_failed", "details": help_result}
        return _run([binary, "serve", "--bg", self.target])

    def rollback(self, *, confirm: str) -> dict:
        if confirm != "DISABLE TAILSCALE SERVE":
            return {"ok": False, "error": "confirmation_required"}
        binary = shutil.which("tailscale")
        return _run([binary, "serve", "reset"]) if binary else {"ok": False, "error": "tailscale_cli_missing"}


class CloudflareTunnelAdapter:
    def __init__(self, hostname: str, tunnel_id: str, credentials_file: Path, target: str = "http://127.0.0.1:8781") -> None:
        self.hostname = hostname
        self.tunnel_id = tunnel_id
        self.credentials_file = Path(credentials_file)
        self.target = target

    def config_yaml(self) -> str:
        if not self.hostname or not self.tunnel_id:
            raise ValueError("cloudflare_hostname_and_tunnel_id_required")
        return (
            f"tunnel: {self.tunnel_id}\n"
            f"credentials-file: {self.credentials_file}\n"
            "ingress:\n"
            f"  - hostname: {self.hostname}\n"
            f"    service: {self.target}\n"
            "  - service: http_status:404\n"
        )

    def plan(self) -> dict:
        return {
            "channel": "cloudflare",
            "public_origin_port_exposed": False,
            "access_required": True,
            "target": self.target,
            "hostname": self.hostname,
            "credentials_file": str(self.credentials_file),
            "credentials_must_be_mode": "0600",
            "tunnel_secret_stored_in_database": False,
            "apply": "cloudflared tunnel --config /etc/cloudflared/digua.yml run",
            "rollback": "systemctl disable --now cloudflared.service",
        }

    def inspect(self) -> dict:
        binary = shutil.which("cloudflared")
        mode = None
        if self.credentials_file.exists():
            mode = oct(self.credentials_file.stat().st_mode & 0o777)
        return {
            "available": bool(binary),
            "credentials_present": self.credentials_file.is_file(),
            "credentials_mode": mode,
            "credentials_mode_safe": mode == "0o600",
            "plan": self.plan(),
        }


def shell_join(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)
