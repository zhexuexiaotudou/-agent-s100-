import unittest

from tools.token_budget.cloud_route_decider import decide_route
from tools.token_budget.context_compressor import ContextCompressor
from tools.token_budget.privacy_redactor import PrivacyRedactor


class ContextCompressorTest(unittest.TestCase):
    def test_public_cloud_payload_stays_under_budget_and_keeps_hash(self):
        case = {
            "case_id": "t1",
            "task_type": "report_generation",
            "user_prompt": "Write a public AI-NAS report section",
            "context_text": "\n".join([f"public benchmark line {i} hash_abcd1234" for i in range(40)]),
            "context_items": [f"public benchmark line {i} hash_abcd1234" for i in range(40)],
            "evidence_hashes": ["hash_abcd1234"],
            "complexity": "high",
        }
        route = decide_route(case).to_dict()
        redactor = PrivacyRedactor()
        red_prompt = redactor.redact(case["user_prompt"]).redacted_text
        red_context = redactor.redact(case["context_text"]).redacted_text
        result = ContextCompressor().compress(case, red_prompt, red_context, route)
        self.assertTrue(result.budget_compliant)
        self.assertEqual(result.private_leak_count, 0)
        self.assertEqual(result.citation_hashes_preserved, 1)

    def test_local_route_has_no_cloud_payload(self):
        case = {"case_id": "t2", "task_type": "nas_search", "user_prompt": "Find pdf", "context_text": "file list"}
        result = ContextCompressor().compress(case, "Find pdf", "file list", {"route": "local_only"})
        self.assertEqual(result.tokens, 0)
        self.assertEqual(result.payload_text, "")


if __name__ == "__main__":
    unittest.main()

