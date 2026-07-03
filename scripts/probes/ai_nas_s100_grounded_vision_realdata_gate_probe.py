#!/usr/bin/env python3
"""Real-data gate for the S100 grounded vision gateway."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_nas_common import ensure_report_dir, safe_write_json, safe_write_text


OK = "ok_ai_nas_s100_grounded_vision_realdata_gate"
FAILED = "failed_ai_nas_s100_grounded_vision_realdata_gate"


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def post_json(url: str, payload: dict[str, Any], timeout: int = 180) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace") or "{}")


def get_json(url: str, timeout: int = 20) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace") or "{}")


def parse_caption_response(payload: dict[str, Any]) -> dict[str, Any]:
    choices = payload.get("choices") if isinstance(payload.get("choices"), list) else []
    if not choices:
        return {}
    message = choices[0].get("message") if isinstance(choices[0], dict) else {}
    content = message.get("content") if isinstance(message, dict) else ""
    if not isinstance(content, str):
        return {}
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# AI-NAS S100 Grounded Vision Real-Data Gate",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- base_url: `{payload['base_url']}`",
        f"- region_file: `{payload['fixtures']['region_image']}`",
        f"- ocr_file: `{payload['fixtures']['ocr_image']}`",
        "",
        "## Checks",
        "",
    ]
    for check in payload["checks"]:
        lines.append(f"- {check['name']}: `{check['ok']}`")
    lines.extend(["", "## Failures", ""])
    failures = payload.get("failures") or []
    lines.extend(f"- `{item}`" for item in failures) if failures else lines.append("- None.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate S100 grounded vision gateway on real NAS image data.")
    parser.add_argument("--base-url", default="http://192.168.127.10:18183")
    parser.add_argument("--report-root", type=Path, default=Path("tmp/ai_nas_s100_grounded_vision_gate_local"))
    parser.add_argument(
        "--region-image",
        type=Path,
        default=Path(r"F:\mnt\nas\openclaw\Personal\Photos\QA_20260624\football_player_pele_commons.jpg"),
    )
    parser.add_argument(
        "--ocr-image",
        type=Path,
        default=Path(r"F:\mnt\nas\openclaw\Personal\Photos\Family\2024\beach_child_invoice_screenshot_000.jpg"),
    )
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "s100_grounded_vision_realdata_gate")
    base = args.base_url.rstrip("/")
    failures: list[str] = []
    checks: list[dict[str, Any]] = []
    started = time.time()

    try:
        health = get_json(base + "/health")
    except Exception as exc:
        health = {"ok": False, "error": f"{type(exc).__name__}:{exc}"}
    checks.append({"name": "health_ready", "ok": bool(health.get("ready")), "payload": health})
    if not health.get("ready"):
        failures.append("health_not_ready")

    if not args.region_image.exists():
        failures.append("region_image_missing")
    if not args.ocr_image.exists():
        failures.append("ocr_image_missing")

    region_payload: dict[str, Any] = {}
    if args.region_image.exists():
        try:
            region_payload = post_json(
                base + "/region",
                {
                    "schema_version": "ai_nas_product_region_attributes_v1",
                    "relative_path": "Photos/QA_20260624/football_player_pele_commons.jpg",
                    "image_url": {"url": data_url(args.region_image), "detail": "high"},
                },
            )
        except Exception as exc:
            region_payload = {"ok": False, "error": f"{type(exc).__name__}:{exc}"}
    regions = region_payload.get("regions") if isinstance(region_payload.get("regions"), list) else []
    has_person = any(item.get("region_kind") == "person" or item.get("label") == "person" for item in regions if isinstance(item, dict))
    has_white_upper = any(
        item.get("region_kind") == "upper_clothing"
        and any(
            isinstance(attr, dict)
            and attr.get("namespace") == "upper_clothing"
            and attr.get("name") == "color"
            and attr.get("value") == "white"
            for attr in (item.get("attributes") or [])
        )
        for item in regions
        if isinstance(item, dict)
    )
    checks.append(
        {
            "name": "football_region_person_and_white_upper",
            "ok": bool(region_payload.get("ok") and has_person and has_white_upper),
            "region_count": len(regions),
            "has_person": has_person,
            "has_white_upper": has_white_upper,
        }
    )
    if not (region_payload.get("ok") and has_person and has_white_upper):
        failures.append("football_region_person_white_upper_not_verified")

    ocr_payload: dict[str, Any] = {}
    if args.ocr_image.exists():
        try:
            ocr_payload = post_json(
                base + "/ocr",
                {
                    "schema_version": "ai_nas_product_ocr_v1",
                    "relative_path": "Photos/Family/2024/beach_child_invoice_screenshot_000.jpg",
                    "image_url": {"url": data_url(args.ocr_image), "detail": "high"},
                },
            )
        except Exception as exc:
            ocr_payload = {"ok": False, "error": f"{type(exc).__name__}:{exc}"}
    ocr_text = str(ocr_payload.get("text") or "").strip()
    checks.append({"name": "screenshot_ocr_nonempty", "ok": bool(ocr_payload.get("ok") and ocr_text), "text_preview": ocr_text[:120]})
    if not (ocr_payload.get("ok") and ocr_text):
        failures.append("screenshot_ocr_empty_or_failed")

    caption_payload: dict[str, Any] = {}
    if args.region_image.exists():
        try:
            caption_payload = post_json(
                base + "/chat/completions",
                {
                    "model": "s100p-grounded-caption-yolo-ppocr-v1",
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": "Return JSON only."},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Describe for NAS search."},
                                {"type": "image_url", "image_url": {"url": data_url(args.region_image), "detail": "high"}},
                            ],
                        },
                    ],
                },
            )
        except Exception as exc:
            caption_payload = {"ok": False, "error": f"{type(exc).__name__}:{exc}"}
    caption = parse_caption_response(caption_payload)
    caption_text = str(caption.get("caption") or "")
    checks.append(
        {
            "name": "grounded_caption_mentions_detection",
            "ok": bool(caption_text and ("Detected" in caption_text or caption.get("objects"))),
            "caption": caption_text[:240],
        }
    )
    if not (caption_text and ("Detected" in caption_text or caption.get("objects"))):
        failures.append("grounded_caption_not_verified")

    verdict = OK if not failures else FAILED
    payload = {
        "generated_at": iso_now(),
        "tool_id": "ai_nas_s100_grounded_vision_realdata_gate",
        "verdict": verdict,
        "ok": verdict == OK,
        "base_url": base,
        "elapsed_seconds": round(time.time() - started, 3),
        "fixtures": {"region_image": str(args.region_image), "ocr_image": str(args.ocr_image)},
        "checks": checks,
        "failures": failures,
        "responses": {
            "health": health,
            "region": {
                "ok": region_payload.get("ok"),
                "model_id": region_payload.get("model_id"),
                "region_count": len(regions),
                "metadata": region_payload.get("metadata"),
            },
            "ocr": {
                "ok": ocr_payload.get("ok"),
                "model_id": ocr_payload.get("model_id"),
                "text_preview": ocr_text[:240],
                "metadata": ocr_payload.get("metadata"),
            },
            "caption": {
                "model": caption_payload.get("model"),
                "parsed": caption,
            },
        },
        "audit": {
            "real_data_used": True,
            "real_personal_source_modified": False,
            "writes": "bounded JSON/Markdown gate evidence under report root only",
        },
    }
    safe_write_json(run_dir / "s100_grounded_vision_realdata_gate.json", payload)
    safe_write_text(run_dir / "s100_grounded_vision_realdata_gate.md", markdown(payload))
    print(run_dir / "s100_grounded_vision_realdata_gate.md")
    print(run_dir / "s100_grounded_vision_realdata_gate.json")
    print(verdict)
    return 0 if verdict == OK else 1


if __name__ == "__main__":
    raise SystemExit(main())
