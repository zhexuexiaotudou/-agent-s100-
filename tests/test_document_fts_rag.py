import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROBES_ROOT = REPO_ROOT / "scripts" / "probes"
if str(PROBES_ROOT) not in sys.path:
    sys.path.insert(0, str(PROBES_ROOT))

from ai_nas_operator_portal_server import PortalState


class DocumentFtsRagTest(unittest.TestCase):
    def make_state(self, root: Path) -> PortalState:
        personal_root = root / "Personal"
        docs_root = personal_root / "Documents"
        docs_root.mkdir(parents=True)
        (docs_root / "sample.md").write_text(
            "地瓜 AI-NAS 采用本地优先策略，文档问答先使用 SQLite FTS 召回证据，"
            "再返回脱敏片段和 evidence_ref，不默认启用 embedding RAG。",
            encoding="utf-8",
        )
        state = PortalState(
            root / "reports",
            [],
            refresh_on_start=False,
            personal_root=personal_root,
            sqlite_index_path=root / "personal_inventory.sqlite3",
            operation_db_path=root / "operator_portal_operations.sqlite3",
            document_fts_db_path=root / "document_fts.sqlite3",
        )
        assert state.identity_store is not None
        state.identity_store.create_user("admin", "admin123", "admin")
        return state

    def test_document_query_uses_sqlite_fts_first_with_evidence_refs(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = self.make_state(Path(tmp))
            status, payload = state.document_query_payload("地瓜 AI-NAS 本地优先 FTS", "Documents", {"username": "admin", "role": "admin"})

            self.assertEqual(status, 200)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["retrieval_mode"], "sqlite_fts_first")
            self.assertFalse(payload["embedding_enabled"])
            self.assertFalse(payload["cloud_used"])
            self.assertGreaterEqual(payload["evidence_count"], 1)
            self.assertTrue(payload["evidence_refs"])
            self.assertIn("ev_", payload["evidence_refs"][0])

    def test_document_query_returns_empty_evidence_without_embedding_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = self.make_state(Path(tmp))
            status, payload = state.document_query_payload("completely_missing_phrase_xyz", "Documents", {"username": "admin", "role": "admin"})

            self.assertEqual(status, 200)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["retrieval_mode"], "sqlite_fts_first")
            self.assertFalse(payload["embedding_feature_flag"])
            self.assertEqual(payload["evidence_count"], 0)
            self.assertIn("未找到可靠证据", payload["answer"])


if __name__ == "__main__":
    unittest.main()
