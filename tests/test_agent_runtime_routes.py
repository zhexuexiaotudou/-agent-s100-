import tempfile
import unittest
from pathlib import Path

from src.openclaw.harness_default_middleware import HarnessDefaultMiddleware
from src.openclaw.routes.agent_runtime_routes import agent_runtime_route_response


class AgentRuntimeRoutesTest(unittest.TestCase):
    def test_status_route_and_harness_status_include_runtime_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            status_code, payload = agent_runtime_route_response(
                "/api/agent-runtime/status",
                report_root=root / "reports",
                personal_root=root / "Personal",
            )
            self.assertEqual(status_code, 200)
            self.assertTrue(payload["ok"])
            self.assertFalse(payload["qwen_execution_authority"])
            self.assertFalse(payload["public_mcp_exposed"])

            harness = HarnessDefaultMiddleware(report_root=root / "reports", personal_root=root / "Personal").status()
            self.assertIn("agent_runtime", harness)
            self.assertFalse(harness["agent_runtime"]["qwen_execution_authority"])

    def test_context_pack_route_compiles_without_raw_private_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            status_code, payload = agent_runtime_route_response(
                "/api/agent-runtime/context-pack",
                method="POST",
                payload={"query": "OpenClaw Harness", "user_id": "admin"},
                report_root=Path(tmp) / "reports",
                personal_root=Path(tmp) / "Personal",
            )
            self.assertEqual(status_code, 200)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["evidence_refs"])
            self.assertFalse(payload["cloud_private_raw_egress"])

    def test_path_routes_reject_parent_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            for route in ["/api/agent-runtime/multimodal-index/scan", "/api/agent-runtime/rag/query"]:
                status_code, payload = agent_runtime_route_response(
                    route,
                    method="POST",
                    payload={"path": "../tmp", "query": "harness"},
                    report_root=Path(tmp) / "reports",
                    personal_root=Path(tmp) / "Personal",
                )
                self.assertEqual(status_code, 400)
                self.assertEqual(payload["error"], "parent_traversal_is_not_allowed")


if __name__ == "__main__":
    unittest.main()
