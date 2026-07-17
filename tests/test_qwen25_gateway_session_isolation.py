import importlib.util
import io
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "qwen25_openai_gateway.py"
SPEC = importlib.util.spec_from_file_location("qwen25_gateway_session_test", MODULE_PATH)
assert SPEC and SPEC.loader
gateway = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gateway
SPEC.loader.exec_module(gateway)


class FakePersistentProcess:
    def __init__(self, output: str) -> None:
        self.stdin = io.StringIO()
        self.stdout = io.StringIO(output)
        self.killed = False

    def poll(self):
        return None

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout: int = 0) -> int:
        return 0


class Qwen25GatewaySessionIsolationTest(unittest.TestCase):
    def setUp(self) -> None:
        gateway._BPU_PROCESS = None
        gateway._BPU_POLICY_HASH = None
        gateway._BPU_READY = False
        self.policy = {
            "official_runtime": {
                "runtime_bin": "/fake/oellm_multichat",
                "active_config": "/fake/qwen_multichat_config.json",
                "runtime_lib_dir": "/fake/lib",
                "chat_timeout_seconds": 5,
            }
        }

    def tearDown(self) -> None:
        gateway._BPU_PROCESS = None
        gateway._BPU_POLICY_HASH = None
        gateway._BPU_READY = False

    def attach_process(self, output: str) -> FakePersistentProcess:
        process = FakePersistentProcess(output)
        gateway._BPU_PROCESS = process
        gateway._BPU_POLICY_HASH = gateway._bpu_policy_hash(self.policy)
        gateway._BPU_READY = True
        return process

    def test_each_prompt_resets_multichat_and_strips_control_token(self):
        process = self.attach_process(
            "[User] <<< "
            "[Assistant] >>> \u6211\u662f\u5730\u74dc AI-NAS \u7684\u672c\u5730 AI \u52a9\u624b\u3002<|im_end|>\n"
            "[User] <<< "
        )

        result = gateway.run_qwen_runtime(self.policy, "\u4f60\u662f\u8c01")

        self.assertTrue(result["ok"])
        self.assertEqual(result["answer"], "\u6211\u662f\u5730\u74dc AI-NAS \u7684\u672c\u5730 AI \u52a9\u624b\u3002")
        self.assertTrue(result["session_reset"])
        self.assertEqual(result["runtime_retry_count"], 0)
        self.assertEqual(process.stdin.getvalue(), "reset\n\u4f60\u662f\u8c01\n")

    def test_consecutive_requests_each_start_with_reset_and_keep_answers_separate(self):
        process = self.attach_process(
            "[User] <<< "
            "[Assistant] >>> first answer<|im_end|>\n[User] <<< "
            "[User] <<< "
            "[Assistant] >>> second answer<|im_end|>\n[User] <<< "
        )

        first = gateway.run_qwen_runtime(self.policy, "first question")
        second = gateway.run_qwen_runtime(self.policy, "second question")

        self.assertEqual(first["answer"], "first answer")
        self.assertEqual(second["answer"], "second answer")
        self.assertEqual(
            process.stdin.getvalue(),
            "reset\nfirst question\nreset\nsecond question\n",
        )

    def test_control_token_only_output_is_not_a_valid_answer(self):
        self.assertEqual(gateway._sanitize_bpu_answer("<|im_end|>"), "")
        self.assertEqual(gateway._sanitize_bpu_answer("<|im_start|>assistant<|im_end|>"), "assistant")


if __name__ == "__main__":
    unittest.main()
