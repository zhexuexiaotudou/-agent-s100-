import unittest
from pathlib import Path

from scripts.build_release import collect_files


REPO_ROOT = Path(__file__).resolve().parents[1]


class ReleaseContractTest(unittest.TestCase):
    def test_release_collects_runnable_application(self):
        files = {path.relative_to(REPO_ROOT).as_posix() for path in collect_files()}
        required = {
            "requirements.txt",
            "scripts/metrics_detector.py",
            "scripts/probes/ai_nas_operator_portal_server.py",
            "scripts/probes/safety_attack_probe.py",
            "scripts/qwen25_openai_gateway.py",
            "src/product_jobs/worker.py",
            "web/ai_nas_desktop_v2.html",
        }
        self.assertTrue(required <= files, required - files)
        self.assertFalse(
            any(path.startswith("dream_s100p_lladacpp/") for path in files)
        )

    def test_release_units_use_rendered_install_paths_and_valid_portal_cli(self):
        gateway = (
            REPO_ROOT / "release" / "systemd" / "openclaw-gateway.service"
        ).read_text(encoding="utf-8")
        worker = (
            REPO_ROOT / "release" / "systemd" / "digua-ai-index-worker.service"
        ).read_text(encoding="utf-8")
        self.assertIn("@DIGUA_INSTALL_ROOT@/app", gateway)
        self.assertIn("--bind 127.0.0.1", gateway)
        self.assertNotIn("--host 127.0.0.1", gateway)
        self.assertIn("-m src.product_jobs.worker", worker)
        self.assertIn("--personal-root @DIGUA_PERSONAL_ROOT@", worker)
        installer = (
            REPO_ROOT / "release" / "install" / "install_systemd_units.sh"
        ).read_text(encoding="utf-8")
        self.assertNotIn("digua-ai-nightly-index.timer", installer)

    def test_clean_install_gate_checks_app_not_only_venv(self):
        source = (
            REPO_ROOT / "gates" / "stage10_release_clean_install_gate.py"
        ).read_text(encoding="utf-8")
        self.assertIn("application source copied", source)
        self.assertIn("portal entrypoint copied", source)
        self.assertIn("web UI copied", source)


if __name__ == "__main__":
    unittest.main()
