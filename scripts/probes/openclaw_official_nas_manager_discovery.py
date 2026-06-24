from __future__ import annotations

import argparse
import json
import socket
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LINK_CONFIG = ROOT / "scripts" / "startup_link_check" / "link-check.config.json"
DEFAULT_PORTAL_CONFIG = ROOT / "configs" / "openclaw_nas_portal.local.json"
DEFAULT_PORTS = (8080, 5001, 80, 443, 8081, 8443, 5000)


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def tcp_open(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def http_probe(url: str, timeout: float) -> dict[str, Any]:
    context = ssl._create_unverified_context()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "OpenClaw-NAS-discovery"})
        with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
            sample = resp.read(512).decode("utf-8", "ignore").replace("\n", " ")[:240]
            return {
                "ok": True,
                "status": resp.status,
                "url": url,
                "final_url": resp.geturl(),
                "qnap_like": any(mark in sample.lower() for mark in ("qnap", "qts", "cgi-bin", "background:#007cef", "secure login")),
                "sample": sample,
            }
    except Exception as exc:  # noqa: BLE001 - discovery should report all failures compactly.
        return {"ok": False, "url": url, "error": type(exc).__name__, "detail": str(exc)[:160]}


def url_for(host: str, port: int) -> str:
    scheme = "https" if port in {443, 5001, 8081, 8443} else "http"
    return f"{scheme}://{host}:{port}/"


def remote_probe_via_ssh(user: str, host: str, key: str, nas_host: str, timeout: float, ports: list[int]) -> dict[str, Any]:
    remote_code = r"""
import json, socket, ssl, urllib.request
host = __HOST__
ports = __PORTS__
timeout = __TIMEOUT__
def url_for(host, port):
    return ('https' if port in {443, 5001, 8081, 8443} else 'http') + '://' + host + ':' + str(port) + '/'
def tcp_open(host, port):
    sock = socket.socket()
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()
def http_probe(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'OpenClaw-NAS-discovery'})
        with urllib.request.urlopen(req, timeout=timeout, context=ssl._create_unverified_context()) as resp:
            sample = resp.read(512).decode('utf-8', 'ignore').replace('\n', ' ')[:240]
            return {'ok': True, 'status': resp.status, 'url': url, 'final_url': resp.geturl(), 'qnap_like': any(x in sample.lower() for x in ('qnap','qts','cgi-bin','background:#007cef','secure login')), 'sample': sample}
    except Exception as exc:
        return {'ok': False, 'url': url, 'error': type(exc).__name__, 'detail': str(exc)[:160]}
tcp = [{'host': host, 'port': p, 'open': tcp_open(host, p)} for p in ports]
http = [http_probe(url_for(host, p)) for p in ports if any(row['port'] == p and row['open'] for row in tcp)]
print(json.dumps({'tcp': tcp, 'http': http}, ensure_ascii=False))
"""
    remote_code = remote_code.replace("__HOST__", json.dumps(nas_host))
    remote_code = remote_code.replace("__PORTS__", json.dumps(ports))
    remote_code = remote_code.replace("__TIMEOUT__", repr(timeout))
    cmd = [
        "ssh",
        "-i",
        key,
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={max(1, int(timeout + 1))}",
        "-o",
        "StrictHostKeyChecking=no",
        f"{user}@{host}",
        "python3 - <<'PY'\n" + remote_code + "\nPY",
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=max(8, int(timeout * len(ports) + 5)))
    if proc.returncode != 0:
        return {"ok": False, "error": proc.stderr.strip()[-500:] or proc.stdout.strip()[-500:]}
    try:
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"invalid_remote_json: {exc}", "stdout": proc.stdout[-500:]}
    payload["ok"] = True
    return payload


def choose_preferred(http_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    ok_rows = [row for row in http_rows if row.get("ok")]
    if not ok_rows:
        return None
    priority = (8080, 5001, 80, 443, 8081, 8443, 5000)
    for port in priority:
        for row in ok_rows:
            if f":{port}/" in row.get("url", ""):
                return row
    return ok_rows[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover the vendor NAS manager URL for OpenClaw NAS portal.")
    parser.add_argument("--link-config", type=Path, default=DEFAULT_LINK_CONFIG)
    parser.add_argument("--write-config", type=Path, default=None, help="Optional portal config JSON to write.")
    parser.add_argument("--local-port", type=int, default=18090)
    parser.add_argument("--timeout", type=float, default=1.5)
    args = parser.parse_args()

    cfg = load_json(args.link_config)
    s100p = cfg.get("s100p", {})
    nas = cfg.get("nas", {})
    ssh_host = str(s100p.get("host") or "")
    ssh_user = str(s100p.get("user") or "sunrise")
    ssh_key = str(s100p.get("sshKey") or "")
    nas_host = str(nas.get("ip") or "")
    if not nas_host:
        print(json.dumps({"ok": False, "error": "missing nas.ip in link config"}, ensure_ascii=False, indent=2))
        return 2

    ports = list(DEFAULT_PORTS)
    windows_tcp = [{"host": nas_host, "port": p, "open": tcp_open(nas_host, p, args.timeout)} for p in ports]
    windows_http = [http_probe(url_for(nas_host, p), args.timeout) for p in ports if any(row["port"] == p and row["open"] for row in windows_tcp)]
    remote: dict[str, Any] = {"ok": False, "error": "ssh_not_configured"}
    if ssh_host and ssh_key:
        remote = remote_probe_via_ssh(ssh_user, ssh_host, ssh_key, nas_host, args.timeout, ports)

    preferred_remote = choose_preferred(remote.get("http", []) if remote.get("ok") else [])
    preferred_windows = choose_preferred(windows_http)
    direct_url = preferred_windows.get("url") if preferred_windows else ""
    tunnel_url = f"http://127.0.0.1:{args.local_port}/" if preferred_remote else ""
    official_url = direct_url or tunnel_url
    result = {
        "ok": bool(official_url),
        "nas_host": nas_host,
        "s100p_host": ssh_host,
        "windows_direct": {"tcp": windows_tcp, "http": windows_http, "preferred": preferred_windows},
        "s100p_remote": remote,
        "preferred_remote": preferred_remote,
        "tunnel_required": bool(preferred_remote and not preferred_windows),
        "official_manager_url": official_url,
        "ssh_forward_command": (
            f"ssh -i {ssh_key} -N -L 127.0.0.1:{args.local_port}:{nas_host}:"
            f"{8080 if preferred_remote and ':8080/' in preferred_remote.get('url', '') else 5001} "
            f"{ssh_user}@{ssh_host}"
        )
        if preferred_remote and ssh_host and ssh_key
        else "",
    }

    if args.write_config and official_url:
        route = {
            "mode": "direct" if direct_url else "ssh_local_forward",
            "local_url": official_url,
            "local_port": args.local_port,
            "ssh_host": ssh_host,
            "ssh_user": ssh_user,
            "ssh_key": ssh_key.replace("\\", "/"),
            "nas_host": nas_host,
            "nas_http_port": 8080,
            "nas_https_port": 5001,
            "remote_http_url": f"http://{nas_host}:8080/",
            "remote_https_url": f"https://{nas_host}:5001/",
            "nas_export": nas.get("nfsExport", ""),
            "s100p_mount_point": nas.get("mountPoint", ""),
        }
        args.write_config.parent.mkdir(parents=True, exist_ok=True)
        args.write_config.write_text(
            json.dumps({"official_manager_url": official_url, "official_manager_route": route}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result["written_config"] = str(args.write_config)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
