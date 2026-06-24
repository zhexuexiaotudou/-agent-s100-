#!/usr/bin/env python3
"""
Check whether Dream-v0-Instruct-7B can reuse the S100 leap_llm text-model
compiler skeleton.

This is a static compatibility probe. It does not download or load the large
Dream safetensor shards. It verifies the parts that matter before a full HBM
compile attempt: config shape, expected weight names, and the available S100
runtime model surface.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DREAM_DIR = REPO_ROOT / "tmp" / "dream_hf"
DEFAULT_SDK_DIR = (
    REPO_ROOT
    / "tmp"
    / "s100_llm_sdk"
    / "inspect"
    / "leap_llm_wheel"
    / "leap_llm"
)
DEFAULT_XLM_HEADER = (
    REPO_ROOT
    / "tmp"
    / "s100_llm_sdk"
    / "inspect"
    / "D-Robotics_LLM_S100_1.0.0_SDK"
    / "oellm_runtime"
    / "include"
    / "xlm.h"
)


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def dream_layer_keys(layer_id: int) -> set[str]:
    prefix = f"model.layers.{layer_id}"
    return {
        f"{prefix}.input_layernorm.weight",
        f"{prefix}.post_attention_layernorm.weight",
        f"{prefix}.self_attn.q_proj.weight",
        f"{prefix}.self_attn.q_proj.bias",
        f"{prefix}.self_attn.k_proj.weight",
        f"{prefix}.self_attn.k_proj.bias",
        f"{prefix}.self_attn.v_proj.weight",
        f"{prefix}.self_attn.v_proj.bias",
        f"{prefix}.self_attn.o_proj.weight",
        f"{prefix}.mlp.gate_proj.weight",
        f"{prefix}.mlp.up_proj.weight",
        f"{prefix}.mlp.down_proj.weight",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dream-dir", type=Path, default=DEFAULT_DREAM_DIR)
    parser.add_argument("--sdk-dir", type=Path, default=DEFAULT_SDK_DIR)
    parser.add_argument("--xlm-header", type=Path, default=DEFAULT_XLM_HEADER)
    args = parser.parse_args()

    config_path = args.dream_dir / "config.json"
    index_path = args.dream_dir / "model.safetensors.index.json"
    generation_path = args.dream_dir / "generation_utils.py"
    deepseek_model_path = args.sdk_dir / "models" / "deepseek" / "model.py"
    factory_path = args.sdk_dir / "apis" / "model" / "model_factory.py"

    config = load_json(config_path)
    index = load_json(index_path)
    weight_keys = set(index["weight_map"].keys())
    xlm_header = args.xlm_header.read_text(encoding="utf-8", errors="replace")
    generation_text = generation_path.read_text(encoding="utf-8", errors="replace")
    deepseek_text = deepseek_model_path.read_text(encoding="utf-8", errors="replace")
    factory_text = factory_path.read_text(encoding="utf-8", errors="replace")

    required_top = {"model.embed_tokens.weight", "model.norm.weight", "lm_head.weight"}
    required_layers = set()
    for i in range(int(config["num_hidden_layers"])):
        required_layers.update(dream_layer_keys(i))
    missing = sorted((required_top | required_layers) - weight_keys)

    supported_dream = "dream" in factory_text.lower()
    xlm_has_dream = "DREAM" in xlm_header
    diffusion_loop = all(
        needle in generation_text
        for needle in [
            "def diffusion_generate",
            "for i in range(steps)",
            "mask_index = (x == mask_token_id)",
            "logits = self(x, attention_mask, tok_idx).logits",
        ]
    )
    deepseek_has_cache_compile = all(
        needle in deepseek_text
        for needle in [
            "def get_leap_input_types",
            "for _ in range(self.model_args.num_hidden_layers * 2)",
            'if stage in {"prefill", "all"}',
            'if stage in {"decode", "all"}',
        ]
    )

    print("Dream config:")
    print(f"  architecture: {config.get('architectures')}")
    print(f"  model_type: {config.get('model_type')}")
    print(f"  layers: {config.get('num_hidden_layers')}")
    print(f"  hidden_size: {config.get('hidden_size')}")
    print(f"  intermediate_size: {config.get('intermediate_size')}")
    print(f"  attention_heads: {config.get('num_attention_heads')}")
    print(f"  kv_heads: {config.get('num_key_value_heads')}")
    print(f"  rope_theta: {config.get('rope_theta')}")
    print(f"  vocab_size: {config.get('vocab_size')}")
    print(f"  mask_token_id: {config.get('mask_token_id')}")
    print()

    print("Static compatibility:")
    print(f"  S100 oellm_build directly supports Dream: {supported_dream}")
    print(f"  S100 xlm runtime enum contains Dream: {xlm_has_dream}")
    print(f"  Dream generation is diffusion loop: {diffusion_loop}")
    print(f"  DeepSeek skeleton exposes cached prefill/decode compile path: {deepseek_has_cache_compile}")
    print(f"  Dream HF weight names match decoder skeleton expectation: {not missing}")
    if missing:
        print("  missing example keys:")
        for key in missing[:10]:
            print(f"    - {key}")
    print()

    print("Recommended adapter direction:")
    print("  1. Do not use xlm_infer for Dream; it has no Dream model_type and assumes autoregressive chat.")
    print("  2. Fork/copy leap_llm.models.deepseek into a Dream text-forward module.")
    print("  3. Remove causal/KV-cache semantics for the Dream path, or feed zero caches and a full zero attention mask.")
    print("  4. Compile a fixed-length full-sequence logits HBM graph for Dream forward.")
    print("  5. Implement Dream diffusion_generate on the host side and call the HBM graph once per denoise step.")

    return 0 if not missing and diffusion_loop and deepseek_has_cache_compile else 2


if __name__ == "__main__":
    raise SystemExit(main())
