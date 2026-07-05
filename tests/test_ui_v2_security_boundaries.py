import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class UiV2SecurityBoundaryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.js = (REPO_ROOT / "web" / "static" / "digua_ai_nas_v2.js").read_text(encoding="utf-8")

    def test_high_risk_actions_are_not_frontend_commands(self):
        risky_action_pattern = re.compile(
            r'data-action="[^"]*(delete|remove|move|rename|chmod|chown|overwrite|recursive)[^"]*"',
            re.IGNORECASE,
        )
        self.assertIsNone(risky_action_pattern.search(self.js))
        self.assertNotIn('action.operation === "delete"', self.js)
        self.assertNotIn('operation: "delete"', self.js)
        self.assertNotIn("overwrite: true", self.js)

    def test_qwen_is_not_presented_as_tool_executor(self):
        self.assertNotIn("Qwen 执行权", self.js)
        self.assertNotIn("Qwen 可执行", self.js)
        self.assertNotIn("Qwen 可以自主执行", self.js)
        self.assertIn("Harness / allowlist dispatcher", self.js)

    def test_controlled_copy_route_requires_confirmation_chain(self):
        for step in ["copyPreview", "copyDryRun", "copyConfirm", "copyExecute", "copyRollback"]:
            self.assertIn(step, self.js)
        self.assertIn("approvalPhrase", self.js)
        self.assertIn("signed_approval_token", self.js)
        self.assertIn("/api/nas/copy/confirm", self.js)

    def test_no_employee_monitoring_language(self):
        forbidden = ["员工监控", "桌面截图", "键鼠记录", "keyboard tracking", "mouse tracking"]
        for phrase in forbidden:
            self.assertNotIn(phrase, self.js)


if __name__ == "__main__":
    unittest.main()
