from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


REPO_ROOT = Path(__file__).resolve().parents[2]
KNOWN_TOKENIZER_FILES = (
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "vocab.json",
    "merges.txt",
    "config.json",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_hash(data: Any) -> str:
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def candidate_paths(explicit_path: Optional[str] = None) -> Iterable[Path]:
    names = [
        explicit_path,
        os.environ.get("QWEN_TOKENIZER_PATH"),
        os.environ.get("QWEN_TOKENIZER_DIR"),
        os.environ.get("QWEN_TOKENIZER_JSON"),
        str(REPO_ROOT / "evidence" / "token_budget" / "qwen2_5-1_5b-hf"),
        str(REPO_ROOT / "tmp" / "token_budget" / "qwen2_5-1_5b-hf"),
        str(REPO_ROOT / "tools" / "token_budget" / "tokenizer_cache" / "qwen2_5-1_5b-hf"),
    ]
    seen = set()
    for item in names:
        if not item:
            continue
        path = Path(item).expanduser()
        key = str(path.resolve()) if path.exists() else str(path)
        if key not in seen:
            seen.add(key)
            yield path


def resolve_tokenizer_dir(explicit_path: Optional[str] = None) -> Optional[Path]:
    for path in candidate_paths(explicit_path):
        if path.is_file() and path.name == "tokenizer.json":
            return path.parent
        if path.is_dir() and (path / "tokenizer.json").exists():
            return path
    return None


def file_hashes(tokenizer_dir: Optional[Path]) -> Dict[str, Dict[str, Any]]:
    if tokenizer_dir is None:
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for name in KNOWN_TOKENIZER_FILES:
        path = tokenizer_dir / name
        if path.exists() and path.is_file():
            out[name] = {
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
    return out


def load_tokenizer_backend(tokenizer_dir: Optional[Path]) -> tuple[Optional[Any], str, str, Optional[int]]:
    if tokenizer_dir is None:
        return None, "fallback_char_estimate", "char_estimate", None

    try:
        from transformers import AutoTokenizer  # type: ignore

        tokenizer = AutoTokenizer.from_pretrained(
            str(tokenizer_dir),
            trust_remote_code=True,
            local_files_only=True,
        )
        vocab_size = len(tokenizer)
        return tokenizer, "transformers_auto", tokenizer.__class__.__name__, vocab_size
    except Exception:
        pass

    tokenizer_json = tokenizer_dir / "tokenizer.json"
    try:
        from tokenizers import Tokenizer  # type: ignore

        tokenizer = Tokenizer.from_file(str(tokenizer_json))
        return tokenizer, "tokenizers_json", tokenizer.__class__.__name__, tokenizer.get_vocab_size()
    except Exception:
        return None, "fallback_char_estimate", "char_estimate", None


@dataclass(frozen=True)
class TokenizerBundle:
    tokenizer: Optional[Any]
    identity: Dict[str, Any]


def build_tokenizer_bundle(explicit_path: Optional[str] = None) -> TokenizerBundle:
    tokenizer_dir = resolve_tokenizer_dir(explicit_path)
    tokenizer, backend, tokenizer_class, vocab_size = load_tokenizer_backend(tokenizer_dir)
    hashes = file_hashes(tokenizer_dir)
    tokenizer_config = hashes.get("tokenizer_config.json", {})
    tokenizer_json = hashes.get("tokenizer.json", {})
    vocab_json = hashes.get("vocab.json", {})
    merges_txt = hashes.get("merges.txt", {})
    added_tokens = hashes.get("added_tokens.json", {})
    model_identity = "Qwen2.5-1.5B-Instruct-S100P-official" if tokenizer_dir else None
    identity_core = {
        "tokenizer_path": str(tokenizer_dir) if tokenizer_dir else None,
        "backend": backend,
        "load_method": backend,
        "fallback_used": backend == "fallback_char_estimate",
        "tokenizer_class": tokenizer_class,
        "vocab_size": vocab_size,
        "tokenizer_config_hash": tokenizer_config.get("sha256"),
        "tokenizer_json_hash": tokenizer_json.get("sha256"),
        "vocab_hash": vocab_json.get("sha256"),
        "merges_hash": merges_txt.get("sha256"),
        "added_tokens_hash": added_tokens.get("sha256"),
        "model_identity": model_identity,
        "file_hashes": hashes,
        "remote_source_path": os.environ.get(
            "QWEN_TOKENIZER_REMOTE_SOURCE",
            "/mnt/nas/openclaw/models/qwen2_5-1_5b-hf",
        )
        if tokenizer_dir
        else None,
    }
    identity = {
        "generated_at": now_iso(),
        "real_tokenizer_available": backend in {"transformers_auto", "tokenizers_json"},
        **identity_core,
        "tokenizer_identity_hash": stable_hash(identity_core),
    }
    return TokenizerBundle(tokenizer=tokenizer, identity=identity)


def build_tokenizer_identity(explicit_path: Optional[str] = None) -> Dict[str, Any]:
    return build_tokenizer_bundle(explicit_path).identity
