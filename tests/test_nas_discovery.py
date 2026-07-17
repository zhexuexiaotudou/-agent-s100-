import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("digua_discover_nas", REPO_ROOT / "release" / "install" / "discover_nas.py")
assert SPEC and SPEC.loader
DISCOVERY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DISCOVERY)


class NasDiscoveryTest(unittest.TestCase):
    def test_parsers_keep_discovery_secret_free(self):
        self.assertEqual(DISCOVERY.parse_neighbours("192.168.1.20 dev eth0 REACHABLE\n192.168.1.21 dev eth0 FAILED\n"), ["192.168.1.20"])
        self.assertEqual(
            DISCOVERY.parse_avahi("=;eth0;IPv4;NAS;_http._tcp;local;nas.local;192.168.1.20;5000;\n"),
            ["192.168.1.20"],
        )
        self.assertEqual(DISCOVERY.parse_nfs_exports("Export list for nas:\n/OpenClawWorkspace 192.168.1.0/24\n"), ["/OpenClawWorkspace"])
        self.assertEqual(DISCOVERY.parse_smb_shares("Disk|OpenClawWorkspace|AI files\nIPC|IPC$|IPC\n"), ["OpenClawWorkspace"])

    def test_single_nfs_candidate_is_recommended_without_login(self):
        outputs = {
            ("findmnt", "-J", "-t", "nfs,nfs4,cifs", "-o", "SOURCE,TARGET,FSTYPE"): '{"filesystems":[]}',
            ("ip", "neigh", "show"): "192.168.1.20 dev eth0 REACHABLE\n",
            ("avahi-browse", "-artp"): "",
            ("showmount", "-e", "192.168.1.20"): "Export list:\n/OpenClawWorkspace 192.168.1.0/24\n",
        }

        def runner(command, _timeout):
            return outputs.get(tuple(command), "")

        def connector(_host, port, _timeout):
            return port in {2049, 443}

        result = DISCOVERY.discover(runner=runner, connector=connector)
        self.assertEqual(result["recommendation"], {"host": "192.168.1.20", "protocol": "nfs", "share": "/OpenClawWorkspace", "automatic_selection_safe": True})
        self.assertTrue(result["safety"]["subnet_scan_performed"] is False)
        self.assertTrue(all(item["credentials_attempted"] is False for item in result["candidates"]))
        self.assertNotIn("nas_ip_or_hostname", result["user_required"])

    def test_ambiguous_candidates_require_user_selection(self):
        outputs = {
            ("findmnt", "-J", "-t", "nfs,nfs4,cifs", "-o", "SOURCE,TARGET,FSTYPE"): '{"filesystems":[]}',
            ("ip", "neigh", "show"): "192.168.1.20 dev eth0 STALE\n192.168.1.30 dev eth0 REACHABLE\n",
            ("avahi-browse", "-artp"): "",
        }
        result = DISCOVERY.discover(runner=lambda command, _: outputs.get(tuple(command), ""), connector=lambda _host, port, _timeout: port == 2049)
        self.assertFalse(result["recommendation"]["automatic_selection_safe"])
        self.assertIn("nas_ip_or_hostname", result["user_required"])

    def test_management_page_alone_is_not_a_safe_mount_recommendation(self):
        outputs = {
            ("findmnt", "-J", "-t", "nfs,nfs4,cifs", "-o", "SOURCE,TARGET,FSTYPE"): '{"filesystems":[]}',
            ("ip", "neigh", "show"): "192.168.1.20 dev eth0 REACHABLE\n",
            ("avahi-browse", "-artp"): "",
        }
        result = DISCOVERY.discover(
            runner=lambda command, _: outputs.get(tuple(command), ""),
            connector=lambda _host, port, _timeout: port == 5000,
        )
        self.assertFalse(result["recommendation"]["automatic_selection_safe"])
        self.assertIn("nas_ip_or_hostname", result["user_required"])


if __name__ == "__main__":
    unittest.main()
