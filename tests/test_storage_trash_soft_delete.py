import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROBES_ROOT = REPO_ROOT / "scripts" / "probes"
if str(PROBES_ROOT) not in sys.path:
    sys.path.insert(0, str(PROBES_ROOT))

from ai_nas_operator_portal_server import PortalState
from ai_nas_snapshot import SnapshotStore


class StorageTrashSoftDeleteTest(unittest.TestCase):
    def make_state(self, root: Path) -> PortalState:
        personal_root = root / "Personal"
        personal_root.mkdir(parents=True)
        state = PortalState(
            root / "reports",
            [],
            refresh_on_start=False,
            personal_root=personal_root,
            sqlite_index_path=root / "personal_inventory.sqlite3",
            operation_db_path=root / "operator_portal_operations.sqlite3",
            document_fts_db_path=root / "document_fts.sqlite3",
            snapshot_db_path=root / "snapshot.sqlite3",
            media_db_path=root / "media.sqlite3",
        )
        assert state.identity_store is not None
        state.identity_store.create_user("admin", "admin123", "admin")
        return state

    def test_path_hash_trash_moves_photo_and_removes_media_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = self.make_state(root)
            assert state.media_center is not None
            assert state.snapshot_store is not None
            photo = root / "Personal" / "Photos" / "sample_person.jpg"
            photo.parent.mkdir(parents=True, exist_ok=True)
            photo.write_bytes(b"\xff\xd8\xfffake-jpeg-bytes")

            indexed = state.media_center.index_photos(root / "Personal" / "Photos", asset_root=root / "Personal")
            self.assertTrue(indexed["ok"])
            rows = state.media_center.list_photos(limit=10)
            self.assertEqual(len(rows), 1)
            path_hash = rows[0]["path_hash"]

            status, payload = state.storage_trash_payload(
                {"path_hash": path_hash},
                {"username": "admin", "role": "admin"},
            )

            self.assertEqual(status, 200)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["moved_to_trash"])
            self.assertFalse(payload["physical_file_deleted"])
            self.assertEqual(payload["retention_days"], 30)
            self.assertFalse(payload["raw_path_returned"])
            self.assertEqual(payload["media_index"]["removed"], 1)
            self.assertFalse(photo.exists())
            self.assertIsNone(state.media_center.photo_path_by_hash(path_hash))
            trash = state.snapshot_store.list_trash("admin")
            self.assertEqual(len(trash), 1)
            self.assertEqual(trash[0]["original_path"], "Photos/sample_person.jpg")
            self.assertTrue((root / "Personal" / ".trash" / trash[0]["trash_path"]).exists())
            self.assertIn("expires_at", trash[0])

    def test_expired_trash_cleanup_removes_unrestored_files_after_retention(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            personal = root / "Personal"
            docs = personal / "Documents"
            docs.mkdir(parents=True)
            doc = docs / "old.txt"
            doc.write_text("old trash fixture", encoding="utf-8")
            store = SnapshotStore(personal, root / "snapshot.sqlite3")
            result = store.trash_file(doc, "admin")
            self.assertTrue(result["ok"])
            trash_name = result["trash_name"]
            trash_path = personal / ".trash" / trash_name
            self.assertTrue(trash_path.exists())

            now = datetime.now(timezone.utc)
            expired_at = (now - timedelta(days=1)).isoformat()
            con = sqlite3.connect(root / "snapshot.sqlite3")
            try:
                con.execute(
                    "UPDATE trash_entries SET expires_at=? WHERE id=?",
                    (expired_at, result["trash_id"]),
                )
                con.commit()
            finally:
                con.close()

            cleanup = store.cleanup_expired_trash(30, now=now)

            self.assertTrue(cleanup["ok"])
            self.assertEqual(cleanup["removed"], 1)
            self.assertFalse(trash_path.exists())
            self.assertEqual(store.list_trash("admin"), [])


if __name__ == "__main__":
    unittest.main()
