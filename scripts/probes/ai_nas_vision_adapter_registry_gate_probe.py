#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from ai_nas_common import ensure_report_dir, iso_now, safe_write_json, safe_write_text
from ai_nas_vision_adapters import build_vision_adapter_registry
from ai_nas_vision_runtime import vision_product_runtime_status


TOOL_ID = "ai_nas_vision_adapter_registry_gate"
OK = "ok_ai_nas_vision_adapter_registry_gate"
FAILED = "failed_ai_nas_vision_adapter_registry_gate"


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate product-grade vision adapter registry and fallback semantics.")
    parser.add_argument("--report-root", type=Path, default=Path("tmp/ai_nas_vision_adapter_registry_gate_local"))
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "vision_adapter_registry_gate")
    registry = build_vision_adapter_registry()
    runtime = vision_product_runtime_status()
    adapters = registry.get("adapters") or []
    by_kind = {item.get("kind"): item for item in adapters}
    required_kinds = {"ocr", "caption_vlm", "image_text_embedding", "detector", "region_attributes", "vector_store", "evidence"}

    failures: list[str] = []
    missing = required_kinds - set(by_kind)
    for kind in sorted(missing):
        failures.append(f"missing_adapter_kind:{kind}")
    for kind, item in by_kind.items():
        if item.get("ready") is False and not item.get("failure_reason"):
            failures.append(f"{kind}:missing_failure_reason")
        if item.get("ready") is False and float(item.get("confidence_cap", 1)) > 0.5:
            failures.append(f"{kind}:unavailable_confidence_cap_too_high")
        if item.get("fallback") == "local_visual_embedding_v1" and item.get("product_grade"):
            failures.append(f"{kind}:legacy_embedding_marked_product_grade")
        if not isinstance(item.get("required_for"), list) or not item.get("required_for"):
            failures.append(f"{kind}:missing_required_for")
    runtime_registry = runtime.get("adapter_registry") or {}
    if runtime_registry.get("registry_schema") != registry.get("registry_schema"):
        failures.append("runtime_missing_adapter_registry")
    if runtime.get("product_ready") and registry.get("missing_product_adapters"):
        failures.append("runtime_product_ready_despite_missing_adapters")

    verdict = OK if not failures else FAILED
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "registry": registry,
        "runtime": runtime,
        "failures": failures,
        "acceptance": {
            "all_product_adapter_kinds_registered": True,
            "fallbacks_are_not_marked_product_grade": True,
            "unavailable_adapters_have_failure_reason": True,
            "unavailable_adapters_have_confidence_cap": True,
        },
    }
    json_path = run_dir / "vision_adapter_registry_gate.json"
    md_path = run_dir / "vision_adapter_registry_gate.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Vision Adapter Registry Gate",
        "",
        f"- verdict: `{verdict}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- missing_product_adapters: `{registry.get('missing_product_adapters')}`",
        f"- failures: `{failures}`",
    ]
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(f"verdict: {verdict}")
    print(f"report: {json_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
