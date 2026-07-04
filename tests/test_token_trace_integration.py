import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.harness.token_budget_integration import TokenBudgetIntegration


class TokenBudgetIntegrationTest(unittest.TestCase):
    def test_private_request_is_safe_and_traced(self):
        with TemporaryDirectory() as tmp:
            api = TokenBudgetIntegration(trace_path=Path(tmp) / "trace.jsonl")
            result = api.estimate(
                {
                    "case_id": "integration_private",
                    "task_type": "document_qa",
                    "user_prompt": "Summarize this private document",
                    "context_text": "/mnt/nas/openclaw/Personal/家庭/身份证扫描件.pdf",
                    "private_markers": ["/mnt/nas/openclaw/Personal/家庭/身份证扫描件.pdf"],
                }
            )
        self.assertEqual(result["private_leak_count"], 0)
        self.assertIn(result["route"], {"local_only", "cloud_blocked_private"})
        self.assertFalse(result["redaction_map_included"])
        self.assertIn("trace_hash", result["trace"])

    def test_public_request_can_be_redacted_cloud(self):
        with TemporaryDirectory() as tmp:
            api = TokenBudgetIntegration(trace_path=Path(tmp) / "trace.jsonl")
            result = api.route(
                {
                    "case_id": "integration_public",
                    "task_type": "public_research",
                    "user_prompt": "Compare public AI NAS trends",
                    "context_text": "public S100P OpenClaw Qwen evidence hash_abcd1234",
                    "evidence_hashes": ["hash_abcd1234"],
                    "complexity": "high",
                }
            )
        self.assertEqual(result["route"], "cloud_allowed_redacted")
        self.assertEqual(result["private_leak_count"], 0)
        self.assertGreater(result["token_counts"]["naive_cloud_payload_tokens"], 0)


if __name__ == "__main__":
    unittest.main()
