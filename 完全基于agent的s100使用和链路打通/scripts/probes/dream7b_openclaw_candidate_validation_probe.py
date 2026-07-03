#!/usr/bin/env python3
import json
import os
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path


APPROVED_REPORT_PREFIXES = (
    "/tmp/",
    "/mnt/nas/openclaw/reports",
    "/mnt/nas/openclaw/reports/",
    "/root/.openclaw/workspace/reports",
    "/root/.openclaw/workspace/reports/",
)


def is_approved(path: Path) -> bool:
    text = str(path)
    return any(text == prefix.rstrip("/") or text.startswith(prefix) for prefix in APPROVED_REPORT_PREFIXES)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def http_json(method: str, url: str, payload: dict | None = None, timeout: int = 180) -> tuple[int, dict]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        return resp.status, json.loads(body)


def latest_sort_report(root: Path) -> Path | None:
    reports = sorted(root.glob("personal_data_sort_*/personal_data_sort.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return reports[0] if reports else None


def main() -> int:
    report_root = Path(sys.argv[1] if len(sys.argv) > 1 else "/mnt/nas/openclaw/reports/models")
    if not is_approved(report_root):
        raise ValueError(f"Refusing report root outside approved report directories: {report_root}")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = report_root / f"dream7b_openclaw_candidate_validation_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    config_path = Path(os.environ.get("OPENCLAW_CONFIG", "/root/.openclaw/openclaw.json"))
    trace_path = Path(os.environ.get("DREAM7B_OPENAI_TRACE_PATH", "/mnt/nas/openclaw/reports/models/dream7b_local_gateway_candidate/requests.jsonl"))
    sort_report_root = Path(os.environ.get("DREAM7B_OPENAI_PERSONAL_SORT_REPORT_ROOT", "/mnt/nas/openclaw/reports/personal-data-sort-dry-run"))
    base_url = os.environ.get("DREAM7B_OPENAI_BASE_URL", "http://127.0.0.1:18888")
    model_id = os.environ.get("DREAM7B_OPENAI_MODEL_ID", "Dream7B-S100P-local")
    provider_key = "dream7b-local"
    primary_model = f"{provider_key}/{model_id}"

    errors: list[str] = []
    warnings: list[str] = []
    artifacts: dict[str, str] = {}

    config = {}
    try:
        config = read_json(config_path)
        (run_dir / "openclaw_config_snapshot.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception as exc:
        errors.append(f"failed to read OpenClaw config: {type(exc).__name__}: {exc}")

    config_text = json.dumps(config, ensure_ascii=False)
    primary = (((config.get("agents") or {}).get("defaults") or {}).get("model") or {}).get("primary")
    provider = ((config.get("models") or {}).get("providers") or {}).get(provider_key) or {}
    minimax_present = "MiniMax" in config_text or "minimax" in config_text
    if primary != primary_model:
        errors.append(f"unexpected OpenClaw primary model: {primary!r} != {primary_model!r}")
    if provider.get("baseUrl") != f"{base_url}/v1":
        errors.append(f"unexpected dream7b-local baseUrl: {provider.get('baseUrl')!r}")
    if provider.get("api") != "openai-completions":
        errors.append(f"unexpected dream7b-local api: {provider.get('api')!r}")
    if not minimax_present:
        warnings.append("MiniMax fallback provider not found in OpenClaw config snapshot")

    try:
        health_status, health = http_json("GET", f"{base_url}/health")
        models_status, models = http_json("GET", f"{base_url}/v1/models")
        (run_dir / "health.json").write_text(json.dumps(health, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (run_dir / "models.json").write_text(json.dumps(models, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if health_status != 200 or health.get("model") != model_id:
            errors.append(f"unexpected gateway health: status={health_status}, payload={health}")
        model_ids = [item.get("id") for item in models.get("data", []) if isinstance(item, dict)]
        if model_id not in model_ids:
            errors.append(f"model not listed by gateway: {model_id}; ids={model_ids}")
    except Exception as exc:
        errors.append(f"gateway health/model check failed: {type(exc).__name__}: {exc}")

    before_sort = latest_sort_report(sort_report_root)
    prompt = "Please organize Personal/Movies into Sorted as a dry run and keep original files unchanged."
    request_payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 80,
        "stream": False,
    }
    (run_dir / "chat_request.json").write_text(json.dumps(request_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    chat = {}
    try:
        chat_status, chat = http_json("POST", f"{base_url}/v1/chat/completions", request_payload)
        (run_dir / "chat_response.json").write_text(json.dumps(chat, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if chat_status != 200:
            errors.append(f"unexpected chat status: {chat_status}")
    except Exception as exc:
        errors.append(f"gateway chat check failed: {type(exc).__name__}: {exc}")

    after_sort = latest_sort_report(sort_report_root)
    if after_sort:
        artifacts["latest_sort_report"] = str(after_sort)
        try:
            (run_dir / "latest_sort_report.md").write_text(after_sort.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception as exc:
            warnings.append(f"failed to copy latest sort report: {exc}")
    if after_sort is None:
        errors.append("no Personal/Movies dry-run sort report found")
    elif before_sort is not None and after_sort == before_sort:
        warnings.append("latest Personal/Movies dry-run report did not change during validation")

    content = ""
    try:
        content = chat.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception:
        content = ""
    if "Personal/Movies" not in content and "personal_data_sort" not in content and "Preview report" not in content:
        errors.append("gateway chat response does not mention the fixed Personal/Movies dry-run workflow")

    recent_trace = []
    if trace_path.is_file():
        lines = [line for line in trace_path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
        recent_trace = [json.loads(line) for line in lines[-20:]]
        (run_dir / "requests_trace_tail.jsonl").write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in recent_trace) + "\n", encoding="utf-8")
    else:
        errors.append(f"missing Dream gateway trace path: {trace_path}")
    has_openclaw_heartbeat = any(
        item.get("path") == "/v1/chat/completions"
        and item.get("model") == model_id
        and item.get("tool_available") is True
        and "HEARTBEAT" in str(item.get("latest_user_text_preview", ""))
        for item in recent_trace
    )
    has_sort_trace = any(item.get("should_sort_personal_movies") is True for item in recent_trace)
    if not has_openclaw_heartbeat:
        warnings.append("recent trace does not include an OpenClaw heartbeat/tool-available call")
    if not has_sort_trace:
        errors.append("recent trace does not include a Personal/Movies sort-triggering call")

    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_openclaw_candidate_validation_probe" if not errors else "failed_dream7b_openclaw_candidate_validation_probe",
        "run_dir": str(run_dir),
        "openclaw_config": str(config_path),
        "primary_model": primary,
        "expected_primary_model": primary_model,
        "dream_provider_base_url": provider.get("baseUrl"),
        "minimax_fallback_present": minimax_present,
        "gateway_base_url": base_url,
        "model_id": model_id,
        "trace_path": str(trace_path),
        "recent_trace_has_openclaw_heartbeat": has_openclaw_heartbeat,
        "recent_trace_has_sort_trigger": has_sort_trace,
        "chat_response_content": content,
        "artifacts": artifacts,
        "default_service_replaced": False,
        "warnings": warnings,
        "errors": errors,
    }
    (run_dir / "openclaw_candidate_validation_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Dream 7B OpenClaw Candidate Validation",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- primary_model: {payload['primary_model']}",
        f"- gateway_base_url: {payload['gateway_base_url']}",
        f"- minimax_fallback_present: {payload['minimax_fallback_present']}",
        f"- recent_trace_has_openclaw_heartbeat: {payload['recent_trace_has_openclaw_heartbeat']}",
        f"- recent_trace_has_sort_trigger: {payload['recent_trace_has_sort_trigger']}",
        f"- latest_sort_report: {artifacts.get('latest_sort_report', '')}",
        "",
        "## Errors",
        "",
    ]
    lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- none")
    (run_dir / "openclaw_candidate_validation_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(run_dir / "openclaw_candidate_validation_probe.md")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
