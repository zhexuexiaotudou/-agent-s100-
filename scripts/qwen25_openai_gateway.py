#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = Path(os.environ.get("QWEN25_POLICY", "configs/qwen25_official_route_policy.json"))
MAX_REQUEST_BYTES = 5 * 1024 * 1024
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from src.harness.token_budget_integration import TokenBudgetIntegration
except Exception:
    TokenBudgetIntegration = None  # type: ignore[assignment]


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json_request(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    try:
        length = int(handler.headers.get("Content-Length", "0") or "0")
    except ValueError as exc:
        raise ValueError("Content-Length must be an integer") from exc
    if length < 0:
        raise ValueError("Content-Length must not be negative")
    if length > MAX_REQUEST_BYTES:
        raise ValueError(f"request body too large: {length} bytes")
    raw = handler.rfile.read(length) if length else b"{}"
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")
    return payload


def first_text(payload: dict[str, Any]) -> str:
    messages = payload.get("messages")
    if isinstance(messages, list):
        for item in reversed(messages):
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = [part.get("text", "") for part in content if isinstance(part, dict)]
                text = "\n".join(part for part in parts if isinstance(part, str))
                if text:
                    return text
    prompt = payload.get("prompt")
    return prompt if isinstance(prompt, str) else ""


def ai_nas_tools_enabled(payload: dict[str, Any]) -> bool:
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    disabled = (
        payload.get("disable_ai_nas_tools") is True
        or payload.get("ai_nas_tools") is False
        or metadata.get("disable_ai_nas_tools") is True
        or metadata.get("ai_nas_tools") is False
    )
    return not disabled


def is_edge_cloud_route_request(payload: dict[str, Any]) -> bool:
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        return False
    return metadata.get("purpose") == "edge_cloud_route_classifier"


def extract_original_query(prompt: str) -> str:
    marker = "ORIGINAL USER QUERY:"
    if marker in prompt:
        return prompt.split(marker, 1)[1].strip()
    return prompt.strip()


def route_term_hits(query: str, groups: dict[str, list[str]]) -> dict[str, list[str]]:
    lowered = query.lower()
    hits: dict[str, list[str]] = {}
    for group, terms in groups.items():
        matched = [term for term in terms if term.lower() in lowered or term in query]
        if matched:
            hits[group] = matched
    return hits


def token_budget_api() -> Any | None:
    if TokenBudgetIntegration is None:
        return None
    try:
        return TokenBudgetIntegration()
    except Exception:
        return None


def token_budget_route_for_prompt(prompt: str) -> dict[str, Any]:
    api = token_budget_api()
    if api is None:
        return {"ok": False, "error": "token_budget_integration_unavailable"}
    return api.route(
        {
            "case_id": f"qwen_gateway_{uuid.uuid4().hex[:12]}",
            "task_type": "public_research",
            "user_prompt": extract_original_query(prompt),
            "context_text": "",
        },
        record_trace=True,
    )


def edge_cloud_route_classification(prompt: str, token_budget_route: dict[str, Any] | None = None) -> dict[str, Any]:
    query = extract_original_query(prompt)
    privacy_terms = {
        "id_card": ["身份证", "护照", "驾驶证", "id card", "passport", "driver license"],
        "contract": ["合同", "协议", "contract", "agreement"],
        "invoice": ["发票", "票据", "收据", "invoice", "receipt", "reimbursement"],
        "family_photo": ["家庭照片", "孩子", "小孩", "宝宝", "family photo", "family", "child", "kid", "baby"],
        "face": ["人脸", "头像", "face", "portrait"],
        "nas_private_path": ["/mnt/nas", "personal/", "我的nas", "我的 nas", "私人目录", "my nas", "private folder"],
        "chat_screenshot": ["聊天截图", "微信截图", "chat screenshot", "screenshot"],
        "finance": ["金额", "付款", "银行卡", "工资", "财务", "报销", "payment", "bank", "salary"],
    }
    simple_terms = {
        "summary": ["summary", "summarize", "总结", "摘要"],
        "classification": ["classify", "分类", "整理", "sort"],
        "search": ["find", "search", "查找", "搜索"],
        "local_file_qa": ["folder", "documents", "photos", "movies", "inbox", "文件夹", "文档", "照片", "电影", "收件箱"],
    }
    privacy_hits = route_term_hits(query, privacy_terms)
    simple_hits = route_term_hits(query, simple_terms)
    has_public_complex = any(
        term in query.lower()
        for term in ["market", "public", "trend", "strategy", "launch", "行业", "趋势", "市场", "战略", "发布"]
    ) or len(query) > 120
    privacy_level = "none"
    if privacy_hits:
        privacy_level = "high" if any(key in privacy_hits for key in ["id_card", "family_photo", "face", "finance"]) else "medium"
    task_complexity = "complex" if has_public_complex and privacy_level == "none" else "simple"
    route = "cloud" if task_complexity == "complex" and privacy_level == "none" else "local"
    if route == "cloud":
        reason = "public non-private complex market or strategy request"
        local_tool_id = None
    elif privacy_level != "none":
        reason = "privacy-sensitive or personal NAS query stays on device"
        local_tool_id = "ai_nas_allowlisted_tools"
    elif simple_hits:
        reason = "simple local NAS task stays on device"
        local_tool_id = "ai_nas_allowlisted_tools"
    else:
        reason = "uncertain route defaults local"
        local_tool_id = None
    if token_budget_route and token_budget_route.get("ok"):
        budget_route = token_budget_route.get("route")
        if budget_route == "cloud_allowed_redacted":
            route = "cloud"
            reason = f"token_budget_router allowed redacted cloud: {token_budget_route.get('route_reason')}"
            local_tool_id = None
        elif budget_route in {"local_only", "cloud_blocked_private"}:
            route = "local"
            reason = f"token_budget_router blocked cloud: {token_budget_route.get('route_reason')}"
            local_tool_id = "ai_nas_allowlisted_tools" if budget_route == "local_only" else None
    return {
        "route": route,
        "privacy_level": privacy_level,
        "task_complexity": task_complexity,
        "reason": reason,
        "local_tool_id": local_tool_id,
        "classifier": "qwen_gateway_structured_router",
        "token_budget_route": token_budget_route or {"ok": False, "error": "not_run"},
        "privacy_hits": privacy_hits,
        "simple_hits": simple_hits,
        "original_query_preview": query[:180],
    }


def clean_runtime_text(text: str) -> str:
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)
    return text.replace("\r", "")


