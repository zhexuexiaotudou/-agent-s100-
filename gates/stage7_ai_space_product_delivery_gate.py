from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

from ai_space_gate_common import add_common_args, blockers, check, verdict, write_gate


NAME = "stage7_ai_space_product_delivery_gate"
SUB_GATES = [
    "stage6_multimodal_live_clip_gate.py",
    "stage6_person_attribute_search_gate.py",
    "stage7_ai_space_catalog_gate.py",
    "stage7_smart_classification_gate.py",
    "stage7_subtitle_extraction_gate.py",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate AI Space product delivery gate.")
    add_common_args(parser)
    args = parser.parse_args()
    gate_dir = Path(__file__).resolve().parent
    results = {}
    report_files: list[Path] = []
    for gate in SUB_GATES:
        cmd = [sys.executable, str(gate_dir / gate), "--report-root", str(args.report_root)]
        if args.personal_root:
            cmd.extend(["--personal-root", str(args.personal_root)])
        if args.no_rebuild:
            cmd.append("--no-rebuild")
        completed = subprocess.run(cmd, text=True, capture_output=True, check=False)
        json_path = args.report_root / gate.replace(".py", ".json")
        if json_path.exists():
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            results[gate] = payload
            report_files.append(json_path)
            md_path = json_path.with_suffix(".md")
            if md_path.exists():
                report_files.append(md_path)
        else:
            results[gate] = {"ok": False, "verdict": "missing_report", "stdout": completed.stdout, "stderr": completed.stderr}
    checks = [check(gate, bool(result.get("ok")), result.get("verdict")) for gate, result in results.items()]
    checks.extend(
        [
            check("all reports have SHA256", all(path.exists() for path in report_files), len(report_files)),
        ]
    )
    sha256 = {}
    for path in report_files:
        sha256[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    bundle_path = None
    evidence_dir = Path("evidence_for_gptpro")
    try:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = evidence_dir / "digua_ai_space_product_delivery_latest.zip"
        with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in report_files:
                zf.write(path, arcname=path.name)
    except Exception:
        bundle_path = None
    payload = {
        "ok": all(item["ok"] for item in checks),
        "verdict": verdict("ok_stage7_ai_space_product_delivery_gate", "blocked_stage7_ai_space_product_delivery_gate", checks),
        "checks": checks,
        "blockers": blockers(checks),
        "sub_gates": results,
        "report_sha256": sha256,
        "gptpro_bundle": str(bundle_path) if bundle_path else None,
    }
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    if bundle_path:
        print(bundle_path)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
