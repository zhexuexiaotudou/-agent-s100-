#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import socket
import threading
import time
import urllib.request
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ai_nas_common import DEFAULT_REPORT_ROOT, ensure_report_dir, safe_write_json, safe_write_text


TOOL_ID = "ai_nas_edge_cloud_router"
LOCAL_MODEL = "Qwen2.5-1.5B-Instruct-S100P-official"
DEFAULT_QWEN_BASE_URL = "http://127.0.0.1:18080"
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
    "id_card": ["身份证", "护照", "驾驶证", "id card", "passport", "driver license"],
    "contract": ["合同", "协议", "contract", "agreement"],
    "invoice": ["发票", "票据", "收据", "invoice", "receipt", "reimbursement"],
    "family_photo": ["家庭照片", "孩子", "小孩", "宝宝", "family photo", "family", "child", "kid", "baby"],
    "face": ["人脸", "头像", "face", "portrait"],
    "nas_private_path": ["/mnt/nas", "personal/", "我的nas", "我的 nas", "私人目录", "my nas", "private folder"],
    "chat_screenshot": ["聊天截图", "微信截图", "chat screenshot", "screenshot"],
    "finance": ["金额", "付款", "银行卡", "工资", "财务", "报销", "payment", "bank", "salary"],
}

SIMPLE_TERMS = {
    "summary": ["summary", "summarize", "总结", "摘要"],
    "classification": ["classify", "分类", "整理", "sort"],
    "search": ["find", "search", "查找", "搜索"],
    "local_file_qa": ["folder", "documents", "photos", "movies", "inbox", "文件夹", "文档", "照片", "电影", "收件箱"],
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
    ("ai_nas_case_packet", ["contract", "合同", "invoice", "发票", "receipt", "收据", "chat screenshot", "聊天截图", "payment", "付款", "renovation"]),
    ("ai_nas_photo_semantic_search", ["photo", "照片", "image", "图片", "beach", "car", "screenshot", "截图"]),
    ("ai_nas_folder_summary", ["summary", "summarize", "总结", "摘要", "folder", "文件夹", "documents", "文档"]),
    ("ai_nas_file_search", ["find", "查找", "search", "搜索"]),
    ("ai_nas_personal_inventory", ["inventory", "清单", "scan", "扫描", "index", "索引"]),
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
    """Fallback and privacy-floor classifier.

    This policy is not the primary router when Qwen classification is enabled.
    It is used only when Qwen fails to return structured JSON, and as a hard
    privacy guardrail that can block cloud routing for private queries.
    """
    privacy_hits = hits_by_group(query, PRIVACY_TERMS)
    simple_hits = hits_by_group(query, SIMPLE_TERMS)
    has_market_or_public = any(
        term in query.lower()
        for term in ["market", "public", "trend", "strategy", "launch", "行业", "趋势", "市场", "战略", "发布"]
    )
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
            reason = "simple local NAS task can be handled by Qwen and allowlisted tools"
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
        "classifier": "policy_fallback_or_privacy_guardrail",
    }


def build_qwen_router_prompt(query: str) -> str:
    return (
        "You are the local Qwen edge-cloud router. Classify the ORIGINAL USER QUERY below. "
        "Do not answer the user query. Return exactly one JSON object and no markdown.\n"
        "Schema: {\"route\":\"local|cloud\",\"privacy_level\":\"none|low|medium|high\","
        "\"task_complexity\":\"simple|complex\",\"reason\":\"short reason\",\"local_tool_id\":null}.\n"
        "Rules: route local for private or personal NAS content, family photos, faces, invoices, "
        "contracts, payments, screenshots, local files, or simple NAS search/list/summarize tasks. "
        "Route cloud only for public, non-private, complex research, market, strategy, or launch "
        "reasoning that benefits from cloud intelligence. If uncertain, route local.\n"
        f"ORIGINAL USER QUERY:\n{query}"
    )


