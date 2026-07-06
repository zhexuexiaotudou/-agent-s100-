from __future__ import annotations

import argparse

from ai_space_gate_common import add_common_args, check, write_gate
from stage8_demo_common import gate_payload, http_get_json


NAME = "stage8_demo2_ai_nas_features_gate"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate demo 2 AI-NAS feature surface.")
    add_common_args(parser)
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--timeout", type=int, default=12)
    args = parser.parse_args()
    product = http_get_json(args.base_url, "/api/product/status", timeout=args.timeout)
    auto_status = http_get_json(args.base_url, "/api/auto-organize/status", timeout=args.timeout)
    ai_space = http_get_json(args.base_url, "/api/ai-space/status", timeout=args.timeout)
    smart = http_get_json(args.base_url, "/api/smart-classification/status", timeout=args.timeout)
    modules = (product.get("payload") or {}).get("modules") if isinstance((product.get("payload") or {}).get("modules"), dict) else {}
    checks = [
        check("product status ok", product.get("ok") is True and (product.get("payload") or {}).get("ok") is True, product),
        check("auto organizer status ok", auto_status.get("ok") is True and (auto_status.get("payload") or {}).get("ok") is True, auto_status),
        check("ai space status ok", ai_space.get("ok") is True and (ai_space.get("payload") or {}).get("ok") is True, ai_space),
        check("smart classification status ok", smart.get("ok") is True and (smart.get("payload") or {}).get("ok") is True, smart),
        check("auto organizer module exposed", "auto_organizer" in modules, sorted(modules)),
        check("assistant trace module exposed", "assistant_trace" in modules, sorted(modules)),
        check("AI Space has assets", int((ai_space.get("payload") or {}).get("asset_count") or 0) >= 1, (ai_space.get("payload") or {}).get("asset_count")),
        check("Smart classification has categories", int((smart.get("payload") or {}).get("category_count") or 0) >= 1, (smart.get("payload") or {}).get("category_count")),
        check("delete disabled in auto organizer", (auto_status.get("payload") or {}).get("delete_enabled") is False, auto_status.get("payload")),
        check("overwrite disabled in auto organizer", (auto_status.get("payload") or {}).get("overwrite_enabled") is False, auto_status.get("payload")),
    ]
    payload = gate_payload("ok_stage8_demo2_ai_nas_features_gate", "blocked_stage8_demo2_ai_nas_features_gate", checks, {"product": product, "auto_status": auto_status, "ai_space": ai_space, "smart": smart})
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
