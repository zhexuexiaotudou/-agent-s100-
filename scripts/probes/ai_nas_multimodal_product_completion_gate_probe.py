#!/usr/bin/env python3
"""Completion gate for the AI-NAS multimodal search product slice."""

from __future__ import annotations

import argparse
import json
import sqlite3
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_nas_common import ensure_report_dir, safe_write_json, safe_write_text


OK = "ok_ai_nas_multimodal_product_completion_gate"
FAILED = "failed_ai_nas_multimodal_product_completion_gate"

EXPECTED_REPORTS = {
    "s100_grounded_vision_realdata_gate.json": "ok_ai_nas_s100_grounded_vision_realdata_gate",
    "s100_clip_realdata_gate.json": "ok_ai_nas_s100_clip_realdata_gate",
    "product_embedding_region_gate.json": "ok_ai_nas_product_embedding_region_gate",
    "product_visual_acl_evidence_gate.json": "ok_ai_nas_product_visual_acl_evidence_gate",
    "product_visual_search_contract_gate.json": "ok_ai_nas_product_visual_search_contract_gate",
}


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def latest_report(root: Path, filename: str) -> dict[str, Any]:
    candidates = [path for path in root.rglob(filename) if path.is_file()] if root.exists() else []
    if not candidates:
        return {"found": False, "filename": filename}
    selected = max(candidates, key=lambda path: path.stat().st_mtime)
    payload = read_json(selected) or {}
    return {
        "found": True,
        "filename": filename,
        "path": str(selected),
        "verdict": payload.get("verdict"),
        "ok": payload.get("verdict") == EXPECTED_REPORTS.get(filename),
        "generated_at": payload.get("generated_at"),
    }


def http_json(method: str, url: str, payload: dict[str, Any] | None = None, token: str = "", timeout: int = 60) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace") or "{}")


def search(base_url: str, token: str, query: str) -> dict[str, Any]:
    url = base_url.rstrip("/") + "/api/vision/search?query=" + urllib.parse.quote(query) + "&limit=5"
    return http_json("GET", url, token=token, timeout=90)