def _structured_result_from_json(parsed: dict[str, Any], content: str, metadata: dict[str, Any]) -> dict[str, Any] | None:
    if parsed.get("route") not in {"local", "cloud"}:
        return None
    privacy_level = str(parsed.get("privacy_level") or "none").lower()
    if privacy_level in {"public", "non_private", "non-private"}:
        privacy_level = "none"
    if privacy_level not in {"none", "low", "medium", "high"}:
        privacy_level = "none"
    task_complexity = str(parsed.get("task_complexity") or ("complex" if parsed.get("route") == "cloud" else "simple")).lower()
    if task_complexity not in {"simple", "complex"}:
        task_complexity = "complex" if parsed.get("route") == "cloud" else "simple"
    return {
        "route": parsed["route"],
        "reason": str(parsed.get("reason") or "Qwen returned structured route JSON"),
        "privacy_level": privacy_level,
        "task_complexity": task_complexity,
        "local_tool_id": parsed.get("local_tool_id"),
        "classifier": "qwen_structured_json",
        "raw_content": content[:500],
        "metadata": metadata,
        "original_query_sent": True,
        "structured_json_required": True,
    }


def local_qwen_classifier(base_url: str, model: str, query: str, timeout: int) -> dict[str, Any] | None:
    prompt = build_qwen_router_prompt(query)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 192,
        "stream": False,
        "disable_ai_nas_tools": True,
        "metadata": {
            "purpose": "edge_cloud_route_classifier",
            "disable_ai_nas_tools": True,
            "original_query_sent": True,
        },
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
    if not isinstance(body, dict):
        return None
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first_choice = choices[0] if isinstance(choices[0], dict) else {}
    message = first_choice.get("message") if isinstance(first_choice.get("message"), dict) else {}
    content = str(message.get("content") or "")
    metadata = message.get("metadata") if isinstance(message.get("metadata"), dict) else {}
    if metadata.get("route") == "ai_nas_allowlisted_tools":
        return {
            "route": "local",
            "reason": "Qwen gateway handled the original query through local AI-NAS allowlisted tools",
            "privacy_level": "high",
            "task_complexity": "simple",
            "local_tool_id": "ai_nas_allowlisted_tools",
            "classifier": "qwen_ai_nas_tool_route",
            "raw_content": content[:500],
            "metadata": metadata,
            "original_query_sent": True,
            "structured_json_required": True,
        }
    match = re.search(r"\{.*\}", content, flags=re.S)
    if match:
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            route_match = re.search(r'"?route"?\s*[:=]\s*"?\b(local|cloud)\b', content, flags=re.I)
            if not route_match:
                raise
            parsed = {"route": route_match.group(1).lower(), "reason": "Qwen returned malformed JSON with explicit route"}
        if isinstance(parsed, dict):
            result = _structured_result_from_json(parsed, content, metadata)
            if result:
                return result
    return None


def route_query(query: str, base_url: str, model: str, timeout: int, use_qwen_classifier: bool) -> dict[str, Any]:
    policy = classify_policy(query)
    qwen_result = None
    qwen_error = ""
    if use_qwen_classifier:
        try:
            qwen_result = local_qwen_classifier(base_url, model, query, timeout)
        except Exception as exc:
            qwen_error = f"{type(exc).__name__}:{exc}"
    if qwen_result:
        result = dict(qwen_result)
        if policy["privacy_level"] != "none":
            result["privacy_level"] = policy["privacy_level"]
            if result.get("route") == "cloud":
                result["route"] = "local"
                result["classifier"] = "privacy_guardrail_override_after_qwen"
                result["reason"] = policy["reason"]
                result["local_tool_id"] = result.get("local_tool_id") or policy.get("local_tool_id")
        result["qwen_classifier"] = qwen_result
        result["policy_guardrail"] = {
            "privacy_level": policy["privacy_level"],
            "route_if_qwen_failed": policy["route"],
            "privacy_hits": policy["privacy_hits"],
            "simple_hits": policy["simple_hits"],
        }
        return result
    result = dict(policy)
    if use_qwen_classifier:
        result["classifier"] = "policy_fallback_after_qwen_structured_failure"
        result["reason"] = f"{policy['reason']} (fallback after Qwen failed to return structured JSON)"
        result["qwen_classifier_error"] = qwen_error or "qwen_classifier_returned_no_structured_json"
        result["qwen_original_query_sent"] = True
        result["structured_json_required"] = True
    else:
        result["classifier"] = "policy_only_qwen_disabled"
    return result


