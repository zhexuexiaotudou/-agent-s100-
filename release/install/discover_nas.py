#!/usr/bin/env python3
"""Secret-free NAS discovery for the Digua first-run deployment guide.

The discovery surface is deliberately narrow: it inspects existing mounts,
passive neighbour/mDNS state and explicitly supplied hosts.  It never scans a
subnet, attempts credentials, mounts a share, or changes NAS/S100P state.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Callable


PORTS = {
    2049: "nfs",
    445: "smb",
    5000: "synology_http",
    5001: "nas_https",
    8080: "qnap_http",
    443: "https",
    80: "http",
}
HOST_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,251}[A-Za-z0-9])?$")


def safe_host(value: str) -> str | None:
    host = value.strip().strip("[]")
    if not host or any(char.isspace() for char in host):
        return None
    try:
        ipaddress.ip_address(host.split("%", 1)[0])
        return host
    except ValueError:
        return host if HOST_RE.fullmatch(host) else None


def run_text(command: list[str], timeout: float = 4.0) -> str:
    if not command or shutil.which(command[0]) is None:
        return ""
    try:
        completed = subprocess.run(
            command,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return completed.stdout if completed.returncode == 0 else ""


def parse_neighbours(text: str) -> list[str]:
    hosts: list[str] = []
    for line in text.splitlines():
        if re.search(r"\b(?:FAILED|INCOMPLETE)\b", line, re.IGNORECASE):
            continue
        first = line.split(maxsplit=1)[0] if line.split() else ""
        host = safe_host(first)
        if host:
            hosts.append(host)
    return list(dict.fromkeys(hosts))


def parse_avahi(text: str) -> list[str]:
    hosts: list[str] = []
    for line in text.splitlines():
        if not line.startswith("="):
            continue
        fields = line.split(";")
        for field in fields:
            # avahi's parsable output also contains numeric port fields.  Only
            # accept values that are shaped like an IPv4 or IPv6 address.
            if "." not in field and ":" not in field:
                continue
            host = safe_host(field)
            if not host:
                continue
            try:
                ipaddress.ip_address(host.split("%", 1)[0])
            except ValueError:
                continue
            hosts.append(host)
    return list(dict.fromkeys(hosts))


def parse_mounts(text: str) -> tuple[list[dict[str, str]], list[str]]:
    mounts: list[dict[str, str]] = []
    hosts: list[str] = []
    try:
        payload = json.loads(text) if text.strip() else {}
    except json.JSONDecodeError:
        return mounts, hosts
    for item in payload.get("filesystems", []):
        if not isinstance(item, dict):
            continue
        source = str(item.get("source") or "")
        fstype = str(item.get("fstype") or "")
        target = str(item.get("target") or "")
        host = source.split(":", 1)[0] if fstype.startswith("nfs") else ""
        if fstype == "cifs" and source.startswith("//"):
            host = source[2:].split("/", 1)[0]
        checked = safe_host(host) if host else None
        mounts.append({"source": source, "target": target, "fstype": fstype})
        if checked:
            hosts.append(checked)
    return mounts, list(dict.fromkeys(hosts))


def parse_nfs_exports(text: str) -> list[str]:
    exports: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("/"):
            continue
        export = stripped.split()[0]
        if re.fullmatch(r"/[A-Za-z0-9._/-]+", export):
            exports.append(export)
    return list(dict.fromkeys(exports))


def parse_smb_shares(text: str) -> list[str]:
    shares: list[str] = []
    for line in text.splitlines():
        fields = line.strip().split("|")
        if len(fields) < 2 or fields[0].lower() != "disk":
            continue
        name = fields[1].strip()
        if name and name.upper() != "IPC$" and re.fullmatch(r"[A-Za-z0-9._-]+", name):
            shares.append(name)
    return list(dict.fromkeys(shares))


def tcp_open(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def vendor_hint(services: list[str]) -> str:
    values = set(services)
    if "qnap_http" in values:
        return "qnap_or_compatible"
    if "synology_http" in values:
        return "synology_or_compatible"
    return "generic_nas"


def recommendation(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [
        item
        for item in candidates
        if {"nfs", "smb"}.intersection(item.get("services") or [])
    ]
    selected = usable[0] if len(usable) == 1 else None
    protocol = ""
    share = ""
    if selected:
        services = set(selected.get("services") or [])
        if "nfs" in services:
            protocol = "nfs"
            exports = selected.get("nfs_exports") or []
            preferred = [item for item in exports if "openclaw" in item.lower()]
            share = (preferred or exports or [""])[0]
        elif "smb" in services:
            protocol = "smb"
            shares = selected.get("smb_guest_shares") or []
            preferred = [item for item in shares if "openclaw" in item.lower()]
            share = (preferred or shares or [""])[0]
    return {
        "host": selected.get("host", "") if selected else "",
        "protocol": protocol,
        "share": share,
        "automatic_selection_safe": bool(selected),
    }


def discover(
    explicit_hosts: list[str] | None = None,
    timeout: float = 0.5,
    runner: Callable[[list[str], float], str] = run_text,
    connector: Callable[[str, int, float], bool] = tcp_open,
) -> dict[str, Any]:
    started = time.time()
    mount_text = runner(["findmnt", "-J", "-t", "nfs,nfs4,cifs", "-o", "SOURCE,TARGET,FSTYPE"], 4.0)
    mounts, mount_hosts = parse_mounts(mount_text)
    neighbour_hosts = parse_neighbours(runner(["ip", "neigh", "show"], 4.0))
    avahi_hosts = parse_avahi(runner(["avahi-browse", "-artp"], 6.0))
    requested = [host for value in (explicit_hosts or []) if (host := safe_host(value))]
    hosts = list(dict.fromkeys([*requested, *mount_hosts, *avahi_hosts, *neighbour_hosts]))[:16]

    candidates: list[dict[str, Any]] = []
    for host in hosts:
        open_ports = [port for port in PORTS if connector(host, port, timeout)]
        services = [PORTS[port] for port in open_ports]
        nfs_exports = parse_nfs_exports(runner(["showmount", "-e", host], 5.0)) if 2049 in open_ports else []
        smb_shares = parse_smb_shares(runner(["smbclient", "-g", "-N", "-L", host], 6.0)) if 445 in open_ports else []
        manager_urls = []
        for port, scheme in ((5001, "https"), (5000, "http"), (8080, "http"), (443, "https"), (80, "http")):
            if port in open_ports:
                manager_urls.append(f"{scheme}://{host}:{port}/")
        candidates.append(
            {
                "host": host,
                "source": "explicit" if host in requested else "passive_local_state",
                "open_ports": open_ports,
                "services": services,
                "vendor_hint": vendor_hint(services),
                "nfs_exports": nfs_exports,
                "smb_guest_shares": smb_shares,
                "manager_urls": manager_urls,
                "credentials_attempted": False,
            }
        )

    recommended = recommendation(candidates)
    required: list[str] = ["allowed_share_scope_confirmation"]
    if not recommended["host"]:
        required.append("nas_ip_or_hostname")
    if not recommended["protocol"]:
        required.append("enabled_nfs_or_smb_protocol")
    if not recommended["share"]:
        required.append("dedicated_export_or_share_name")
    if recommended["protocol"] == "smb":
        required.append("dedicated_smb_credentials_file")
    return {
        "ok": True,
        "schema": "digua_nas_discovery_v1",
        "generated_at_epoch": int(started),
        "discovery_status": "candidate_found" if candidates else "no_candidate",
        "candidates": candidates,
        "existing_mounts": mounts,
        "recommendation": recommended,
        "user_required": required,
        "safety": {
            "passive_or_explicit_hosts_only": True,
            "subnet_scan_performed": False,
            "credentials_attempted": False,
            "mount_performed": False,
            "state_changed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover NAS candidates without credentials or state changes.")
    parser.add_argument("--host", action="append", default=[], help="Probe an explicitly supplied NAS host in addition to passive candidates.")
    parser.add_argument("--timeout", type=float, default=0.5)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    payload = discover(args.host, max(0.1, min(args.timeout, 5.0)))
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
