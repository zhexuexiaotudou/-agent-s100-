import json
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from scripts.metrics_detector import detect
from scripts.probes.safety_attack_probe import run_probe


class ProbeMetricsTruthTest(unittest.TestCase):
    def write(self, root: Path, name: str, payload: dict) -> None:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_transport_failure_is_inconclusive_not_blocked(self):
        with patch("scripts.probes.safety_attack_probe.preflight", return_value=(False, "gateway_unreachable:timeout")):
            result = run_probe("http://127.0.0.1:1", timeout=0.01)
        self.assertFalse(result["ok"])
        self.assertEqual(result["verdict"], "inconclusive_gateway_unreachable")
        self.assertEqual(result["summary"]["blocked"], 0)
        self.assertEqual(result["summary"]["measured"], 0)

    def test_metrics_denominator_includes_failed_gates_and_penalizes_degraded_smoke(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            now = time.time()
            stamp = datetime.fromtimestamp(now, tz=timezone.utc).isoformat()
            self.write(root, "alpha_gate.json", {"ok": True, "gate": "alpha", "generated_at": stamp, "verdict": "ok_alpha"})
            self.write(root, "beta_gate.json", {"ok": False, "gate": "beta", "generated_at": stamp, "verdict": "blocked_beta"})
            self.write(root, "product_smoke_latest.json", {"generated_at": stamp, "summary": {"failure_count": 0, "warning_count": 2, "degraded_modules": ["yolo"], "production_ready": True}})
            self.write(root, "safety_attack_latest.json", {"generated_at": stamp, "verdict": "ok_all_measured_attacks_blocked", "summary": {"measured": 4, "blocked": 4, "leaked": 0, "inconclusive": 0}})
            result = detect(root, now=now)
            self.assertEqual(result["gates"]["current_total"], 2)
            self.assertEqual(result["gates"]["passed"], 1)
            self.assertEqual(result["gates"]["failed"], 1)
            self.assertEqual(result["gates"]["score"], 0.5)
            self.assertLess(result["product_smoke"]["score"], 1.0)

    def test_inference_availability_requires_model_directory_and_stale_evidence_is_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stale_stamp = datetime.fromtimestamp(time.time() - 10 * 24 * 3600, tz=timezone.utc).isoformat()
            current_stamp = datetime.now(timezone.utc).isoformat()
            self.write(root, "old_gate.json", {"ok": True, "gate": "old", "generated_at": stale_stamp})
            self.write(root, "qwen_inference_bench_latest_cache.json", {"generated_at": current_stamp, "qwen7b": {"available": True, "model_dirs": []}})
            result = detect(root, max_age_hours=72)
            self.assertEqual(result["gates"]["current_total"], 0)
            self.assertFalse(result["inference"]["consistent"])
            self.assertIn("inference_availability_inconsistent", result["blockers"])
            self.assertFalse(result["production_ready"])


if __name__ == "__main__":
    unittest.main()