def load_queries(path: Path | None) -> list[dict[str, str]]:
    if path is None:
        return DEFAULT_QUERIES
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("--queries-json must contain a list")
    queries: list[dict[str, str]] = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"--queries-json item {index} must be an object")
        query = item.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError(f"--queries-json item {index} must contain a non-empty query string")
        query_id = item.get("id")
        expected = item.get("expected_route")
        if expected is not None and expected not in {"local", "cloud"}:
            raise ValueError(f"--queries-json item {index} expected_route must be local or cloud")
        queries.append(
            {
                "id": str(query_id or f"query_{index}"),
                "query": query,
                "expected_route": str(expected) if expected else "",
            }
        )
    return queries


def free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    try:
        return int(sock.getsockname()[1])
    finally:
        sock.close()


class LocalCloudStubHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:
        return

    def send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self) -> None:
        if self.path.rstrip("/") != "/route-demo":
            self.send_json({"ok": False, "error": "not_found"}, HTTPStatus.NOT_FOUND)
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except json.JSONDecodeError as exc:
            self.send_json({"ok": False, "error": f"invalid_json:{exc}"}, HTTPStatus.BAD_REQUEST)
            return
        query = str(payload.get("query") or "")
        call = {
            "received_at": iso_now(),
            "endpoint_kind": "controlled_cloud_endpoint",
            "path": self.path,
            "query_preview": query[:180],
            "query_length": len(query),
        }
        self.server.calls.append(call)  # type: ignore[attr-defined]
        self.send_json(
            {
                "ok": True,
                "provider": "controlled_cloud_endpoint",
                "received": True,
                "call_index": len(self.server.calls),  # type: ignore[attr-defined]
                "query_length": len(query),
            }
        )


