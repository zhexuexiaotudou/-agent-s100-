import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class OfflineUiContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = (REPO_ROOT / "web" / "ai_nas_desktop_v2.html").read_text(encoding="utf-8")
        cls.css = (REPO_ROOT / "web" / "static" / "digua_ai_nas_v2.css").read_text(encoding="utf-8")
        cls.js = (REPO_ROOT / "web" / "static" / "digua_ai_nas_v2.js").read_text(encoding="utf-8")

    def test_default_route_is_user_dashboard(self):
        self.assertIn('? routePage : "dashboard"', self.js)
        self.assertIn('"dashboard-welcome"', self.js)
        self.assertIn("现在想做什么？", self.js)
        self.assertNotIn("欢迎回来，管理员", self.js)

    def test_navigation_is_grouped_and_mobile_routes_remain_reachable(self):
        for label in ["常用", "内容", "系统与记录"]:
            self.assertIn(f'label: "{label}"', self.js)
        self.assertIn('const mobilePrimaryNavIds = ["dashboard", "assistant", "files", "media"]', self.js)
        self.assertIn('data-action="openMobileMore"', self.js)
        self.assertIn('aria-current="page"', self.js)
        for page_id in ["dashboard", "assistant", "files", "reports", "tokenBudget", "agentRuntime", "media", "backup", "journal", "audit", "settings"]:
            self.assertRegex(self.js, rf'\{{ id: "{page_id}", label:')

    def test_offline_state_does_not_claim_fake_capacity_or_identity(self):
        for fake_value in ["1.28 TB", "2.00 TB", "64%", '|| "管理员"', "notification-dot"]:
            self.assertNotIn(fake_value, self.js)
        self.assertIn("存储容量待连接", self.js)
        self.assertIn("capacity?.total_bytes", self.js)
        self.assertIn('const userLabel = username || "登录"', self.js)

    def test_expired_session_clears_stale_identity_and_routes_to_login(self):
        self.assertIn("function clearProductSession()", self.js)
        self.assertIn('safeLocalStorageRemove("diguaAiNasToken")', self.js)
        self.assertIn('safeLocalStorageRemove("diguaAiNasUser")', self.js)
        self.assertIn('response.status === 401 && data?.error === "auth_required"', self.js)
        self.assertIn("if (payload.authenticated)", self.js)
        self.assertIn("else {\n          clearProductSession();", self.js)
        self.assertGreaterEqual(self.js.count('button("前往登录", { icon: "lock", page: "files" })'), 2)
        self.assertIn('appState.assistant = { status: "auth"', self.js)

    def test_public_health_distinguishes_online_device_from_authenticated_nas_capacity(self):
        self.assertIn('/api/v1/system/health', self.js)
        self.assertIn('设备已就绪', self.js)
        self.assertIn('登录后读取 NAS 容量与个人空间', self.js)
        self.assertIn('设备在线，容量需登录', self.js)

    def test_assistant_uses_progressive_disclosure(self):
        self.assertIn('const hasAnswer = appState.assistant.status === "ready"', self.js)
        self.assertIn('class="actions assistant-followups"', self.js)
        self.assertIn('class="card assistant-context-details"', self.js)
        self.assertIn("完成一次回答后", self.js)
        self.assertNotIn('contextPanel("可直接尝试"', self.js)

    def test_assistant_model_selection_is_owned_by_workspace_harness(self):
        self.assertIn('模型由 Workspace Harness 自动选择', self.js)
        self.assertIn('const modelRouting = copilot.model_routing || {}', self.js)
        self.assertIn('["Workspace", modelRouting.selected_workspace', self.js)
        self.assertIn('["用户选择模型", modelRouting.user_selectable === false', self.js)
        self.assertIn('本次模型调用', self.js)
        for removed_contract in [
            'id="assistantModelChoice"',
            'appState.assistantModelChoice',
            'model_choice:',
            'diguaAssistantModelChoice',
        ]:
            self.assertNotIn(removed_contract, self.js)
        self.assertLess(
            self.js.index('raw.includes("storage")'),
            self.js.index('raw.includes("document")'),
        )

    def test_files_use_accessible_tabs_and_soft_delete(self):
        self.assertGreaterEqual(self.js.count('role="tab"'), 3)
        self.assertGreaterEqual(self.js.count('aria-selected="${mode ==='), 3)
        self.assertIn("storageTrashButton({ kind: \"document\"", self.js)
        self.assertNotIn("docDeleteFile", self.js)
        self.assertNotIn("/api/documents/delete", self.js)

    def test_visible_copy_avoids_emoji_and_em_dash_placeholders(self):
        self.assertNotIn("—", self.js)
        emoji_pattern = re.compile(r"[\U0001F300-\U0001FAFF]")
        self.assertIsNone(emoji_pattern.search(self.js))
        self.assertNotIn("private_leak_count</span>", self.js)

    def test_accessibility_and_responsive_preflight_rules_exist(self):
        for selector_or_rule in [
            "@media (prefers-color-scheme: dark)",
            "@media (prefers-reduced-motion: reduce)",
            ".textarea::placeholder",
            ".control::placeholder",
            "min-height: 44px",
            "min-width: 44px",
            ".mobile-more-grid",
            ".segmented-control",
        ]:
            self.assertIn(selector_or_rule, self.css)
        self.assertIn('lang="zh-CN"', self.html)
        self.assertIn("<title>地瓜 AI-NAS</title>", self.html)
        self.assertIn("20260718-live-media", self.html)

    def test_authenticated_shell_loads_real_capacity_on_every_entry_page(self):
        self.assertIn("async function loadShellStorageCapacity()", self.js)
        self.assertIn('const storage = await fetchJson("/api/storage/status")', self.js)
        self.assertIn("if (appState.authToken) await loadShellStorageCapacity();", self.js)
        self.assertIn("await loadShellStorageCapacity();\n      showToast", self.js)

    def test_native_static_stack_and_existing_api_contract_remain(self):
        self.assertNotRegex(self.html, r"react|vue|angular|tailwind|bootstrap")
        for endpoint in [
            "/api/harness/status",
            "/api/storage/status",
            "/api/storage/list",
            "/api/copilot/chat",
            "/api/nas/copy/confirm",
            "/api/storage/trash",
        ]:
            self.assertIn(endpoint, self.js)


if __name__ == "__main__":
    unittest.main()