def parse_assistant(stdout: str) -> str:
    text = clean_runtime_text(stdout)
    matches = re.findall(r"\[Assistant\]\s*>>>\s*(.*)", text)
    if matches:
        return matches[-1].strip()
    return text.strip()[-2000:] or "Qwen runtime completed without a parsed assistant line."


def chat_completion(model: str, content: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                    "metadata": metadata or {},
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def path_status(path: str | None) -> dict[str, Any]:
    if not path:
        return {"path": "", "exists": False, "size_bytes": 0}
    p = Path(path)
    return {"path": str(p), "exists": p.exists(), "size_bytes": p.stat().st_size if p.exists() and p.is_file() else 0}


def is_ai_nas_request(text: str) -> bool:
    lowered = text.lower()
    terms = [
        "nas",
        "ai-nas",
        "evidence",
        "report",
        "invoice",
        "receipt",
        "payment",
        "contract",
        "screenshot",
        "\u68c0\u7d22",
        "\u641c\u7d22",
        "\u6458\u8981",
        "\u62a5\u544a",
        "\u8bc1\u636e",
        "\u53d1\u7968",
        "\u4ed8\u6b3e",
        "\u5408\u540c",
        "\u622a\u56fe",
    ]
    return any(term in lowered for term in terms)


def extract_paths(stdout: str) -> list[str]:
    paths: list[str] = []
    for line in stdout.splitlines():
        text = line.strip()
        if text.startswith("/") and (text.endswith(".json") or text.endswith(".md")):
            paths.append(text)
    return list(dict.fromkeys(paths))


def summarize_payload(path: str) -> dict[str, Any]:
    p = Path(path)
    item: dict[str, Any] = {"path": path, "exists": p.exists()}
    if p.suffix != ".json" or not p.exists():
        return item
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        item["error"] = f"{type(exc).__name__}: {exc}"
        return item
    item["verdict"] = payload.get("verdict")
    item["summary"] = payload.get("summary")
    item["answer_status"] = payload.get("answer_status")
    item["match_count"] = (payload.get("summary") or {}).get("match_count", payload.get("match_count"))
    item["audit"] = payload.get("audit")
    return item


def run_tool(policy: dict[str, Any], tool_id: str, args: list[str], timeout: int) -> dict[str, Any]:
    ai_nas = policy["ai_nas"]
    dispatcher = Path(os.environ.get("QWEN25_TOOL_DISPATCHER", ai_nas["tool_dispatcher"]))
    env = dict(os.environ)
    env["AI_NAS_PERSONAL_ROOT"] = os.environ.get("AI_NAS_PERSONAL_ROOT", ai_nas["personal_root"])
    env["AI_NAS_REPORT_ROOT"] = os.environ.get("AI_NAS_REPORT_ROOT", ai_nas["report_root"])
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            ["bash", str(dispatcher), tool_id, *args],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            env=env,
        )
        stdout = completed.stdout
        stderr = completed.stderr
        returncode = completed.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        returncode = None
        timed_out = True
    paths = extract_paths(stdout)
    return {
        "tool_id": tool_id,
        "args": args,
        "returncode": returncode,
        "timed_out": timed_out,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "stdout_tail": stdout[-2000:],
        "stderr_tail": stderr[-2000:],
        "paths": paths,
        "payloads": [summarize_payload(path) for path in paths],
    }


