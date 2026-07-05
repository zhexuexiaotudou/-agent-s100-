import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROBES_ROOT = REPO_ROOT / "scripts" / "probes"
if str(PROBES_ROOT) not in sys.path:
    sys.path.insert(0, str(PROBES_ROOT))

from ai_nas_operator_portal_server import PortalState, readonly_sqlite_summary


class PersonalInventorySqliteReadonlyTest(unittest.TestCase):
    def test_readonly_summary_degrades_on_corrupt_inventory_without_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "personal_inventory.sqlite3"
            db_path.write_text("not a sqlite database", encoding="utf-8")

            summary = readonly_sqlite_summary(db_path)

            self.assertFalse(summary["ok"])
            self.assertEqual(summary["status"], "degraded")
            self.assertIn("personal_inventory.sqlite3", summary["path"])

    def test_operation_log_uses_separate_database_from_inventory_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            personal_root = root / "Personal"
            report_root = root / "reports"
            personal_root.mkdir()
            inventory_db = root / "personal_inventory.sqlite3"
            operation_db = root / "operator_portal_operations.sqlite3"
            con = sqlite3.connect(inventory_db)
            try:
                con.execute("CREATE TABLE file_operations(id INTEGER PRIMARY KEY)")
                con.commit()
            finally:
                con.close()
            before = readonly_sqlite_summary(inventory_db)

            state = PortalState(
                report_root,
                [],
                refresh_on_start=False,
                personal_root=personal_root,
                sqlite_index_path=inventory_db,
                operation_db_path=operation_db,
                document_fts_db_path=root / "document_fts.sqlite3",
            )
            state.record_operation("copy", "Documents/a.md", "Documents/b.md", "harness_route_required", "test")
            payload = state.storage_status_payload()

            after = readonly_sqlite_summary(inventory_db)
            operation = readonly_sqlite_summary(operation_db)
            self.assertEqual(before["operation_log_count"], 0)
            self.assertEqual(after["operation_log_count"], 0)
            self.assertEqual(operation["operation_log_count"], 1)
            self.assertEqual(payload["sqlite_readonly_status"]["status"], "readonly_ok")
            self.assertEqual(payload["operation_log_status"]["status"], "readonly_ok")


if __name__ == "__main__":
    unittest.main()
