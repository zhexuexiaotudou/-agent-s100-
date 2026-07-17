#!/usr/bin/env python3
"""No-secret live auth/CSRF/role acceptance for the product access facade."""
from __future__ import annotations

import argparse
import http.client
import json
import secrets
import sys
from pathlib import Path
from urllib.parse import urlparse

APP_ROOT = Path("/opt/digua-ai-nas/app")
PROBE_ROOT = APP_ROOT / "scripts" / "probes"
sys.path.insert(0, str(PROBE_ROOT))
from ai_nas_identity import IdentityStore  # noqa: E402


def request(base_url: str, method: str, path: str, body: dict | None = None, *, cookie: str = "", csrf: str = "") -> tuple[int, dict, dict]:
    parsed = urlparse(base_url)
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=30)
    raw = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Accept": "application/json"}
    if raw is not None:
        headers["Content-Type"] = "application/json"
    if cookie:
        headers["Cookie"] = cookie
    if csrf:
        headers["X-CSRF-Token"] = csrf
    connection.request(method, path, body=raw, headers=headers)
    response = connection.getresponse()
    payload_raw = response.read()
    response_headers = dict(response.getheaders())
    connection.close()
    try:
        payload = json.loads(payload_raw.decode("utf-8")) if payload_raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = {}
    return response.status, response_headers, payload


def login(base_url: str, username: str, password: str) -> tuple[int, str, str, str]:
    status, headers, payload = request(base_url, "POST", "/api/v1/auth/login", {"username": username, "password": password})
    set_cookie = str(headers.get("Set-Cookie") or "")
    cookie = set_cookie.split(";", 1)[0]
    return status, cookie, str(payload.get("csrf_token") or ""), set_cookie


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1")
    parser.add_argument("--local-identity", type=Path, default=Path("/var/lib/digua-ai-nas/identity.sqlite3"))
    parser.add_argument("--upstream-identity", type=Path, default=Path("/mnt/nas/openclaw/reports/qwen25_ai_nas/identity.sqlite3"))
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    local = IdentityStore(args.local_identity)
    upstream = IdentityStore(args.upstream_identity)
    suffix = secrets.token_hex(5)
    users = {
        "admin": f"__digua_accept_admin_{suffix}",
        "operator": f"__digua_accept_operator_{suffix}",
        "viewer": f"__digua_accept_viewer_{suffix}",
    }
    passwords = {role: secrets.token_urlsafe(24) for role in users}
    checks: dict[str, bool | int | str] = {"no_secret_output": True}
    ok = False
    try:
        checks["seed_local_admin"] = bool(local.create_user(users["admin"], passwords["admin"], "admin").get("ok"))
        checks["seed_upstream_admin"] = bool(upstream.create_user(users["admin"], passwords["admin"], "admin").get("ok"))
        admin_status, admin_cookie, admin_csrf, admin_set_cookie = login(args.base_url, users["admin"], passwords["admin"])
        checks["admin_login_status"] = admin_status
        checks["admin_cookie_httponly"] = "digua_session=" in admin_set_cookie and "HttpOnly" in admin_set_cookie
        checks["admin_cookie_samesite"] = "SameSite=Lax" in admin_set_cookie
        checks["admin_csrf_issued"] = bool(admin_csrf)

        status, _, _ = request(args.base_url, "POST", "/api/v1/admin/users", {"username": users["operator"], "password": passwords["operator"], "role": "operator"}, cookie=admin_cookie)
        checks["missing_csrf_denied"] = status == 403
        status, _, _ = request(args.base_url, "POST", "/api/v1/admin/users", {"username": users["operator"], "password": passwords["operator"], "role": "operator"}, cookie=admin_cookie, csrf=admin_csrf)
        checks["admin_created_operator"] = status == 200
        status, _, _ = request(args.base_url, "POST", "/api/v1/admin/users", {"username": users["viewer"], "password": passwords["viewer"], "role": "viewer"}, cookie=admin_cookie, csrf=admin_csrf)
        checks["admin_created_viewer"] = status == 200
        upstream_roles = {item["username"]: item["role"] for item in upstream.list_users()}
        checks["users_mirrored_upstream"] = upstream_roles.get(users["operator"]) == "operator" and upstream_roles.get(users["viewer"]) == "viewer"

        operator_status, operator_cookie, operator_csrf, _ = login(args.base_url, users["operator"], passwords["operator"])
        checks["operator_login_status"] = operator_status
        status, _, _ = request(args.base_url, "GET", "/api/jobs/recent", cookie=operator_cookie)
        checks["operator_upstream_bridge_status"] = status
        checks["operator_upstream_bridge_accepted"] = status not in {401, 403, 503}
        status, _, _ = request(args.base_url, "POST", "/api/example", {}, cookie=operator_cookie)
        checks["operator_missing_csrf_denied"] = status == 403

        viewer_status, viewer_cookie, viewer_csrf, _ = login(args.base_url, users["viewer"], passwords["viewer"])
        checks["viewer_login_status"] = viewer_status
        status, _, payload = request(args.base_url, "POST", "/api/example", {}, cookie=viewer_cookie, csrf=viewer_csrf)
        checks["viewer_write_denied"] = status == 403 and payload.get("error") == "viewer_write_forbidden"
        status, _, _ = request(args.base_url, "GET", "/api/v1/admin/users", cookie=viewer_cookie)
        checks["viewer_admin_denied"] = status == 403

        status, _, _ = request(args.base_url, "POST", "/api/v1/admin/sessions/revoke", {"username": users["operator"]}, cookie=admin_cookie, csrf=admin_csrf)
        checks["admin_revoked_operator"] = status == 200
        status, _, payload = request(args.base_url, "GET", "/api/v1/auth/session", cookie=operator_cookie)
        checks["revoked_operator_session_invalid"] = status == 200 and not payload.get("authenticated")

        status, _, _ = request(args.base_url, "POST", "/api/v1/auth/logout", {}, cookie=admin_cookie, csrf=admin_csrf)
        checks["admin_logout_status"] = status
        status, _, payload = request(args.base_url, "GET", "/api/v1/auth/session", cookie=admin_cookie)
        checks["logout_session_invalid"] = status == 200 and not payload.get("authenticated")
        status, _, _ = request(args.base_url, "POST", "/api/identity/create-user", {"username": "blocked", "password": "not-used"})
        checks["public_user_create_denied"] = status == 403
        status, _, payload = request(args.base_url, "GET", "/api/v1/setup/status")
        checks["claim_ineligible_after_existing_users"] = status == 200 and payload.get("eligible") is False

        bool_checks = [value for key, value in checks.items() if isinstance(value, bool) and key != "no_secret_output"]
        ok = all(bool_checks) and all(checks.get(key) == 200 for key in ("admin_login_status", "operator_login_status", "viewer_login_status", "admin_logout_status"))
    finally:
        for username in users.values():
            local.delete_user(username)
            upstream.delete_user(username)

    payload = {"ok": ok, "gate": "product_access_live_auth_matrix", "production_verified": ok, "checks": checks, "temporary_users_removed": True, "secrets_emitted": False}
    encoded = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