def run_ai_nas_flow(policy: dict[str, Any], prompt: str) -> dict[str, Any]:
    report_root = Path(policy["ai_nas"]["gateway_report_root"])
    run_dir = report_root / f"qwen25_gateway_turn_{stamp()}"
    query = prompt.strip() or policy["ai_nas"]["default_case_query"]
    tool_runs = [
        run_tool(policy, "ai_nas_personal_inventory", [], 300),
        run_tool(policy, "ai_nas_evidence_report", [query], 240),
        run_tool(policy, "ai_nas_case_packet", [query], 300),
        run_tool(policy, "ai_nas_folder_rag", ["Documents", query], 240),
    ]
    errors = []
    for run in tool_runs:
        if run["returncode"] != 0:
            errors.append(f"{run['tool_id']}:returncode_{run['returncode']}")
        if run["timed_out"]:
            errors.append(f"{run['tool_id']}:timeout")
        if not run["paths"]:
            errors.append(f"{run['tool_id']}:no_report_paths")
    payload = {
        "generated_at": iso_now(),
        "model": policy["model_id"],
        "query": query,
        "verdict": "ok_qwen25_ai_nas_gateway_turn" if not errors else "failed_qwen25_ai_nas_gateway_turn",
        "errors": errors,
        "tool_runs": tool_runs,
        "audit": {
            "source_files_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "tool_dispatcher": policy["ai_nas"]["tool_dispatcher"],
        },
    }
    json_path = run_dir / "qwen25_gateway_turn.json"
    md_path = run_dir / "qwen25_gateway_turn.md"
    write_json(json_path, payload)
    lines = [
        "# Qwen2.5 AI-NAS Gateway Turn",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- model: `{payload['model']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- query: `{query}`",
        "",
        "## Tool Runs",
        "",
    ]
    for run in tool_runs:
        lines.append(
            f"- `{run['tool_id']}` returncode `{run['returncode']}` elapsed_ms `{run['elapsed_ms']}` paths `{len(run['paths'])}`"
        )
        for path in run["paths"]:
            lines.append(f"  - `{path}`")
    lines.extend(["", "## Errors", ""])
    lines.extend([f"- `{item}`" for item in errors] or ["- none"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    payload["gateway_turn_paths"] = {"json": str(json_path), "md": str(md_path)}
    return payload


def run_qwen_runtime(policy: dict[str, Any], prompt: str) -> dict[str, Any]:
    runtime = policy["official_runtime"]
    runtime_bin = Path(os.environ.get("QWEN25_RUNTIME_BIN", runtime["runtime_bin"]))
    runtime_config = Path(os.environ.get("QWEN25_RUNTIME_CONFIG", runtime["active_config"]))
    lib_dir = Path(os.environ.get("QWEN25_RUNTIME_LIB_DIR", runtime["runtime_lib_dir"]))
    timeout = int(os.environ.get("QWEN25_CHAT_TIMEOUT_SECONDS", str(runtime.get("chat_timeout_seconds", 90))))
    if not runtime_bin.is_file():
        return {"ok": False, "error": f"runtime_bin_missing:{runtime_bin}"}
    if not runtime_config.is_file():
        return {"ok": False, "error": f"runtime_config_missing:{runtime_config}"}
    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = str(lib_dir)
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [str(runtime_bin), "-c", str(runtime_config)],
            cwd=str(runtime_bin.parent),
            input=prompt.strip() + "\nexit\n",
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            env=env,
        )
        timed_out = False
        stdout = completed.stdout
        stderr = completed.stderr
        returncode = completed.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        returncode = None
    answer = parse_assistant(stdout)
    return {
        "ok": returncode == 0 and not timed_out,
        "returncode": returncode,
        "timed_out": timed_out,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "answer": answer,
        "stdout_tail": clean_runtime_text(stdout)[-2000:],
        "stderr_tail": clean_runtime_text(stderr)[-2000:],
        "runtime_config": str(runtime_config),
        "runtime_bin": str(runtime_bin),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "Qwen25OpenAIGateway/1.0"

    def json_response(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    @property
    def policy(self) -> dict[str, Any]:
        return self.server.policy  # type: ignore[attr-defined]

    def do_GET(self) -> None:
        policy = self.policy
        runtime = policy["official_runtime"]
        if self.path in {"/api/token-budget/summary", "/api/token-budget/benchmark-summary"}:
            api = token_budget_api()
            if api is None:
                self.json_response(503, {"ok": False, "error": "token_budget_integration_unavailable"})
                return
            if self.path == "/api/token-budget/summary":
                self.json_response(200, api.summary())
                return
            self.json_response(200, api.benchmark_summary())
            return
        if self.path == "/health":
            self.json_response(
                200,
                {
                    "ok": True,
                    "model": policy["model_id"],
                    "backend": "official-qwen2.5-oellm-multichat-plus-ai-nas-tools",
                    "port": policy["gateway"]["port"],
                    "active_profile": runtime["active_profile"],
                    "priority_profile": runtime["priority_profile"],
                    "priority_status": runtime["priority_status"],
                    "active_hbm": path_status(runtime["active_hbm_path"]),
                    "priority_hbm": path_status(runtime["priority_hbm_path"]),
                    "tool_dispatcher": policy["ai_nas"]["tool_dispatcher"],
                    "report_root": policy["ai_nas"]["report_root"],
                },
            )
            return
        if self.path == "/v1/models":
            self.json_response(
                200,
                {
                    "object": "list",
                    "data": [
                        {
                            "id": policy["model_id"],
                            "object": "model",
                            "owned_by": "local-s100p-official-qwen",
                        }
                    ],
                },
            )
            return
        self.json_response(404, {"error": {"message": "not found", "type": "not_found"}})

    def do_POST(self) -> None:
        if self.path in {"/api/token-budget/estimate", "/api/token-budget/route"}:
            try:
                payload = read_json_request(self)
            except Exception as exc:
                self.json_response(400, {"error": {"message": str(exc), "type": "invalid_request"}})
                return
            api = token_budget_api()
            if api is None:
                self.json_response(503, {"ok": False, "error": "token_budget_integration_unavailable"})
                return
            result = api.estimate(payload) if self.path.endswith("/estimate") else api.route(payload)
            self.json_response(200 if result.get("ok") else 400, result)
            return
        if self.path not in {"/v1/chat/completions", "/v1/completions"}:
            self.json_response(404, {"error": {"message": "not found", "type": "not_found"}})
            return
        try:
            payload = read_json_request(self)
        except Exception as exc:
            self.json_response(400, {"error": {"message": str(exc), "type": "invalid_request"}})
            return
        prompt = first_text(payload)
        policy = self.policy
        if is_edge_cloud_route_request(payload):
            token_budget_route = token_budget_route_for_prompt(prompt)
            classification = edge_cloud_route_classification(prompt, token_budget_route)
            self.json_response(
                200,
                chat_completion(
                    policy["model_id"],
                    json.dumps(classification, ensure_ascii=False),
                    {
                        "route": "edge_cloud_structured_router",
                        "classifier": "qwen_gateway_structured_router",
                        "original_query_sent": True,
                        "disable_ai_nas_tools": not ai_nas_tools_enabled(payload),
                    },
                ),
            )
            return
        if ai_nas_tools_enabled(payload) and is_ai_nas_request(prompt):
            flow = run_ai_nas_flow(policy, prompt)
            paths = flow.get("gateway_turn_paths") or {}
            report_paths = []
            for run in flow["tool_runs"]:
                report_paths.extend(run["paths"])
            content = (
                "Qwen2.5 official AI-NAS entry completed the NAS evidence flow. "
                f"verdict={flow['verdict']}; reports={len(report_paths)}; "
                f"gateway_md={paths.get('md', '')}"
            )
            self.json_response(
                200 if flow["verdict"].startswith("ok_") else 500,
                chat_completion(
                    policy["model_id"],
                    content,
                    {
                        "route": "ai_nas_allowlisted_tools",
                        "gateway_turn": paths,
                        "report_paths": report_paths,
                        "errors": flow["errors"],
                    },
                ),
            )
            return
        runtime_result = run_qwen_runtime(policy, prompt)
        if not runtime_result.get("ok"):
            self.json_response(
                502,
                {
                    "error": {
                        "message": runtime_result.get("error") or "official Qwen runtime failed",
                        "type": "qwen25_runtime_error",
                        "details": runtime_result,
                    }
                },
            )
            return
        self.json_response(
            200,
            chat_completion(policy["model_id"], runtime_result["answer"], {"route": "official_qwen_runtime", **runtime_result}),
        )

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser(description="Qwen2.5 official OpenAI-compatible gateway for AI-NAS.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--host", default=os.environ.get("QWEN25_OPENAI_HOST"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("QWEN25_OPENAI_PORT", "0") or "0"))
    args = parser.parse_args()
    policy = load_json(args.config)
    host = args.host or policy["gateway"]["host"]
    port = args.port or int(policy["gateway"]["port"])
    server = ThreadingHTTPServer((host, port), Handler)
    server.policy = policy  # type: ignore[attr-defined]
    print(json.dumps({"listening": f"http://{host}:{port}", "model": policy["model_id"]}, ensure_ascii=False), flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
