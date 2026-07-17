import ast
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
PROBES_ROOT = REPO_ROOT / "scripts" / "probes"
if str(PROBES_ROOT) not in sys.path:
    sys.path.insert(0, str(PROBES_ROOT))

from ai_nas_media import MediaCenter
from ai_nas_operator_portal_server import PortalHandler, PortalState, ThreadingHTTPServer


def jpeg_fixture(seed: int) -> bytes:
    return b"\xff\xd8\xff\xe0" + f"album-{seed}".encode("ascii")


class MediaAlbumRecoveryTest(unittest.TestCase):
    def test_index_rejects_text_placeholders_and_library_scope_is_exact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            personal = root / "Personal"
            photos = personal / "Photos"
            uploads = personal / "Uploads"
            photos.mkdir(parents=True)
            uploads.mkdir(parents=True)
            for index in range(30):
                (photos / f"photo-{index:02d}.jpg").write_bytes(jpeg_fixture(index))
            (uploads / "assistant-fixture.jpg").write_bytes(jpeg_fixture(100))
            (personal / "placeholder.jpg").write_text("Placeholder: not an image", encoding="utf-8")

            media = MediaCenter(root / "media.sqlite3")
            result = media.index_photos(personal, asset_root=personal)

            self.assertEqual(result["indexed"], 31)
            self.assertEqual(result["invalid"], 1)
            self.assertEqual(len(media.list_photos(limit=100)), 31)
            self.assertEqual(len(media.list_photos(limit=100, path_prefix=photos)), 30)

    def test_library_summary_returns_more_than_legacy_24_without_upload_fixtures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            personal = root / "Personal"
            photos = personal / "Photos"
            uploads = personal / "Uploads"
            photos.mkdir(parents=True)
            uploads.mkdir(parents=True)
            for index in range(30):
                (photos / f"photo-{index:02d}.jpg").write_bytes(jpeg_fixture(index))
            (uploads / "assistant-fixture.jpg").write_bytes(jpeg_fixture(100))

            state = PortalState(root / "reports", [], refresh_on_start=False, personal_root=personal)
            assert state.identity_store is not None
            assert state.media_center is not None
            state.identity_store.create_user("admin", "admin123", "admin")
            state.media_center.index_photos(personal, asset_root=personal)
            login = state.identity_store.login("admin", "admin123")

            server = ThreadingHTTPServer(("127.0.0.1", 0), PortalHandler)
            server.state = state
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                def get(path: str) -> dict:
                    request = Request(base + path, headers={"Authorization": f"Bearer {login['token']}"})
                    with urlopen(request, timeout=5) as response:
                        return json.loads(response.read().decode("utf-8"))

                legacy = get("/api/media/summary")
                library = get("/api/media/summary?scope=library")
                self.assertEqual(len(legacy["photos"]), 24)
                self.assertEqual(len(library["photos"]), 30)
                self.assertEqual(library["stats"]["photo_count"], 30)
                self.assertEqual(library["photo_scope"], "library")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_ui_loads_library_without_blocking_auto_organize(self):
        source = (REPO_ROOT / "web" / "static" / "digua_ai_nas_v2.js").read_text(encoding="utf-8")
        start = source.index("  async function loadMediaData()")
        end = source.index("  async function selectMediaAlbum", start)
        loader = source[start:end]
        self.assertIn('/api/media/summary?scope=library', loader)
        self.assertNotIn("runAiAlbumAutoOrganize", loader)
        self.assertIn("const PREVIEW_HYDRATION_CONCURRENCY = 4", source)
        self.assertIn("const immediate = images.slice(0, 6)", source)
        self.assertIn('target_dir: "Photos/Uploads"', source)

    def test_portal_runtime_parses_with_s100p_python_311_grammar(self):
        source = (PROBES_ROOT / "ai_nas_operator_portal_server.py").read_text(encoding="utf-8")
        ast.parse(source, filename="ai_nas_operator_portal_server.py", feature_version=(3, 11))


if __name__ == "__main__":
    unittest.main()
