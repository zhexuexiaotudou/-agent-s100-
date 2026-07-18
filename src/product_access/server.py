from __future__ import annotations

import argparse
import html
import http.client
import json
import io
import os
import sqlite3
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE_ROOT = REPO_ROOT / "scripts" / "probes"
if str(PROBE_ROOT) not in sys.path:
    sys.path.insert(0, str(PROBE_ROOT))

from ai_nas_identity import IdentityStore  # noqa: E402

from .network import inspect_network, is_lan_address, scan_wifi, validate_plan  # noqa: E402
from .remote import CloudflareTunnelAdapter, TailscaleServeAdapter  # noqa: E402
from .security import (  # noqa: E402
    CloudflareJwtVerifier,
    clear_session_cookie,
    csrf_token,
    parse_session_cookie,
    session_cookie,
    valid_csrf,
)
from .store import ProductAccessStore  # noqa: E402

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
HOP_HEADERS = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers", "transfer-encoding", "upgrade"}
IDENTITY_HEADERS = {"tailscale-user-login", "tailscale-user-name", "tailscale-user-profile-pic", "cf-access-jwt-assertion", "cf-access-authenticated-user-email", "x-digua-remote-channel"}
VIEWER_POST_ALLOWLIST = {
    "/api/assistant/chat", "/api/copilot/chat", "/api/documents/query",
    "/api/ai-space/search", "/api/multimodal-search/query", "/api/person-attribute/search",
    "/api/token-budget/route", "/api/agent-runtime/rag/query",
}
NAS_DEPENDENT_PREFIXES = ("/api/storage/", "/api/media/", "/api/backup/", "/api/snapshot/", "/api/nas/", "/api/auto-organize/", "/api/ai-album/")
LOCAL_UI_ROUTES = {"/ui", "/ai-album"}
LOCAL_STATIC_ASSETS = {
    "/static/digua_ai_nas_v2.css": ("digua_ai_nas_v2.css", "text/css; charset=utf-8"),
    "/static/digua_ai_nas_v2.js": ("digua_ai_nas_v2.js", "application/javascript; charset=utf-8"),
    "/static/pwa-icon-192.svg": ("pwa-icon-192.svg", "image/svg+xml"),
    "/static/pwa-icon-512.svg": ("pwa-icon-512.svg", "image/svg+xml"),
}
UPSTREAM_IDENTITY_TIMEOUT_SECONDS = 0.35
UPSTREAM_BRIDGE_SESSION_TTL_SECONDS = 3600
UPSTREAM_BRIDGE_CACHE_SECONDS = 3300
UPSTREAM_BRIDGE_RETRY_DELAYS_SECONDS = (0.05, 0.15)
DEFAULT_UPSTREAM_TIMEOUT_SECONDS = 60
ASSISTANT_UPSTREAM_TIMEOUT_SECONDS = 240
LONG_RUNNING_UPSTREAM_ROUTES = {"/api/assistant/chat", "/api/copilot/chat"}


def _upstream_timeout_seconds(path: str) -> int:
    route = urlparse(path).path
    return ASSISTANT_UPSTREAM_TIMEOUT_SECONDS if route in LONG_RUNNING_UPSTREAM_ROUTES else DEFAULT_UPSTREAM_TIMEOUT_SECONDS


