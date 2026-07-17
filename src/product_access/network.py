from __future__ import annotations

import ipaddress
import json
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Callable


def _command(command: list[str], timeout: int = 8) -> dict:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
        return {"command": command, "ok": result.returncode == 0, "exit_code": result.returncode, "stdout": result.stdout[-12000:], "stderr": result.stderr[-4000:]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"command": command, "ok": False, "error": f"{type(exc).__name__}:{exc}"}


def is_lan_address(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
        return address.is_private or address.is_link_local or address.is_loopback
    except ValueError:
        return False


def inspect_network() -> dict:
    checks: list[dict] = []
    if platform.system() == "Linux":
        for command in (["ip", "-j", "address"], ["ip", "-j", "route"], ["resolvectl", "status"], ["nmcli", "-t", "connection", "show"]):
            if shutil.which(command[0]):
                checks.append(_command(list(command)))
    addresses: list[str] = []
    try:
        addresses = sorted({item[4][0] for item in socket.getaddrinfo(socket.gethostname(), None) if item[0] in {socket.AF_INET, socket.AF_INET6}})
    except OSError:
        pass
    return {
        "platform": platform.system(),
        "hostname": socket.gethostname(),
        "addresses": addresses,
        "digua_local": "http://digua.local/",
        "commands": checks,
        "read_only": True,
        "wifi": wifi_capability(),
    }


def wifi_capability() -> dict:
    if not shutil.which("nmcli"):
        return {"available": False, "reason": "nmcli_unavailable"}
    result = _command(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"])
    devices = []
    for line in str(result.get("stdout") or "").splitlines():
        parts = line.split(":", 2)
        if len(parts) == 3 and parts[1] == "wifi":
            devices.append({"device": parts[0], "state": parts[2]})
    return {"available": bool(devices), "devices": devices, "station_only": True, "soft_ap_enabled": False}


def scan_wifi() -> dict:
    capability = wifi_capability()
    if not capability.get("available"):
        return {"ok": False, "error": "wifi_station_unavailable", "capability": capability}
    result = _command(["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan", "yes"], timeout=20)
    networks = []
    for line in str(result.get("stdout") or "").splitlines():
        parts = line.rsplit(":", 2)
        if len(parts) == 3 and parts[0]:
            networks.append({"ssid": parts[0], "signal": parts[1], "security": parts[2]})
    return {"ok": bool(result.get("ok")), "networks": networks, "passwords_included": False}


def connect_wifi(ssid: str, password: str, *, confirm: str) -> dict:
    if confirm != "CONNECT WIFI":
        return {"ok": False, "error": "confirmation_required"}
    if not ssid or not password:
        return {"ok": False, "error": "ssid_and_password_required"}
    if not wifi_capability().get("available"):
        return {"ok": False, "error": "wifi_station_unavailable"}
    try:
        completed = subprocess.run(
            ["nmcli", "--ask", "device", "wifi", "connect", ssid],
            input=password + "\n", capture_output=True, text=True, timeout=45, check=False,
        )
        return {
            "ok": completed.returncode == 0,
            "exit_code": completed.returncode,
            "stdout": completed.stdout[-2000:],
            "stderr": completed.stderr[-2000:],
            "password_logged": False,
            "password_stored_in_sqlite": False,
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": f"{type(exc).__name__}:{exc}", "password_logged": False}


def validate_plan(payload: dict) -> dict:
    allowed = {"connection", "interface", "ipv4_method", "ipv4_address", "ipv4_gateway", "dns"}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        return {"ok": False, "error": "unsupported_network_fields", "fields": unknown}
    method = str(payload.get("ipv4_method") or "auto")
    if method not in {"auto", "manual"}:
        return {"ok": False, "error": "invalid_ipv4_method"}
    if method == "manual":
        try:
            ipaddress.ip_interface(str(payload.get("ipv4_address") or ""))
            if payload.get("ipv4_gateway"):
                ipaddress.ip_address(str(payload["ipv4_gateway"]))
        except ValueError:
            return {"ok": False, "error": "invalid_ipv4_configuration"}
    if not str(payload.get("connection") or "").strip():
        return {"ok": False, "error": "connection_required"}
    return {"ok": True, "plan": {key: payload[key] for key in allowed if key in payload}, "requires_confirmation": "APPLY NETWORK CHANGE"}


def nmcli_commands(plan: dict) -> list[list[str]]:
    connection = str(plan["connection"])
    commands = [["nmcli", "connection", "modify", connection, "ipv4.method", str(plan.get("ipv4_method") or "auto")]]
    for field, prop in (("ipv4_address", "ipv4.addresses"), ("ipv4_gateway", "ipv4.gateway"), ("dns", "ipv4.dns")):
        if field in plan:
            commands.append(["nmcli", "connection", "modify", connection, prop, str(plan[field])])
    commands.append(["nmcli", "connection", "up", connection])
    return commands


def apply_plan(plan: dict, *, confirm: str, runner: Callable[[list[str]], dict] = _command) -> dict:
    checked = validate_plan(plan)
    if not checked.get("ok"):
        return checked
    if confirm != "APPLY NETWORK CHANGE":
        return {"ok": False, "error": "confirmation_required", "plan": checked["plan"]}
    if not shutil.which("nmcli"):
        return {"ok": False, "error": "nmcli_unavailable", "commands": nmcli_commands(checked["plan"])}
    results = [runner(command) for command in nmcli_commands(checked["plan"])]
    return {"ok": all(item.get("ok") for item in results), "results": results}


def snapshot_connection(connection: str) -> dict:
    if not shutil.which("nmcli"):
        return {"ok": False, "error": "nmcli_unavailable", "connection": connection}
    result = _command([
        "nmcli", "--show-secrets", "no", "-g",
        "connection.id,connection.interface-name,ipv4.method,ipv4.addresses,ipv4.gateway,ipv4.dns",
        "connection", "show", connection,
    ])
    values = (result.get("stdout") or "").splitlines()
    if not result.get("ok") or len(values) < 6:
        return {"ok": False, "error": "network_snapshot_failed", "probe": result}
    return {
        "ok": True,
        "connection": values[0] or connection,
        "interface": values[1],
        "ipv4_method": values[2] or "auto",
        "ipv4_address": values[3],
        "ipv4_gateway": values[4],
        "dns": values[5],
        "secrets_included": False,
    }


def rollback_connection(state: dict, *, confirm: str, runner: Callable[[list[str]], dict] = _command) -> dict:
    if confirm != "ROLLBACK NETWORK CHANGE":
        return {"ok": False, "error": "confirmation_required"}
    plan = {key: state.get(key, "") for key in ("connection", "ipv4_method", "ipv4_address", "ipv4_gateway", "dns")}
    results = [runner(command) for command in nmcli_commands(plan)]
    return {"ok": all(item.get("ok") for item in results), "results": results, "restored_secrets": False}


def schedule_rollback(snapshot_id: str, access_db: str, seconds: int = 120) -> dict:
    binary = shutil.which("systemd-run")
    if not binary:
        return {"ok": False, "error": "systemd_run_unavailable", "manual_command": f"digua-access --access-db {access_db} network-rollback {snapshot_id} --confirm 'ROLLBACK NETWORK CHANGE'"}
    unit = f"digua-network-rollback-{snapshot_id[:12]}"
    command = [
        binary, "--unit", unit, f"--working-directory={Path(__file__).resolve().parents[2]}",
        "--on-active", f"{max(30, min(seconds, 900))}s",
        sys.executable, "-m", "src.product_access.cli", "--access-db", access_db,
        "network-rollback", snapshot_id, "--confirm", "ROLLBACK NETWORK CHANGE",
    ]
    result = _command(command)
    result["unit"] = unit
    return result
