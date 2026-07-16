import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROBES_ROOT = REPO_ROOT / "scripts" / "probes"
if str(PROBES_ROOT) not in sys.path:
    sys.path.insert(0, str(PROBES_ROOT))

from ai_nas_operator_portal_server import PortalState


class DocumentClassificationTest(unittest.TestCase):
    def test_classification_is_virtual_acl_filtered_and_returns_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            personal = root / "Personal"
            (personal / "Documents" / "Alice").mkdir(parents=True)
            (personal / "Documents" / "Bob").mkdir(parents=True)
            (personal / "Documents" / "Alice" / "项目报告.pdf").write_bytes(b"pdf")
            (personal / "Documents" / "Bob" / "工资账单.xlsx").write_bytes(b"xlsx")
            state = PortalState(root / "reports", [], refresh_on_start=False, personal_root=personal)
            assert state.identity_store is not None
            state.identity_store.create_user("admin", "admin123", "admin")
            state.identity_store.create_user("alice", "alice123", "user")
            state.identity_store.set_acl("Documents/Alice", "user", "alice", "read")

            status, payload = state.document_classification_payload("Documents", {"username": "alice", "role": "user"})

            self.assertEqual(status, 200)
            self.assertEqual(payload["total_items"], 1)
            self.assertEqual(payload["items"][0]["name"], "项目报告.pdf")
            self.assertIn("PDF文档", payload["items"][0]["categories"])
            self.assertTrue(payload["virtual_only"])
            self.assertFalse(payload["physical_file_moved"])
            self.assertNotIn("工资账单", str(payload))

    def test_upload_ui_uses_streaming_storage_contract_and_soft_delete(self):
        source = (REPO_ROOT / "web" / "static" / "digua_ai_nas_v2.js").read_text(encoding="utf-8")
        self.assertIn('`/api/storage/upload-stream?${query.toString()}`', source)
        self.assertIn('uploadFileStream(file, "Documents")', source)
        self.assertNotIn("content_base64: base64", source)
        self.assertNotIn('"/api/documents/upload"', source)
        self.assertNotIn("docDeleteFile", source)


if __name__ == "__main__":
    unittest.main()
