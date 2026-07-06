from __future__ import annotations

import argparse
import json
import sys
import tarfile
from pathlib import Path

from ai_space_gate_common import check, write_gate
from stage10_common import add_stage10_args, gate_payload, run_cmd


NAME = "stage10_release_package_integrity_gate"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and verify the Stage 10 release package.")
    add_stage10_args(parser)
    parser.add_argument("--version", default="0.1.0")
    parser.add_argument("--dist", default="dist")
    args = parser.parse_args()
    run = run_cmd([sys.executable, "scripts/build_release.py", "--version", args.version, "--out", args.dist], timeout=180)
    manifest_path = Path(args.dist) / "release_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest_consistency = packaged_manifest_consistency(manifest)
    checks = [
        check("release manifest exists", bool(manifest), run.get("stderr")),
        check("release package ok", manifest.get("ok") is True, manifest.get("forbidden_files")),
        check("tar package exists", Path(str(manifest.get("tar_gz") or "")).exists(), manifest.get("tar_gz")),
        check("zip package exists", Path(str(manifest.get("zip") or "")).exists(), manifest.get("zip")),
        check("no model weights", (manifest.get("self_check") or {}).get("no_model_weights") is True, manifest.get("self_check")),
        check("no third-party images", (manifest.get("self_check") or {}).get("no_third_party_images") is True, manifest.get("self_check")),
        check("no private user data", (manifest.get("self_check") or {}).get("no_private_user_data") is True, manifest.get("self_check")),
        check("no secrets", (manifest.get("self_check") or {}).get("no_secrets") is True, manifest.get("self_check")),
        check("manifest-packaged sample files present", manifest_consistency["ok"], manifest_consistency),
    ]
    payload = gate_payload("ok_stage10_release_package_integrity_gate", "blocked_stage10_release_package_integrity_gate", checks, {"release_manifest": manifest, "run": run})
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    return 0 if payload["ok"] else 1


def packaged_manifest_consistency(manifest: dict) -> dict:
    files = set(manifest.get("files") or [])
    missing_from_file_list: list[str] = []
    missing_from_tar: list[str] = []
    checked_records = 0

    tar_members = tar_member_files(manifest)
    for manifest_rel in sorted(path for path in files if path.startswith("demo_corpus/manifests/") and path.endswith(".jsonl")):
        manifest_path = Path(manifest_rel)
        if not manifest_path.exists():
            continue
        for line_number, line in enumerate(manifest_path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("release_package_includes_file") is not True:
                continue
            local_rel = str(record.get("local_rel") or "").replace("\\", "/")
            expected = f"demo_corpus/{local_rel}"
            checked_records += 1
            if expected not in files:
                missing_from_file_list.append(f"{manifest_rel}:{line_number}:{expected}")
            if tar_members and expected not in tar_members:
                missing_from_tar.append(f"{manifest_rel}:{line_number}:{expected}")

    return {
        "ok": not missing_from_file_list and not missing_from_tar,
        "checked_records": checked_records,
        "missing_from_file_list": missing_from_file_list,
        "missing_from_tar": missing_from_tar,
    }


def tar_member_files(manifest: dict) -> set[str]:
    tar_path = Path(str(manifest.get("tar_gz") or ""))
    if not tar_path.exists():
        return set()
    package_prefix = str(manifest.get("package_name") or "").rstrip("/") + "/"
    members: set[str] = set()
    with tarfile.open(tar_path, "r:gz") as tf:
        for member in tf.getmembers():
            if not member.isfile() or not member.name.startswith(package_prefix):
                continue
            members.add(member.name[len(package_prefix) :])
    return members


if __name__ == "__main__":
    raise SystemExit(main())
