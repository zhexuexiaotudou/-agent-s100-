import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TRACK = ROOT / "dream_s100p_lladacpp"


class LladaCppTrackArtifactsTest(unittest.TestCase):
    def load_json(self, rel):
        with (TRACK / rel).open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def test_phase0_claim_boundary(self):
        data = self.load_json("reports/30000_baseline_lock.json")
        self.assertEqual(data["status"], "phase0_baseline_locked")
        self.assertIn("logits-invalid", data["exact_blockers"][0])
        self.assertIn("OpenClaw foreground model", data["forbidden_claims"][0])

    def test_phase1_has_required_design_points(self):
        data = self.load_json("reports/30010_lladacpp_to_s100p_requirements.json")
        self.assertGreaterEqual(len(data["design_points"]), 8)
        for point in data["design_points"]:
            self.assertTrue(point["s100p_equivalent_implementation"])
            self.assertTrue(point["required_tests"])

    def test_phase2_holds_without_full_truth_set(self):
        data = self.load_json("reports/30020_pytorch_truth_export_gate.json")
        self.assertEqual(data["verdict"], "external_truth_missing_hold")
        self.assertFalse(data["safety"]["generation_allowed"])
        self.assertFalse(data["safety"]["openclaw_product_route_allowed"])


if __name__ == "__main__":
    unittest.main()
