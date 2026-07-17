import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "qwen25_openai_gateway.py"
SPEC = importlib.util.spec_from_file_location("qwen25_gateway_model_selection", MODULE_PATH)
assert SPEC and SPEC.loader
gateway = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gateway)


def test_selectable_model_policy_resolves_1_5b_and_7b_configs():
    policy = json.loads((REPO_ROOT / "configs" / "qwen25_official_route_policy.json").read_text(encoding="utf-8"))
    models = gateway.selectable_model_policies(policy)

    assert list(models) == [
        "Qwen2.5-1.5B-Instruct-S100P-official",
        "Qwen2.5-7B-Instruct-S100P-official",
    ]
    assert models["Qwen2.5-1.5B-Instruct-S100P-official"]["official_runtime"]["active_config"].endswith(
        "qwen25_512_multichat_config.json"
    )
    assert models["Qwen2.5-7B-Instruct-S100P-official"]["official_runtime"]["active_config"].endswith(
        "qwen25_7b_1024_multichat_config.json"
    )
    assert gateway._bpu_policy_hash(models["Qwen2.5-1.5B-Instruct-S100P-official"]) != gateway._bpu_policy_hash(
        models["Qwen2.5-7B-Instruct-S100P-official"]
    )


def test_unknown_model_is_not_resolved():
    policy = json.loads((REPO_ROOT / "configs" / "qwen25_official_route_policy.json").read_text(encoding="utf-8"))
    assert gateway.resolve_model_policy(policy, "not-enabled") is None
