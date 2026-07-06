from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

from ai_space_gate_common import add_common_args, blockers, check, verdict, write_gate


NAME = "stage7_smart_album_classification_delivery_gate"
SUB_GATES = [
    "stage7_media_album_nonzero_gate.py",
    "stage7_chinese_smart_naming_gate.py",
    "stage7_upload_auto_classify_gate.py",
    "stage7_smart_classification_gate.py",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate smart album auto classification and Chinese naming delivery gate.")
    add_common_args(parser)
    args = parser.parse_args()
    gate_dir = Path(__file__).resolve().parent
    results: dict[str, dict[str, Any]] = {}
    report_files: list[Path] = []
    for gate in SUB_GATES:
        cmd = [sys.executable, str(gate_dir / gate), "--report-root", str(args.report_root)]
        if args.personal_root:
            cmd.extend(["--personal-root", str(args.personal_root)])
        if args.no_rebuild and gate != "stage7_upload_auto_classify_gate.py":
            cmd.append("--no-rebuild")
        completed = subprocess.run(cmd, text=True, capture_output=True, check=False)
        json_path = args.report_root / gate.replace(".py", ".json")
        if json_path.exists():
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            payload["subprocess_returncode"] = completed.returncode
            results[gate] = payload
            report_files.append(json_path)
            md_path = json_path.with_suffix(".md")
            if md_path.exists():
                report_files.append(md_path)
        else:
            results[gate] = {"ok": False, "verdict": "missing_report", "stdout": completed.stdout[-2000:], "stderr": completed.stderr[-2000:]}

    checks = [check(gate, bool(result.get("ok")), result.get("verdict")) for gate, result in results.items()]
    checks.append(check("all report files exist", all(path.exists() for path in report_files), len(report_files)))
    sha256 = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in report_files if path.exists()}
    bundle_path = _bundle(report_files)
    payload = {
        "ok": all(item["ok"] for item in checks),
        "verdict": verdict("ok_stage7_smart_album_classification_delivery_gate", "blocked_stage7_smart_album_classification_delivery_gate", checks),
        "checks": checks,
        "blockers": blockers(checks),
        "sub_gates": results,
        "report_sha256": sha256,
        "gptpro_bundle": str(bundle_path) if bundle_path else None,
        "claim_boundary": {
            "physical_rename_enabled": False,
            "physical_move_enabled": False,
            "copy_execute_requires_harness": True,
            "face_recognition_used": False,
            "cloud_person_recognition_used": False,
            "raw_path_returned": False,
        },
    }
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    if bundle_path:
        print(bundle_path)
    return 0 if payload["ok"] else 1


def _bundle(report_files: list[Path]) -> Path | None:
    try:
        evidence_dir = Path("evidence_for_gptpro")
        evidence_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = evidence_dir / "digua_smart_album_classification_delivery_latest.zip"
        with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in report_files:
                if path.exists():
                    zf.write(path, arcname=path.name)
        return bundle_path
    except Exception:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
