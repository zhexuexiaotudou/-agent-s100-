from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from ai_space_gate_common import check


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

RAW_PATH_RE = re.compile(r"([A-Za-z]:\\|/mnt/nas/|/home/|/root/)")


def has_raw_path(payload: Any) -> bool:
    return bool(RAW_PATH_RE.search(json.dumps(payload, ensure_ascii=False)))


def http_get_json(base_url: str, path: str, *, timeout: int = 12) -> dict[str, Any]:
    return _http_json("GET", base_url, path, None, timeout=timeout)


def http_post_json(base_url: str, path: str, payload: dict[str, Any], *, timeout: int = 20) -> dict[str, Any]:
    return _http_json("POST", base_url, path, payload, timeout=timeout)


def _http_json(method: str, base_url: str, path: str, payload: dict[str, Any] | None, *, timeout: int) -> dict[str, Any]:
    url = base_url.rstrip("/") + path
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers={"Accept": "application/json", "Content-Type": "application/json"})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read(2 * 1024 * 1024).decode("utf-8", errors="replace")
            return {
                "ok": 200 <= response.status < 300,
                "status": response.status,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                "payload": json.loads(raw),
            }
    except urllib.error.HTTPError as exc:
        raw = exc.read(65536).decode("utf-8", errors="replace")
        try:
            parsed: Any = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"raw": raw[:2000]}
        return {"ok": False, "status": exc.code, "elapsed_ms": round((time.perf_counter() - started) * 1000, 3), "payload": parsed, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "status": None, "elapsed_ms": round((time.perf_counter() - started) * 1000, 3), "payload": {}, "error": f"{type(exc).__name__}:{exc}"}


def run_command(cmd: list[str], *, timeout: int = 120) -> dict[str, Any]:
    completed = subprocess.run(cmd, text=True, capture_output=True, check=False, timeout=timeout)
    return {"ok": completed.returncode == 0, "returncode": completed.returncode, "stdout": completed.stdout[-4000:], "stderr": completed.stderr[-4000:]}


def gate_payload(ok_verdict: str, blocked_verdict: str, checks: list[dict[str, Any]], evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "ok": all(item.get("ok") for item in checks),
        "verdict": ok_verdict if all(item.get("ok") for item in checks) else blocked_verdict,
        "checks": checks,
        "blockers": [str(item.get("name")) for item in checks if not item.get("ok")],
        "evidence": evidence or {},
    }


def fixture_file(personal_root: Path, rel: str, content: bytes) -> Path:
    path = personal_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def status_checks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        check("status ok", payload.get("ok") is True, payload.get("error")),
        check("controlled move enabled", payload.get("controlled_move_enabled") is True, payload.get("controlled_move_enabled")),
        check("controlled rename enabled", payload.get("controlled_rename_enabled") is True, payload.get("controlled_rename_enabled")),
        check("uncontrolled move disabled", payload.get("uncontrolled_move_enabled") is False, payload.get("uncontrolled_move_enabled")),
        check("uncontrolled rename disabled", payload.get("uncontrolled_rename_enabled") is False, payload.get("uncontrolled_rename_enabled")),
        check("delete disabled", payload.get("delete_enabled") is False, payload.get("delete_enabled")),
        check("overwrite disabled", payload.get("overwrite_enabled") is False, payload.get("overwrite_enabled")),
        check("rollback required", payload.get("rollback_required") is True, payload.get("rollback_required")),
        check("raw path not returned", payload.get("raw_path_returned") is False and not has_raw_path(payload), "redacted"),
    ]