def db_metrics(db_path: Path) -> dict[str, Any]:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        counts = {}
        for table in [
            "photo_visual_state",
            "image_captions",
            "ocr_results",
            "vision_embeddings_v2",
            "vision_regions",
            "vision_attributes",
            "vision_artifacts",
        ]:
            counts[table] = int(con.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"])
        caption_completed = int(
            con.execute(
                """
                SELECT COUNT(*) AS c
                FROM image_captions
                WHERE status = 'llm_caption_completed'
                  AND model_id = 's100p-grounded-caption-yolo-ppocr-v1'
                """
            ).fetchone()["c"]
        )
        ocr_completed = int(
            con.execute("SELECT COUNT(*) AS c FROM ocr_results WHERE status = 'ocr_completed'").fetchone()["c"]
        )
        white_upper = int(
            con.execute(
                """
                SELECT COUNT(*) AS c
                FROM vision_attributes
                WHERE namespace = 'upper_clothing'
                  AND name = 'color'
                  AND lower(value) = 'white'
                  AND region_id IS NOT NULL
                """
            ).fetchone()["c"]
        )
        region_state = int(
            con.execute(
                """
                SELECT COUNT(*) AS c
                FROM photo_visual_state
                WHERE status = 'indexed_with_product_embedding_and_region_attributes'
                """
            ).fetchone()["c"]
        )
        embedding_completed = int(
            con.execute(
                """
                SELECT COUNT(*) AS c
                FROM vision_embeddings_v2
                WHERE status = 'product_image_text_embedding_completed'
                  AND model_id = 's100p-clip-vit-base-patch32'
                """
            ).fetchone()["c"]
        )
    finally:
        con.close()
    return {
        "counts": counts,
        "caption_completed": caption_completed,
        "ocr_completed": ocr_completed,
        "white_upper_attribute_count": white_upper,
        "region_attribute_state_count": region_state,
        "embedding_completed": embedding_completed,
    }


def check(label: str, condition: bool, details: Any, checks: list[dict[str, Any]], failures: list[str]) -> None:
    checks.append({"label": label, "ok": bool(condition), "details": details})
    if not condition:
        failures.append(label)


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# AI-NAS Multimodal Product Completion Gate",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- portal_url: `{payload['portal_url']}`",
        f"- sqlite_index_path: `{payload['sqlite_index_path']}`",
        "",
        "## Checks",
        "",
    ]
    for item in payload["checks"]:
        lines.append(f"- {item['label']}: `{item['ok']}`")
    lines.extend(["", "## Failures", ""])
    failures = payload.get("failures") or []
    lines.extend(f"- `{item}`" for item in failures) if failures else lines.append("- None.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify current AI-NAS multimodal product completion evidence.")
    parser.add_argument("--portal-url", default="http://127.0.0.1:53306")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="admin123")
    parser.add_argument("--sqlite-index-path", type=Path, default=Path(r"F:\mnt\nas\openclaw\reports\ai_nas_mvp\personal_inventory.sqlite3"))
    parser.add_argument("--report-root", type=Path, default=Path("tmp/ai_nas_multimodal_product_completion_gate_local"))
    parser.add_argument("--evidence-root", type=Path, default=Path("tmp"))
    parser.add_argument("--ui-qa-json", type=Path, default=Path(r"F:\Project\Digua\output\playwright\ai-nas-grounded-visual-ui-qa-result.json"))
    args = parser.parse_args()

    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    base = args.portal_url.rstrip("/")

    try:
        login = http_json("POST", base + "/api/identity/login", {"username": args.username, "password": args.password}, timeout=20)
        token = str(login.get("token") or "")
    except Exception as exc:
        login = {"ok": False, "error": f"{type(exc).__name__}:{exc}"}
        token = ""
    check("portal_admin_login", bool(login.get("ok") and token), {"ok": login.get("ok")}, checks, failures)

    status: dict[str, Any] = {}
    if token:
        try:
            status = http_json("GET", base + "/api/vision/status", token=token, timeout=30)
        except Exception as exc:
            status = {"ok": False, "error": f"{type(exc).__name__}:{exc}"}
    product = ((status.get("runtime") or {}).get("vision_product") or {}) if isinstance(status, dict) else {}
    check(
        "vision_product_runtime_ready",
        bool(product.get("product_ready") and not product.get("missing_for_product")),
        {"product_ready": product.get("product_ready"), "missing_for_product": product.get("missing_for_product")},
        checks,
        failures,
    )

    metrics = db_metrics(args.sqlite_index_path) if args.sqlite_index_path.exists() else {"missing": True}
    check("clip_embeddings_realdata", metrics.get("embedding_completed", 0) >= 11, metrics, checks, failures)
    check("grounded_captions_realdata", metrics.get("caption_completed", 0) >= 11, metrics, checks, failures)
    check("ocr_realdata", metrics.get("ocr_completed", 0) >= 8, metrics, checks, failures)
    check("region_attributes_realdata", metrics.get("white_upper_attribute_count", 0) >= 1 and metrics.get("region_attribute_state_count", 0) >= 1, metrics, checks, failures)
    check("evidence_artifacts_created", (metrics.get("counts") or {}).get("vision_artifacts", 0) >= 80, metrics, checks, failures)

    football: dict[str, Any] = {}
    white_top: dict[str, Any] = {}
    if token:
        try:
            football = search(base, token, "football player")
            white_top = search(base, token, "找穿白色上衣的照片")
        except Exception as exc:
            failures.append(f"search_exception:{type(exc).__name__}:{exc}")
    football_results = football.get("results") if isinstance(football.get("results"), list) else []
    white_results = white_top.get("results") if isinstance(white_top.get("results"), list) else []
    check(
        "football_search_not_degraded",
        bool(football_results and football_results[0].get("relative_path") == "Photos/QA_20260624/football_player_pele_commons.jpg" and football.get("degraded") is False),
        {"first": football_results[0] if football_results else None, "degraded": football.get("degraded")},
        checks,
        failures,
    )
    first_white = white_results[0] if white_results else {}
    check(
        "white_upper_region_search_not_degraded",
        bool(
            first_white.get("relative_path") == "Photos/QA_20260624/football_player_pele_commons.jpg"
            and first_white.get("visual_source") == "product_region_attribute_search"
            and white_top.get("degraded") is False
            and any("upper_clothing.color=white" in str(chip) for chip in first_white.get("evidence_chips") or [])
        ),
        {"first": first_white, "degraded": white_top.get("degraded")},
        checks,
        failures,
    )

    reports = {filename: latest_report(args.evidence_root, filename) for filename in EXPECTED_REPORTS}
    check("supporting_gates_ok", all(report.get("ok") for report in reports.values()), reports, checks, failures)

    ui_qa = read_json(args.ui_qa_json) if args.ui_qa_json.exists() else None
    screenshots = (ui_qa or {}).get("screenshots") if isinstance(ui_qa, dict) else {}
    screenshot_ok = bool(
        ui_qa
        and ui_qa.get("ok")
        and screenshots
        and all(Path(path).exists() and Path(path).stat().st_size > 10000 for path in screenshots.values())
    )
    check("browser_ui_qa_ok", screenshot_ok, ui_qa or {"missing": True}, checks, failures)

    verdict = OK if not failures else FAILED
    payload = {
        "generated_at": iso_now(),
        "tool_id": "ai_nas_multimodal_product_completion_gate",
        "verdict": verdict,
        "ok": verdict == OK,
        "portal_url": base,
        "sqlite_index_path": str(args.sqlite_index_path),
        "checks": checks,
        "failures": failures,
        "runtime_status": {
            "product_ready": product.get("product_ready"),
            "missing_for_product": product.get("missing_for_product"),
            "schema_counts": (status.get("vision_schema") or {}).get("counts") if isinstance(status, dict) else {},
        },
        "db_metrics": metrics,
        "supporting_reports": reports,
        "ui_qa": ui_qa,
        "audit": {
            "real_data_used": True,
            "browser_verified": bool(screenshot_ok),
            "source_modified": False,
            "writes": "bounded completion JSON/Markdown evidence under report root only",
        },
    }
    run_dir = ensure_report_dir(args.report_root, "multimodal_product_completion_gate")
    safe_write_json(run_dir / "multimodal_product_completion_gate.json", payload)
    safe_write_text(run_dir / "multimodal_product_completion_gate.md", markdown(payload))
    print(run_dir / "multimodal_product_completion_gate.md")
    print(run_dir / "multimodal_product_completion_gate.json")
    print(verdict)
    return 0 if verdict == OK else 1


if __name__ == "__main__":
    raise SystemExit(main())
