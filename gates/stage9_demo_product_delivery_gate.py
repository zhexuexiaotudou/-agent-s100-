from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

from ai_space_gate_common import add_common_args, check, write_gate
from stage8_demo_common import gate_payload


NAME = "stage9_demo_product_delivery_gate"
SUB_GATES = [
    "stage8_demo1_link_readiness_gate.py",
    "stage8_auto_organize_move_rename_gate.py",
    "stage8_auto_organize_delete_block_gate.py",
    "stage8_auto_organize_rollback_gate.py",
    "stage8_assistant_trace_global_coverage_gate.py",
    "stage8_demo2_ai_nas_features_gate.py",
    "stage8_demo3_qwen_router_trace_gate.py",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate Stage8 demo product delivery gates and product smoke.")
    add_common_args(parser)
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--qwen-url", default="http://127.0.0.1:18080/health")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()
    gate_dir = Path(__file__).resolve().parent
    results: dict[str, dict[str, Any]] = {}
    report_files: list[Path] = []
    for gate in SUB_GATES:
        cmd = [sys.executable, str(gate_dir / gate), "--report-root", str(args.report_root), "--base-url", args.base_url] if gate.startswith("stage8_demo") else [sys.executable, str(gate_dir / gate), "--report-root", str(args.report_root)]
        if gate == "stage8_demo1_link_readiness_gate.py":
            cmd.extend(["--qwen-url", args.qwen_url])
        if args.personal_root:
            cmd.extend(["--personal-root", str(args.personal_root)])
        cmd.extend(["--timeout", str(args.timeout)]) if gate in {"stage8_demo1_link_readiness_gate.py", "stage8_demo2_ai_nas_features_gate.py", "stage8_demo3_qwen_router_trace_gate.py"} else None
        completed = subprocess.run(cmd, text=True, capture_output=True, check=False)
        json_path = args.report_root / gate.replace(".py", ".json")
        if json_path.exists():
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            payload["subprocess_returncode"] = completed.returncode
            results[gate] = payload
            report_files.extend([p for p in [json_path, json_path.with_suffix(".md")] if p.exists()])
        else:
            results[gate] = {"ok": False, "verdict": "missing_report", "stdout": completed.stdout[-2000:], "stderr": completed.stderr[-2000:], "returncode": completed.returncode}

    smoke = _run_product_smoke(args.base_url, args.report_root, args.timeout)
    results["product_smoke_test.py"] = smoke
    if smoke.get("json_path"):
        path = Path(str(smoke["json_path"]))
        report_files.extend([p for p in [path, path.with_suffix(".md")] if p.exists()])

    checks = [check(name, bool(result.get("ok")), result.get("verdict") or result.get("error")) for name, result in results.items()]
    checks.append(check("evidence files exist", bool(report_files) and all(path.exists() for path in report_files), len(report_files)))
    sha256 = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in report_files if path.exists()}
    bundle = _bundle(report_files)
    payload = gate_payload("ok_stage9_demo_product_delivery_gate", "blocked_stage9_demo_product_delivery_gate", checks, {"sub_gates": results, "report_sha256": sha256, "gptpro_bundle": str(bundle) if bundle else None})
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    if bundle:
        print(bundle)
    return 0 if payload["ok"] else 1


def _run_product_smoke(base_url: str, report_root: Path, timeout: int) -> dict[str, Any]:
    cmd = [sys.executable, str(Path("scripts") / "product_smoke_test.py"), "--base-url", base_url, "--report-root", str(report_root), "--timeout", str(timeout)]
    completed = subprocess.run(cmd, text=True, capture_output=True, check=False)
    candidates = sorted(report_root.glob("product_smoke_test_*/product_smoke_test.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        return {"ok": False, "verdict": "missing_product_smoke_report", "stdout": completed.stdout[-2000:], "stderr": completed.stderr[-2000:], "returncode": completed.returncode}
    payload = json.loads(candidates[0].read_text(encoding="utf-8"))
    payload["json_path"] = str(candidates[0])
    payload["subprocess_returncode"] = completed.returncode
    return payload


def _bundle(report_files: list[Path]) -> Path | None:
    try:
        evidence_dir = Path("evidence_for_gptpro")
        evidence_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = evidence_dir / f"digua_demo_product_delivery_{time.strftime('%Y%m%d-%H%M%S')}.zip"
        with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in report_files:
                if path.exists():
                    zf.write(path, arcname=path.name)
        return bundle_path
    except Exception:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
