#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_nas_common import DEFAULT_REPORT_ROOT, ensure_report_dir, safe_write_json, safe_write_text


TOOL_ID = "ai_nas_edge_cloud_router"
LOCAL_MODEL = "Dream7B-S100P-local"
DEFAULT_QUERIES = [
    {
        "id": "simple_local",
        "query": "Summarize my Documents folder and list likely payment dates.",
        "expected_route": "local",
    },
    {
        "id": "privacy_local",
        "query": "Find my child's beach photo and the renovation invoice screenshot in the NAS.",
        "expected_route": "local",
    },
    {
        "id": "complex_cloud",
        "query": "Compare public 2026 AI NAS market trends and draft a strategic launch narrative.",
        "expected_route": "cloud",
    },
]

PRIVACY_TERMS = {
    "id_card": ["身份证", "id card", "passport", "driver license"],
    "contract": ["合同", "contract", "agreement"],
    "invoice": ["发票", "invoice", "receipt", "reimbursement"],
    "family_photo": ["家庭照片", "family photo", "family", "孩子", "child", "kid", "baby"],
    "face": ["人脸", "face", "portrait"],
    "nas_private_path": ["/mnt/nas", "personal/", "my nas", "private folder"],
    "chat_screenshot": ["聊天截图", "chat screenshot", "screenshot"],
    "finance": ["金额", "payment", "bank", "salary", "财务", "报销"],
}

SIMPLE_TERMS = {
    "summary": ["summary", "summarize", "总结", "摘要"],
    "classification": ["classify", "分类", "整理", "sort"],
    "search": ["find", "search", "查找", "搜索"],
    "local_file_qa": ["folder", "documents", "photos", "movies", "inbox", "文件夹"],
    "allowlisted_tool": [
        "ai_nas_personal_inventory",
        "ai_nas_file_search",
        "ai_nas_folder_summary",
        "ai_nas_case_packet",
        "ai_nas_duplicate_report",
        "ai_nas_movie_sort_enhanced",
    ],
}

LOCAL_TOOL_RULES = [
    ("ai_nas_case_packet", ["contract", "invoice", "receipt", "chat screenshot", "payment", "renovation"]),
    ("ai_nas_photo_semantic_search", ["photo", "image", "beach", "car", "screenshot", "照片", "图片"]),
    ("ai_nas_folder_summary", ["summary", "summarize", "folder", "documents", "总结", "摘要"]),
    ("ai_nas_file_search", ["find", "search", "查找", "搜索"]),
    ("ai_nas_personal_inventory", ["inventory", "scan", "index", "清单", "扫描"]),
]


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def hits_by_group(query: str, groups: dict[str, list[str]]) -> dict[str, list[str]]:
    lowered = query.lower()
    hits: dict[str, list[str]] = {}
    for group, terms in groups.items():
        matched = [term for term in terms if term.lower() in lowered or term in query]
        if matched:
            hits[group] = matched
    return hits


def infer_local_tool(query: str) -> str | None:
    lowered = query.lower()
    for tool_id, needles in LOCAL_TOOL_RULES:
        if any(needle.lower() in lowered or needle in query for needle in needles):
            return tool_id
    return None


def classify_policy(query: str) -> dict[str, Any]:
    privacy_hits = hits_by_group(query, PRIVACY_TERMS)
    simple_hits = hits_by_group(query, SIMPLE_TERMS)
    has_market_or_public = any(term in query.lower() for term in ["market", "public", "trend", "strategy", "launch", "行业", "趋势"])
    has_complex = has_market_or_public or len(query) > 120

    privacy_level = "none"
    if privacy_hits:
        privacy_level = "high" if any(key in privacy_hits for key in ["id_card", "family_photo", "face", "finance"]) else "medium"
    task_complexity = "simple" if simple_hits and not has_complex else "complex"
    if has_complex and privacy_level == "none":
        route = "cloud"
        reason = "non-private complex query can be sent to cloud for broader reasoning"
    else:
        route = "local"
        if privacy_level != "none":
            reason = "privacy-sensitive query must stay on device"
        elif task_complexity == "simple":
            reason = "simple local NAS task can be handled by Dream7B and allowlisted tools"
        else:
            reason = "default local route for uncertain classification"

    return {
        "route": route,
        "reason": reason,
        "privacy_level": privacy_level,
        "task_complexity": task_complexity,
        "privacy_hits": privacy_hits,
        "simple_hits": simple_hits,
        "local_tool_id": infer_local_tool(query) if route == "local" else None,
        "classifier": "deterministic_policy_guardrail",
    }


