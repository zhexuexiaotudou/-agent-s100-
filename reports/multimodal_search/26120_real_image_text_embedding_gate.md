# 26120_real_image_text_embedding_gate

- ok: `True`
- verdict: `real_image_text_embedding_unavailable_fallback_claims_required`

```json
{
  "ok": true,
  "status": {
    "backend": "pillow_numpy_fallback",
    "claim_level": "limited_semantic_color_brightness_aspect",
    "fallback_model": "digua-local-visual-text-embedding-v1",
    "http_probe": {
      "error": "<urlopen error [WinError 10061] 由于目标计算机积极拒绝，无法连接。>",
      "latency_ms": 2070.253,
      "ok": false,
      "status": null,
      "url": "http://192.168.127.10:18182/health"
    },
    "model_dir": {
      "configured": false,
      "env": "DIGUA_REAL_IMAGE_TEXT_MODEL_DIR",
      "exists": false,
      "reason": "env_not_set"
    },
    "model_family": "local_feature_embedding",
    "real_image_text_embedding_available": false,
    "runtime_probes": [
      {
        "error": null,
        "executable": "C:\\Users\\zhexu\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe",
        "label": "current_python",
        "modules": {
          "PIL": true,
          "clip": false,
          "numpy": true,
          "open_clip": false,
          "sentence_transformers": false,
          "torch": false,
          "transformers": false
        },
        "ok": true
      },
      {
        "error": null,
        "executable": "C:\\Users\\zhexu\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe",
        "label": "bundled_python",
        "modules": {
          "PIL": true,
          "clip": false,
          "numpy": true,
          "open_clip": false,
          "sentence_transformers": false,
          "torch": false,
          "transformers": false
        },
        "ok": true
      },
      {
        "error": null,
        "executable": "F:\\Project\\Digua\\tmp\\v21_torch_env\\Scripts\\python.exe",
        "label": "v21_torch_env",
        "modules": {
          "PIL": false,
          "clip": false,
          "numpy": true,
          "open_clip": false,
          "sentence_transformers": false,
          "torch": true,
          "transformers": true
        },
        "ok": true
      }
    ],
    "safe_statement": "No validated local CLIP/SigLIP-compatible backend is available; v1 uses the Pillow/Numpy fallback only."
  },
  "verdict": "real_image_text_embedding_unavailable_fallback_claims_required"
}
```
