from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REAL_MODEL_ENV = "DIGUA_REAL_IMAGE_TEXT_MODEL_DIR"
DEFAULT_HTTP_HEALTH = "http://192.168.127.10:18182/health"


@dataclass(frozen=True)
class RuntimeProbe:
    label: str
    executable: str
    ok: bool
    modules: dict[str, bool]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "executable": self.executable,
            "ok": self.ok,
            "modules": self.modules,
            "error": self.error,
        }


def module_probe() -> dict[str, bool]:
    modules = ["torch", "transformers", "open_clip", "clip", "sentence_transformers", "PIL", "numpy"]
    return {name: importlib.util.find_spec(name) is not None for name in modules}


def probe_runtime(label: str, executable: str | Path) -> RuntimeProbe:
    exe = str(executable)
    code = (
        "import importlib.util,json;"
        "mods=['torch','transformers','open_clip','clip','sentence_transformers','PIL','numpy'];"
        "print(json.dumps({m: importlib.util.find_spec(m) is not None for m in mods}, sort_keys=True))"
    )
    try:
        result = subprocess.run([exe, "-c", code], text=True, capture_output=True, timeout=30)
    except Exception as exc:
        return RuntimeProbe(label=label, executable=exe, ok=False, modules={}, error=f"{type(exc).__name__}: {exc}")
    if result.returncode != 0:
        return RuntimeProbe(label=label, executable=exe, ok=False, modules={}, error=(result.stderr or result.stdout)[-1000:])
    try:
        modules = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return RuntimeProbe(label=label, executable=exe, ok=False, modules={}, error=f"json_decode_error: {exc}")
    return RuntimeProbe(label=label, executable=exe, ok=True, modules={str(k): bool(v) for k, v in modules.items()})


def model_dir_probe(env: dict[str, str] | None = None) -> dict[str, Any]:
    env = env or os.environ
    configured = env.get(REAL_MODEL_ENV)
    if not configured:
        return {"configured": False, "env": REAL_MODEL_ENV, "exists": False, "reason": "env_not_set"}
    path = Path(configured)
    marker_names = {"config.json", "open_clip_config.json", "preprocessor_config.json", "tokenizer.json", "pytorch_model.bin", "model.safetensors"}
    markers = []
    if path.exists():
        try:
            markers = sorted(item.name for item in path.iterdir() if item.name in marker_names)
        except OSError:
            markers = []
    return {
        "configured": True,
        "env": REAL_MODEL_ENV,
        "path": str(path),
        "exists": path.exists(),
        "markers": markers,
        "looks_like_model_dir": path.exists() and bool(markers),
    }


def http_health_probe(url: str = DEFAULT_HTTP_HEALTH, timeout_sec: float = 3.0) -> dict[str, Any]:
    started = time.time()
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read(4096).decode("utf-8", errors="replace")
            try:
                payload: dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"raw": raw[:1000]}
            return {
                "ok": 200 <= int(resp.status) < 300,
                "url": url,
                "status": int(resp.status),
                "latency_ms": round((time.time() - started) * 1000, 3),
                "payload": payload,
            }
    except urllib.error.URLError as exc:
        return {
            "ok": False,
            "url": url,
            "status": None,
            "latency_ms": round((time.time() - started) * 1000, 3),
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "ok": False,
            "url": url,
            "status": None,
            "latency_ms": round((time.time() - started) * 1000, 3),
            "error": f"{type(exc).__name__}: {exc}",
        }


def evaluate_real_image_text_embedding(runtime_probes: list[RuntimeProbe], *, http_probe: dict[str, Any] | None = None) -> dict[str, Any]:
    model_dir = model_dir_probe()
    local_openclip_ready = any(
        probe.ok
        and probe.modules.get("PIL")
        and probe.modules.get("numpy")
        and probe.modules.get("torch")
        and (probe.modules.get("open_clip") or probe.modules.get("clip"))
        for probe in runtime_probes
    )
    local_siglip_ready = any(
        probe.ok
        and probe.modules.get("PIL")
        and probe.modules.get("numpy")
        and probe.modules.get("torch")
        and probe.modules.get("transformers")
        and model_dir.get("looks_like_model_dir")
        for probe in runtime_probes
    )
    http_ready = bool(http_probe and http_probe.get("ok") and (http_probe.get("payload") or {}).get("ready"))
    available = bool((local_openclip_ready or local_siglip_ready) and model_dir.get("looks_like_model_dir"))
    if http_ready:
        available = True

    if available and http_ready:
        backend = "s100p_http_clip_compatible"
        model_family = "clip_compatible_http_local_appliance"
    elif available and local_openclip_ready:
        backend = "open_clip_local"
        model_family = "openclip_or_clip"
    elif available and local_siglip_ready:
        backend = "transformers_siglip_local"
        model_family = "siglip"
    else:
        backend = "pillow_numpy_fallback"
        model_family = "local_feature_embedding"

    return {
        "real_image_text_embedding_available": available,
        "backend": backend,
        "model_family": model_family,
        "model_dir": model_dir,
        "runtime_probes": [probe.to_dict() for probe in runtime_probes],
        "http_probe": http_probe,
        "fallback_model": "digua-local-visual-text-embedding-v1",
        "claim_level": "real_image_semantic" if available else "limited_semantic_color_brightness_aspect",
        "safe_statement": (
            "A validated local CLIP/SigLIP-compatible image-text embedding backend is available."
            if available
            else "No validated local CLIP/SigLIP-compatible backend is available; v1 uses the Pillow/Numpy fallback only."
        ),
    }


def current_runtime_status() -> dict[str, Any]:
    return evaluate_real_image_text_embedding([RuntimeProbe("current", sys.executable, True, module_probe())])
