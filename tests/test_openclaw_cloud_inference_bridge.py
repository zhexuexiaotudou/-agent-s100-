import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
PROBES_ROOT = REPO_ROOT / "scripts" / "probes"
if str(PROBES_ROOT) not in sys.path:
    sys.path.insert(0, str(PROBES_ROOT))

from openclaw_cloud_inference_bridge import (
    authorized,
    build_web_research_prompt,
    extract_source_urls,
    parse_openclaw_agent_output,
    prompt_from_messages,
    read_bridge_token,
    run_openclaw_agent,
)


class OpenClawCloudInferenceBridgeTest(unittest.TestCase):
    def test_token_authentication_is_exact(self):
        self.assertTrue(authorized("Bearer bridge-token", "bridge-token"))
        self.assertFalse(authorized("Bearer wrong", "bridge-token"))
        self.assertFalse(authorized(None, "bridge-token"))

    def test_token_file_must_not_be_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            token_file = Path(tmp) / "token"
            token_file.write_text("bridge-token\n", encoding="utf-8")
            self.assertEqual(read_bridge_token(token_file), "bridge-token")
            token_file.write_text("\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_bridge_token(token_file)

    def test_prompt_accepts_only_chat_roles_and_enforces_content(self):
        prompt = prompt_from_messages({"messages": [{"role": "user", "content": "Public question"}]})
        self.assertEqual(prompt, "user: Public question")
        with self.assertRaises(ValueError):
            prompt_from_messages({"messages": [{"role": "tool", "content": "run this"}]})

    def test_parser_accepts_openclaw_json_after_non_json_prefix(self):
        output = "notice\n" + json.dumps(
            {"status": "ok", "result": {"payloads": [{"text": "OK"}], "meta": {"toolSummary": {"calls": 1, "tools": ["web_search"], "failures": 0}}}}
        )
        self.assertEqual(parse_openclaw_agent_output(output)["result"]["payloads"][0]["text"], "OK")

    def test_web_research_prompt_requires_search_and_extracts_sources(self):
        prompt = build_web_research_prompt("user: latest public news")
        self.assertIn("must use web_search", prompt)
        self.assertIn("Never use shell", prompt)
        self.assertEqual(
            extract_source_urls("Sources: https://example.com/a. https://example.com/b?q=1"),
            ["https://example.com/a", "https://example.com/b?q=1"],
        )

    def test_agent_run_uses_dedicated_agent_and_verified_web_tools(self):
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    "status": "ok",
                    "result": {
                        "payloads": [{"text": "CURRENT_RESULT https://example.com/source"}],
                        "meta": {
                            "agentMeta": {"provider": "custom-gateway", "model": "MiniMax-M2.7"},
                            "toolSummary": {"calls": 2, "tools": ["tavily_search", "tavily_extract"], "failures": 0},
                        },
                    },
                }
            ),
            stderr="",
        )
        with (
            patch("openclaw_cloud_inference_bridge.uuid.uuid4") as uuid4,
            patch("openclaw_cloud_inference_bridge.subprocess.run", return_value=completed) as run,
        ):
            uuid4.return_value.hex = "abc123"
            answer, result = run_openclaw_agent(
                "/opt/openclaw",
                "web-research",
                "custom-gateway/MiniMax-M2.7",
                "user: hello",
                30,
            )

        self.assertEqual(answer, "CURRENT_RESULT https://example.com/source")
        self.assertEqual(result["provider"], "custom-gateway")
        self.assertEqual(result["tools"], ["tavily_search", "tavily_extract"])
        self.assertEqual(result["sources"], ["https://example.com/source"])
        args = run.call_args.args[0]
        self.assertEqual(args[:4], ["/opt/openclaw", "agent", "--agent", "web-research"])
        self.assertEqual(args[args.index("--session-id") + 1], "ai-nas-web-abc123")
        self.assertNotIn("infer", args)
        self.assertNotIn("shell", args)
        self.assertFalse(run.call_args.kwargs["check"])

    def test_agent_run_rejects_missing_or_unauthorized_tool_use(self):
        def completed(tools: list[str], calls: int = 1) -> subprocess.CompletedProcess:
            return subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=json.dumps(
                    {
                        "status": "ok",
                        "result": {
                            "payloads": [{"text": "answer"}],
                            "meta": {"agentMeta": {}, "toolSummary": {"calls": calls, "tools": tools, "failures": 0}},
                        },
                    }
                ),
                stderr="",
            )

        with patch("openclaw_cloud_inference_bridge.subprocess.run", return_value=completed([], calls=0)):
            with self.assertRaisesRegex(ValueError, "without using"):
                run_openclaw_agent("/opt/openclaw", "web-research", "model", "prompt", 30)
        with patch("openclaw_cloud_inference_bridge.subprocess.run", return_value=completed(["browser"])):
            with self.assertRaisesRegex(ValueError, "unauthorized tools"):
                run_openclaw_agent("/opt/openclaw", "web-research", "model", "prompt", 30)

    def test_systemd_and_configurator_keep_agent_web_only(self):
        unit = (REPO_ROOT / "configs" / "systemd" / "digua-openclaw-cloud-bridge.service").read_text(encoding="utf-8")
        configurator = (REPO_ROOT / "scripts" / "production" / "configure_openclaw_web_research_agent.sh").read_text(encoding="utf-8")
        self.assertIn("--agent web-research", unit)
        self.assertIn("/root/.openclaw/agents/web-research", unit)
        self.assertIn('ALLOWED_TOOLS=\'["web_search","web_fetch","tavily_search","tavily_extract"]\'', configurator)
        self.assertIn('DENIED_TOOLS=\'["read","edit","write","apply_patch","exec"', configurator)


if __name__ == "__main__":
    unittest.main()
