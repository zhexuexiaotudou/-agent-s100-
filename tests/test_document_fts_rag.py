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

    def test_bill_amount_query_returns_grounded_amount_from_scoped_documents(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = self.make_state(Path(tmp))
            docs_root = Path(tmp) / "Personal" / "Documents"
            demo_root = docs_root / "DemoDocs"
            demo_root.mkdir(parents=True, exist_ok=True)
            (demo_root / "family_expense_bill_20260520_1314.md").write_text(
                "\n".join(
                    [
                        "# 2026\u5e745\u670820\u65e5\u5bb6\u5ead\u5f00\u652f\u8d26\u5355",
                        "\u8d26\u5355\u65e5\u671f\uff1a2026\u5e745\u670820\u65e5",
                        "\u8d26\u5355\u7c7b\u578b\uff1a\u5bb6\u5ead\u5f00\u652f",
                        "\u5408\u8ba1\u91d1\u989d\uff1a1314\u5143",
                        "\u5f53\u7528\u6237\u8be2\u95ee\u201c2026\u5e745\u670820\u65e5\u5bb6\u5ead\u5f00\u652f\u8d26\u5355\u91d1\u989d\u662f\u591a\u5c11\uff1f\u201d\u65f6\uff0c\u5e94\u56de\u7b54 1314\u5143\u3002",
                    ]
                ),
                encoding="utf-8",
            )
            (docs_root / "Invoices" / "2025").mkdir(parents=True, exist_ok=True)
            (docs_root / "Invoices" / "2025" / "old_invoice.txt").write_text(
                "Invoice 2025-046 Total: USD 2902.00 Service date: 2025-11-20.",
                encoding="utf-8",
            )

            status, payload = state.document_query_payload(
                "2026\u5e745\u670820\u65e5\u5bb6\u5ead\u5f00\u652f\u8d26\u5355\u91d1\u989d\u662f\u591a\u5c11\uff1f",
                "Documents/DemoDocs",
                {"username": "admin", "role": "admin"},
            )

            self.assertEqual(status, 200)
            self.assertTrue(payload["ok"])
            self.assertGreaterEqual(payload["evidence_count"], 1)
            self.assertEqual(payload["evidence"][0]["relative_path"], "Documents/DemoDocs/family_expense_bill_20260520_1314.md")
            self.assertEqual(
                payload["evidence"][0]["open_url"],
                "/api/storage/download?path=Documents%2FDemoDocs%2Ffamily_expense_bill_20260520_1314.md&preview=1",
            )
            self.assertEqual(payload["evidence"][0]["open_kind"], "document")
            self.assertIn("1314\u5143", payload["amount_hits"])
            self.assertIn("1314\u5143", payload["answer"])

            status, natural_payload = state.document_query_payload(
                "2026\u5e745\u670820\u65e5\u5bb6\u5ead\u5f00\u652f\u8d26\u5355\u4fe1\u606f",
                "Documents/DemoDocs",
                {"username": "admin", "role": "admin"},
            )

            self.assertEqual(status, 200)
            self.assertTrue(natural_payload["ok"])
            self.assertGreaterEqual(natural_payload["evidence_count"], 1)
            self.assertIn("1314\u5143", natural_payload["amount_hits"])

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
