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
    parse_openclaw_output,
    prompt_from_messages,
    read_bridge_token,
    run_openclaw_model,
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
        output = 'notice\n' + json.dumps({"ok": True, "provider": "custom-gateway", "model": "MiniMax-M2.7", "outputs": [{"text": "OK"}]})
        self.assertEqual(parse_openclaw_output(output)["outputs"][0]["text"], "OK")

    def test_model_run_uses_gateway_and_no_shell(self):
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"ok": True, "provider": "custom-gateway", "model": "MiniMax-M2.7", "outputs": [{"text": "MINIMAX_OK"}]}),
            stderr="",
        )
        with patch("openclaw_cloud_inference_bridge.subprocess.run", return_value=completed) as run:
            answer, result = run_openclaw_model("/opt/openclaw", "custom-gateway/MiniMax-M2.7", "user: hello", 30)

        self.assertEqual(answer, "MINIMAX_OK")
        self.assertEqual(result["provider"], "custom-gateway")
        args = run.call_args.args[0]
        self.assertEqual(args[:5], ["/opt/openclaw", "infer", "model", "run", "--gateway"])
        self.assertNotIn("shell", run.call_args.kwargs)
        self.assertFalse(run.call_args.kwargs["check"])


if __name__ == "__main__":
    unittest.main()
