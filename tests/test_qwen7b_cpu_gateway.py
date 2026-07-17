import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "qwen7b_cpu_openai_gateway.py"
SPEC = importlib.util.spec_from_file_location("qwen7b_cpu_gateway_test", MODULE_PATH)
assert SPEC and SPEC.loader
gateway = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gateway)


def test_normalize_messages_accepts_openai_chat_roles():
    assert gateway.normalize_messages([
        {"role": "system", "content": "Be brief."},
        {"role": "user", "content": "Hello"},
    ]) == [
        {"role": "system", "content": "Be brief."},
        {"role": "user", "content": "Hello"},
    ]


@pytest.mark.parametrize(
    "messages",
    [[], [{"role": "tool", "content": "no"}], [{"role": "user", "content": {"text": "no"}}]],
)
def test_normalize_messages_rejects_unsupported_or_empty_payloads(messages):
    with pytest.raises(ValueError):
        gateway.normalize_messages(messages)


def test_cpu_service_uses_durable_paths_and_loopback_port():
    unit = (REPO_ROOT / "configs" / "systemd" / "qwen7b-cpu.service").read_text(encoding="utf-8")
    assert "/tmp/" not in unit
    assert "QWEN7B_CPU_PORT=18081" in unit
    assert "Qwen2.5-7B-Instruct-Q4_K_M.gguf" in unit
    assert "qwen7b_cpu_openai_gateway.py" in unit