def start_local_cloud_stub() -> tuple[ThreadingHTTPServer, str, list[dict[str, Any]]]:
    port = free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), LocalCloudStubHandler)
    calls: list[dict[str, Any]] = []
    server.calls = calls  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}", calls


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
    parser = argparse.ArgumentParser(description="AI-NAS edge-cloud routing demo with privacy-first local Qwen gate.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--queries-json", type=Path, default=None)
    parser.add_argument("--qwen-base-url", default=DEFAULT_QWEN_BASE_URL)
    parser.add_argument("--qwen-model", default=LOCAL_MODEL)
    parser.add_argument("--use-qwen-classifier", action="store_true")
    parser.add_argument("--dream-base-url", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--use-dream-classifier", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--cloud-base-url", default="https://cloud.example.invalid")
    parser.add_argument("--execute-cloud", action="store_true")
    parser.add_argument("--use-local-cloud-stub", action="store_true", help="Start a controlled local HTTP cloud endpoint for live cloud-call acceptance.")
    parser.add_argument("--require-cloud-call", action="store_true", help="Fail if a cloud-routed query does not perform a real cloud call.")
    parser.add_argument("--require-qwen-touch", action="store_true", help="Fail if Qwen classifier evidence is missing for any query.")
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()
    classifier_base_url = args.dream_base_url or args.qwen_base_url
    classifier_enabled = args.use_qwen_classifier or args.use_dream_classifier
    cloud_base_url = args.cloud_base_url
    cloud_stub_server: ThreadingHTTPServer | None = None
    cloud_stub_calls: list[dict[str, Any]] = []
    cloud_endpoint_kind = "external_cloud_endpoint"
    if args.use_local_cloud_stub:
        cloud_stub_server, cloud_base_url, cloud_stub_calls = start_local_cloud_stub()
        cloud_endpoint_kind = "controlled_cloud_endpoint"
    elif not args.execute_cloud:
        cloud_endpoint_kind = "dry_run"

    run_dir = ensure_report_dir(args.report_root, "edge_cloud_router")
    queries = load_queries(args.queries_json)
    audit_events = []
    failures: list[str] = []
    try:
        for item in queries:
            query_id = item.get("id") or f"query_{len(audit_events) + 1}"
            query = item["query"]
            classification = route_query(query, classifier_base_url, args.qwen_model, args.timeout, classifier_enabled)
            cloud = {"called": False, "mode": "not_applicable"}
            if args.require_qwen_touch and classifier_enabled and not (
                classification.get("qwen_classifier")
                or classification.get("qwen_classifier_error")
                or classification.get("qwen_original_query_sent")
            ):
                failures.append(f"{query_id}:qwen_classifier_evidence_missing")
            if classification["route"] == "cloud":
                try:
                    cloud = maybe_call_cloud(query, cloud_base_url, args.timeout, args.execute_cloud)
                    cloud["endpoint_kind"] = cloud_endpoint_kind
                except Exception as exc:
                    cloud = {"called": False, "endpoint_kind": cloud_endpoint_kind, "error": f"{type(exc).__name__}:{exc}"}
                    failures.append(f"{query_id}:cloud_call_failed")
                if args.require_cloud_call and not cloud.get("called"):
                    failures.append(f"{query_id}:cloud_call_required_but_not_performed")
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
    finally:
        if cloud_stub_server:
            cloud_stub_server.shutdown()
            cloud_stub_server.server_close()

    route_counts: dict[str, int] = {}
    privacy_counts: dict[str, int] = {}
    classifier_counts: dict[str, int] = {}
    for event in audit_events:
        route = event["classification"]["route"]
        privacy = event["classification"]["privacy_level"]
        classifier = event["classification"]["classifier"]
        route_counts[route] = route_counts.get(route, 0) + 1
        privacy_counts[privacy] = privacy_counts.get(privacy, 0) + 1
        classifier_counts[classifier] = classifier_counts.get(classifier, 0) + 1
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_edge_cloud_router" if not failures else "failed_ai_nas_edge_cloud_router",
        "scope": "all queries enter local Qwen first; structured Qwen JSON is primary, policy is privacy/failure fallback",
        "qwen_base_url": classifier_base_url,
        "qwen_model": args.qwen_model,
        "qwen_classifier_enabled": classifier_enabled,
        "qwen_structured_json_required": True,
        "cloud_base_url": cloud_base_url,
        "cloud_endpoint_kind": cloud_endpoint_kind,
        "execute_cloud": args.execute_cloud,
        "require_cloud_call": args.require_cloud_call,
        "require_qwen_touch": args.require_qwen_touch,
        "controlled_cloud_endpoint_enabled": args.use_local_cloud_stub,
        "summary": {
            "query_count": len(audit_events),
            "route_counts": route_counts,
            "privacy_counts": privacy_counts,
            "classifier_counts": classifier_counts,
            "privacy_query_sent_to_cloud": any(
                event["classification"]["privacy_level"] != "none" and event["cloud_request"].get("called")
                for event in audit_events
            ),
            "local_query_count": route_counts.get("local", 0),
            "cloud_query_count": route_counts.get("cloud", 0),
            "cloud_call_count": sum(1 for event in audit_events if event["cloud_request"].get("called")),
            "controlled_cloud_call_count": len(cloud_stub_calls),
            "failures": failures,
        },
        "audit_events": audit_events,
        "controlled_cloud_calls": cloud_stub_calls,
        "policy": {
            "privacy_terms": PRIVACY_TERMS,
            "simple_terms": SIMPLE_TERMS,
            "local_tool_rules": LOCAL_TOOL_RULES,
            "privacy_floor": "policy may override Qwen only to prevent privacy-sensitive cloud routing",
            "fallback_rule": "policy is used when Qwen does not return structured JSON or errors",
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
        f"- qwen_classifier_enabled: `{payload['qwen_classifier_enabled']}`",
        f"- qwen_structured_json_required: `{payload['qwen_structured_json_required']}`",
        f"- execute_cloud: `{payload['execute_cloud']}`",
        f"- cloud_endpoint_kind: `{payload['cloud_endpoint_kind']}`",
        f"- route_counts: `{route_counts}`",
        f"- classifier_counts: `{classifier_counts}`",
        f"- cloud_call_count: `{payload['summary']['cloud_call_count']}`",
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
            f"complexity `{cls['task_complexity']}` classifier `{cls['classifier']}` "
            f"local_tool `{cls.get('local_tool_id')}` reason `{cls['reason']}`"
        )
    lines.extend(
        [
            "",
            "## Guardrail",
            "",
            "- The original user query is sent to the local Qwen gateway before routing.",
            "- Structured Qwen JSON is the primary route signal when available.",
            "- Policy is used only as a privacy guardrail or fallback after Qwen structured-output failure.",
            "- Privacy-sensitive queries are never sent to cloud in this probe.",
            "- `--use-local-cloud-stub` starts a controlled HTTP endpoint for cloud-call acceptance without external credentials.",
        ]
    )
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
