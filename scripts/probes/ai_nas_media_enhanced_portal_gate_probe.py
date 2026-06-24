#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from http import HTTPStatus
from pathlib import Path
from typing import Any

from ai_nas_common import ensure_report_dir, iso_now, safe_write_json, safe_write_text


TOOL_ID = "ai_nas_media_enhanced_portal_gate"
OK = "ok_ai_nas_media_enhanced_portal_gate"
FAILED = "failed_ai_nas_media_enhanced_portal_gate"


def free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    try:
        return int(sock.getsockname()[1])
    finally:
        sock.close()


def http_json(method: str, url: str, payload: dict[str, Any] | None = None, token: str | None = None, timeout: int = 30) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return {"ok": 200 <= response.status < 300, "status": response.status, "payload": json.loads(raw) if raw else {}}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return {"ok": False, "status": exc.code, "payload": parsed}
    except Exception as exc:
        return {"ok": False, "status": 0, "payload": {"error": f"{type(exc).__name__}:{exc}"}}


def http_text(url: str, timeout: int = 30) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return {"ok": 200 <= response.status < 300, "status": response.status, "text": response.read().decode("utf-8", errors="replace")}
    except Exception as exc:
        return {"ok": False, "status": 0, "text": "", "error": f"{type(exc).__name__}:{exc}"}


def http_bytes(url: str, token: str | None = None, timeout: int = 30) -> dict[str, Any]:
    headers = {"Accept": "*/*"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {"ok": 200 <= response.status < 300, "status": response.status, "headers": dict(response.headers.items()), "body": response.read()}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "headers": dict(exc.headers.items()), "body": exc.read()}
    except Exception as exc:
        return {"ok": False, "status": 0, "headers": {}, "body": f"{type(exc).__name__}:{exc}".encode("utf-8")}


def wait_ready(base_url: str, proc: subprocess.Popen, timeout: float = 20.0) -> dict[str, Any]:
    deadline = time.perf_counter() + timeout
    last: dict[str, Any] = {}
    while time.perf_counter() < deadline:
        if proc.poll() is not None:
            return {"ok": False, "error": "server_exited", "returncode": proc.poll(), "last": last}
        last = http_json("GET", f"{base_url}/api/storage/status", timeout=3)
        if last.get("ok"):
            return last
        time.sleep(0.2)
    return {"ok": False, "error": "timeout", "last": last}


def check(label: str, cond: bool, failures: list[str], checks: list[dict[str, Any]], evidence: dict[str, Any] | None = None) -> None:
    item = {"label": label, "ok": bool(cond)}
    if evidence:
        item["evidence"] = evidence
    checks.append(item)
    print(f"  {'PASS' if cond else 'FAIL'}: {label}")
    if not cond:
        failures.append(label)


