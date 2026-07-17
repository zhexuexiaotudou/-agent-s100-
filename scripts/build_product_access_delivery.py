from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERDICT = "product_access_code_complete_s100p_execution_bundle_ready"
INCLUDES = [
    "src/product_access", "scripts/probes/ai_nas_identity.py", "scripts/digua-access", "scripts/digua-doctor",
    "scripts/build_product_access_delivery.py", "deploy/product_access", "config", "release/avahi",
    "release/systemd/digua-product-access.service", "release/systemd/digua-product-remote-ingress.service",
    "release/install", "requirements.txt", "web/ai_nas_desktop_v2.html", "web/static/digua_ai_nas_v2.css", "web/static/digua_ai_nas_v2.js",
    "web/static/pwa-icon-192.svg", "web/static/pwa-icon-512.svg", "tests/test_product_access.py",
    "gates/stage10_release_clean_install_gate.py", "docs/product_access", "docs/security/PRODUCT_ACCESS_THREAT_MODEL.md",
    "reports/access", "validation/product_access_s100p", "GPT_REVIEW_PRODUCT_ACCESS_PROMPT.md",
]


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False)
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except OSError:
        return "unknown"


def copy_inputs(stage: Path) -> None:
    for relative in INCLUDES:
        source = ROOT / relative
        if not source.exists():
            raise FileNotFoundError(relative)
        target = stage / relative
        if source.is_dir():
            shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.sqlite*", "*.db", ".pytest_cache"))
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


SELF_CHECK = r'''#!/usr/bin/env python3
import hashlib, json, re, sys
from pathlib import Path

root=Path(__file__).resolve().parent
manifest=json.loads((root/'MANIFEST.json').read_text(encoding='utf-8'))
errors=[]
for item in manifest['files']:
    path=root/item['path']
    if not path.is_file(): errors.append('missing:'+item['path']); continue
    got=hashlib.sha256(path.read_bytes()).hexdigest()
    if got != item['sha256']: errors.append('sha256:'+item['path'])
for path in root.rglob('*'):
    if not path.is_file() or path.name in {'SELF_CHECK.py'}: continue
    rel=path.relative_to(root).as_posix().lower()
    if any(part in rel.split('/') for part in ('secrets','credentials','personal','models')): errors.append('forbidden_path:'+rel)
    if path.suffix.lower() in {'.sqlite','.sqlite3','.db','.hbm','.onnx','.safetensors','.gguf','.pem','.key'}: errors.append('forbidden_file:'+rel)
    if path.stat().st_size < 5_000_000:
        text=path.read_text(encoding='utf-8', errors='ignore')
        if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|tskey-[A-Za-z0-9_-]{16,}|cloudflared\s+tunnel\s+run\s+--token\s+[A-Za-z0-9._-]{16,}', text): errors.append('secret_pattern:'+rel)
if manifest.get('final_verdict') != 'product_access_code_complete_s100p_execution_bundle_ready': errors.append('verdict')
for path in root.rglob('*.json'):
    try: json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc: errors.append('json:'+path.relative_to(root).as_posix()+':'+type(exc).__name__)
try:
    import yaml
    for path in root.rglob('*.yaml'): yaml.safe_load(path.read_text(encoding='utf-8'))
except ImportError: errors.append('pyyaml_missing_for_yaml_check')
except Exception as exc: errors.append('yaml:'+type(exc).__name__)
print(json.dumps({'ok':not errors,'files_checked':len(manifest['files']),'errors':errors},ensure_ascii=False,indent=2))
raise SystemExit(0 if not errors else 1)
'''


def zip_tree(source: Path, target: Path, prefix: str = "") -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                archive.write(path, (Path(prefix) / path.relative_to(source)).as_posix())


def main() -> int:
    parser = argparse.ArgumentParser(description="Build secret-safe product access delivery and S100P validation bundles")
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    parser.add_argument("--timestamp", default=time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    validation_zip = args.out / f"product_access_s100p_validation_bundle_{args.timestamp}.zip"
    zip_tree(ROOT / "validation" / "product_access_s100p", validation_zip)

    with tempfile.TemporaryDirectory(prefix="digua_product_access_delivery_") as temp:
        stage = Path(temp) / f"product_access_delivery_{args.timestamp}"
        stage.mkdir()
        copy_inputs(stage)
        shutil.copy2(validation_zip, stage / validation_zip.name)
        (stage / "FINAL_VERDICT.txt").write_text(VERDICT + "\n", encoding="utf-8")
        (stage / "SELF_CHECK.py").write_text(SELF_CHECK, encoding="utf-8")
        candidates = [path for path in sorted(stage.rglob("*")) if path.is_file() and path.name not in {"MANIFEST.json", "SHA256SUMS.txt"}]
        manifest = {
            "schema": "digua_product_access_delivery_v1",
            "created_at": args.timestamp,
            "source_commit": git_commit(),
            "final_verdict": VERDICT,
            "production_verified": False,
            "s100p_and_nas_powered": False,
            "excludes": ["passwords", "claim plaintext", "tunnel keys", "credentials", "private keys", ".env", "runtime databases", "NAS/user data", "model weights"],
            "files": [{"path": path.relative_to(stage).as_posix(), "size": path.stat().st_size, "sha256": sha(path)} for path in candidates],
        }
        (stage / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        all_files = [path for path in sorted(stage.rglob("*")) if path.is_file() and path.name != "SHA256SUMS.txt"]
        (stage / "SHA256SUMS.txt").write_text("".join(f"{sha(path)}  {path.relative_to(stage).as_posix()}\n" for path in all_files), encoding="utf-8")
        delivery_zip = args.out / f"product_access_delivery_{args.timestamp}.zip"
        zip_tree(stage, delivery_zip, stage.name)

    summary = {
        "ok": True,
        "final_verdict": VERDICT,
        "delivery_zip": str(delivery_zip),
        "delivery_sha256": sha(delivery_zip),
        "validation_zip": str(validation_zip),
        "validation_sha256": sha(validation_zip),
        "self_check_command": "unzip delivery; python SELF_CHECK.py",
    }
    summary_path = args.out / "product_access_delivery_latest.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
