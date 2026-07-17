from __future__ import annotations

import http.client
import base64
import hashlib
import json
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from src.product_access.network import is_lan_address, validate_plan
from src.product_access.remote import CloudflareTunnelAdapter, TailscaleServeAdapter
from src.product_access.security import CloudflareJwtVerifier, csrf_token
from src.product_access.server import AccessState, ProductAccessHandler
from src.product_access.store import ProductAccessStore


class EchoHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def _reply(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length:
            self.rfile.read(length)
        payload = json.dumps({
            "ok": True,
            "authorization": self.headers.get("Authorization"),
            "spoofed_tailscale": self.headers.get("Tailscale-User-Login"),
            "method": self.command,
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_GET = _reply
    do_POST = _reply


class ProductAccessStoreTest(unittest.TestCase):
    def test_device_is_stable_and_claim_is_hash_only(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "access.sqlite3"
            store = ProductAccessStore(path)
            device_id = store.device()["id"]
            token = store.create_claim(30)
            self.assertNotIn(token, path.read_bytes().decode("latin1", errors="ignore"))
            self.assertTrue(store.verify_claim(token))
            self.assertTrue(store.consume_claim(token))
            self.assertFalse(store.verify_claim(token))
            second = store.create_claim(30)
            self.assertTrue(store.redeem_claim(second))
            self.assertFalse(store.redeem_claim(second))
            self.assertEqual(ProductAccessStore(path).device()["id"], device_id)

    def test_audit_redacts_secret_named_fields(self):
        with tempfile.TemporaryDirectory() as td:
            store = ProductAccessStore(Path(td) / "access.sqlite3")
            store.audit("admin", "test", "lan", "allowed", {"token": "leak", "safe": "value", "password_hint": "leak"})
            event = store.recent_audit()[0]
            self.assertEqual(event["details"], {"safe": "value"})


class ProductAccessHttpTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.echo = ThreadingHTTPServer(("127.0.0.1", 0), EchoHandler)
        self.echo_thread = threading.Thread(target=self.echo.serve_forever, daemon=True)
        self.echo_thread.start()
        self.state = AccessState(
            access_db=root / "access.sqlite3",
            identity_db=root / "identity.sqlite3",
            upstream=f"http://127.0.0.1:{self.echo.server_port}",
            channel="lan",
        )
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), ProductAccessHandler)
        self.server.state = self.state
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close()
        self.echo.shutdown(); self.echo.server_close()
        self.temp.cleanup()

    def request(self, method: str, path: str, body: dict | None = None, headers: dict | None = None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        raw = json.dumps(body).encode() if body is not None else None
        supplied = dict(headers or {})
        if raw is not None:
            supplied["Content-Type"] = "application/json"
        connection.request(method, path, body=raw, headers=supplied)
        response = connection.getresponse()
        data = response.read()
        result_headers = dict(response.getheaders())
        connection.close()
        return response.status, result_headers, json.loads(data) if data else {}

    def test_claim_cookie_csrf_proxy_and_logout_flow(self):
        token = self.state.store.create_claim()
        status, headers, payload = self.request("POST", "/api/v1/claim/complete", {"claim_token": token, "username": "owner", "password": "strong-password"})
        self.assertEqual(status, 200)
        self.assertEqual(payload["user"]["role"], "admin")
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        csrf = payload["csrf_token"]
        self.assertNotIn("strong-password", self.state.store.path.read_bytes().decode("latin1", errors="ignore"))

        status, _, session = self.request("GET", "/api/v1/auth/session", headers={"Cookie": cookie})
        self.assertEqual(status, 200)
        self.assertTrue(session["authenticated"])
        self.assertEqual(session["csrf_token"], csrf)

        status, _, _ = self.request("POST", "/api/example", {}, headers={"Cookie": cookie})
        self.assertEqual(status, 403)
        status, _, proxied = self.request("POST", "/api/example", {}, headers={"Cookie": cookie, "X-CSRF-Token": csrf, "Tailscale-User-Login": "spoof@example.com"})
        self.assertEqual(status, 200)
        self.assertTrue(proxied["authorization"].startswith("Bearer "))
        self.assertIsNone(proxied["spoofed_tailscale"])

        self.state.require_nas_mount = Path(self.temp.name) / "missing-nas"
        status, _, degraded = self.request("GET", "/api/storage/list", headers={"Cookie": cookie})
        self.assertEqual(status, 503)
        self.assertEqual(degraded["error"], "nas_not_mounted")
        self.state.require_nas_mount = None

        status, headers, payload = self.request("POST", "/api/v1/auth/logout", {}, headers={"Cookie": cookie, "X-CSRF-Token": csrf})
        self.assertEqual(status, 200)
        self.assertIn("Max-Age=0", headers["Set-Cookie"])

    def test_public_user_creation_is_blocked_and_setup_is_mobile(self):
        status, _, payload = self.request("POST", "/api/identity/create-user", {"username": "x", "password": "strong-password"})
        self.assertEqual(status, 403)
        self.assertEqual(payload["error"], "use_lan_claim_or_admin_api")
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        connection.request("GET", "/setup")
        response = connection.getresponse(); text = response.read().decode("utf-8")
        self.assertEqual(response.status, 200)
        self.assertIn('name="viewport"', text)
        self.assertIn("/api/v1/setup/claim", text)
        self.assertIn("box-sizing:border-box", text)
        self.assertIn("min-height:100dvh", text)
        connection.close()

    def test_product_access_serves_packaged_ui_instead_of_stale_upstream_assets(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        connection.request("GET", "/ui")
        response = connection.getresponse(); page = response.read().decode("utf-8")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Content-Type"), "text/html; charset=utf-8")
        self.assertIn("20260716-offline-ui", page)
        connection.close()

        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        connection.request("GET", "/static/digua_ai_nas_v2.js?v=20260716-offline-ui")
        response = connection.getresponse(); script = response.read().decode("utf-8")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Content-Type"), "application/javascript; charset=utf-8")
        self.assertIn('mobilePrimaryNavIds = ["dashboard", "assistant", "files", "media"]', script)
        self.assertNotIn('navItems.map(renderNavItem).join("")}</nav>', script)
        connection.close()

    def test_pwa_service_worker_excludes_api_and_downloads(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        connection.request("GET", "/sw.js")
        response = connection.getresponse(); script = response.read().decode()
        self.assertEqual(response.status, 200)
        self.assertIn("startsWith('/api/')", script)
        self.assertIn("includes('download')", script)
        connection.close()


class ProductAccessContractTest(unittest.TestCase):
    def test_network_plan_is_bounded(self):
        self.assertTrue(is_lan_address("192.168.1.2"))
        self.assertFalse(is_lan_address("8.8.8.8"))
        self.assertTrue(validate_plan({"connection": "lan0", "ipv4_method": "manual", "ipv4_address": "192.168.1.20/24", "ipv4_gateway": "192.168.1.1"})["ok"])
        self.assertFalse(validate_plan({"connection": "lan0", "shell": "rm -rf /"})["ok"])

    def test_remote_plans_never_enable_funnel_or_public_origin(self):
        tailscale = TailscaleServeAdapter().plan()
        self.assertFalse(tailscale["funnel_allowed"])
        self.assertEqual(tailscale["target"], "http://127.0.0.1:8781")
        cloudflare = CloudflareTunnelAdapter("nas.example.com", "abc", Path("/run/secret.json"))
        self.assertFalse(cloudflare.plan()["public_origin_port_exposed"])
        self.assertIn("http_status:404", cloudflare.config_yaml())

    def test_cloudflare_jwt_rejects_unsigned_and_wrong_key(self):
        encode = lambda value: base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).rstrip(b"=").decode()
        unsigned = encode({"alg": "none", "kid": "k1"}) + "." + encode({"iss": "https://team.cloudflareaccess.com", "aud": ["aud"], "exp": int(time.time()) + 60, "email": "user@example.com"}) + "."
        verifier = CloudflareJwtVerifier(
            "team.cloudflareaccess.com", "aud",
            fetcher=lambda _url: {"keys": [{"kid": "k1", "kty": "RSA", "n": "AQAB", "e": "AQAB"}]},
        )
        self.assertEqual(verifier.verify(unsigned)["error"], "unsupported_jwt_algorithm")
        bad_signature = encode({"alg": "RS256", "kid": "k1"}) + "." + encode({"iss": "https://team.cloudflareaccess.com", "aud": ["aud"], "exp": int(time.time()) + 60, "email": "user@example.com"}) + "." + base64.urlsafe_b64encode(hashlib.sha256(b"bad").digest()).rstrip(b"=").decode()
        self.assertIn(verifier.verify(bad_signature)["error"], {"jwt_signature_invalid", "jwt_validation_failed:OverflowError"})

    def test_release_units_keep_backends_on_loopback_and_remote_disabled(self):
        repo = Path(__file__).resolve().parents[1]
        portal = (repo / "release/systemd/openclaw-gateway.service").read_text(encoding="utf-8")
        lan = (repo / "release/systemd/digua-product-access.service").read_text(encoding="utf-8")
        remote = (repo / "release/systemd/digua-product-remote-ingress.service").read_text(encoding="utf-8")
        self.assertIn("--bind 127.0.0.1 --port 8765", portal)
        self.assertIn("--identity-db-path ${DIGUA_IDENTITY_DB}", portal)
        self.assertIn("--port 80 --channel lan", lan)
        self.assertIn("--upstream-identity-db ${DIGUA_UPSTREAM_IDENTITY_DB}", lan)
        self.assertIn("--require-nas-mount ${DIGUA_NAS_MOUNT}", lan)
        self.assertIn("CAP_NET_BIND_SERVICE", lan)
        self.assertNotIn("Requires=openclaw-gateway.service", lan)
        self.assertIn("--bind 127.0.0.1 --port 8781", remote)
        self.assertNotIn("Requires=openclaw-gateway.service", remote)
        self.assertNotIn("WantedBy=", remote)

    def test_product_install_entry_uses_guided_no_argument_flow(self):
        repo = Path(__file__).resolve().parents[1]
        installer = (repo / "deploy/product_access/install.sh").read_text(encoding="utf-8")
        wizard = (repo / "release/install/deploy_wizard.py").read_text(encoding="utf-8")
        self.assertIn('if [[ $# -eq 0 ]]', installer)
        self.assertIn('--product-access', installer)
        self.assertIn('"--product-access"', wizard)
        self.assertIn('configure_lan_access.sh', wizard)
        self.assertIn('claim-create', wizard)

    def test_access_only_install_never_manages_existing_backend_units(self):
        repo = Path(__file__).resolve().parents[1]
        installer = (repo / "release/install/install_product_access_only.sh").read_text(encoding="utf-8")
        uninstaller = (repo / "release/install/uninstall_product_access_only.sh").read_text(encoding="utf-8")
        wrapper = (repo / "deploy/product_access/install.sh").read_text(encoding="utf-8")
        self.assertIn('"--access-only"', wrapper)
        self.assertNotIn("systemctl enable --now openclaw-gateway.service", installer)
        self.assertNotIn("systemctl enable --now qwen25-local-openai-gateway.service", installer)
        self.assertNotIn("openclaw-gateway.service", uninstaller)
        self.assertNotIn("qwen25-local-openai-gateway.service", uninstaller)
        self.assertIn("backend_units_touched':[]", installer)
        self.assertIn("systemctl restart digua-product-access.service", installer)

    def test_lan_configuration_synchronizes_hosts_and_restarts_avahi(self):
        repo = Path(__file__).resolve().parents[1]
        source = (repo / "release/install/configure_lan_access.sh").read_text(encoding="utf-8")
        self.assertIn('127.0.1.1', source)
        self.assertIn('invalid_hostname', source)
        self.assertIn('systemctl restart avahi-daemon.service', source)

    def test_distinct_upstream_identity_store_receives_bridged_sessions_and_user_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = AccessState(
                access_db=root / "access.sqlite3",
                identity_db=root / "local-identity.sqlite3",
                upstream="http://127.0.0.1:8765",
                channel="lan",
                upstream_identity_db=root / "upstream-identity.sqlite3",
            )
            self.assertIsNotNone(state.upstream_identity)
            self.assertTrue(state.create_user("bridge-admin", "strong-password", "admin")["ok"])
            login = state.identity.login("bridge-admin", "strong-password")
            local_token = login["token"]
            upstream_token = state.upstream_token(local_token, login["user"])
            self.assertTrue(upstream_token)
            self.assertEqual(state.upstream_identity.validate_token(upstream_token)["username"], "bridge-admin")
            self.assertTrue(state.create_user("bridge-viewer", "strong-password", "viewer")["ok"])
            self.assertTrue(state.set_user_role("bridge-viewer", "operator")["ok"])
            upstream_roles = {item["username"]: item["role"] for item in state.upstream_identity.list_users()}
            self.assertEqual(upstream_roles["bridge-viewer"], "operator")
            self.assertTrue(state.identity.create_user("local-only-admin", "strong-password", "admin")["ok"])
            rejected = state.set_user_role("bridge-admin", "viewer")
            self.assertFalse(rejected["ok"])
            local_roles = {item["username"]: item["role"] for item in state.identity.list_users()}
            self.assertEqual(local_roles["bridge-admin"], "admin")
            self.assertTrue(state.revoke_user_sessions("bridge-admin")["ok"])
            self.assertIsNone(state.upstream_identity.validate_token(upstream_token))
            state.drop_bridge(local_token)

    def test_frontend_uses_cookie_session_csrf_and_current_pwa(self):
        repo = Path(__file__).resolve().parents[1]
        html = (repo / "web/ai_nas_desktop_v2.html").read_text(encoding="utf-8")
        js = (repo / "web/static/digua_ai_nas_v2.js").read_text(encoding="utf-8")
        self.assertIn('/manifest.webmanifest', html)
        self.assertIn('/api/v1/auth/session', js)
        self.assertIn('X-CSRF-Token', js)
        self.assertIn('serviceWorker.register("/sw.js")', js)


if __name__ == "__main__":
    unittest.main()