def seed_personal(root: Path) -> None:
    for name in ["Movies", "Documents", "Photos", "Inbox"]:
        (root / name).mkdir(parents=True, exist_ok=True)
    movie = root / "Movies" / "The.Matrix.1999.1080p.mp4"
    movie.write_bytes(b"fake-matrix-video-bytes")
    movie.with_suffix(".srt").write_text("1\n00:00:01,000 --> 00:00:03,000\nWake up, Neo.\n", encoding="utf-8")
    movie.with_suffix(".jpg").write_bytes(b"fake-matrix-poster")
    episode = root / "Movies" / "Blue.Planet.S01E02.2020.mkv"
    episode.write_bytes(b"fake-blue-planet-video-bytes")
    episode.with_suffix(".vtt").write_text("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nOcean.\n", encoding="utf-8")
    (root / "Photos" / "family_2026.jpg").write_bytes(b"fake-family-photo")


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate for enhanced media metadata and player links in the OpenClaw NAS portal.")
    parser.add_argument("--report-root", type=Path, default=Path("tmp/ai_nas_media_enhanced_portal_gate_local"))
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "media_enhanced_portal_gate")
    personal_root = run_dir / "Personal"
    seed_personal(personal_root)
    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    server_script = Path(__file__).with_name("ai_nas_operator_portal_server.py")
    cmd = [
        sys.executable,
        str(server_script),
        "--bind",
        "127.0.0.1",
        "--port",
        str(port),
        "--report-root",
        str(run_dir),
        "--personal-root",
        str(personal_root),
        "--sqlite-index-path",
        str(run_dir / "personal_inventory.sqlite3"),
        "--identity-db-path",
        str(run_dir / "identity.sqlite3"),
        "--snapshot-db-path",
        str(run_dir / "snapshot.sqlite3"),
        "--backup-db-path",
        str(run_dir / "backup.sqlite3"),
        "--media-db-path",
        str(run_dir / "media.sqlite3"),
        "--ops-db-path",
        str(run_dir / "ops.sqlite3"),
        "--app-db-path",
        str(run_dir / "apps.sqlite3"),
        "--schedule-db-path",
        str(run_dir / "schedule.sqlite3"),
        "--nas-portal",
        "--no-refresh",
    ]
    env = os.environ.copy()
    env.update(
        {
            "OPENCLAW_JELLYFIN_URL": "http://jellyfin.local:8096",
            "OPENCLAW_PLEX_URL": "http://plex.local:32400",
        }
    )
    proc = subprocess.Popen(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    failures: list[str] = []
    checks: list[dict[str, Any]] = []
    stdout = ""
    stderr = ""
    collected: dict[str, Any] = {"base_url": base_url, "run_dir": str(run_dir)}
    try:
        print("AI-NAS Enhanced Media Portal Gate")
        ready = wait_ready(base_url, proc)
        check("Portal server ready", bool(ready.get("ok")), failures, checks)

        html = http_text(base_url + "/")
        text = html.get("text", "")
        check(
            "NAS portal exposes enhanced media UI",
            html.get("ok") and "movieCards" in text and "poster_url" in text and "mediaTranscodingPolicy" in text,
            failures,
            checks,
        )

        create_admin = http_json("POST", base_url + "/api/identity/create-user", {"username": "admin", "password": "admin123", "role": "admin"})
        check("Admin bootstrap", create_admin.get("ok") and create_admin.get("payload", {}).get("ok"), failures, checks)
        admin_login = http_json("POST", base_url + "/api/identity/login", {"username": "admin", "password": "admin123"})
        admin_token = (admin_login.get("payload") or {}).get("token")
        check("Admin login", admin_login.get("ok") and bool(admin_token), failures, checks)

        index_media = http_json("POST", base_url + "/api/media/index", {"path": ""}, token=admin_token)
        index_payload = index_media.get("payload") or {}
        check("Media index scans videos and photos", index_media.get("ok") and (index_payload.get("index") or {}).get("scanned", 0) >= 3, failures, checks, {"index": index_payload.get("index")})

        summary = http_json("GET", base_url + "/api/media/summary", token=admin_token)
        payload = summary.get("payload") or {}
        movies = payload.get("movies") or []
        stats = payload.get("stats") or {}
        matrix = next((item for item in movies if item.get("title") == "The Matrix"), {})
        episode = next((item for item in movies if item.get("episode_label") == "S01E02"), {})
        collected["summary"] = {"stats": stats, "movie_count": len(movies), "movies": movies}
        check("Media summary exposes movie count", summary.get("ok") and stats.get("video_count", 0) >= 2 and len(movies) >= 2, failures, checks, {"stats": stats})
        check("Movie metadata parses title and year", matrix.get("year") == 1999 and matrix.get("subtitle_status") == "available", failures, checks, {"matrix": matrix})
        check("Episode metadata parses season and episode", episode.get("season") == 1 and episode.get("episode") == 2, failures, checks, {"episode": episode})
        check("Poster and subtitle sidecars are surfaced", bool(matrix.get("poster_url")) and matrix.get("poster_status") == "available", failures, checks)
        check(
            "External player links are configurable",
            any(link.get("configured") and "jellyfin" in link.get("url", "") for link in matrix.get("player_links") or [])
            and any(link.get("configured") and "plex" in link.get("url", "") for link in matrix.get("player_links") or []),
            failures,
            checks,
            {"player_links": matrix.get("player_links")},
        )
        check(
            "Realtime transcoding remains explicitly disabled",
            matrix.get("transcoding_enabled") is False
            and (matrix.get("transcoding") or {}).get("enabled") is False,
            failures,
            checks,
        )
        preview = http_bytes(base_url + str(matrix.get("open_url") or ""), token=admin_token)
        check(
            "Authorized direct preview link opens video bytes",
            preview.get("ok") and preview.get("body") == b"fake-matrix-video-bytes",
            failures,
            checks,
            {"content_type": preview.get("headers", {}).get("Content-Type")},
        )
    finally:
        proc.terminate()
        try:
            stdout, stderr = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate(timeout=10)

    verdict = OK if not failures else FAILED
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "scope": "Enhanced media metadata and player-link gate: title/year/episode/subtitle/poster/direct preview/external player config.",
        "checks": checks,
        "failures": failures,
        "summary": collected,
        "server": {
            "command": cmd,
            "stdout": stdout[-4000:],
            "stderr": stderr[-4000:],
        },
    }
    json_path = run_dir / "media_enhanced_portal_gate.json"
    md_path = run_dir / "media_enhanced_portal_gate.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Enhanced Media Portal Gate",
        "",
        f"- verdict: `{verdict}`",
        f"- checks: `{sum(1 for item in checks if item['ok'])}/{len(checks)}`",
        f"- base_url: `{base_url}`",
        "",
        "## Checks",
        "",
    ]
    for item in checks:
        lines.append(f"- {'PASS' if item['ok'] else 'FAIL'}: `{item['label']}`")
    if failures:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- `{item}`" for item in failures)
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0 if verdict == OK else 2


if __name__ == "__main__":
    raise SystemExit(main())
