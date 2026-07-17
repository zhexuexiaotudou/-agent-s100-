import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DeploymentWizardContractTest(unittest.TestCase):
    def test_deploy_wizard_accepts_reviewed_secret_free_discovery_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "discovery.json"
            report.write_text(json.dumps({
                "ok": True,
                "schema": "digua_nas_discovery_v1",
                "discovery_status": "candidate_found",
                "candidates": [{"host": "192.168.1.20", "vendor_hint": "generic_nas", "services": ["nfs"], "nfs_exports": ["/OpenClawWorkspace"], "smb_guest_shares": []}],
                "recommendation": {"host": "192.168.1.20", "protocol": "nfs", "share": "/OpenClawWorkspace", "automatic_selection_safe": True},
                "user_required": ["allowed_share_scope_confirmation"],
                "safety": {"subnet_scan_performed": False, "credentials_attempted": False, "mount_performed": False, "state_changed": False},
            }), encoding="utf-8")
            completed = subprocess.run([
                sys.executable, str(REPO_ROOT / "release" / "install" / "deploy_wizard.py"),
                "--discover-only", "--discovery-json", str(report), "--non-interactive",
            ], cwd=REPO_ROOT, text=True, capture_output=True, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
            self.assertIn("192.168.1.20", completed.stdout)
            self.assertIn("allowed_share_scope_confirmation", completed.stdout)

    def test_deploy_wizard_rejects_discovery_that_did_not_prove_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "unsafe-discovery.json"
            report.write_text(json.dumps({
                "schema": "digua_nas_discovery_v1",
                "safety": {"credentials_attempted": True, "mount_performed": False, "state_changed": False},
            }), encoding="utf-8")
            completed = subprocess.run([
                sys.executable, str(REPO_ROOT / "release" / "install" / "deploy_wizard.py"),
                "--discover-only", "--discovery-json", str(report), "--non-interactive",
            ], cwd=REPO_ROOT, text=True, capture_output=True, check=False)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("credential-free", completed.stderr)

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

    def test_cloud_provider_is_live_probed_and_private_nas_prompts_stay_local(self):
        module = load_module("qwen_gateway_cloud_test", REPO_ROOT / "scripts" / "qwen25_openai_gateway.py")
        observed = {}

        class Provider(BaseHTTPRequestHandler):
            def do_GET(self):
                observed["models_auth"] = self.headers.get("Authorization")
                body = json.dumps({"object": "list", "data": [{"id": "fixture-cloud"}]}).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                observed["chat_auth"] = self.headers.get("Authorization")
                observed["chat"] = json.loads(self.rfile.read(length))
                body = json.dumps({"id": "fixture", "choices": [{"message": {"role": "assistant", "content": "ok"}}]}).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

            def log_message(self, _format, *_args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        names = ("DIGUA_MODEL_MODE", "DIGUA_CLOUD_BASE_URL", "DIGUA_CLOUD_MODEL", "DIGUA_CLOUD_API_KEY_FILE", "DIGUA_ALLOW_INSECURE_CLOUD_ENDPOINT")
        old = {name: os.environ.get(name) for name in names}
        try:
            with tempfile.TemporaryDirectory() as tmp:
                key = Path(tmp) / "cloud-key"
                key.write_text("fixture-secret-key\n", encoding="utf-8")
                os.environ.update({
                    "DIGUA_MODEL_MODE": "cloud",
                    "DIGUA_CLOUD_BASE_URL": f"http://127.0.0.1:{server.server_port}",
                    "DIGUA_CLOUD_MODEL": "fixture-cloud",
                    "DIGUA_CLOUD_API_KEY_FILE": str(key),
                    "DIGUA_ALLOW_INSECURE_CLOUD_ENDPOINT": "1",
                })
                readiness = module.cloud_runtime_readiness()
                self.assertTrue(readiness["inference_ready"], readiness)
                result = module.call_cloud({"messages": [{"role": "user", "content": "public market outlook"}], "metadata": {"private_path": "/mnt/nas/private"}})
                self.assertTrue(result["ok"], result)
                self.assertEqual(observed["chat"]["model"], "fixture-cloud")
                self.assertNotIn("metadata", observed["chat"])
                self.assertEqual(observed["chat_auth"], "Bearer fixture-secret-key")
                self.assertNotIn("fixture-secret-key", json.dumps(readiness) + json.dumps(result))
                allowed, classification = module.cloud_prompt_allowed("summarize my private NAS invoice")
                self.assertFalse(allowed)
                self.assertNotEqual(classification["privacy_level"], "none")
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)
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
        self.assertIn("--model-mode", installer)
        self.assertIn("cloud-api-key", installer)

    def test_verifiers_require_bearer_auth(self):
        verify = (REPO_ROOT / "release" / "scripts" / "verify_install.py").read_text(encoding="utf-8")
        smoke = (REPO_ROOT / "scripts" / "product_smoke_test.py").read_text(encoding="utf-8")
        self.assertIn('headers["Authorization"] = f"Bearer {token}"', verify)
        self.assertIn('headers["Authorization"] = f"Bearer {token}"', smoke)
        self.assertIn("admin_token_missing", smoke)


if __name__ == "__main__":
    unittest.main()
