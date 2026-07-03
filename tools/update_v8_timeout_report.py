#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path


root = Path("evidence/s100p_remote_v8_reports")
root.mkdir(parents=True, exist_ok=True)
p = root / "630_640_hf_full_and_isolated_final_remote.json"
data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
data["status"] = "stopped_timeout_after_model_load"
data["runtime_versions_second_attempt"] = {
    "torch": "2.2.2",
    "transformers": "4.46.2",
    "tokenizers": "0.20.3",
    "safetensors": "0.8.0",
    "numpy": "2.2.6",
}
data["modern_runtime_install"] = "success in isolated pydeps_modern; accelerate installed with --no-deps after CUDA dependency path was rejected"
data["second_attempt_observation"] = "checkpoint shards loaded successfully; first BF16 full forward produced no logits within evidence-run budget and process was terminated; no generation was run"
data["full_forward_rows"] = data.get("full_forward_rows", [])
data["isolated_final_rows"] = data.get("isolated_final_rows", [])
data["errors"] = data.get("errors", []) + [
    {
        "type": "TimeoutStoppedAfterModelLoad",
        "message": "second attempt loaded model under torch 2.2.2/transformers 4.46.2, then no logits were produced before timeout",
    }
]
data["stopped_at_unix"] = time.time()
p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
(root / "630_640_hf_full_and_isolated_final_remote.md").write_text(
    "# HF Full and Isolated Final v8\n\n"
    "- status: `stopped_timeout_after_model_load`\n"
    "- full_forward_rows: `0`\n"
    "- isolated_final_rows: `0`\n"
    "- observation: checkpoint shards loaded successfully under isolated torch 2.2.2, but first BF16 full forward did not finish within the v8 evidence-run budget.\n",
    encoding="utf-8",
)
