#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    yolo_manifest = Path("reports/yolo_production/27110_final_delivery_package_manifest.json")
    if yolo_manifest.exists():
        return yolo_self_check(yolo_manifest)
    return token_budget_self_check()


def yolo_self_check(manifest_path: Path) -> int:
    required = [
        "src/yolo_index/backend.py",
        "src/yolo_index/indexer.py",
        "src/yolo_index/service.py",
        "src/openclaw/routes/yolo_index_routes.py",
        "benchmarks/yolo_object_search_eval_cases.jsonl",
        "reports/yolo_production/27000_s100p_environment_lock.json",
        "reports/yolo_production/27010_yolo_backend_discovery_gate.json",
        "reports/yolo_production/27020_yolo_sqlite_schema_gate.json",
        "reports/yolo_production/27030_image_yolo_index_gate.json",
        "reports/yolo_production/27040_video_keyframe_yolo_index_gate.json",
        "reports/yolo_production/27050_object_label_search_gate.json",
        "reports/yolo_production/27060_hybrid_retrieval_gate.json",
        "reports/yolo_production/27070_openclaw_api_gate.json",
        "reports/yolo_production/27080_ui_visual_detection_gate.json",
        "reports/yolo_production/27090_security_privacy_gate.json",
        "reports/yolo_production/27100_s100p_test_matrix_gate.json",
        "reports/yolo_production/27110_final_delivery_package_manifest.json",
    ]
    missing = [item for item in required if not Path(item).exists()]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    package = manifest.get("package") or {}
    remote = manifest.get("remote_summary") or {}
    checks = {
        "missing_required_count": len(missing),
        "final_verdict": manifest.get("final_verdict"),
        "package_sha256": package.get("sha256"),
        "forbidden_file_count": package.get("forbidden_file_count"),
        "s100p_reachable": remote.get("s100p_reachable"),
        "openclaw_8765_live": remote.get("openclaw_8765_live"),
        "detection_count": remote.get("detection_count"),
        "keyframe_count": remote.get("keyframe_count"),
        "strict_eval_pass_rate": remote.get("strict_eval_pass_rate"),
        "private_leak_count": remote.get("private_leak_count"),
        "raw_path_rows": remote.get("raw_path_rows"),
    }
    ok = (
        len(missing) == 0
        and bool(package.get("sha256"))
        and checks["forbidden_file_count"] == 0
        and bool(checks["s100p_reachable"])
        and bool(checks["openclaw_8765_live"])
        and int(checks["detection_count"] or 0) > 0
        and int(checks["keyframe_count"] or 0) > 0
        and float(checks["strict_eval_pass_rate"] or 0) >= 1.0
        and int(checks["private_leak_count"] or 0) == 0
        and int(checks["raw_path_rows"] or 0) == 0
    )
    print(json.dumps({"ok": ok, "mode": "yolo_multimodal_search_v2", "missing": missing, "checks": checks}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


def token_budget_self_check() -> int:
    required = [
        "src/harness/token_budget_integration.py",
        "reports/17000_tokenizer_product_baseline_lock.json",
        "reports/17010_qwen_tokenizer_identity_gate.json",
        "reports/17020_privacy_redactor_product_gate.json",
        "reports/17030_context_compressor_product_gate.json",
        "reports/17040_cloud_route_decider_product_gate.json",
        "reports/17050_token_trace_harness_integration_gate.json",
        "reports/17060_openclaw_token_budget_product_api_gate.json",
        "reports/17070_token_budget_benchmark_results.json",
        "reports/17080_token_cost_reduction_analysis.json",
        "reports/17090_token_budget_product_integration_gate.json",
        "reports/17100_token_budget_product_regression_gate.json",
        "reports/17110_updated_claim_matrix_token_budget_gate.json",
    ]
    missing = [item for item in required if not Path(item).exists()]
    summary = json.loads(Path("reports/17070_token_budget_benchmark_results.json").read_text(encoding="utf-8"))
    analysis = json.loads(Path("reports/17080_token_cost_reduction_analysis.json").read_text(encoding="utf-8"))
    checks = {
        "missing_required_count": len(missing),
        "real_qwen_tokenizer_used": summary.get("real_qwen_tokenizer_used"),
        "private_leak_count": summary.get("private_leak_count"),
        "total_cases": summary.get("total_cases"),
        "quality_pass_rate": summary.get("quality_pass_rate"),
        "final_verdict": analysis.get("final_verdict"),
    }
    ok = len(missing) == 0 and checks["real_qwen_tokenizer_used"] and checks["private_leak_count"] == 0 and checks["total_cases"] >= 120 and checks["quality_pass_rate"] >= 0.9
    print(json.dumps({"ok": ok, "mode": "token_budget", "missing": missing, "checks": checks}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
