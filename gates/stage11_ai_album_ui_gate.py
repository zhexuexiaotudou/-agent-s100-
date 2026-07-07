from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from ai_space_gate_common import blockers, check, verdict, write_gate


NAME = "stage11_ai_album_ui_gate"
RAW_PATH_MARKERS = ("C:\\", "F:\\", "/mnt/nas/", "/root/", "/home/")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the AI Album UI route, API wiring, preview path, and safety boundary.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--report-root", type=Path, default=Path("reports"))
    parser.add_argument("--auth-token", default=os.environ.get("DIGUA_DEMO_AUTH_TOKEN", ""))
    parser.add_argument("--username", default=os.environ.get("DIGUA_GATE_USERNAME", "admin"))
    parser.add_argument("--password", default=os.environ.get("DIGUA_GATE_PASSWORD", "admin123"))
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    token = str(args.auth_token or "").strip()
    login = {"ok": bool(token), "status": None, "payload": {"token_source": "argument" if token else "missing"}}
    if not token:
        login = http_json(
            "POST",
            args.base_url,
            "/api/identity/login",
            {"username": args.username, "password": args.password},
            timeout=args.timeout,
        )
        token = str((login.get("payload") or {}).get("token") or "")

    page = http_text(args.base_url, "/ai-album", timeout=args.timeout)
    script = http_text(args.base_url, "/static/digua_ai_nas_v2.js", timeout=args.timeout)
    style = http_text(args.base_url, "/static/digua_ai_nas_v2.css", timeout=args.timeout)

    status = http_json("GET", args.base_url, "/api/ai-space/status", token=token, timeout=args.timeout)
    facets = http_json("GET", args.base_url, "/api/ai-space/facets", token=token, timeout=args.timeout)
    assets = http_json("GET", args.base_url, "/api/ai-space/assets?limit=40", token=token, timeout=args.timeout)
    photos = http_json("GET", args.base_url, "/api/media/photos?limit=40", token=token, timeout=args.timeout)
    smart_categories = http_json("GET", args.base_url, "/api/smart-classification/categories", token=token, timeout=args.timeout)
    auto_status = http_json("GET", args.base_url, "/api/auto-organize/status", token=token, timeout=args.timeout)
    ai_search = http_json("POST", args.base_url, "/api/ai-space/search", {"query": "票据发票", "top_k": 8}, token=token, timeout=args.timeout)
    person_search = http_json("POST", args.base_url, "/api/person-attribute/search", {"query": "穿白色上衣的人", "top_k": 8}, token=token, timeout=args.timeout)
    plan = http_json(
        "POST",
        args.base_url,
        "/api/auto-organize/plan",
        {"mode": "move_and_rename", "source_root": "Uploads", "limit": 1},
        token=token,
        timeout=args.timeout,
    )

    photos_payload = photos.get("payload") or {}
    photo_items = photos_payload.get("photos") if isinstance(photos_payload.get("photos"), list) else []
    preview_photo = next((item for item in photo_items if item.get("path_hash")), None)
    preview = {"ok": False, "status": None, "bytes": 0, "content_type": ""}
    if preview_photo:
        preview_path = "/api/media/preview?" + urllib.parse.urlencode({"path_hash": preview_photo["path_hash"]})
        preview = http_binary(args.base_url, preview_path, token=token, timeout=args.timeout)

    all_api_payloads = {
        "status": status.get("payload"),
        "facets": facets.get("payload"),
        "assets": assets.get("payload"),
        "photos": photos.get("payload"),
        "smart_categories": smart_categories.get("payload"),
        "auto_status": auto_status.get("payload"),
        "ai_search": ai_search.get("payload"),
        "person_search": person_search.get("payload"),
        "plan": plan.get("payload"),
    }
    script_text = script.get("text") or ""
    style_text = style.get("text") or ""
    page_text = page.get("text") or ""
    status_payload = status.get("payload") or {}
    assets_payload = assets.get("payload") or {}
    auto_payload = auto_status.get("payload") or {}
    plan_payload = plan.get("payload") or {}
    asset_items = assets_payload.get("assets") if isinstance(assets_payload.get("assets"), list) else []
    smart_category_items = (smart_categories.get("payload") or {}).get("categories")
    if not isinstance(smart_category_items, list):
        smart_category_items = []
    suspicious_full_categories = [
        item
        for item in smart_category_items
        if int(item.get("item_count") or 0) >= len(asset_items) > 0 and str(item.get("name_zh") or item.get("name") or "") != "待整理"
    ]
    bad_evidence_free_assets = evidence_free_false_labels(asset_items)

    checks = [
        check("login token available", bool(token), redact_auth(login.get("payload") or login.get("error"))),
        check("/ai-album route serves v2 app", page.get("ok") is True and "digua_ai_nas_v2.js" in page_text, page.get("status")),
        check("AI Album JS page registered", "aiAlbumPage" in script_text and "aiAlbum: aiAlbumPage" in script_text, "aiAlbumPage"),
        check("AI Album API wiring present", all(marker in script_text for marker in ["/api/ai-space/status", "/api/media/photos", "/api/person-attribute/search", "/api/auto-organize/plan"]), "required API markers"),
        check("identity query blocked in UI", "aiAlbumIsIdentityQuery" in script_text and "identity_recognition_blocked" in script_text, "front-end local block"),
        check("no destructive AI Album action handlers", all(marker not in script_text for marker in ["aiAlbumDelete", "aiAlbumOverwrite", "aiAlbumRawPath"]), "delete/overwrite/raw-path actions absent"),
        check("AI Album CSS present", "ai-album-grid" in style_text and "ai-album-detail" in style_text, "layout classes"),
        check("AI Space status ok", status.get("ok") is True and status_payload.get("ok") is True, status_payload.get("error")),
        check("AI Space has assets", int(status_payload.get("asset_count") or len(asset_items) or 0) > 0, status_payload.get("asset_count")),
        check("facets returned", facets.get("ok") is True and bool((facets.get("payload") or {}).get("facets")), facets.get("payload")),
        check("assets returned", assets.get("ok") is True and len(asset_items) > 0, len(asset_items)),
        check("media photos returned", photos.get("ok") is True and len(photo_items) > 0, len(photo_items)),
        check("smart categories returned", smart_categories.get("ok") is True and bool(smart_category_items), len(smart_category_items)),
        check("smart categories are not all-asset false positives", not suspicious_full_categories, summarize_categories(suspicious_full_categories)),
        check("evidence-free assets do not claim person/clothing/pet/vehicle/document labels", not bad_evidence_free_assets, bad_evidence_free_assets[:5]),
        check("preview hash available", bool(preview_photo), preview_photo.get("asset_id") if preview_photo else "missing"),
        check("preview endpoint returns bytes", preview.get("ok") is True and int(preview.get("bytes") or 0) > 0, preview),
        check("AI Space search endpoint ok", ai_search.get("ok") is True and (ai_search.get("payload") or {}).get("ok") is not False, ai_search.get("payload")),
        check("person attribute endpoint ok", person_search.get("ok") is True and (person_search.get("payload") or {}).get("ok") is not False, person_search.get("payload")),
        check("auto organizer status ok", auto_status.get("ok") is True and auto_payload.get("ok") is True, auto_payload.get("error")),
        check("auto organizer plan reachable", plan.get("ok") is True and isinstance(plan_payload, dict) and ("ok" in plan_payload or "blocker" in plan_payload), plan_payload.get("error") or plan_payload.get("blocker")),
        check("delete remains blocked", not has_true_key({"auto_status": auto_payload, "plan": plan_payload}, "delete_allowed"), "delete_allowed not true"),
        check("overwrite remains blocked", not has_true_key({"auto_status": auto_payload, "plan": plan_payload}, "overwrite_allowed"), "overwrite_allowed not true"),
        check("Qwen has no execution authority", not has_true_key({"auto_status": auto_payload, "plan": plan_payload}, "qwen_execution_authority"), "qwen_execution_authority not true"),
        check("raw paths not returned by product APIs", not has_raw_path(all_api_payloads), "redacted"),
        check("cloud private processing remains off", status_payload.get("cloud_used") is False, status_payload.get("cloud_used")),
    ]
    payload = {
        "ok": all(item["ok"] for item in checks),
        "verdict": verdict("ok_stage11_ai_album_ui_gate", "blocked_stage11_ai_album_ui_gate", checks),
        "checks": checks,
        "blockers": blockers(checks),
        "evidence": {
            "base_url": args.base_url,
            "asset_count": status_payload.get("asset_count") or len(asset_items),
            "photo_count": len(photo_items),
            "smart_category_count": len(smart_category_items),
            "suspicious_full_categories": summarize_categories(suspicious_full_categories),
            "bad_evidence_free_asset_count": len(bad_evidence_free_assets),
            "preview": preview,
            "search_result_count": len((ai_search.get("payload") or {}).get("results") or []),
            "plan_status": {
                "ok": plan_payload.get("ok"),
                "plan_id_present": bool(plan_payload.get("plan_id")),
                "blocker": plan_payload.get("blocker") or plan_payload.get("error"),
                "item_count": plan_payload.get("item_count"),
            },
            "safety": {
                "identity_block_source": "front_end_ui",
                "face_identification_enabled": False,
                "biometric_recognition_enabled": False,
                "sensitive_attribute_inference_enabled": False,
                "raw_path_returned": False,
            },
        },
    }
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    return 0 if payload["ok"] else 1


