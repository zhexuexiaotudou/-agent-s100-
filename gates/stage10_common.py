from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ai_space_gate_common import check, write_gate  # noqa: E402
from stage8_demo_common import gate_payload  # noqa: E402


RAW_PATH_MARKERS = ("C:\\", "F:\\", "/mnt/nas/", "/root/", "/home/")


def add_stage10_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--report-root", type=Path, default=Path("reports"))
    parser.add_argument("--corpus-root", type=Path, default=Path("demo_corpus"))
    parser.add_argument("--release-root", type=Path, default=Path("release"))
    parser.add_argument("--personal-root", type=Path, default=None)
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--qwen-url", default="http://127.0.0.1:18080/health")
    parser.add_argument("--auth-token", default=os.environ.get("DIGUA_DEMO_AUTH_TOKEN", ""))
    parser.add_argument("--timeout", type=int, default=30)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def all_manifest_records(corpus_root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted((corpus_root / "manifests").glob("*.jsonl")):
        for record in read_jsonl(path):
            asset_id = str(record.get("asset_id") or "")
            key = asset_id or json.dumps(record, sort_keys=True, ensure_ascii=False)
            if key in seen:
                continue
            seen.add(key)
            records.append(record)
    return records


def has_raw_path(value: Any) -> bool:
    encoded = json.dumps(value, ensure_ascii=False)
    return any(marker in encoded for marker in RAW_PATH_MARKERS)


def run_cmd(cmd: list[str], *, timeout: int = 300, env: dict[str, str] | None = None) -> dict[str, Any]:
    completed = subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True, check=False, timeout=timeout, env=env)
    return {"ok": completed.returncode == 0, "returncode": completed.returncode, "stdout": completed.stdout[-4000:], "stderr": completed.stderr[-4000:], "cmd": cmd}


def http_json(method: str, base_url: str, path: str, payload: dict[str, Any] | None = None, *, timeout: int = 20, token: str = "") -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(base_url.rstrip("/") + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read(2 * 1024 * 1024).decode("utf-8", errors="replace")
            return {"ok": 200 <= response.status < 300, "status": response.status, "payload": json.loads(raw)}
    except urllib.error.HTTPError as exc:
        raw = exc.read(256 * 1024).decode("utf-8", errors="replace")
        try:
            parsed: Any = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"raw": raw[:2000]}
        return {"ok": False, "status": exc.code, "payload": parsed, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "status": None, "payload": {}, "error": f"{type(exc).__name__}:{exc}"}


def token_from_args(args: argparse.Namespace) -> str:
    token = str(getattr(args, "auth_token", "") or "").strip()
    if token:
        return token
    token_file = Path("/tmp/stage9_demo_token.txt")
    if token_file.exists():
        return token_file.read_text(encoding="utf-8").strip()
    return ""


def latest_product_smoke(report_root: Path) -> dict[str, Any] | None:
    candidates = sorted(report_root.glob("product_smoke_test_*/product_smoke_test.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        return None
    payload = json.loads(candidates[0].read_text(encoding="utf-8"))
    payload["json_path"] = str(candidates[0])
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bundle_stage10(report_root: Path) -> tuple[Path | None, str | None]:
    try:
        evidence_dir = Path("evidence_for_gptpro")
        evidence_dir.mkdir(parents=True, exist_ok=True)
        bundle = evidence_dir / f"digua_release_product_delivery_{time.strftime('%Y%m%d-%H%M%S')}.zip"
        with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(report_root.glob("stage10_*")):
                if path.is_file():
                    zf.write(path, arcname=path.name)
            for path in sorted(Path("dist").glob("release_manifest.json")):
                if path.is_file():
                    zf.write(path, arcname=path.as_posix())
        digest = sha256_file(bundle)
        bundle.with_suffix(bundle.suffix + ".sha256.txt").write_text(f"{digest}  {bundle.name}\n", encoding="utf-8")
        return bundle, digest
    except Exception:
        return None, None


def redact_auth(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: redact_auth(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_auth(item) for item in value]
    if isinstance(value, str) and len(value) >= 32:
        return value.replace(value, "[redacted]")
    return value