def local_dream_classifier(base_url: str, query: str, timeout: int) -> dict[str, Any] | None:
    prompt = (
        "Classify this user query for an edge-cloud router. Return compact JSON with keys "
        "route, reason, privacy_level, task_complexity, local_tool_id. Query: "
        + query
    )
    payload = {
        "model": LOCAL_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 128,
        "stream": False,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8", errors="replace"))
    content = str(((body.get("choices") or [{}])[0].get("message") or {}).get("content") or "")
    match = re.search(r"\{.*\}", content, flags=re.S)
    if not match:
        return None
    parsed = json.loads(match.group(0))
    if parsed.get("route") not in {"local", "cloud"}:
        return None
    parsed["classifier"] = "dream7b_local_json"
    parsed["raw_content"] = content[:500]
    return parsed


def route_query(query: str, base_url: str, timeout: int, use_dream_classifier: bool) -> dict[str, Any]:
    policy = classify_policy(query)
    dream_result = None
    dream_error = ""
    if use_dream_classifier:
        try:
            dream_result = local_dream_classifier(base_url, query, timeout)
        except Exception as exc:
            dream_error = f"{type(exc).__name__}:{exc}"
    result = dict(policy)
    if dream_result:
        # Keep policy as the privacy floor: Dream may make local routes stricter, but not weaker.
        if policy["privacy_level"] != "none" and dream_result.get("route") == "cloud":
            result["classifier"] = "policy_override_after_dream"
            result["dream_classifier"] = dream_result
            result["reason"] = policy["reason"]
        else:
            result.update({key: dream_result.get(key, result.get(key)) for key in ["route", "reason", "privacy_level", "task_complexity", "local_tool_id", "classifier"]})
            result["dream_classifier"] = dream_result
    elif use_dream_classifier:
        result["dream_classifier_error"] = dream_error or "dream_classifier_returned_no_json"
    return result


def load_queries(path: Path | None) -> list[dict[str, str]]:
    if path is None:
        return DEFAULT_QUERIES
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("--queries-json must contain a list")
    return data


def maybe_call_cloud(query: str, cloud_base_url: str, timeout: int, execute_cloud: bool) -> dict[str, Any]:
    if not execute_cloud:
        return {"called": False, "mode": "dry_run", "trace": "cloud call intentionally skipped"}
    payload = {"query": query}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        cloud_base_url.rstrip("/") + "/route-demo",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    return {
        "called": True,
        "status": resp.status,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "body_preview": body[:500],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS edge-cloud routing demo with privacy-first local Dream7B gate.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--queries-json", type=Path, default=None)
    parser.add_argument("--dream-base-url", default="http://127.0.0.1:18888")
    parser.add_argument("--use-dream-classifier", action="store_true")
    parser.add_argument("--cloud-base-url", default="https://cloud.example.invalid")
    parser.add_argument("--execute-cloud", action="store_true")
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "edge_cloud_router")
    queries = load_queries(args.queries_json)
    audit_events = []
    failures: list[str] = []
    for item in queries:
        query_id = item.get("id") or f"query_{len(audit_events) + 1}"
        query = item["query"]
        classification = route_query(query, args.dream_base_url, args.timeout, args.use_dream_classifier)
        cloud = {"called": False, "mode": "not_applicable"}
        if classification["route"] == "cloud":
            try:
                cloud = maybe_call_cloud(query, args.cloud_base_url, args.timeout, args.execute_cloud)
            except Exception as exc:
                cloud = {"called": False, "error": f"{type(exc).__name__}:{exc}"}
                failures.append(f"{query_id}:cloud_call_failed")
        expected = item.get("expected_route")
        if expected and classification["route"] != expected:
            failures.append(f"{query_id}:route_mismatch:{classification['route']}!={expected}")
        if classification["privacy_level"] != "none" and cloud.get("called"):
            failures.append(f"{query_id}:privacy_query_sent_to_cloud")
        audit_events.append(
            {
                "query_id": query_id,
                "query_preview": query[:180],
                "classification": classification,
                "expected_route": expected,
                "cloud_request": cloud if classification["route"] == "cloud" else {"called": False, "privacy_guard": True},
                "local_tool_would_run": classification.get("local_tool_id"),
            }
        )

    route_counts: dict[str, int] = {}
    privacy_counts: dict[str, int] = {}
    for event in audit_events:
        route = event["classification"]["route"]
        privacy = event["classification"]["privacy_level"]
        route_counts[route] = route_counts.get(route, 0) + 1
        privacy_counts[privacy] = privacy_counts.get(privacy, 0) + 1
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_edge_cloud_router" if not failures else "failed_ai_nas_edge_cloud_router",
        "scope": "thin auditable edge-cloud router; local Dream7B or deterministic policy classifies before any cloud call",
        "dream_base_url": args.dream_base_url,
        "dream_classifier_enabled": args.use_dream_classifier,
        "cloud_base_url": args.cloud_base_url,
        "execute_cloud": args.execute_cloud,
        "summary": {
            "query_count": len(audit_events),
            "route_counts": route_counts,
            "privacy_counts": privacy_counts,
            "privacy_query_sent_to_cloud": any(
                event["classification"]["privacy_level"] != "none" and event["cloud_request"].get("called")
                for event in audit_events
            ),
            "local_query_count": route_counts.get("local", 0),
            "cloud_query_count": route_counts.get("cloud", 0),
            "failures": failures,
        },
        "audit_events": audit_events,
        "policy": {
            "privacy_terms": PRIVACY_TERMS,
            "simple_terms": SIMPLE_TERMS,
            "local_tool_rules": LOCAL_TOOL_RULES,
            "privacy_floor": "policy guardrail prevents Dream classifier from routing privacy-sensitive queries to cloud",
        },
    }
    json_path = run_dir / "edge_cloud_router.json"
    md_path = run_dir / "edge_cloud_router.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Edge Cloud Router",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- dream_classifier_enabled: `{payload['dream_classifier_enabled']}`",
        f"- execute_cloud: `{payload['execute_cloud']}`",
        f"- route_counts: `{route_counts}`",
        f"- privacy_query_sent_to_cloud: `{payload['summary']['privacy_query_sent_to_cloud']}`",
        f"- failures: `{failures}`",
        "",
        "## Audit Events",
        "",
    ]
    for event in audit_events:
        cls = event["classification"]
        lines.append(
            f"- `{event['query_id']}` route `{cls['route']}` privacy `{cls['privacy_level']}` "
            f"complexity `{cls['task_complexity']}` local_tool `{cls.get('local_tool_id')}` reason `{cls['reason']}`"
        )
    lines.extend(
        [
            "",
            "## Guardrail",
            "",
            "- Privacy-sensitive queries are never sent to cloud in this probe.",
            "- Cloud execution is dry-run unless `--execute-cloud` is set.",
            "- The deterministic policy remains the privacy floor even when the optional Dream7B classifier is enabled.",
        ]
    )
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
