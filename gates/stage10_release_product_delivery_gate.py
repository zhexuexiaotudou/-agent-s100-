from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ai_space_gate_common import check, write_gate
from stage10_common import add_stage10_args, bundle_stage10, gate_payload, run_cmd


NAME = "stage10_release_product_delivery_gate"
SUB_GATES = [
    "stage10_demo_corpus_recording_readiness_gate.py",
    "stage10_release_preflight_gate.py",
    "stage10_release_installer_dry_run_gate.py",
    "stage10_release_clean_install_gate.py",
    "stage10_release_cloud_install_gate.py",
    "stage10_release_nas_mount_gate.py",
    "stage10_release_product_smoke_gate.py",
    "stage10_release_upgrade_rollback_gate.py",
    "stage10_release_package_integrity_gate.py",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate Stage 10 release product delivery acceptance.")
    add_stage10_args(parser)
    parser.add_argument("--demo-image", default="")
    args = parser.parse_args()
    results = {}
    for gate in SUB_GATES:
        cmd = [sys.executable, str(Path(__file__).resolve().parent / gate), "--report-root", str(args.report_root), "--corpus-root", str(args.corpus_root), "--base-url", args.base_url, "--qwen-url", args.qwen_url, "--timeout", str(args.timeout)]
        if args.personal_root:
            cmd.extend(["--personal-root", str(args.personal_root)])
        if args.auth_token:
            cmd.extend(["--auth-token", args.auth_token])
        if gate == "stage10_demo_corpus_recording_readiness_gate.py" and args.demo_image:
            cmd.extend(["--demo-image", args.demo_image])
        run = run_cmd(cmd, timeout=args.timeout + 480)
        path = args.report_root / gate.replace(".py", ".json")
        results[gate] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"ok": False, "verdict": "missing_report", "run": run}
    checks = [check(gate, result.get("ok") is True, result.get("verdict")) for gate, result in results.items()]
    bundle, digest = bundle_stage10(args.report_root)
    manifest = {}
    manifest_path = Path("dist") / "release_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    yolo_gate = results.get("stage10_demo_corpus_recording_readiness_gate.py", {}).get("evidence", {}).get("sub_gates", {}).get("stage10_yolo_bbox_recording_gate.py", {})
    payload = gate_payload(
        "ok_stage10_release_product_delivery_gate",
        "blocked_stage10_release_product_delivery_gate",
        checks,
        {
            "sub_gates": results,
            "release_manifest": manifest,
            "dist_package": manifest.get("tar_gz"),
            "dist_sha256": (manifest.get("sha256") or {}).get(Path(str(manifest.get("tar_gz") or "")).name),
            "gptpro_bundle": str(bundle) if bundle else None,
            "gptpro_bundle_sha256": digest,
            "yolo_recording_boundary": (yolo_gate.get("evidence") or {}).get("recording_blocker"),
        },
    )
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    if bundle:
        print(bundle)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
