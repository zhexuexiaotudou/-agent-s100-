from __future__ import annotations

import argparse

from ai_space_gate_common import check, write_gate
from stage10_common import add_stage10_args, gate_payload, has_raw_path, http_json, redact_auth, token_from_args


NAME = "stage10_gold_query_multimodal_gate"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run authenticated golden demo queries against live product APIs.")
    add_stage10_args(parser)
    args = parser.parse_args()
    token = token_from_args(args)
    flows = {}
    if token:
        flows["multimodal_laptop"] = http_json("POST", args.base_url, "/api/multimodal-search/query", {"query": "找有电脑的照片", "top_k": 8}, timeout=args.timeout, token=token)
        flows["multimodal_pet"] = http_json("POST", args.base_url, "/api/multimodal-search/query", {"query": "找宠物照片", "top_k": 8}, timeout=args.timeout, token=token)
        flows["multimodal_video"] = http_json("POST", args.base_url, "/api/multimodal-search/query", {"query": "找视频里有人的片段", "top_k": 8}, timeout=args.timeout, token=token)
        flows["ai_space_pet"] = http_json("POST", args.base_url, "/api/ai-space/search", {"query": "找宠物照片", "top_k": 8}, timeout=args.timeout, token=token)
        flows["person_white"] = http_json("POST", args.base_url, "/api/person-attribute/search", {"query": "找穿白色上衣的人", "top_k": 8}, timeout=args.timeout, token=token)
        flows["identity_block"] = http_json("POST", args.base_url, "/api/person-attribute/search", {"query": "这个人是谁？", "top_k": 8}, timeout=args.timeout, token=token)
        flows["invoice_rag"] = http_json("POST", args.base_url, "/api/document-rag/query", {"query": "这张票据里的金额和日期是什么？", "path": "Documents"}, timeout=args.timeout, token=token)
        flows["contract_rag"] = http_json("POST", args.base_url, "/api/document-rag/query", {"query": "这份合同的付款条款是什么？", "path": "Documents"}, timeout=args.timeout, token=token)
    identity = (flows.get("identity_block") or {}).get("payload") or {}
    invoice = (flows.get("invoice_rag") or {}).get("payload") or {}
    contract = (flows.get("contract_rag") or {}).get("payload") or {}
    checks = [
        check("auth token available", bool(token), "DIGUA_DEMO_AUTH_TOKEN or /tmp/stage9_demo_token.txt"),
        check("multimodal laptop query ok", api_ok(flows.get("multimodal_laptop")), summarize(flows.get("multimodal_laptop"))),
        check("multimodal pet query ok", api_ok(flows.get("multimodal_pet")), summarize(flows.get("multimodal_pet"))),
        check("multimodal video query ok", api_ok(flows.get("multimodal_video")), summarize(flows.get("multimodal_video"))),
        check("AI Space pet query ok", api_ok(flows.get("ai_space_pet")), summarize(flows.get("ai_space_pet"))),
        check("person white query safely handled", api_ok(flows.get("person_white")), summarize(flows.get("person_white"))),
        check("identity query blocked", identity.get("blocked") is True and identity.get("face_identification_enabled") is False, identity),
        check("invoice grounded or explicit no answer", invoice.get("ok") is True or invoice.get("no_grounded_answer") is True, invoice),
        check("contract grounded or explicit no answer", contract.get("ok") is True or contract.get("no_grounded_answer") is True, contract),
        check("no raw path in query responses", not has_raw_path(flows), "redacted"),
        check("cloud not used for private query flow", not cloud_used(flows), "cloud_used=false"),
    ]
    payload = gate_payload("ok_stage10_gold_query_multimodal_gate", "blocked_stage10_gold_query_multimodal_gate", checks, {"flows": redact_auth(flows), "auth_token_supplied": bool(token)})
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    return 0 if payload["ok"] else 1


def api_ok(flow: dict | None) -> bool:
    return bool(flow and flow.get("ok") and (flow.get("payload") or {}).get("ok") is True)


def summarize(flow: dict | None) -> dict:
    payload = (flow or {}).get("payload") or {}
    return {"status": (flow or {}).get("status"), "ok": payload.get("ok"), "blocked": payload.get("blocked"), "result_count": len(payload.get("results") or []), "degraded": payload.get("degraded"), "error": payload.get("error")}


def cloud_used(value: object) -> bool:
    if isinstance(value, dict):
        return any((key == "cloud_used" and item is True) or cloud_used(item) for key, item in value.items())
    if isinstance(value, list):
        return any(cloud_used(item) for item in value)
    return False


if __name__ == "__main__":
    raise SystemExit(main())

