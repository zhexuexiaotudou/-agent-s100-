#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlencode

from ai_nas_common import default_official_manager_url, ensure_report_dir, iso_now, open_index_db, safe_write_json, safe_write_text
from ai_nas_product_embedding_region_gate_probe import start_fixture_server, write_fixture_image
from ai_nas_visual_search_gate_probe import free_port, http_json, wait_ready


TOOL_ID = "ai_nas_product_visual_acl_evidence_gate"
OK = "ok_ai_nas_product_visual_acl_evidence_gate"
FAILED = "failed_ai_nas_product_visual_acl_evidence_gate"


def check(label: str, cond: bool, failures: list[str], checks: list[dict]) -> None:
    checks.append({"label": label, "ok": bool(cond)})
    print(f"  {'PASS' if cond else 'FAIL'}: {label}")
    if not cond:
        failures.append(label)


def artifact_summary(db_path: Path) -> dict:
    con = open_index_db(db_path)
    try:
        rows = con.execute(
            """
            SELECT artifact_type, COUNT(*) AS count,
                   SUM(CASE WHEN uri LIKE 'sqlite://%' THEN 1 ELSE 0 END) AS protected_uri_count
            FROM vision_artifacts
            GROUP BY artifact_type
            """
        ).fetchall()
        by_type = {
            row["artifact_type"]: {
                "count": int(row["count"]),
                "protected_uri_count": int(row["protected_uri_count"] or 0),
            }
            for row in rows
        }
        total = sum(item["count"] for item in by_type.values())
        protected = sum(item["protected_uri_count"] for item in by_type.values())
    finally:
        con.close()
    return {"by_type": by_type, "total": total, "protected_uri_count": protected}