def _json_bytes(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def _setup_html(device_name: str) -> str:
    name = html.escape(device_name)
    return f"""<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><meta name=\"theme-color\" content=\"#16362e\"><title>认领 {name}</title><link rel=\"manifest\" href=\"/manifest.webmanifest\"><style>
    :root{{font-family:Inter,system-ui,sans-serif;color:#19302a;background:#f4f7f4}}body{{margin:0;min-height:100dvh;display:grid;place-items:center;padding:20px;box-sizing:border-box}}main{{box-sizing:border-box;width:min(520px,100%);background:#fff;border:1px solid #dce7e1;border-radius:24px;padding:30px;box-shadow:0 18px 60px #173b2d14}}h1{{font-size:clamp(28px,7vw,44px);margin:0 0 8px;letter-spacing:-.04em}}p{{line-height:1.65;color:#5a6c66}}label{{display:grid;gap:7px;margin:16px 0;font-weight:650}}input{{box-sizing:border-box;width:100%;font:inherit;padding:13px 14px;border:1px solid #bdcec6;border-radius:12px}}button{{width:100%;border:0;border-radius:12px;padding:14px;background:#16362e;color:#fff;font:inherit;font-weight:750;cursor:pointer}}small{{display:block;margin-top:16px;color:#667970}}#result{{min-height:24px;margin-top:14px}}a{{color:#16362e}}@media(max-width:420px){{body{{padding:12px}}main{{padding:24px 20px;border-radius:18px}}}}
    </style></head><body><main><p>地瓜 AI-NAS · 首次设置</p><h1>认领这台设备</h1><p>此操作仅允许在局域网、设备尚无用户且一次性认领码有效时执行。认领码不会保存在数据库明文中。</p><form id=\"claim\"><label>一次性认领码<input name=\"claim_token\" required autocomplete=\"one-time-code\"></label><label>管理员用户名<input name=\"username\" required autocomplete=\"username\"></label><label>管理员密码<input name=\"password\" type=\"password\" minlength=\"8\" required autocomplete=\"new-password\"></label><button>完成认领</button></form><div id=\"result\" role=\"status\"></div><small>已有账户？<a href=\"/ui\">返回工作台</a></small></main><script>
    const fragment=new URLSearchParams(location.hash.replace(/^#/,''));if(fragment.get('claim')){{claim.elements.claim_token.value=fragment.get('claim');history.replaceState(null,'',location.pathname)}}
    claim.addEventListener('submit',async e=>{{e.preventDefault();result.textContent='正在验证…';const body=Object.fromEntries(new FormData(claim));const r=await fetch('/api/v1/setup/claim',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});const d=await r.json();if(r.ok){{result.textContent='认领完成，正在进入工作台…';location.href='/ui'}}else result.textContent='未完成：'+(d.error||r.status)}});
    if('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(()=>{{}});
    </script></body></html>"""


def _settings_html(device_name: str) -> str:
    name = html.escape(device_name)
    return f"""<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>{name} · 访问设置</title><style>:root{{font-family:system-ui;color:#18332b;background:#f4f7f4}}body{{margin:0;padding:24px}}main{{max-width:760px;margin:auto}}header{{display:flex;justify-content:space-between;align-items:center;gap:16px}}a{{color:#174c3d}}section{{background:white;border:1px solid #dce7e1;border-radius:18px;padding:20px;margin:16px 0}}code{{overflow-wrap:anywhere}}.pill{{display:inline-block;border-radius:99px;padding:4px 9px;background:#e7f2ed}}li{{margin:10px 0}}</style></head><body><main><header><div><small>地瓜 AI-NAS</small><h1>访问设置</h1></div><a href=\"/ui\">返回工作台</a></header><section><h2>设备</h2><div id=\"device\">载入中…</div></section><section><h2>入口</h2><ul id=\"endpoints\"></ul><p>远程访问默认关闭。Tailscale 仅使用 Serve，禁止 Funnel；Cloudflare 必须启用 Access 且验证 JWT。</p></section><section><h2>诊断</h2><pre id=\"doctor\">载入中…</pre></section></main><script>const deviceNode=document.getElementById('device'),endpointList=document.getElementById('endpoints'),doctorNode=document.getElementById('doctor');Promise.all([fetch('/api/v1/device').then(r=>r.json()),fetch('/api/v1/endpoints').then(r=>r.json()),fetch('/api/v1/doctor').then(r=>r.json())]).then(([d,e,x])=>{{deviceNode.textContent=d.device.name+' · '+d.device.id;endpointList.replaceChildren();const items=e.endpoints||[];if(!items.length){{const empty=document.createElement('li');empty.textContent='尚无入口记录';endpointList.append(empty)}}else items.forEach(v=>{{const row=document.createElement('li'),badge=document.createElement('span'),url=document.createElement('code');badge.className='pill';badge.textContent=v.channel;url.textContent=v.url;row.append(badge,document.createTextNode(' '),url,document.createTextNode(' · '+(v.enabled?'已启用':'未启用')+' · '+(v.verified?'已实测':'待实测')));endpointList.append(row)}});doctorNode.textContent=JSON.stringify(x,null,2)}})</script></body></html>"""


class AccessState:
    def __init__(self, *, access_db: Path, identity_db: Path, upstream: str, channel: str, remote_enabled: bool = False, cf_team_domain: str = "", cf_audience: str = "", require_nas_mount: Path | None = None, upstream_identity_db: Path | None = None) -> None:
        self.store = ProductAccessStore(access_db)
        self.identity = IdentityStore(identity_db)
        self.require_nas_mount = Path(require_nas_mount) if require_nas_mount else None
        upstream_identity_path = Path(upstream_identity_db) if upstream_identity_db else None
        self.upstream_identity_path = upstream_identity_path if upstream_identity_path and upstream_identity_path.resolve() != Path(identity_db).resolve() else None
        self.upstream_identity = self._ensure_upstream_identity()
        self.bridge_sessions: dict[str, tuple[str, str, float]] = {}
        self.bridge_lock = threading.Lock()
        parsed = urlparse(upstream)
        self.upstream_host = parsed.hostname or "127.0.0.1"
        self.upstream_port = parsed.port or 8765
        self.channel = channel
        self.remote_enabled = remote_enabled
        self.cf_verifier = CloudflareJwtVerifier(cf_team_domain, cf_audience) if cf_team_domain and cf_audience else None
        self.claim_lock = threading.Lock()
        if not self.store.endpoints():
            self.store.set_endpoint("lan_mdns", "http://digua.local/", enabled=True, verified=False, details={"fallback": "device IPv4 address"})
            self.store.set_endpoint("tailscale", "private HTTPS URL assigned by Tailscale Serve", enabled=False, verified=False)
            self.store.set_endpoint("cloudflare", "optional Access-protected hostname", enabled=False, verified=False)

    def users(self) -> list[dict]:
        return self.identity.list_users()

    def user_for_token(self, token: str | None) -> dict | None:
        return self.identity.validate_token(token) if token else None

    def _ensure_upstream_identity(self) -> IdentityStore | None:
        current = getattr(self, "upstream_identity", None)
        if current:
            return current
        path = getattr(self, "upstream_identity_path", None)
        if not path or (self.require_nas_mount and self.nas_mounted() is not True):
            return None
        try:
            self.upstream_identity = IdentityStore(path, connection_timeout=UPSTREAM_IDENTITY_TIMEOUT_SECONDS)
        except (OSError, sqlite3.Error):
            return None
        return self.upstream_identity

    def upstream_token(self, local_token: str, user: dict) -> str | None:
        upstream = self._ensure_upstream_identity()
        if not upstream:
            if self.upstream_identity_path:
                return None
            return local_token
        with self.bridge_lock:
            cached = self.bridge_sessions.get(local_token)
            if cached and cached[0] == str(user["username"]) and cached[2] > time.monotonic():
                return cached[1]
            self.bridge_sessions.pop(local_token, None)
            created = None
            for attempt in range(len(UPSTREAM_BRIDGE_RETRY_DELAYS_SECONDS) + 1):
                try:
                    created = upstream.create_session_for_user(
                        str(user["username"]), ttl=UPSTREAM_BRIDGE_SESSION_TTL_SECONDS
                    )
                    break
                except sqlite3.OperationalError as exc:
                    busy = "locked" in str(exc).lower() or "busy" in str(exc).lower()
                    if not busy or attempt >= len(UPSTREAM_BRIDGE_RETRY_DELAYS_SECONDS):
                        return None
                    time.sleep(UPSTREAM_BRIDGE_RETRY_DELAYS_SECONDS[attempt])
                except (OSError, sqlite3.Error):
                    return None
            if not created:
                return None
            if not created.get("ok"):
                return None
            token = str(created["token"])
            self.bridge_sessions[local_token] = (
                str(user["username"]),
                token,
                time.monotonic() + UPSTREAM_BRIDGE_CACHE_SECONDS,
            )
            return token

    def drop_bridge(self, local_token: str) -> None:
        upstream = self._ensure_upstream_identity()
        if not upstream:
            return
        with self.bridge_lock:
            cached = self.bridge_sessions.pop(local_token, None)
        if cached:
            try:
                upstream.logout(cached[1])
            except (OSError, sqlite3.Error):
                pass

    def create_user(self, username: str, password: str, role: str) -> dict:
        result = self.identity.create_user(username, password, role)
        if not result.get("ok"):
            return result
        upstream = self._ensure_upstream_identity()
        if not upstream:
            if self.upstream_identity_path:
                self.identity.delete_user(username)
                return {"ok": False, "error": "upstream_identity_bridge_unavailable"}
            return result
        mirrored = upstream.create_user(username, password, role)
        if not mirrored.get("ok"):
            self.identity.delete_user(username)
            return {"ok": False, "error": "upstream_identity_mirror_failed", "detail": mirrored.get("error")}
        return result

    def set_user_role(self, username: str, role: str) -> dict:
        local_before = next((item["role"] for item in self.identity.list_users() if item["username"] == username), None)
        result = self.identity.set_user_role(username, role)
        if not result.get("ok"):
            return result
        upstream = self._ensure_upstream_identity()
        if not upstream:
            if self.upstream_identity_path and local_before:
                self.identity.set_user_role(username, str(local_before))
                return {"ok": False, "error": "upstream_identity_bridge_unavailable", "local_role_rolled_back": True}
            return result
        mirrored = upstream.set_user_role(username, role)
        if mirrored.get("ok"):
            return result
        if local_before:
            self.identity.set_user_role(username, str(local_before))
        return {"ok": False, "error": "upstream_role_mirror_failed", "detail": mirrored.get("error"), "local_role_rolled_back": bool(local_before)}

    def revoke_user_sessions(self, username: str) -> dict:
        result = self.identity.revoke_user_sessions(username)
        upstream = self._ensure_upstream_identity()
        if upstream:
            mirrored = upstream.revoke_user_sessions(username)
            if not mirrored.get("ok"):
                return {"ok": False, "error": "upstream_session_revoke_failed", "detail": mirrored.get("error")}
            with self.bridge_lock:
                self.bridge_sessions = {key: value for key, value in self.bridge_sessions.items() if value[0] != username}
        return result

    def doctor(self) -> dict:
        tailscale = TailscaleServeAdapter().inspect()
        cf = CloudflareTunnelAdapter("<hostname>", "<tunnel-id>", Path("/etc/cloudflared/digua-credentials.json")).inspect()
        return {
            "verdict": "offline_code_ready_device_execution_pending",
            "production_verified": False,
            "device_power_state": "not_observed",
            "checks": {
                "identity_db": self.identity.db_path.exists(),
                "upstream_identity_bridge": {"configured": self.upstream_identity_path is not None, "available": bool(self._ensure_upstream_identity())},
                "access_db": self.store.path.exists(),
                "backend_loopback": self.upstream_host in {"127.0.0.1", "localhost", "::1"},
                "remote_ingress_enabled": self.remote_enabled,
                "nas_mount": {"required": str(self.require_nas_mount) if self.require_nas_mount else None, "mounted": self.nas_mounted()},
                "tailscale": tailscale,
                "cloudflare": cf,
            },
            "network": inspect_network(),
        }

    def nas_mounted(self) -> bool | None:
        if not self.require_nas_mount:
            return None
        try:
            return self.require_nas_mount.exists() and self.require_nas_mount.is_mount()
        except OSError:
            return False


class ProductAccessHandler(BaseHTTPRequestHandler):
    server_version = "DiguaProductAccess"
    sys_version = ""

    @property
    def state(self) -> AccessState:
        return self.server.state  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), fmt % args))

    def _channel(self) -> str:
        if self.state.channel == "remote":
            return "remote"
        return "lan" if is_lan_address(self.client_address[0]) else "untrusted"

    def _secure(self) -> bool:
        return self._channel() == "remote"

    def _send(self, status: int, body: bytes, content_type: str, headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
        )
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload: dict, status: int = HTTPStatus.OK, headers: dict[str, str] | None = None) -> None:
        self._send(status, _json_bytes(payload), "application/json; charset=utf-8", headers)

    def _read_json(self) -> tuple[dict | None, str | None]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > 1024 * 1024:
                return None, "invalid_content_length"
            value = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            return (value, None) if isinstance(value, dict) else (None, "json_object_required")
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            return None, "invalid_json"

    def _session(self) -> tuple[str | None, dict | None]:
        token = parse_session_cookie(self.headers.get("Cookie"), secure=self._secure())
        return token, self.state.user_for_token(token)

    def _require_user(self, *, admin: bool = False) -> tuple[str, dict] | None:
        token, user = self._session()
        if not token or not user:
            self._json({"ok": False, "error": "auth_required"}, HTTPStatus.UNAUTHORIZED)
            return None
        if admin and user.get("role") != "admin":
            self._json({"ok": False, "error": "admin_required"}, HTTPStatus.FORBIDDEN)
            return None
        return token, user

    def _csrf_ok(self, token: str) -> bool:
        if valid_csrf(token, self.headers.get("X-CSRF-Token")):
            return True
        self._json({"ok": False, "error": "csrf_validation_failed"}, HTTPStatus.FORBIDDEN)
        return False

    def _remote_identity_session(self) -> tuple[str | None, dict | None, str | None]:
        if self._channel() != "remote" or not self.state.remote_enabled:
            return None, None, None
        provider = ""
        subject = ""
        assertion = self.headers.get("Cf-Access-Jwt-Assertion")
        if assertion:
            provider = "cloudflare"
            if not self.state.cf_verifier:
                return None, None, "cloudflare_jwt_verifier_not_configured"
            verified = self.state.cf_verifier.verify(assertion)
            if not verified.get("ok"):
                return None, None, str(verified.get("error"))
            subject = str(verified["subject"])
        else:
            subject = str(self.headers.get("Tailscale-User-Login") or "").strip().lower()
            provider = "tailscale" if subject else ""
        if not provider or not subject:
            return None, None, "remote_identity_missing"
        username = self.state.store.mapped_user(provider, subject)
        if not username:
            return None, None, "remote_identity_not_mapped"
        created = self.state.identity.create_session_for_user(username, ttl=3600)
        if not created.get("ok"):
            return None, None, str(created.get("error"))
        self.state.store.audit(username, "remote_identity_login", provider, "allowed", {"subject": subject})
        return str(created["token"]), dict(created["user"]), None

    def _api_get(self, route: str) -> bool:
        if route in {"/api/v1/status", "/api/v1/access/status"}:
            self._json({"ok": True, "device": self.state.store.device(), "claimed": bool(self.state.users()), "channel": self._channel(), "production_verified": False})
        elif route == "/api/v1/system/health":
            self._json({"ok": True, "status": "degraded" if not self.state.users() else "running", "details_redacted": True})
        elif route == "/api/v1/system/readiness":
            self._json({"ok": bool(self.state.users()), "ready": bool(self.state.users()), "reason": None if self.state.users() else "first_claim_pending"}, HTTPStatus.OK if self.state.users() else HTTPStatus.SERVICE_UNAVAILABLE)
        elif route == "/api/v1/device":
            self._json({"ok": True, "device": self.state.store.device()})
        elif route in {"/api/v1/endpoints", "/api/v1/access/endpoints"}:
            if not self._require_user(): return True
            self._json({"ok": True, "endpoints": self.state.store.endpoints()})
        elif route == "/api/v1/access/qr":
            if not self._require_user(): return True
            import qrcode
            from qrcode.image.svg import SvgPathImage
            mode = str(parse_qs(urlparse(self.path).query).get("mode", ["lan"])[0])
            channel = {"lan": "lan_mdns", "tailscale": "tailscale", "cloudflare": "cloudflare"}.get(mode)
            endpoint = next((item for item in self.state.store.endpoints() if item["channel"] == channel), None)
            if not endpoint:
                self._json({"ok": False, "error": "endpoint_not_configured"}, HTTPStatus.NOT_FOUND); return True
            output = io.BytesIO(); qrcode.make(endpoint["url"], image_factory=SvgPathImage).save(output)
            self._send(HTTPStatus.OK, output.getvalue(), "image/svg+xml", {"Content-Disposition": f"inline; filename=digua-{mode}-qr.svg"}); return True
        elif route in {"/api/v1/claim/status", "/api/v1/setup/status"}:
            self._json({"ok": True, "claim": self.state.store.claim_status(), "eligible": self._channel() == "lan" and not self.state.users()})
        elif route in {"/api/v1/auth/session", "/api/v1/auth/me"}:
            token, user = self._session()
            headers: dict[str, str] = {}
            if not user:
                token, user, remote_error = self._remote_identity_session()
                if remote_error:
                    self._json({"ok": False, "authenticated": False, "error": remote_error}, HTTPStatus.UNAUTHORIZED)
                    return True
                if token:
                    headers["Set-Cookie"] = session_cookie(token, secure=True, max_age=3600)
            self._json({"ok": True, "authenticated": bool(user), "user": user, "csrf_token": csrf_token(token) if token and user else None}, headers=headers)
        elif route in {"/api/v1/users", "/api/v1/admin/users"}:
            if not self._require_user(admin=True): return True
            self._json({"ok": True, "users": self.state.users(), "mappings": self.state.store.mappings()})
        elif route == "/api/v1/audit":
            if not self._require_user(admin=True): return True
            self._json({"ok": True, "events": self.state.store.recent_audit()})
        elif route in {"/api/v1/network/status", "/api/v1/network/interfaces"}:
            if not self._require_user(admin=True): return True
            self._json({"ok": True, "network": inspect_network()})
        elif route == "/api/v1/nas/status":
            if not self._require_user(): return True
            mounted = self.state.nas_mounted()
            self._json({"ok": mounted is not False, "status": "mounted" if mounted is True else "not_configured" if mounted is None else "nas_not_mounted", "nas_root_exposed": False, "production_verified": False})
        elif route == "/api/v1/network/wifi/networks":
            if not self._require_user(admin=True): return True
            self._json(scan_wifi())
        elif route in {"/api/v1/remote/status", "/api/v1/access/tailscale/status"}:
            if not self._require_user(admin=True): return True
            self._json({"ok": True, "enabled": self.state.remote_enabled, "tailscale": TailscaleServeAdapter().inspect(), "endpoints": self.state.store.endpoints()})
        elif route == "/api/v1/access/cloudflare/status":
            if not self._require_user(admin=True): return True
            self._json({"ok": True, "enabled": self.state.remote_enabled, "jwt_validation_configured": self.state.cf_verifier is not None, "status": "configured_but_external_validation_pending"})
        elif route == "/api/v1/doctor":
            if not self._require_user(admin=True): return True
            self._json({"ok": True, **self.state.doctor()})
        else:
            return False
        return True

    def _api_post(self, route: str) -> bool:
        payload, error = self._read_json()
        if error:
            self._json({"ok": False, "error": error}, HTTPStatus.BAD_REQUEST); return True
        payload = payload or {}
        channel = self._channel()
        if route in {"/api/v1/claim/complete", "/api/v1/setup/claim"}:
            if channel != "lan":
                self._json({"ok": False, "error": "claim_lan_only"}, HTTPStatus.FORBIDDEN); return True
            with self.state.claim_lock:
                if self.state.users():
                    self._json({"ok": False, "error": "device_already_claimed"}, HTTPStatus.CONFLICT); return True
                claim = str(payload.get("claim_token") or "")
                username = str(payload.get("username") or "").strip()
                password = str(payload.get("password") or "")
                if not username or len(password) < 8:
                    self._json({"ok": False, "error": "username_and_strong_password_required", "minimum_password_length": 8}, HTTPStatus.BAD_REQUEST); return True
                if not self.state.store.redeem_claim(claim):
                    self.state.store.audit("anonymous", "claim", channel, "denied")
                    self._json({"ok": False, "error": "invalid_or_expired_claim"}, HTTPStatus.FORBIDDEN); return True
                result = self.state.create_user(username, password, "admin")
                if not result.get("ok"):
                    self._json(result, HTTPStatus.BAD_REQUEST); return True
                login = self.state.identity.login(username, password)
                self.state.store.audit(username, "claim", channel, "allowed")
                token = str(login.get("token") or "")
                self._json({"ok": True, "user": login.get("user"), "csrf_token": csrf_token(token)}, headers={"Set-Cookie": session_cookie(token, secure=False)})
            return True
        if route in {"/api/v1/auth/login", "/api/identity/login"}:
            result = self.state.identity.login(str(payload.get("username") or ""), str(payload.get("password") or ""))
            if not result.get("ok"):
                self.state.store.audit(str(payload.get("username") or ""), "login", channel, "denied")
                self._json(result, HTTPStatus.UNAUTHORIZED); return True
            token = str(result.pop("token"))
            result["csrf_token"] = csrf_token(token)
            self.state.store.audit(str(result["user"]["username"]), "login", channel, "allowed")
            self._json(result, headers={"Set-Cookie": session_cookie(token, secure=self._secure())}); return True
        if route == "/api/v1/auth/logout":
            required = self._require_user()
            if not required: return True
            token, user = required
            if not self._csrf_ok(token): return True
            self.state.identity.logout(token)
            self.state.drop_bridge(token)
            self.state.store.audit(str(user["username"]), "logout", channel, "allowed")
            self._json({"ok": True}, headers={"Set-Cookie": clear_session_cookie(secure=self._secure())}); return True
        required = self._require_user(admin=True)
        if not required: return True
        token, user = required
        if not self._csrf_ok(token): return True
        if route in {"/api/v1/users", "/api/v1/admin/users"}:
            result = self.state.create_user(str(payload.get("username") or ""), str(payload.get("password") or ""), str(payload.get("role") or "viewer"))
        elif route in {"/api/v1/users/role", "/api/v1/admin/users/role"}:
            result = self.state.set_user_role(str(payload.get("username") or ""), str(payload.get("role") or ""))
        elif route == "/api/v1/admin/sessions/revoke":
            result = self.state.revoke_user_sessions(str(payload.get("username") or ""))
        elif route == "/api/v1/identity-mappings":
            try:
                self.state.store.map_identity(str(payload.get("provider") or ""), str(payload.get("subject") or ""), str(payload.get("username") or "")); result = {"ok": True}
            except ValueError as exc: result = {"ok": False, "error": str(exc)}
        elif route == "/api/v1/network/plan":
            result = validate_plan(payload)
        elif route in {"/api/v1/network/wifi/test", "/api/v1/network/wifi/apply"}:
            result = {"ok": False, "error": "root_network_agent_required", "password_logged": False, "next_command": "digua-access wifi-connect --ssid '<SSID>' --confirm 'CONNECT WIFI' (password is prompted without echo)"}
        elif route in {"/api/v1/access/tailscale/enable", "/api/v1/access/tailscale/test"}:
            adapter = TailscaleServeAdapter()
            result = adapter.apply(confirm=str(payload.get("confirm") or "")) if route.endswith("enable") else {"ok": True, "plan": adapter.plan(), "inspection": adapter.inspect(), "production_verified": False}
        elif route == "/api/v1/access/tailscale/disable":
            result = TailscaleServeAdapter().rollback(confirm=str(payload.get("confirm") or ""))
        elif route == "/api/v1/access/cloudflare/configure":
            if any(key.lower() in {"token", "credential", "credentials", "secret", "password", "private_key"} for key in payload):
                result = {"ok": False, "error": "secrets_not_accepted_by_api"}
            else:
                hostname = str(payload.get("hostname") or "")
                self.state.store.set_endpoint("cloudflare", "https://" + hostname if hostname else "optional Access-protected hostname", enabled=False, verified=False, details={"access_policy_required": True})
                result = {"ok": bool(hostname), "status": "configured_but_external_validation_pending" if hostname else "not_configured", "external_secret_install": "root_only_file_required"}
        elif route in {"/api/v1/access/cloudflare/enable", "/api/v1/access/cloudflare/disable", "/api/v1/access/cloudflare/test"}:
            result = {"ok": route.endswith("test"), "status": "configured_but_external_validation_pending", "root_helper_required": True, "next_command": "release/install/configure_remote_access.sh --provider cloudflare --dry-run"}
        elif route == "/api/v1/access/test":
            result = {"ok": True, "channel": channel, "upstream": "loopback", "production_verified": False}
        else:
            return False
        self.state.store.audit(str(user["username"]), route.removeprefix("/api/v1/"), channel, "allowed" if result.get("ok") else "denied")
        self._json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST)
        return True

    def _proxy(self) -> None:
        length = 0
        if self.headers.get("Transfer-Encoding"):
            self._json({"ok": False, "error": "chunked_request_not_supported"}, HTTPStatus.LENGTH_REQUIRED); return
        if self.command in MUTATING_METHODS:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._json({"ok": False, "error": "invalid_content_length"}, HTTPStatus.BAD_REQUEST); return
            if length < 0 or length > 2 * 1024 * 1024 * 1024:
                self._json({"ok": False, "error": "request_too_large"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE); return
        token, user = self._session()
        route = urlparse(self.path).path
        if self.state.require_nas_mount and route.startswith(NAS_DEPENDENT_PREFIXES) and self.state.nas_mounted() is not True:
            self._json({"ok": False, "error": "nas_not_mounted", "degraded": True}, HTTPStatus.SERVICE_UNAVAILABLE); return
        if self.command in MUTATING_METHODS and user and user.get("role") == "viewer" and urlparse(self.path).path not in VIEWER_POST_ALLOWLIST:
            self._json({"ok": False, "error": "viewer_write_forbidden"}, HTTPStatus.FORBIDDEN); return
        if self.command in MUTATING_METHODS and token and user and not valid_csrf(token, self.headers.get("X-CSRF-Token")):
            self._json({"ok": False, "error": "csrf_validation_failed"}, HTTPStatus.FORBIDDEN); return
        if self.path.startswith("/api/identity/create-user"):
            if not user or user.get("role") != "admin":
                self._json({"ok": False, "error": "use_lan_claim_or_admin_api"}, HTTPStatus.FORBIDDEN); return
        headers: dict[str, str] = {}
        for key, value in self.headers.items():
            lower = key.lower()
            if lower in HOP_HEADERS or lower in IDENTITY_HEADERS or lower in {"authorization", "cookie", "host", "content-length", "forwarded"} or lower.startswith("x-forwarded-"):
                continue
            headers[key] = value
        if token and user:
            upstream_token = self.state.upstream_token(token, user)
            if not upstream_token:
                self._json({"ok": False, "error": "upstream_identity_bridge_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE); return
            headers["Authorization"] = "Bearer " + upstream_token
        headers["Host"] = f"{self.state.upstream_host}:{self.state.upstream_port}"
        headers["Content-Length"] = str(length)
        connection = http.client.HTTPConnection(
            self.state.upstream_host,
            self.state.upstream_port,
            timeout=_upstream_timeout_seconds(self.path),
        )
        response_started = False
        try:
            connection.putrequest(self.command, self.path, skip_host=True, skip_accept_encoding=True)
            for key, value in headers.items():
                connection.putheader(key, value)
            connection.endheaders()
            remaining = length
            while remaining:
                chunk = self.rfile.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise ConnectionError("request_body_truncated")
                connection.send(chunk)
                remaining -= len(chunk)
            response = connection.getresponse()
            self.send_response(response.status)
            response_length = response.getheader("Content-Length")
            for key, value in response.getheaders():
                if key.lower() not in HOP_HEADERS | {"content-length", "set-cookie"}:
                    self.send_header(key, value)
            if response_length is not None:
                self.send_header("Content-Length", response_length)
            self.end_headers()
            response_started = True
            while chunk := response.read(1024 * 1024):
                self.wfile.write(chunk)
        except (OSError, http.client.HTTPException, ConnectionError) as exc:
            if response_started or self.wfile.closed:
                return
            self._json({"ok": False, "error": "portal_upstream_unavailable", "detail": type(exc).__name__}, HTTPStatus.BAD_GATEWAY)
        finally:
            connection.close()

    def do_GET(self) -> None:
        route = urlparse(self.path).path
        if route == "/healthz":
            self._json({"ok": True, "service": "digua-product-access", "details_redacted": True}); return
        if route == "/readyz":
            ready = bool(self.state.users())
            self._json({"ok": ready, "ready": ready, "reason": None if ready else "first_claim_pending"}, HTTPStatus.OK if ready else HTTPStatus.SERVICE_UNAVAILABLE); return
        if route.startswith("/api/v1/"):
            if self._api_get(route): return
            self._json({"ok": False, "error": "api_route_not_found"}, HTTPStatus.NOT_FOUND); return
        if route in LOCAL_UI_ROUTES:
            asset = REPO_ROOT / "web" / "ai_nas_desktop_v2.html"
            self._send(HTTPStatus.OK, asset.read_bytes(), "text/html; charset=utf-8"); return
        if route in LOCAL_STATIC_ASSETS:
            filename, content_type = LOCAL_STATIC_ASSETS[route]
            asset = REPO_ROOT / "web" / "static" / filename
            self._send(HTTPStatus.OK, asset.read_bytes(), content_type); return
        if route == "/setup":
            self._send(HTTPStatus.OK, _setup_html(self.state.store.device()["name"]).encode("utf-8"), "text/html; charset=utf-8"); return
        if route == "/settings/access":
            self._send(HTTPStatus.OK, _settings_html(self.state.store.device()["name"]).encode("utf-8"), "text/html; charset=utf-8"); return
        if route == "/manifest.webmanifest":
            self._send(HTTPStatus.OK, _json_bytes({"name": "地瓜 AI-NAS", "short_name": "地瓜 NAS", "lang": "zh-CN", "start_url": "/ui", "display": "standalone", "background_color": "#f4f7f4", "theme_color": "#16362e", "icons": [{"src": "/static/pwa-icon-192.svg", "sizes": "192x192", "type": "image/svg+xml", "purpose": "any maskable"}, {"src": "/static/pwa-icon-512.svg", "sizes": "512x512", "type": "image/svg+xml", "purpose": "any maskable"}]}), "application/manifest+json; charset=utf-8"); return
        if route == "/pwa-icon.svg":
            icon = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'><rect width='64' height='64' rx='16' fill='#16362e'/><path d='M16 31 32 17l16 14v17H16Z' fill='none' stroke='white' stroke-width='5'/><circle cx='32' cy='38' r='5' fill='#dcff78'/></svg>"
            self._send(HTTPStatus.OK, icon.encode(), "image/svg+xml"); return
        if route == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT); self.send_header("Cache-Control", "public, max-age=86400"); self.end_headers(); return
        if route == "/sw.js":
            sw = "const C='digua-shell-v3',A=['/ui','/manifest.webmanifest','/static/pwa-icon-192.svg','/static/pwa-icon-512.svg','/static/digua_ai_nas_v2.css','/static/digua_ai_nas_v2.js'];self.addEventListener('install',e=>e.waitUntil(caches.open(C).then(c=>c.addAll(A))));self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(k=>Promise.all(k.filter(x=>x!==C).map(x=>caches.delete(x))))));self.addEventListener('fetch',e=>{const u=new URL(e.request.url);if(e.request.method!=='GET'||u.pathname.startsWith('/api/')||u.pathname.startsWith('/api/v1/')||u.pathname.includes('download'))return;e.respondWith(fetch(e.request).catch(()=>caches.match(e.request)))})"
            self._send(HTTPStatus.OK, sw.encode(), "application/javascript; charset=utf-8", {"Service-Worker-Allowed": "/"}); return
        if route == "/":
            self.send_response(HTTPStatus.SEE_OTHER); self.send_header("Location", "/ui"); self.end_headers(); return
        self._proxy()

    def do_POST(self) -> None:
        route = urlparse(self.path).path
        if route.startswith("/api/v1/"):
            if self._api_post(route): return
            self._json({"ok": False, "error": "api_route_not_found"}, HTTPStatus.NOT_FOUND); return
        if route == "/api/identity/login" and self._api_post(route): return
        self._proxy()

    def do_PUT(self) -> None: self._proxy()

    def do_PATCH(self) -> None:
        route = urlparse(self.path).path
        prefix = "/api/v1/admin/users/"
        if route.startswith(prefix):
            payload, error = self._read_json()
            if error: self._json({"ok": False, "error": error}, HTTPStatus.BAD_REQUEST); return
            required = self._require_user(admin=True)
            if not required: return
            token, user = required
            if not self._csrf_ok(token): return
            username = route[len(prefix):]
            result = self.state.set_user_role(username, str((payload or {}).get("role") or ""))
            self.state.store.audit(str(user["username"]), "user.role_changed", self._channel(), "allowed" if result.get("ok") else "denied", {"target": username})
            self._json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST); return
        if route.startswith("/api/v1/"):
            self._json({"ok": False, "error": "api_route_not_found"}, HTTPStatus.NOT_FOUND); return
        self._proxy()

    def do_DELETE(self) -> None:
        route = urlparse(self.path).path
        if route in {"/api/v1/access/tailscale/credentials", "/api/v1/access/cloudflare/credentials"}:
            required = self._require_user(admin=True)
            if not required: return
            token, user = required
            if not self._csrf_ok(token): return
            provider = "tailscale" if "tailscale" in route else "cloudflare"
            self.state.store.audit(str(user["username"]), f"access.{provider}.credentials_delete_requested", self._channel(), "requires_root_helper")
            self._json({"ok": False, "error": "root_secret_helper_required", "credentials_in_database": False, "provider": provider}, HTTPStatus.CONFLICT); return
        if route.startswith("/api/v1/"):
            self._json({"ok": False, "error": "api_route_not_found"}, HTTPStatus.NOT_FOUND); return
        self._proxy()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Digua AI-NAS unified product access facade")
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=80)
    parser.add_argument("--channel", choices=("lan", "remote"), default="lan")
    parser.add_argument("--upstream", default="http://127.0.0.1:8765")
    parser.add_argument("--access-db", type=Path, default=Path(os.environ.get("DIGUA_ACCESS_DB", "/var/lib/digua-ai-nas/product_access.sqlite3")))
    parser.add_argument("--identity-db", type=Path, default=Path(os.environ.get("DIGUA_IDENTITY_DB", "/var/lib/digua-ai-nas/identity.sqlite3")))
    parser.add_argument("--upstream-identity-db", type=Path, default=Path(os.environ["DIGUA_UPSTREAM_IDENTITY_DB"]) if os.environ.get("DIGUA_UPSTREAM_IDENTITY_DB") else None)
    parser.add_argument("--enable-remote-ingress", action="store_true")
    parser.add_argument("--require-nas-mount", type=Path, default=None)
    parser.add_argument("--cloudflare-team-domain", default=os.environ.get("DIGUA_CF_TEAM_DOMAIN", ""))
    parser.add_argument("--cloudflare-audience", default=os.environ.get("DIGUA_CF_AUDIENCE", ""))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    state = AccessState(access_db=args.access_db, identity_db=args.identity_db, upstream=args.upstream, channel=args.channel, remote_enabled=args.enable_remote_ingress, cf_team_domain=args.cloudflare_team_domain, cf_audience=args.cloudflare_audience, require_nas_mount=args.require_nas_mount, upstream_identity_db=args.upstream_identity_db)
    server = ThreadingHTTPServer((args.bind, args.port), ProductAccessHandler)
    server.state = state  # type: ignore[attr-defined]
    print(f"Digua product access {args.channel}: http://{args.bind}:{args.port} -> {args.upstream}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 130
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
