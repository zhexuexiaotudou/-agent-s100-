import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DeploymentWizardContractTest(unittest.TestCase):
    def test_qwen_health_requires_runtime_files(self):
        module = load_module("qwen_gateway_deploy_test", REPO_ROOT / "scripts" / "qwen25_openai_gateway.py")
        policy = json.loads((REPO_ROOT / "configs" / "qwen25_official_route_policy.json").read_text(encoding="utf-8"))
        old = {name: os.environ.get(name) for name in ("QWEN25_RUNTIME_BIN", "QWEN25_RUNTIME_CONFIG", "QWEN25_RUNTIME_LIB_DIR", "QWEN25_ACTIVE_HBM_PATH")}
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                paths = {"QWEN25_RUNTIME_BIN": root / "runtime", "QWEN25_RUNTIME_CONFIG": root / "config.json", "QWEN25_RUNTIME_LIB_DIR": root / "lib", "QWEN25_ACTIVE_HBM_PATH": root / "model.hbm"}
                for name, path in paths.items():
                    os.environ[name] = str(path)
                self.assertFalse(module.runtime_readiness(policy)["ok"])
                paths["QWEN25_RUNTIME_BIN"].write_text("fixture", encoding="utf-8")
                paths["QWEN25_RUNTIME_BIN"].chmod(0o755)
                paths["QWEN25_RUNTIME_CONFIG"].write_text("{}", encoding="utf-8")
                paths["QWEN25_RUNTIME_LIB_DIR"].mkdir()
                paths["QWEN25_ACTIVE_HBM_PATH"].write_text("fixture", encoding="utf-8")
                self.assertTrue(module.runtime_readiness(policy)["inference_ready"])
        finally:
            for name, value in old.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def test_first_run_bootstraps_real_identity_store_without_token_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            install = root / "install"
            mount = root / "nas"
            personal = mount / "Personal"
            report = mount / "reports" / "qwen25_ai_nas"
            install.mkdir()
            personal.mkdir(parents=True)
            env = dict(os.environ)
            env["DIGUA_ADMIN_PASSWORD"] = "offline-test-password"
            out = root / "wizard.json"
            completed = subprocess.run([
                sys.executable, str(REPO_ROOT / "release" / "install" / "first_run_wizard.py"),
                "--install-root", str(install), "--app-root", str(REPO_ROOT),
                "--nas-mount", str(mount), "--personal-root", str(personal),
                "--report-root", str(report), "--wizard-report-out", str(out),
                "--simulation",
            ], cwd=REPO_ROOT, env=env, text=True, capture_output=True, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertTrue(payload["authentication"]["ok"])
            self.assertTrue((report / "identity.sqlite3").exists())
            self.assertFalse((install / "secrets" / "admin_token").exists())
            self.assertNotIn("offline-test-password", out.read_text(encoding="utf-8"))
            self.assertFalse(payload["production_verified"])

    def test_shell_contracts_do_not_claim_dry_run_as_apply(self):
        installer = (REPO_ROOT / "release" / "install" / "install_s100p.sh").read_text(encoding="utf-8")
        nas = (REPO_ROOT / "release" / "install" / "configure_nas_mount.sh").read_text(encoding="utf-8")
        upgrade = (REPO_ROOT / "release" / "install" / "upgrade_s100p.sh").read_text(encoding="utf-8")
        uninstall = (REPO_ROOT / "release" / "install" / "uninstall_s100p.sh").read_text(encoding="utf-8")
        self.assertIn("--simulate-root", installer)
        self.assertIn("--apply --strict", installer)
        self.assertIn("QWEN25_TOOL_DISPATCHER", installer)
        self.assertIn("findmnt -n -o SOURCE", nas)
        self.assertIn("# BEGIN DIGUA-AI-NAS", nas)
        self.assertIn("--rollback-from", upgrade)
        self.assertNotIn("digua-ai-nightly-index.timer", uninstall)

    def test_verifiers_require_bearer_auth(self):
        verify = (REPO_ROOT / "release" / "scripts" / "verify_install.py").read_text(encoding="utf-8")
        smoke = (REPO_ROOT / "scripts" / "product_smoke_test.py").read_text(encoding="utf-8")
        self.assertIn('headers["Authorization"] = f"Bearer {token}"', verify)
        self.assertIn('headers["Authorization"] = f"Bearer {token}"', smoke)
        self.assertIn("admin_token_missing", smoke)


if __name__ == "__main__":
    unittest.main()
