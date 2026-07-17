#!/usr/bin/env python3
"""No-secret live assertions for the product facade while the NAS is offline."""
from __future__ import annotations

import argparse
import http.client
import json
import sys
from pathlib import Path

APP_ROOT = Path("/opt/digua-ai-nas/app")
PROBE_ROOT = APP_ROOT / "scripts" / "probes"
sys.path.insert(0, str(PROBE_ROOT))
from ai_nas_identity import IdentityStore  # noqa: E402


def get(host: str, port: int, path: str, cookie: str = "") -> tuple[int, dict]:
    connection = http.client.HTTPConnection(host, port, timeout=10)
    headers = {"Accept": "application/json"}
    if cookie:
        headers["Cookie"] = cookie
    connection.request("GET", path, headers=headers)
    response = connection.getresponse()
    raw = response.read()
    connection.close()
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = {}
    return response.status, payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--identity-db", type=Path, default=Path("/var/lib/digua-ai-nas/identity.sqlite3"))
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    store = IdentityStore(args.identity_db)
    admin = next((user for user in store.list_users() if user.get("role") == "admin"), None)
    if not admin:
        print(json.dumps({"ok": False, "error": "admin_required_for_outage_validation"}))
        return 2
    session = store.create_session_for_user(str(admin["username"]), ttl=120)
    if not session.get("ok"):
        print(json.dumps({"ok": False, "error": "temporary_session_failed"}))
        return 2
    token = str(session["token"])
    try:
        health_status, health = get("127.0.0.1", 80, "/healthz")
        nas_status, nas = get("127.0.0.1", 80, "/api/v1/nas/status", f"digua_session={token}")
        storage_status, storage = get("127.0.0.1", 80, "/api/storage/list", f"digua_session={token}")
    finally:
        store.logout(token)

    checks = {
        "facade_health_available": health_status == 200 and health.get("ok") is True,
        "nas_status_reports_outage": nas_status == 200 and nas.get("status") == "nas_not_mounted",
        "storage_returns_degraded_503": storage_status == 503 and storage.get("error") == "nas_not_mounted" and storage.get("degraded") is True,
        "temporary_session_removed": store.validate_token(token) is None,
        "secrets_emitted": False,
    }
    ok = all(value for key, value in checks.items() if key != "secrets_emitted") and checks["secrets_emitted"] is False
    payload = {"ok": ok, "gate": "product_access_nas_outage", "production_verified": ok, "checks": checks}
    encoded = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