def response_contains_raw_artifact_uri(payload: dict) -> bool:
    text = json.dumps(payload, ensure_ascii=False)
    return "sqlite://vision_" in text or "sqlite://ocr_" in text or "sqlite://vision_regions" in text


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate product visual evidence artifacts and ACL filtering.")
    parser.add_argument("--report-root", type=Path, default=Path("tmp/ai_nas_product_visual_acl_evidence_gate_local"))
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "product_visual_acl_evidence_gate")
    personal_root = run_dir / "Personal"
    for name in ("Photos/Public", "Photos/Private", "Documents", "Movies", "Inbox"):
        (personal_root / name).mkdir(parents=True, exist_ok=True)
    write_fixture_image(personal_root / "Photos" / "Public" / "person_white_top_public.jpg", (220, 225, 228), "person white top public")
    write_fixture_image(personal_root / "Photos" / "Private" / "private_person_white_top.jpg", (223, 226, 229), "person white top private")
    write_fixture_image(personal_root / "Photos" / "Public" / "white_car_public.jpg", (245, 245, 240), "white car public")

    fixture_server, fixture_base_url = start_fixture_server()
    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    db_path = run_dir / "personal_inventory.sqlite3"
    server_script = Path(__file__).with_name("ai_nas_operator_portal_server.py")
    env = os.environ.copy()
    env.update(
        {
            "AI_NAS_IMAGE_TEXT_EMBEDDING_ENDPOINT": fixture_base_url + "/embed",
            "AI_NAS_IMAGE_TEXT_EMBEDDING_MODEL": "fixture-siglip-product",
            "AI_NAS_VISION_DETECTOR_ENDPOINT": fixture_base_url + "/region",
            "AI_NAS_VISION_DETECTOR_MODEL": "fixture-yolo-human-parsing-product",
            "AI_NAS_REGION_ATTRIBUTE_ENDPOINT": fixture_base_url + "/region",
            "AI_NAS_REGION_ATTRIBUTE_MODEL": "fixture-yolo-human-parsing-product",
        }
    )
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
        str(db_path),
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
        str(run_dir / "schedules.sqlite3"),
        "--official-manager-url",
        default_official_manager_url(),
        "--nas-portal",
        "--no-refresh",
    ]
    proc = subprocess.Popen(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    failures: list[str] = []
    checks: list[dict] = []
    artifacts: dict = {}
    stdout = ""
    stderr = ""
    try:
        print("OpenClaw NAS Product Visual ACL Evidence Gate")
        ready = wait_ready(base_url, proc)
        check("Portal server ready", bool(ready.get("ok")), failures, checks)
        create_admin = http_json("POST", base_url + "/api/identity/create-user", {"username": "admin", "password": "admin123", "role": "admin"})
        admin_login = http_json("POST", base_url + "/api/identity/login", {"username": "admin", "password": "admin123"})
        admin_token = (admin_login.get("payload") or {}).get("token")
        check("Admin login ready", create_admin.get("ok") and admin_login.get("ok") and bool(admin_token), failures, checks)
        create_viewer = http_json("POST", base_url + "/api/identity/create-user", {"username": "viewer", "password": "viewer123", "role": "user"}, token=admin_token)
        set_acl = http_json("POST", base_url + "/api/identity/set-acl", {"path": "Photos/Public", "principal_type": "user", "principal_name": "viewer", "permission": "read"}, token=admin_token)
        viewer_login = http_json("POST", base_url + "/api/identity/login", {"username": "viewer", "password": "viewer123"})
        viewer_token = (viewer_login.get("payload") or {}).get("token")
        check("Viewer Photos-only ACL ready", create_viewer.get("ok") and set_acl.get("ok") and bool(viewer_token), failures, checks)

        index = http_json("POST", base_url + "/api/vision/index", {"limit": 50, "include_ocr": False, "include_caption": False}, token=admin_token, timeout=90)
        index_payload = index.get("payload") or {}
        product_region_attempted = (index_payload.get("product_region_update") or {}).get("attempted", 0)
        product_embedding_attempted = (index_payload.get("product_embedding_update") or {}).get("attempted", 0)
        check("Product visual index ran", index.get("ok") and product_region_attempted >= 3 and product_embedding_attempted >= 3, failures, checks)

        query = urlencode({"query": "\u627e\u7a7f\u767d\u8272\u4e0a\u8863\u7684\u7167\u7247", "limit": "10"})
        admin_search = http_json("GET", f"{base_url}/api/vision/search?{query}", token=admin_token)
        viewer_search = http_json("GET", f"{base_url}/api/vision/search?{query}", token=viewer_token)
        admin_results = (admin_search.get("payload") or {}).get("results") or []
        viewer_results = (viewer_search.get("payload") or {}).get("results") or []
        check("Admin can see product evidence result", admin_search.get("ok") and any("person_white_top" in str(item.get("relative_path")) for item in admin_results), failures, checks)
        check("Admin can see Private product evidence result", admin_search.get("ok") and any(item.get("relative_path") == "Photos/Private/private_person_white_top.jpg" for item in admin_results), failures, checks)
        check("Viewer receives Photos/Public result", viewer_search.get("ok") and any(item.get("relative_path") == "Photos/Public/person_white_top_public.jpg" for item in viewer_results), failures, checks)
        check("Viewer does not receive Photos/Private result", all(not str(item.get("relative_path") or "").startswith("Photos/Private/") for item in viewer_results), failures, checks)
        check("Viewer result carries evidence chips", any(item.get("evidence_chips") and item.get("evidence_items") for item in viewer_results), failures, checks)
        check("Search response hides raw artifact URIs", not response_contains_raw_artifact_uri(admin_search.get("payload") or {}) and not response_contains_raw_artifact_uri(viewer_search.get("payload") or {}), failures, checks)

        artifact_counts = artifact_summary(db_path)
        check("Evidence artifacts are protected sqlite URIs", artifact_counts.get("total", 0) >= 3 and artifact_counts.get("protected_uri_count") == artifact_counts.get("total"), failures, checks)
        artifacts = {
            "base_url": base_url,
            "fixture_base_url": fixture_base_url,
            "index": index_payload,
            "admin_search": admin_search.get("payload"),
            "viewer_search": viewer_search.get("payload"),
            "artifact_counts": artifact_counts,
        }
    finally:
        proc.terminate()
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate(timeout=5)
        fixture_server.shutdown()
        fixture_server.server_close()

    verdict = OK if not failures else FAILED
    report = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "checks": checks,
        "failures": failures,
        "artifacts": artifacts,
        "server_stdout_tail": stdout[-4000:],
        "server_stderr_tail": stderr[-4000:],
    }
    json_path = run_dir / "product_visual_acl_evidence_gate.json"
    md_path = run_dir / "product_visual_acl_evidence_gate.md"
    safe_write_json(json_path, report)
    lines = [
        "# AI-NAS Product Visual ACL Evidence Gate",
        "",
        f"- verdict: `{verdict}`",
        f"- checks: `{sum(1 for item in checks if item['ok'])}/{len(checks)}`",
        f"- failures: `{failures}`",
        f"- json: `{json_path}`",
    ]
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(f"verdict: {verdict}")
    print(f"report: {json_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
