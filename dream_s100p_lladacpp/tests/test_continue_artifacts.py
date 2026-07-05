import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TRACK = ROOT / "dream_s100p_lladacpp"


class ContinueArtifactsTest(unittest.TestCase):
    def load_json(self, path: Path):
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def test_full_truth_31_is_complete(self):
        manifest = self.load_json(TRACK / "reference" / "full_truth_31_manifest.json")
        self.assertEqual(manifest["status"], "pass")
        self.assertEqual(manifest["truth_row_count"], 31)
        self.assertEqual(manifest["case_type_counts"]["semantic_original"], 8)
        self.assertEqual(manifest["case_type_counts"]["control_command"], 4)

    def test_validation_and_replay_pass(self):
        validation = self.load_json(TRACK / "reports" / "30220_full_truth_31_validation_gate.json")
        replay = self.load_json(TRACK / "reports" / "30230_pytorch_block_driver_gate.json")
        self.assertTrue(validation["full_truth_valid"])
        self.assertTrue(replay["gate_pass"])

    def test_final_verdict_stops_at_bpu_operator_alignment(self):
        packet = self.load_json(ROOT / "01_final_evidence" / "dream7b_s100p_lladacpp_style_continue_gate_packet.json")
        self.assertEqual(packet["final_verdict"], "bpu_operator_alignment_failed_review_required")
        self.assertFalse(packet["review_questions"]["can_enter_product_route_now"])


if __name__ == "__main__":
    unittest.main()