def http_text(base_url: str, path: str, *, timeout: int) -> dict[str, Any]:
    req = urllib.request.Request(base_url.rstrip("/") + path, headers={"Accept": "text/html,application/javascript,text/css,*/*"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read(3 * 1024 * 1024).decode("utf-8", errors="replace")
            return {"ok": 200 <= response.status < 300, "status": response.status, "text": raw, "content_type": response.headers.get("Content-Type", "")}
    except urllib.error.HTTPError as exc:
        raw = exc.read(256 * 1024).decode("utf-8", errors="replace")
        return {"ok": False, "status": exc.code, "text": raw, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "status": None, "text": "", "error": f"{type(exc).__name__}:{exc}"}


def http_binary(base_url: str, path: str, *, token: str, timeout: int) -> dict[str, Any]:
    headers = {"Accept": "image/*,*/*"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(base_url.rstrip("/") + path, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read(5 * 1024 * 1024)
            return {
                "ok": 200 <= response.status < 300,
                "status": response.status,
                "bytes": len(raw),
                "content_type": response.headers.get("Content-Type", ""),
            }
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "bytes": 0, "content_type": "", "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "status": None, "bytes": 0, "content_type": "", "error": f"{type(exc).__name__}:{exc}"}


def http_json(method: str, base_url: str, path: str, payload: dict[str, Any] | None = None, *, token: str = "", timeout: int) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(base_url.rstrip("/") + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read(5 * 1024 * 1024).decode("utf-8", errors="replace")
            return {"ok": 200 <= response.status < 300, "status": response.status, "payload": json.loads(raw)}
    except urllib.error.HTTPError as exc:
        raw = exc.read(512 * 1024).decode("utf-8", errors="replace")
        try:
            parsed: Any = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"raw": raw[:2000]}
        return {"ok": False, "status": exc.code, "payload": parsed, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "status": None, "payload": {}, "error": f"{type(exc).__name__}:{exc}"}


def has_raw_path(value: Any) -> bool:
    encoded = json.dumps(value, ensure_ascii=False)
    return any(marker in encoded for marker in RAW_PATH_MARKERS)


def has_true_key(value: Any, key: str) -> bool:
    if isinstance(value, dict):
        if value.get(key) is True:
            return True
        return any(has_true_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(has_true_key(item, key) for item in value)
    return False


def evidence_free_false_labels(assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocked_labels = {
        "人物照片",
        "白色上衣",
        "红色衣服",
        "黑色衣服",
        "宠物动物",
        "宠物照片",
        "猫咪照片",
        "狗狗照片",
        "车辆交通",
        "电子设备",
        "票据发票",
        "合同资料",
        "课程资料",
    }
    out: list[dict[str, Any]] = []
    for asset in assets:
        object_labels = [str(item) for item in asset.get("object_labels") or [] if item]
        person_attrs = [str(item) for item in asset.get("person_attrs") or [] if item]
        categories = [str(item) for item in asset.get("category_names") or [] if item]
        if object_labels or person_attrs:
            continue
        bad = sorted(set(categories).intersection(blocked_labels))
        if bad:
            out.append(
                {
                    "asset_id": asset.get("asset_id"),
                    "title_redacted": asset.get("title_redacted"),
                    "bad_categories": bad,
                }
            )
    return out


def summarize_categories(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "category_id": item.get("category_id"),
            "name": item.get("name_zh") or item.get("name"),
            "item_count": item.get("item_count"),
        }
        for item in items[:12]
    ]


def redact_auth(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if key.lower() in {"token", "auth_token", "approval_token", "signed_approval_token"}:
                redacted[key] = "[redacted-token]"
            else:
                redacted[key] = redact_auth(item)
        return redacted
    if isinstance(value, list):
        return [redact_auth(item) for item in value]
    if isinstance(value, str) and len(value) >= 32 and all(ch in "0123456789abcdefABCDEF" for ch in value):
        return "[redacted-token]"
    return value


if __name__ == "__main__":
    raise SystemExit(main())
