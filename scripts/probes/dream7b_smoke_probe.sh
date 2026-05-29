#!/usr/bin/env bash
set -euo pipefail

report_dir="${1:-/mnt/nas/openclaw/reports/models}"
config_file="${2:-/root/.openclaw/workspace/config/dream7b_deployment.json}"

case "$report_dir" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_dir" >&2
    exit 2
    ;;
esac

case "$config_file" in
  /root/.openclaw/workspace/config/dream7b_deployment.json|/mnt/nas/openclaw/config/dream7b_deployment.json|/tmp/dream7b_deployment.json) ;;
  *)
    echo "Refusing config path outside approved locations: $config_file" >&2
    exit 2
    ;;
esac

mkdir -p "$report_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$report_dir/dream7b_smoke_$stamp.md"
json="$report_dir/dream7b_smoke_$stamp.json"

python3 - "$report" "$json" "$config_file" <<'PY'
import contextlib
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

report = Path(sys.argv[1])
json_path = Path(sys.argv[2])
config_path = Path(sys.argv[3])

allowed_model_roots = [
    Path("/mnt/nas/openclaw/models"),
    Path("/root/.openclaw/workspace/models"),
    Path("/home/sunrise/models"),
]

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "mode": "bounded local Dream 7B smoke test",
    "report": str(report),
    "json": str(json_path),
    "config_file": str(config_path),
    "verdict": "blocked_no_config",
    "runtime": "not_attempted",
    "model_path": "missing",
    "model_digest": "not_available",
    "elapsed_seconds": 0,
    "stdout_preview": "",
    "stderr_preview": "",
    "notes": [],
}


def redact(text: str) -> str:
    lowered = text
    for word in ("token", "secret", "authorization", "app_secret"):
        lowered = lowered.replace(word, f"{word[:2]}***")
    return lowered[:2000]


def write_outputs():
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Dream 7B Local Smoke Test",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- mode: {payload['mode']}",
        f"- report: {payload['report']}",
        f"- json: {payload['json']}",
        f"- config_file: {payload['config_file']}",
        f"- verdict: {payload['verdict']}",
        "",
        "## Runtime",
        "",
        "| Check | Value |",
        "| --- | --- |",
        f"| Runtime | {payload['runtime']} |",
        f"| Model path | {payload['model_path']} |",
        f"| Model digest | {payload['model_digest']} |",
        f"| Elapsed seconds | {payload['elapsed_seconds']} |",
        "",
        "## Output Preview",
        "",
        "```text",
        payload["stdout_preview"] or "none",
        "```",
        "",
        "## Error Preview",
        "",
        "```text",
        payload["stderr_preview"] or "none",
        "```",
        "",
        "## Notes",
        "",
    ]
    lines.extend(f"- {note}" for note in payload["notes"])
    if not payload["notes"]:
        lines.append("- none")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def is_under_allowed_root(path: Path) -> bool:
    with contextlib.suppress(OSError):
        resolved = path.resolve()
        return any(resolved == root or root in resolved.parents for root in allowed_model_roots)
    return False


def model_digest(path: Path) -> str:
    if path.is_file():
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        return f"sha256:{h.hexdigest()}"
    files = sorted(p for p in path.rglob("*") if p.is_file())[:20]
    h = hashlib.sha256()
    for item in files:
        h.update(str(item.relative_to(path)).encode("utf-8", errors="replace"))
        h.update(str(item.stat().st_size).encode("ascii"))
    return f"tree-sha256:{h.hexdigest()} files_sampled={len(files)}"


if not config_path.exists():
    payload["notes"].append("Create dream7b_deployment.json from config/dream7b_deployment.example.json after model files are available.")
    write_outputs()
    print(report)
    raise SystemExit(0)

try:
    config = json.loads(config_path.read_text(encoding="utf-8"))
except Exception as exc:
    payload["verdict"] = "blocked_invalid_config"
    payload["stderr_preview"] = redact(str(exc))
    write_outputs()
    print(report)
    raise SystemExit(0)

