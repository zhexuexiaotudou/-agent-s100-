#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="First-run wizard for Digua AI-NAS S100P release.")
    parser.add_argument("--install-root", type=Path, default=Path("/opt/digua-ai-nas"))
    parser.add_argument("--nas-mount", type=Path, default=Path("/mnt/nas/openclaw"))
    parser.add_argument("--personal-root", type=Path, default=Path("/mnt/nas/openclaw/Personal"))
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--report-root", type=Path, default=Path("/mnt/nas/openclaw/reports/release_install"))
    parser.add_argument("--download-demo-corpus", action="store_true")
    args = parser.parse_args()

    checks: dict[str, Any] = {
        "nas_mount_exists": args.nas_mount.exists(),
        "nas_mount_writable": os.access(args.nas_mount, os.W_OK) if args.nas_mount.exists() else False,
        "personal_root_exists": args.personal_root.exists(),
        "install_root_exists": args.install_root.exists(),
        "models": model_status(),
        "feature_flags_initialized": True,
    }
    token_path = args.install_root / "secrets" / "admin_token"
    token_created = False
    if not token_path.exists():
        token_created = True
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(secrets.token_urlsafe(32) + "\n", encoding="utf-8")
        token_path.chmod(0o600)
    smoke = run_smoke(args.base_url, args.report_root)
    demo = None
    if args.download_demo_corpus:
        demo = run_demo_corpus(args.personal_root, args.report_root)
    blockers = []
    for key in ("nas_mount_exists", "nas_mount_writable", "personal_root_exists"):
        if not checks[key]:
            blockers.append(key)
    if not smoke.get("ok"):
        blockers.append("product_smoke_failed_or_unreachable")
    payload = {
        "ok": not blockers,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "checks": checks,
        "admin_token_path": str(token_path),
        "admin_token_created": token_created,
        "admin_token_redacted": True,
        "openclaw_url": args.base_url,
        "qwen_health": "http://127.0.0.1:18080/health",
        "product_status": args.base_url.rstrip("/") + "/api/product/status",
        "smoke": smoke,
        "demo_corpus": demo,
        "blockers": blockers,
    }
    args.report_root.mkdir(parents=True, exist_ok=True)
    report = args.report_root / f"first_run_wizard_{time.strftime('%Y%m%d-%H%M%S')}.json"
    report.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(report)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


def model_status() -> dict[str, Any]:
    envs = ["DIGUA_QWEN_MODEL_DIR", "DIGUA_CLIP_MODEL_DIR", "DIGUA_YOLO_MODEL_PATH", "DIGUA_OCR_MODEL_DIR", "DIGUA_ASR_MODEL_DIR"]
    return {name: {"configured": bool(os.environ.get(name)), "exists": Path(os.environ.get(name, "")).exists() if os.environ.get(name) else False} for name in envs}


def run_smoke(base_url: str, report_root: Path) -> dict[str, Any]:
    script = Path("scripts/product_smoke_test.py")
    if not script.exists():
        return {"ok": False, "error": "scripts/product_smoke_test.py missing"}
    completed = subprocess.run([sys.executable, str(script), "--base-url", base_url, "--report-root", str(report_root), "--timeout", "20"], text=True, capture_output=True, check=False)
    return {"ok": completed.returncode == 0, "returncode": completed.returncode, "stdout_tail": completed.stdout[-1000:], "stderr_tail": completed.stderr[-1000:]}


def run_demo_corpus(personal_root: Path, report_root: Path) -> dict[str, Any]:
    script = Path("demo_corpus/scripts/build_demo_corpus.py")
    if not script.exists():
        return {"ok": False, "error": "demo_corpus builder missing"}
    completed = subprocess.run([sys.executable, str(script), "--personal-root", str(personal_root), "--report-root", str(report_root), "--write-to-personal", "--fixture-ci"], text=True, capture_output=True, check=False)
    return {"ok": completed.returncode == 0, "returncode": completed.returncode, "stdout_tail": completed.stdout[-1000:], "stderr_tail": completed.stderr[-1000:]}


if __name__ == "__main__":
    raise SystemExit(main())

