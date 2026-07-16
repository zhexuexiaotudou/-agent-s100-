import os
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.product_jobs.queue import ProductJobQueue
from src.product_jobs.worker import ProductJobDispatcher, run_once
from src.subtitle_extraction.asr_backend import LocalAsrBackend


class ProductJobWorkerTest(unittest.TestCase):
    def test_worker_claims_and_completes_a_real_media_index_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            personal = root / "Personal"
            personal.mkdir()
            (personal / "photo.jpg").write_bytes(b"fixture")
            db = root / "reports" / "product_jobs" / "runtime" / "product_jobs.db"
            queue = ProductJobQueue(db)
            job = queue.enqueue("media_index", {})
            result = run_once(queue, ProductJobDispatcher(report_root=root / "reports", personal_root=personal))
            self.assertTrue(result["ok"])
            saved = queue.get(job["job_id"])["job"]
            self.assertEqual(saved["status"], "completed")
            self.assertEqual(saved["attempt_count"], 1)

    def test_failed_job_is_terminal_instead_of_staying_queued(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue = ProductJobQueue(root / "jobs.db")
            rejected = queue.enqueue("ocr_rebuild", {})
            self.assertFalse(rejected["ok"])
            self.assertEqual(rejected["error"], "unsupported_job_type")
            job_id = "job_legacy_ocr"
            conn = sqlite3.connect(root / "jobs.db")
            conn.execute(
                "INSERT INTO product_jobs(job_id,job_type,payload_json,status,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (job_id, "ocr_rebuild", json.dumps({}), "queued", "2026-07-16T00:00:00Z", "2026-07-16T00:00:00Z"),
            )
            conn.commit()
            conn.close()
            result = run_once(queue, ProductJobDispatcher(report_root=root / "reports", personal_root=root / "Personal"))
            self.assertFalse(result["ok"])
            saved = queue.get(job_id)["job"]
            self.assertEqual(saved["status"], "failed")
            self.assertIn("acl_aware_portal_sync", saved["error"])

    def test_claim_is_atomic(self):
        with tempfile.TemporaryDirectory() as tmp:
            queue = ProductJobQueue(Path(tmp) / "jobs.db")
            queue.enqueue("media_index", {})
            first = queue.claim_next()
            second = queue.claim_next()
            self.assertIsNotNone(first["job"])
            self.assertIsNone(second["job"])

    def test_unimplemented_asr_backends_never_report_available(self):
        for backend in ("faster_whisper", "vosk", "whisper_cpp"):
            with self.subTest(backend=backend), patch.dict(os.environ, {"DIGUA_ASR_BACKEND": backend, "DIGUA_ASR_MODEL_DIR": "."}, clear=False):
                status = LocalAsrBackend().status()
                self.assertFalse(status["available"])
                self.assertFalse(status["execution_implemented"])
                self.assertEqual(status["degraded_reason"], f"asr_execution_not_implemented:{backend}")


if __name__ == "__main__":
    unittest.main()