model_cfg = config.get("model", {})
smoke_cfg = config.get("smoke_test", {})
model_path = Path(str(model_cfg.get("path", "")))
payload["model_path"] = str(model_path)
runtime = str(model_cfg.get("runtime", "auto"))
prompt = str(smoke_cfg.get("prompt", "Respond with exactly: OK"))
max_new_tokens = max(1, min(int(smoke_cfg.get("max_new_tokens", 16)), 64))
timeout_seconds = max(15, min(int(smoke_cfg.get("timeout_seconds", 120)), 180))

if not model_path.exists():
    payload["verdict"] = "blocked_model_path_missing"
    payload["notes"].append("Model path does not exist on S100P.")
    write_outputs()
    print(report)
    raise SystemExit(0)

if not is_under_allowed_root(model_path):
    payload["verdict"] = "blocked_model_path_unapproved"
    payload["notes"].append("Model path must be under an approved local model directory.")
    write_outputs()
    print(report)
    raise SystemExit(0)

payload["model_digest"] = model_digest(model_path)

has_llama = shutil.which("llama-cli") is not None
has_transformers = importlib.util.find_spec("transformers") is not None and importlib.util.find_spec("torch") is not None
selected = runtime
if runtime == "auto":
    selected = "llama-cli" if model_path.is_file() and model_path.suffix.lower() == ".gguf" and has_llama else "transformers"

start = time.monotonic()
try:
    if selected == "llama-cli":
        if not has_llama:
            payload["verdict"] = "blocked_runtime_missing"
            payload["runtime"] = "llama-cli"
            payload["notes"].append("llama-cli is not installed or not on PATH.")
        else:
            payload["runtime"] = "llama-cli"
            cmd = [
                "timeout", str(timeout_seconds),
                "llama-cli", "-m", str(model_path), "-p", prompt,
                "-n", str(max_new_tokens), "--temp", "0", "--ctx-size", "512",
            ]
            proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout_seconds + 10)
            payload["stdout_preview"] = redact(proc.stdout)
            payload["stderr_preview"] = redact(proc.stderr)
            payload["verdict"] = "ok_smoke" if proc.returncode == 0 and proc.stdout.strip() else f"blocked_runtime_exit_{proc.returncode}"
    elif selected == "transformers":
        if not has_transformers:
            payload["verdict"] = "blocked_runtime_missing"
            payload["runtime"] = "transformers"
            payload["notes"].append("torch and transformers are required for a local-files-only Hugging Face smoke test.")
        else:
            payload["runtime"] = "transformers"
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer

            tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True, trust_remote_code=True)
            model = AutoModelForCausalLM.from_pretrained(
                str(model_path),
                local_files_only=True,
                trust_remote_code=True,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                low_cpu_mem_usage=True,
            )
            inputs = tokenizer(prompt, return_tensors="pt")
            with torch.no_grad():
                output = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
            text = tokenizer.decode(output[0], skip_special_tokens=True)
            payload["stdout_preview"] = redact(text)
            payload["verdict"] = "ok_smoke" if text.strip() else "blocked_empty_generation"
    else:
        payload["runtime"] = selected
        payload["verdict"] = "blocked_unknown_runtime"
        payload["notes"].append("Supported runtimes: auto, llama-cli, transformers.")
except subprocess.TimeoutExpired as exc:
    payload["runtime"] = selected
    payload["verdict"] = "blocked_timeout"
    payload["stdout_preview"] = redact(exc.stdout or "")
    payload["stderr_preview"] = redact(exc.stderr or "")
except Exception as exc:
    payload["runtime"] = selected
    payload["verdict"] = "blocked_exception"
    payload["stderr_preview"] = redact(f"{type(exc).__name__}: {exc}")
finally:
    payload["elapsed_seconds"] = round(time.monotonic() - start, 2)
    if payload["verdict"] == "ok_smoke":
        payload["notes"].append("Bounded local inference completed without downloading models or starting a persistent service.")
    write_outputs()
    print(report)
PY
