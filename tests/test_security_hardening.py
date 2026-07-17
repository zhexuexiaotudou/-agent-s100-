import hashlib
import io
import json
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
PROBES_ROOT = REPO_ROOT / "scripts" / "probes"
if str(PROBES_ROOT) not in sys.path:
    sys.path.insert(0, str(PROBES_ROOT))

from ai_nas_identity import IdentityStore
from ai_nas_operator_portal_server import MAX_STREAM_UPLOAD_BYTES, PortalHandler, PortalState, ThreadingHTTPServer


class SecurityHardeningTest(unittest.TestCase):
    def make_state(self, root: Path) -> PortalState:
        personal = root / "Personal"
        (personal / "Photos" / "Alice").mkdir(parents=True)
        (personal / "Photos" / "Bob").mkdir(parents=True)
        (personal / "Documents" / "Alice").mkdir(parents=True)
        (personal / "Photos" / "Alice" / "alice-visible.jpg").write_bytes(b"\xff\xd8\xffalice")
        (personal / "Photos" / "Bob" / "bob-hidden.jpg").write_bytes(b"\xff\xd8\xffbob")
        state = PortalState(root / "reports", [], refresh_on_start=False, personal_root=personal)
        assert state.identity_store is not None
        assert state.media_center is not None
        state.identity_store.create_user("admin", "admin123", "admin")
        state.identity_store.create_user("alice", "alice123", "user")
        state.identity_store.create_user("bob", "bob12345", "user")
        state.identity_store.set_acl("Photos/Alice", "user", "alice", "read")
        state.identity_store.set_acl("Photos/Bob", "user", "bob", "read")
        state.identity_store.set_acl("Documents/Alice", "user", "alice", "write")
        state.media_center.index_photos(personal / "Photos", asset_root=personal)
        return state

    def request_json(self, base: str, path: str, *, method: str = "GET", token: str = "", payload=None):
        body = json.dumps(payload or {}).encode("utf-8") if method != "GET" else None
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(base + path, data=body, headers=headers, method=method)
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as exc:
            response = exc
        return response.status, dict(response.headers), json.loads(response.read().decode("utf-8"))

    def test_sensitive_routes_require_auth_and_media_is_acl_filtered(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = self.make_state(Path(tmp))
            server = ThreadingHTTPServer(("127.0.0.1", 0), PortalHandler)
            server.state = state
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                status, _, payload = self.request_json(base, "/api/assistant/chat", method="POST", payload={"query": "private document"})
                self.assertEqual(status, 401)
                self.assertEqual(payload["error"], "auth_required")
                status, _, payload = self.request_json(base, "/api/ai-space/status")
                self.assertEqual(status, 401)
                self.assertEqual(payload["error"], "auth_required")

                login = state.identity_store.login("alice", "alice123")
                status, headers, payload = self.request_json(base, "/api/media/photos", token=login["token"])
                self.assertEqual(status, 200)
                self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
                encoded = json.dumps(payload, ensure_ascii=False)
                self.assertIn("alice-visible", encoded)
                self.assertNotIn("bob-hidden", encoded)

                status, _, payload = self.request_json(base, "/api/jobs/recent", token=login["token"])
                self.assertEqual(status, 403)
                self.assertEqual(payload["error"], "admin_required")
                admin_login = state.identity_store.login("admin", "admin123")
                status, _, payload = self.request_json(base, "/api/jobs/recent", token=admin_login["token"])
                self.assertEqual(status, 200)
                self.assertTrue(payload["ok"])

                upload_body = b"streamed-over-http"
                upload_query = quote("Documents/Alice")
                request = Request(
                    base + f"/api/storage/upload-stream?filename=note.txt&target_dir={upload_query}",
                    data=upload_body,
                    headers={"Authorization": f"Bearer {login['token']}", "Content-Type": "text/plain"},
                    method="POST",
                )
                with urlopen(request, timeout=5) as response:
                    upload_payload = json.loads(response.read().decode("utf-8"))
                self.assertTrue(upload_payload["ok"])
                download = Request(
                    base + "/api/storage/download?path=" + quote("Documents/Alice/note.txt"),
                    headers={"Authorization": f"Bearer {login['token']}"},
                )
                with urlopen(download, timeout=5) as response:
                    self.assertEqual(response.read(), upload_body)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_session_token_is_hashed_at_rest_and_login_is_rate_limited(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "identity.db"
            store = IdentityStore(db)
            self.assertTrue(store.create_user("admin", "safePass123", "admin")["ok"])
            login = store.login("admin", "safePass123")
            self.assertTrue(login["ok"])
            con = sqlite3.connect(db)
            stored = con.execute("SELECT token FROM sessions").fetchone()[0]
            con.close()
            self.assertNotEqual(stored, login["token"])
            self.assertEqual(stored, hashlib.sha256(login["token"].encode("utf-8")).hexdigest())
            self.assertIsNotNone(store.validate_token(login["token"]))

            con = sqlite3.connect(db)
            con.execute("UPDATE sessions SET token=?", (login["token"],))
            con.commit()
            con.close()
            self.assertIsNotNone(store.validate_token(login["token"]))
            con = sqlite3.connect(db)
            migrated = con.execute("SELECT token FROM sessions").fetchone()[0]
            con.close()
            self.assertEqual(migrated, stored)

            for _ in range(5):
                self.assertEqual(store.login("admin", "wrong-pass")["error"], "invalid_credentials")
            self.assertEqual(store.login("admin", "safePass123")["error"], "too_many_login_attempts")

    def test_first_user_bootstrap_is_atomic(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = IdentityStore(Path(tmp) / "identity.db")
            barrier = threading.Barrier(2)
            results = []

            def create(username: str):
                barrier.wait()
                results.append(store.create_user(username, f"{username}Pass123", "user"))

            threads = [threading.Thread(target=create, args=(name,)) for name in ("first", "second")]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)
            self.assertTrue(all(result["ok"] for result in results))
            users = store.list_users()
            self.assertEqual(sum(user["role"] == "admin" for user in users), 1)

    def test_frontend_has_no_default_admin_login_and_escapes_dynamic_html(self):
        main_js = (REPO_ROOT / "web" / "static" / "digua_ai_nas_v2.js").read_text(encoding="utf-8")
        self.assertNotIn("admin123", main_js)
        self.assertNotIn("ensureDefaultLogin", main_js)
        for name in ("ai_space.js", "auto_organizer.js", "digua_journal.js", "subtitle_extraction.js", "smart_classification.js"):
            source = (REPO_ROOT / "web" / "static" / name).read_text(encoding="utf-8")
            self.assertIn("escapeHtml", source)
            self.assertIn("sessionStorage", source)

    def test_storage_upload_and_download_use_bounded_streaming(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            personal = root / "Personal"
            (personal / "Documents").mkdir(parents=True)
            state = PortalState(root / "reports", [], refresh_on_start=False, personal_root=personal)
            assert state.identity_store is not None
            state.identity_store.create_user("admin", "safePass123", "admin")
            user = {"username": "admin", "role": "admin"}
            content = (b"streamed-content-" * 1024) + b"end"

            status, payload = state.storage_upload_stream("sample.bin", "Documents", len(content), io.BytesIO(content), user)
            self.assertEqual(status, 200)
            self.assertEqual((personal / "Documents" / "sample.bin").read_bytes(), content)
            self.assertEqual(payload["file"]["sha256"], hashlib.sha256(content).hexdigest())

            status, payload = state.storage_upload_stream("sample.bin", "Documents", len(content), io.BytesIO(content), user)
            self.assertEqual(status, 409)
            self.assertEqual(payload["error"], "target_already_exists")

            status, payload = state.storage_upload_stream("too-large.bin", "Documents", MAX_STREAM_UPLOAD_BYTES + 1, io.BytesIO(), user)
            self.assertEqual(status, 413)
            self.assertFalse((personal / "Documents" / "too-large.bin").exists())

            status, payload = state.storage_upload_stream("truncated.bin", "Documents", 10, io.BytesIO(b"short"), user)
            self.assertEqual(status, 400)
            self.assertEqual(payload["error"], "request_body_truncated")
            self.assertFalse((personal / "Documents" / "truncated.bin").exists())

        server_source = (REPO_ROOT / "scripts" / "probes" / "ai_nas_operator_portal_server.py").read_text(encoding="utf-8")
        send_method = server_source.split("def send_storage_file", 1)[1].split("def send_portal_html", 1)[0]
        self.assertNotIn("read_bytes()", send_method)
        self.assertIn("STREAM_CHUNK_BYTES", send_method)


if __name__ == "__main__":
    unittest.main()
